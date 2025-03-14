from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class ReviewBase(BaseModel):
    menu_item_id: str
    rating: int
    comment: Optional[str] = None

    @validator('rating')
    def rating_must_be_valid(cls, v):
        if v < 1 or v > 5:
            raise ValueError('Rating must be between 1 and 5')
        return v


class ReviewCreate(ReviewBase):
    pass


class ReviewUpdate(BaseModel):
    rating: Optional[int] = None
    comment: Optional[str] = None

    @validator('rating')
    def rating_must_be_valid(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError('Rating must be between 1 and 5')
        return v


class Review(ReviewBase):
    id: str = Field(..., alias="_id")
    user_id: str
    user_name: str
    user_image: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True