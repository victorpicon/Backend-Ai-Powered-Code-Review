import os
from typing import Optional

from app.core.security import create_access_token, hash_password, verify_password, decode_token
from app.database.database import db
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests


router = APIRouter()
security = HTTPBearer(auto_error=False)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    subject = decode_token(credentials.credentials)
    if not subject:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"_id": subject}) or await db.users.find_one({"email": subject})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.post("/register")
async def register(data: dict):
    email = (data.get("email") or "").lower().strip()
    password = data.get("password")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    exists = await db.users.find_one({"email": email})
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = {"_id": email, "email": email, "password_hash": hash_password(password)}
    await db.users.insert_one(user)
    token = create_access_token(email)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login")
async def login(data: dict):
    email = (data.get("email") or "").lower().strip()
    password = data.get("password")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(password or "", user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(email)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def me(user=Depends(get_current_user)):
    return {"email": user.get("email")}


@router.post("/google")
async def login_with_google(data: dict):
    token = data.get("id_token")
    if not token or not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Missing Google id_token or client id")
    try:
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        email = (idinfo.get("email") or "").lower()
        if not email:
            raise HTTPException(status_code=400, detail="Google token has no email")
        user = await db.users.find_one({"email": email})
        if not user:
            await db.users.insert_one({"_id": email, "email": email, "google": True})
        jwt = create_access_token(email)
        return {"access_token": jwt, "token_type": "bearer"}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google token")



