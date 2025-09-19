from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    code: str
    language: str


class ReviewResponse(BaseModel):
    id: str
    code: str
    language: str
    status: str
    created_at: datetime
    feedback: Optional[dict] = None
