from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from bson import ObjectId
from core.database import get_notifications_collection
from schemas.notification import Notification, NotificationCreate, NotificationUpdate, NotificationType
from schemas.user import UserInDB
from api.deps import get_current_user, get_current_admin_user
from datetime import datetime

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/", response_model=Notification, status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification_in: NotificationCreate,
    current_user: UserInDB = Depends(get_current_admin_user)
) -> Notification:
    """
    Create a new notification (admin only)
    """
    notifications_collection = get_notifications_collection()

    now = datetime.utcnow()
    notification_data = {
        **notification_in.dict(),
        "created_at": now,
        "updated_at": now
    }

    result = notifications_collection.insert_one(notification_data)
    created_notification = notifications_collection.find_one({"_id": result.inserted_id})
    created_notification["_id"] = str(created_notification["_id"])

    return created_notification


@router.get("/", response_model=List[Notification])
async def get_user_notifications(
    type: Optional[NotificationType] = None,
    is_read: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: UserInDB = Depends(get_current_user)
) -> List[Notification]:
    """
    Get user's notifications
    """
    notifications_collection = get_notifications_collection()

    # Build filter
    filter_query = {"user_id": current_user.id}

    if type:
        filter_query["type"] = type.value
    if is_read is not None:
        filter_query["is_read"] = is_read

    # Get notifications
    notifications = list(
        notifications_collection.find(filter_query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )

    # Convert ObjectId to string
    for notification in notifications:
        notification["_id"] = str(notification["_id"])

    return notifications


@router.put("/{notification_id}/read", response_model=Notification)
async def mark_notification_read(
    notification_id: str,
    current_user: UserInDB = Depends(get_current_user)
) -> Notification:
    """
    Mark a notification as read
    """
    notifications_collection = get_notifications_collection()

    # Check if notification exists and belongs to user
    try:
        notification = notifications_collection.find_one({
            "_id": ObjectId(notification_id),
            "user_id": current_user.id
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    # Update notification
    now = datetime.utcnow()
    notifications_collection.update_one(
        {"_id": ObjectId(notification_id)},
        {"$set": {
            "is_read": True,
            "updated_at": now
        }}
    )

    # Get updated notification
    updated_notification = notifications_collection.find_one({"_id": ObjectId(notification_id)})
    updated_notification["_id"] = str(updated_notification["_id"])

    return updated_notification


@router.get("/admin/notifications", response_model=List[Notification])
async def get_all_notifications(
    user_id: Optional[str] = None,
    type: Optional[NotificationType] = None,
    is_read: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: UserInDB = Depends(get_current_admin_user)
) -> List[Notification]:
    """
    Get all notifications (admin only)
    """
    notifications_collection = get_notifications_collection()

    # Build filter
    filter_query = {}

    if user_id:
        filter_query["user_id"] = user_id
    if type:
        filter_query["type"] = type.value
    if is_read is not None:
        filter_query["is_read"] = is_read

    # Get notifications
    notifications = list(
        notifications_collection.find(filter_query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )

    # Convert ObjectId to string
    for notification in notifications:
        notification["_id"] = str(notification["_id"])

    return notifications