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
    """
    Extract and validate the current authenticated user from JWT token.
    
    This dependency function extracts the JWT token from the Authorization header,
    validates it, and retrieves the corresponding user from the database.
    
    Args:
        credentials: HTTP Bearer token from Authorization header
    
    Returns:
        dict: User document from database containing user information
    
    Raises:
        HTTPException: 401 if not authenticated, invalid token, or user not found
    
    Example:
        Request Headers:
        ```
        Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        ```
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    subject = decode_token(credentials.credentials)
    if not subject:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"_id": subject}) or await db.users.find_one({"email": subject})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """
    Extract and validate the current authenticated user from JWT token (optional).
    
    This dependency function extracts the JWT token from the Authorization header,
    validates it, and retrieves the corresponding user from the database.
    Returns None if no valid token is provided.
    
    Args:
        credentials: HTTP Bearer token from Authorization header (optional)
    
    Returns:
        dict or None: User document from database or None if not authenticated
    
    Example:
        Request Headers (optional):
        ```
        Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        ```
    """
    if not credentials:
        return None
    try:
        subject = decode_token(credentials.credentials)
        if not subject:
            return None
        user = await db.users.find_one({"_id": subject}) or await db.users.find_one({"email": subject})
        return user
    except Exception:
        return None


@router.post("/register")
async def register(data: dict):
    """
    Register a new user with email and password.
    
    Creates a new user account with hashed password and returns a JWT access token
    for immediate authentication. Email is automatically converted to lowercase and trimmed.
    Password is hashed using bcrypt for security.
    
    Args:
        data (dict): Registration data containing:
            - email (str): User's email address (required, must be unique)
            - password (str): User's password (required, minimum length recommended)
    
    Returns:
        dict: Authentication response containing:
            - access_token (str): JWT token for authenticated requests
            - token_type (str): Always "bearer"
    
    Raises:
        HTTPException: 400 if email or password is missing
        HTTPException: 409 if email is already registered
    
    Example:
        Request:
        ```json
        {
            "email": "user@example.com",
            "password": "SecurePassword123"
        }
        ```
        
        Response:
        ```json
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer"
        }
        ```
    """
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
    """
    Authenticate user with email and password.
    
    Validates user credentials and returns a JWT access token if successful.
    Email is automatically converted to lowercase and trimmed.
    Password is verified against the stored bcrypt hash.
    
    Args:
        data (dict): Login credentials containing:
            - email (str): User's email address (required)
            - password (str): User's password (required)
    
    Returns:
        dict: Authentication response containing:
            - access_token (str): JWT token for authenticated requests
            - token_type (str): Always "bearer"
    
    Raises:
        HTTPException: 401 if credentials are invalid
    
    Example:
        Request:
        ```json
        {
            "email": "user@example.com",
            "password": "SecurePassword123"
        }
        ```
        
        Response:
        ```json
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer"
        }
        ```
    """
    email = (data.get("email") or "").lower().strip()
    password = data.get("password")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(password or "", user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(email)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def me(user=Depends(get_current_user)):
    """
    Get current authenticated user information.
    
    Returns the profile information of the currently authenticated user.
    Requires valid JWT token in Authorization header.
    
    Args:
        user: Current authenticated user (injected by dependency)
    
    Returns:
        dict: User profile information containing:
            - email (str): User's email address
    
    Raises:
        HTTPException: 401 if not authenticated or invalid token
    
    Example:
        Request Headers:
        ```
        Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        ```
        
        Response:
        ```json
        {
            "email": "user@example.com"
        }
        ```
    """
    return {"email": user.get("email")}


@router.post("/google")
async def login_with_google(data: dict):
    """
    Authenticate user with Google OAuth ID token.
    
    Verifies Google ID token and creates or retrieves user account.
    Returns JWT access token for API authentication.
    
    Args:
        data (dict): Google OAuth data containing:
            - id_token (str): Google ID token from OAuth flow (required)
    
    Returns:
        dict: Authentication response containing:
            - access_token (str): JWT token for authenticated requests
            - token_type (str): Always "bearer"
    
    Raises:
        HTTPException: 400 if id_token is missing or has no email
        HTTPException: 401 if Google token is invalid
    
    Example:
        Request:
        ```json
        {
            "id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjE2NzI4..."
        }
        ```
        
        Response:
        ```json
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer"
        }
        ```
    """
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



