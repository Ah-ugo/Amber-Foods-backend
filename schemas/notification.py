from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class NotificationType(str, Enum):
    ORDER = "order"
    PROMOTION = "promotion"
    SYSTEM = "system"


class NotificationBase(BaseModel):
    title: str
    message: str
    type: NotificationType
    order_id: Optional[str] = None


class NotificationCreate(NotificationBase):
    user_id: str
    is_read: bool = False


class NotificationUpdate(BaseModel):
    is_read: Optional[bool] = None


class Notification(NotificationBase):
    id: str = Field(..., alias="_id")
    user_id: str
    is_read: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True