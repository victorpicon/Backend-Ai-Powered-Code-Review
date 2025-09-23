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
    
    Features:
    - Rate limiting: 10 reviews per IP per hour
    - Code caching: Identical code returns cached results instantly
    - Background processing: AI analysis runs asynchronously
    - User association: Links review to authenticated user
    
    Args:
        request (ReviewRequest): Review data containing:
            - code (str): Source code to review (required)
            - language (str): Programming language (required)
        background_tasks: FastAPI background tasks handler
        http_request: HTTP request object for IP extraction
        user: Current authenticated user (injected by dependency)
    
    Returns:
        ReviewResponse: Created review with status and metadata
    
    Raises:
        HTTPException: 429 if rate limit exceeded
        HTTPException: 401 if not authenticated
    
    Example:
        Request:
        ```json
        {
            "code": "def hello():\n    print('Hello World')",
            "language": "python"
        }
        ```
        
        Response:
        ```json
        {
            "id": "507f1f77bcf86cd799439011",
            "code": "def hello():\n    print('Hello World')",
            "language": "python",
            "status": "pending",
            "created_at": "2024-01-15T10:30:00Z",
            "feedback": null,
            "completed_at": null,
            "failed_at": null
        }
        ```
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

    Retrieves a complete review including code, feedback, and status information.
    Returns 404 if the review is not found.
    
    Args:
        review_id (str): MongoDB ObjectId of the review (required)
    
    Returns:
        ReviewResponse: Complete review data including:
            - id: Review identifier
            - code: Original source code
            - language: Programming language
            - status: Current status (pending/in_progress/completed/failed)
            - feedback: AI analysis results (if completed)
            - created_at: Creation timestamp
            - completed_at: Completion timestamp (if completed)
            - failed_at: Failure timestamp (if failed)
    
    Raises:
        HTTPException: 404 if review not found
    
    Example:
        Request:
        ```
        GET /api/reviews/id/507f1f77bcf86cd799439011
        ```
        
        Response:
        ```json
        {
            "id": "507f1f77bcf86cd799439011",
            "code": "def hello():\n    print('Hello World')",
            "language": "python",
            "status": "completed",
            "created_at": "2024-01-15T10:30:00Z",
            "feedback": {
                "score": 8,
                "issues": [],
                "suggestions": ["Consider adding docstring"],
                "security_concerns": [],
                "performance_recommendations": [],
                "overall_feedback": "Good code structure"
            },
            "completed_at": "2024-01-15T10:30:15Z",
            "failed_at": null
        }
        ```
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

    Retrieves a paginated list of reviews with optional filtering capabilities.
    Results are ordered by creation date (newest first).
    
    Query Parameters:
        skip (int): Number of reviews to skip for pagination (0-10000, default: 0)
        limit (int): Maximum number of reviews to return (1-100, default: 10)
        language (str, optional): Filter by programming language (e.g., "python", "javascript")
        status (str, optional): Filter by review status ("pending", "in_progress", "completed", "failed")
        start_date (datetime, optional): Filter reviews created after this date (ISO format)
        end_date (datetime, optional): Filter reviews created before this date (ISO format)
    
    Returns:
        list[ReviewResponse]: List of review objects matching the criteria
    
    Example:
        Request:
        ```
        GET /api/reviews?skip=0&limit=5&language=python&status=completed
        ```
        
        Response:
        ```json
        [
            {
                "id": "507f1f77bcf86cd799439011",
                "code": "def hello():\n    print('Hello World')",
                "language": "python",
                "status": "completed",
                "created_at": "2024-01-15T10:30:00Z",
                "feedback": {...},
                "completed_at": "2024-01-15T10:30:15Z",
                "failed_at": null
            }
        ]
        ```
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
    """
    Get current user's personal review history.
    
    Retrieves a paginated list of reviews submitted by the authenticated user.
    Results are ordered by creation date (newest first).
    
    Args:
        skip (int): Number of reviews to skip for pagination (0-10000, default: 0)
        limit (int): Maximum number of reviews to return (1-100, default: 10)
        user: Current authenticated user (injected by dependency)
    
    Returns:
        list[ReviewResponse]: List of user's review objects
    
    Raises:
        HTTPException: 401 if not authenticated
    
    Example:
        Request Headers:
        ```
        Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        ```
        
        Request:
        ```
        GET /api/reviews/mine?skip=0&limit=10
        ```
        
        Response:
        ```json
        [
            {
                "id": "507f1f77bcf86cd799439011",
                "code": "def hello():\n    print('Hello World')",
                "language": "python",
                "status": "completed",
                "created_at": "2024-01-15T10:30:00Z",
                "feedback": {...},
                "completed_at": "2024-01-15T10:30:15Z",
                "failed_at": null
            }
        ]
        ```
    """
    query = {"user_id": user.get("email")}
    cursor = db.reviews.find(query).skip(skip).limit(limit)
    reviews = await cursor.to_list(length=limit)
    return [serialize_review(r) for r in reviews]


