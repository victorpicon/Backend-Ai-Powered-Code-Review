import json
import os
from datetime import datetime

from app.api.reviews.schema import ReviewRequest, ReviewResponse
from app.database.database import db
from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, HTTPException

# from openai import OpenAI
from google import genai

router = APIRouter()
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


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
    """Calls Gemini API to process the code review."""
    try:
        prompt = f"""
        You are an experienced code reviewer. Analyze this {language} code and provide structured feedback.
        Return ONLY valid JSON with this exact structure:

        {{
            "score": <integer from 1 to 10>,
            "issues": [
                {{
                    "line": <optional line number>,
                    "severity": "low|medium|high",
                    "description": "description of the issue",
                    "suggestion": "how to fix it"
                }}
            ],
            "suggestions": ["list of general improvement suggestions"],
            "security_concerns": ["list of security issues"],
            "performance_recommendations": ["list of performance optimizations"],
            "overall_feedback": "brief overall assessment"
        }}

        Code to review:
        ```{language}
        {code}
        ```
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        # Parse and validate the JSON response
        try:
            feedback_data = json.loads(response.text)

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
                "issues": ["Failed to parse AI response"],
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
