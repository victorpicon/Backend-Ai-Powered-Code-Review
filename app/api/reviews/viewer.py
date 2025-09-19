import json
from datetime import datetime

from app.api.reviews.schema import ReviewRequest, ReviewResponse
from app.database.database import db
from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, HTTPException
from openai import OpenAI

router = APIRouter()
client = OpenAI()


def serialize_review(review) -> dict:
    return {
        "id": str(review["_id"]),
        "code": review["code"],
        "language": review["language"],
        "status": review["status"],
        "created_at": review["created_at"],
        "feedback": review.get("feedback"),
    }


async def process_review(review_id: str, code: str, language: str):
    """Calls OpenAI API to process the code review."""
    try:
        prompt = f"""
        You are a code reviewer.
        Analyze the following {language} snippet and return ONLY valid JSON with this structure:

        {{
            "score": <integer 1-10>,
            "issues": [ "list of identified issues" ],
            "suggestions": [ "list of improvement suggestions" ],
            "security": [ "list of security concerns" ],
            "performance": [ "list of performance recommendations" ]
        }}

        Code:
            {code}
        """

        response = await client.chat.completions.acreate(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format="json",
        )

        feedback_json = response.choices[0].message["content"]
        feedback = json.loads(feedback_json)

        await db.reviews.update_one(
            {"_id": ObjectId(review_id)},
            {"$set": {"status": "completed", "feedback": feedback}},
        )

    except Exception as e:
        await db.reviews.update_one(
            {"_id": ObjectId(review_id)},
            {"$set": {"status": "failed", "feedback": {"error": str(e)}}},
        )


@router.post("/", response_model=ReviewResponse)
async def create_review(request: ReviewRequest, background_tasks: BackgroundTasks):
    """Create a new code review request."""
    review = {
        "code": request.code,
        "language": request.language,
        "status": "pending",
        "created_at": datetime.utcnow(),
    }
    result = await db.reviews.insert_one(review)
    review["_id"] = result.inserted_id

    background_tasks.add_task(
        process_review, str(result.inserted_id), request.code, request.language
    )

    return serialize_review(review)


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(review_id: str):
    """Get a specific code review by ID."""
    review = await db.reviews.find_one({"_id": ObjectId(review_id)})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return serialize_review(review)


@router.get("/", response_model=list[ReviewResponse])
async def list_reviews(skip: int = 0, limit: int = 10):
    """List all code reviews with pagination."""
    cursor = db.reviews.find().skip(skip).limit(limit)
    reviews = await cursor.to_list(length=limit)
    return [serialize_review(r) for r in reviews]