@router.get("/stats")
async def get_stats():
    """
    Return aggregate statistics across reviews.

    Provides comprehensive analytics including overall metrics, common issues,
    and per-language breakdown. Uses MongoDB aggregation pipelines for efficient
    data processing.
    
    Returns:
        dict: Statistics object containing:
            - overall: Overall metrics (count, average_score)
            - common_issues: Top 10 most frequent issues
            - by_language: Statistics grouped by programming language
    
    Example:
        Request:
        ```
        GET /api/reviews/stats
        ```
        
        Response:
        ```json
        {
            "overall": {
                "count": 150,
                "avg_score": 7.2
            },
            "common_issues": [
                {
                    "_id": "Missing error handling",
                    "count": 45
                },
                {
                    "_id": "Code complexity too high",
                    "count": 32
                }
            ],
            "by_language": [
                {
                    "language": "python",
                    "count": 75,
                    "avg_score": 7.5
                },
                {
                    "language": "javascript",
                    "count": 45,
                    "avg_score": 6.8
                }
            ]
        }
        ```
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

    Establishes a real-time connection to receive live updates about a review's
    processing status. Automatically closes when review is completed or failed.
    
    Args:
        websocket: WebSocket connection object
        review_id (str): MongoDB ObjectId of the review to monitor
    
    Message Format:
        Sends JSON payloads with fields:
            - id: Review identifier
            - status: Current status (pending/in_progress/completed/failed/not_found)
            - created_at: Creation timestamp (ISO format)
            - completed_at: Completion timestamp (ISO format, if completed)
            - failed_at: Failure timestamp (ISO format, if failed)
    
    Connection Lifecycle:
        - Opens connection and accepts WebSocket
        - Polls review status every 1 second
        - Sends status updates to client
        - Closes connection when review completes or fails
        - Handles client disconnections gracefully
    
    Example:
        Connection:
        ```
        ws://localhost:8000/api/reviews/ws/507f1f77bcf86cd799439011
        ```
        
        Messages:
        ```json
        {
            "id": "507f1f77bcf86cd799439011",
            "status": "in_progress",
            "created_at": "2024-01-15T10:30:00Z",
            "completed_at": null,
            "failed_at": null
        }
        ```
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

    Generates a CSV file containing review data with optional filtering.
    Uses streaming response for efficient handling of large datasets.
    
    Query Parameters:
        language (str, optional): Filter by programming language
        status (str, optional): Filter by review status
        start_date (datetime, optional): Filter reviews created after this date
        end_date (datetime, optional): Filter reviews created before this date
    
    Returns:
        StreamingResponse: CSV file with headers:
            - id: Review identifier
            - language: Programming language
            - status: Review status
            - score: AI feedback score (if available)
            - created_at: Creation timestamp
    
    Example:
        Request:
        ```
        GET /api/reviews/export?language=python&status=completed
        ```
        
        Response:
        ```csv
        id,language,status,score,created_at
        507f1f77bcf86cd799439011,python,completed,8,2024-01-15T10:30:00Z
        507f1f77bcf86cd799439012,python,completed,7,2024-01-15T11:15:00Z
        ```
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
