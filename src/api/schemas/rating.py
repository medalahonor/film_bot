from datetime import datetime

from pydantic import BaseModel, Field


class RatingResponse(BaseModel):
    id: int
    session_id: int
    movie_id: int
    rating: int
    created_at: datetime

    model_config = {"from_attributes": True}


class RatingRequest(BaseModel):
    session_id: int
    movie_id: int
    rating: int = Field(ge=1, le=10)
