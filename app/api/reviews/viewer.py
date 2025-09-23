import json
import os
import hashlib
import asyncio
from datetime import datetime, timedelta

from app.api.reviews.schema import ReviewRequest, ReviewResponse
from app.database.database import db
from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import StreamingResponse
from google import genai
from openai import OpenAI
from app.api.auth.routes import get_current_user

router = APIRouter()
openai_api_key = os.getenv("OPENAI_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")
openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
gemini_client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None


def serialize_review(review) -> dict:
    """
    Normalize a MongoDB review document into an API-friendly dictionary.

    Returns a dict containing identifiers, metadata, and feedback fields.
    """
    return {
        "id": str(review["_id"]),
        "code": review["code"],
        "language": review["language"],
        "status": review["status"],
        "created_at": review["created_at"],
        "feedback": review.get("feedback"),
        "completed_at": review.get("completed_at"),
        "failed_at": review.get("failed_at"),
    }


async def process_review(review_id: str, code: str, language: str):
    """
    Execute the AI-powered code review in the background.

    Fetches feedback from the configured AI provider (Gemini or OpenAI),
    validates the structure, and updates the review document with results
    and completion timestamps. On failure, stores error info and marks as failed.
    """
    try:
        prompt = f"""
You are an experienced code reviewer. Analyze this {language} code and return ONLY valid JSON with this structure:
{{
  "score": <1-10>,
  "issues": [{{"line": <int|null>, "severity": "low|medium|high", "description": "...", "suggestion": "..."}}],
  "suggestions": ["..."],
  "security_concerns": ["..."],
  "performance_recommendations": ["..."],
  "overall_feedback": "..."
}}

Code:
```{language}
{code}
```
"""

        raw_text = None
        last_error = None
        for attempt in range(1, 4):
            try:
                if gemini_client:
                    response = await asyncio.to_thread(
                        gemini_client.models.generate_content,
                        model="gemini-2.5-flash",
                        contents=prompt,
                        config={"response_mime_type": "application/json"},
                    )
                    raw_text = getattr(response, "output_text", None) or getattr(response, "text", None)
                elif openai_client:
                    chat = await asyncio.to_thread(
                        openai_client.chat.completions.create,
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                    )
                    raw_text = chat.choices[0].message.content if chat and chat.choices else None
                else:
                    raise ValueError("No AI provider configured")
                if raw_text:
                    break
                raise ValueError("Empty AI response")
            except Exception as e:
                last_error = e
                if attempt < 3:
                    await asyncio.sleep(0.8 * (2 ** (attempt - 1)))
                else:
                    raise last_error

        # Parse and validate the JSON response
        try:
            if not raw_text:
                raise ValueError("Empty AI response")
            feedback_data = json.loads(raw_text)

            # Validate the response structure
            if (
                not isinstance(feedback_data.get("score"), int)
                or not 1 <= feedback_data["score"] <= 10
            ):
                feedback_data["score"] = 5  # Default score if invalid

            # Ensure all arrays exist
            for key in [
                "issues",
                "suggestions",
                "security_concerns",
                "performance_recommendations",
            ]:
                if key not in feedback_data or not isinstance(feedback_data[key], list):
                    feedback_data[key] = []

            if "overall_feedback" not in feedback_data:
                feedback_data["overall_feedback"] = "No feedback provided"

        except json.JSONDecodeError:
            feedback_data = {
                "score": 5,
                "issues": [
                    {
                        "line": None,
                        "severity": "high",
                        "description": "Failed to parse AI response",
                        "suggestion": "Verify Gemini SDK response format and parsing logic",
                    }
                ],
                "suggestions": [],
                "security_concerns": [],
                "performance_recommendations": [],
                "overall_feedback": "Error processing review",
            }

        await db.reviews.update_one(
            {"_id": ObjectId(review_id)},
            {
                "$set": {
                    "status": "completed",
                    "feedback": feedback_data,
                    "completed_at": datetime.utcnow(),
                }
            },
        )

    except Exception as e:
        await db.reviews.update_one(
            {"_id": ObjectId(review_id)},
            {
                "$set": {
                    "status": "failed",
                    "feedback": {"error": str(e)},
                    "failed_at": datetime.utcnow(),
                }
            },
        )


async def enforce_rate_limit(ip: str) -> None:
    """
    Enforce rate limit of 10 reviews per IP within a 1-hour window.

    Raises HTTP 429 if the limit is exceeded.
    """
    window_start = datetime.utcnow() - timedelta(hours=1)
    count = await db.reviews.count_documents({
        "created_at": {"$gte": window_start},
        "ip": ip
    })
    if count >= 10:
        raise HTTPException(status_code=429, detail="Rate limit exceeded: 10 reviews per hour")


@router.post("/", response_model=ReviewResponse)
async def create_review(request: ReviewRequest, background_tasks: BackgroundTasks, http_request: Request, user=Depends(get_current_user)):
    """
    Submit a new code snippet for AI review.

    Accepts code and language, applies rate limiting by client IP, persists a
    pending review, and queues background processing. Returns the created review.
    """
    forwarded = http_request.headers.get("x-forwarded-for") or http_request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (http_request.client.host if http_request.client else "unknown")
    await enforce_rate_limit(ip)
    code_hash = hashlib.sha256(f"{request.language}\n{request.code}".encode("utf-8")).hexdigest()

    cached = await db.reviews.find_one({
        "code_hash": code_hash,
        "status": "completed",
        "feedback.score": {"$exists": True},
    })

    now = datetime.utcnow()

    if cached:
        review = {
            "code": request.code,
            "language": request.language,
            "status": "completed",
            "created_at": now,
            "completed_at": now,
            "ip": ip,
            "code_hash": code_hash,
            "user_id": user.get("email") if user else None,
            "feedback": cached.get("feedback"),
        }
        result = await db.reviews.insert_one(review)
        review["_id"] = result.inserted_id
        return serialize_review(review)

    review = {
        "code": request.code,
        "language": request.language,
        "status": "pending",
        "created_at": now,
        "ip": ip,
        "code_hash": code_hash,
        "user_id": user.get("email") if user else None,
    }
    result = await db.reviews.insert_one(review)
    review["_id"] = result.inserted_id

    background_tasks.add_task(
        process_review, str(result.inserted_id), request.code, request.language
    )

    return serialize_review(review)


