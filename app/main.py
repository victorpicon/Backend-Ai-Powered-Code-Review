import os
import sys
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.api.reviews import viewer as reviews
from app.api.auth import routes as auth
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.database import db
from motor.motor_asyncio import AsyncIOMotorClient

app = FastAPI(title="AI Code Review API")

cors_env = os.getenv("CORS_ALLOW_ORIGINS", "*")
allow_origins = [o.strip() for o in cors_env.split(",") if o.strip()] if cors_env else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# incluir rotas
app.include_router(reviews.router, prefix="/api/reviews", tags=["reviews"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint returning service status."""
    return {"status": "ok"}


@app.get("/api/stats")
async def stats_root():
    """Return global statistics summary (count and average score)."""
    try:
        pipeline = [
            {"$group": {"_id": None, "count": {"$sum": 1}, "avg_score": {"$avg": "$feedback.score"}}},
            {"$project": {"_id": 0}},
        ]
        overall = await db.reviews.aggregate(pipeline).to_list(length=1)
        return overall[0] if overall else {"count": 0, "avg_score": None}
    except Exception as _:
        return {"count": 0, "avg_score": None}


@app.on_event("startup")
async def startup():
    """Create indexes used by queries and rate limiting on startup."""
    try:
        if db is not None:
            await db.reviews.create_index("created_at")
            await db.reviews.create_index("language")
            await db.reviews.create_index("status")
            await db.reviews.create_index([("ip", 1), ("created_at", 1)])
            await db.reviews.create_index("code_hash")
            await db.reviews.create_index("user_id")
            print("Database indexes created successfully")
        else:
            print("Warning: Database not available, skipping index creation")
    except Exception as e:
        print(f"Warning: Failed to create database indexes: {e}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, forwarded_allow_ips="*")