@router.get("/id/{review_id}", response_model=ReviewResponse)
async def get_review(review_id: str):
    """
    Get a single review by its identifier.

    Returns 404 if the review is not found.
    """
    review = await db.reviews.find_one({"_id": ObjectId(review_id)})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return serialize_review(review)


@router.get("/", response_model=list[ReviewResponse])
async def list_reviews(
    skip: int = Query(0, ge=0, le=10_000),
    limit: int = Query(10, ge=1, le=100),
    language: str | None = Query(None),
    status: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
):
    """
    List reviews with pagination and optional filters.

    Query params:
    - skip: offset for pagination
    - limit: page size (1-100)
    - language: filter by programming language
    - status: filter by review status
    - start_date/end_date: filter by creation time range
    """
    query: dict = {}
    if language:
        query["language"] = language
    if status:
        query["status"] = status
    if start_date or end_date:
        date_filter = {}
        if start_date:
            date_filter["$gte"] = start_date
        if end_date:
            date_filter["$lte"] = end_date
        query["created_at"] = date_filter

    cursor = db.reviews.find(query).skip(skip).limit(limit)
    reviews = await cursor.to_list(length=limit)
    return [serialize_review(r) for r in reviews]


@router.get("/mine", response_model=list[ReviewResponse])
async def list_my_reviews(
    skip: int = Query(0, ge=0, le=10_000),
    limit: int = Query(10, ge=1, le=100),
    user=Depends(get_current_user),
):
    query = {"user_id": user.get("email")}
    cursor = db.reviews.find(query).skip(skip).limit(limit)
    reviews = await cursor.to_list(length=limit)
    return [serialize_review(r) for r in reviews]


@router.get("/stats")
async def get_stats():
    """
    Return aggregate statistics across reviews.

    Includes overall count and average score, most common issues,
    and per-language breakdown (count and average score).
    """
    pipeline = [
        {"$group": {
            "_id": None,
            "count": {"$sum": 1},
            "avg_score": {"$avg": "$feedback.score"},
        }},
        {"$project": {"_id": 0}}
    ]
    overall = await db.reviews.aggregate(pipeline).to_list(length=1)

    common_issues = await db.reviews.aggregate([
        {"$set": {"feedback_issues_as_array": {"$cond": [{"$isArray": "$feedback.issues"}, "$feedback.issues", []]}}},
        {"$unwind": {"path": "$feedback_issues_as_array", "preserveNullAndEmptyArrays": False}},
        {"$group": {"_id": "$feedback_issues_as_array.description", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]).to_list(length=10)

    by_language = await db.reviews.aggregate([
        {"$group": {"_id": "$language", "count": {"$sum": 1}, "avg_score": {"$avg": "$feedback.score"}}},
        {"$project": {"language": "$_id", "count": 1, "avg_score": 1, "_id": 0}},
        {"$sort": {"count": -1}},
    ]).to_list(length=50)

    return {
        "overall": overall[0] if overall else {"count": 0, "avg_score": None},
        "common_issues": common_issues,
        "by_language": by_language,
    }


@router.websocket("/ws/{review_id}")
async def review_status_ws(websocket: WebSocket, review_id: str):
    """
    WebSocket that streams review status updates until completion.

    Sends JSON payloads with fields: id, status, created_at, completed_at, failed_at.
    """
    await websocket.accept()
    try:
        while True:
            review = await db.reviews.find_one({"_id": ObjectId(review_id)})
            if not review:
                await websocket.send_json({"id": review_id, "status": "not_found"})
                await websocket.close(code=1000)
                return
            payload = {
                "id": review_id,
                "status": review.get("status"),
                "created_at": review.get("created_at").isoformat() if review.get("created_at") else None,
                "completed_at": review.get("completed_at").isoformat() if review.get("completed_at") else None,
                "failed_at": review.get("failed_at").isoformat() if review.get("failed_at") else None,
            }
            await websocket.send_json(payload)
            if review.get("status") in {"completed", "failed"}:
                await websocket.close(code=1000)
                return
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return


@router.get("/export")
async def export_reviews(
    language: str | None = Query(None),
    status: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
):
    """
    Export reviews as CSV with optional filters.

    Columns: id, language, status, score, created_at.
    """
    query: dict = {}
    if language:
        query["language"] = language
    if status:
        query["status"] = status
    if start_date or end_date:
        date_filter = {}
        if start_date:
            date_filter["$gte"] = start_date
        if end_date:
            date_filter["$lte"] = end_date
        query["created_at"] = date_filter

    cursor = db.reviews.find(query)
    rows = ["id,language,status,score,created_at"]
    async for r in cursor:
        rid = str(r.get("_id"))
        lang = r.get("language", "")
        st = r.get("status", "")
        score = (
            r.get("feedback", {}).get("score")
            if isinstance(r.get("feedback"), dict)
            else ""
        )
        created = r.get("created_at").isoformat() if r.get("created_at") else ""
        rows.append(f"{rid},{lang},{st},{score},{created}")

    def iterator():
        yield "\n".join(rows)

    return StreamingResponse(iterator(), media_type="text/csv")
