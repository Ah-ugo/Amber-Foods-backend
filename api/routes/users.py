from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body
from typing import Any, Optional, Union
from bson import ObjectId
from core.database import get_users_collection
from models.user import UserModel
from schemas.user import User, UserUpdate, UserInDB
from api.deps import get_current_user, get_current_admin_user
from services.cloudinary_service import cloudinary_service
import json

router = APIRouter()


# @router.put("/me", response_model=User)
# async def update_user_me(
#         *,
#         user_data: Optional[str] = Form(None),
#         profile_image: Optional[UploadFile] = File(None),
#         current_user: UserInDB = Depends(get_current_user)
# ) -> Any:
#     """
#     Update current user
#     """
#     users_collection = get_users_collection()
#
#     # Parse user data from form
#     user_update = None
#     if user_data:
#         user_update = UserUpdate(**json.loads(user_data))
#     else:
#         user_update = UserUpdate()
#
#     # Handle profile image upload
#     if profile_image:
#         # Read file content
#         file_content = await profile_image.read()
#
#         # Upload to Cloudinary
#         upload_result = await cloudinary_service.upload_image(
#             file_data=file_content,
#             folder="user_profiles",
#             public_id=f"user_{current_user.id}"
#         )
#
#         # Update user with image info
#         user_update.profile_image = upload_result["public_id"]
#         user_update.profile_image_url = upload_result["url"]
#
#     # Update user in database
#     update_data = user_update.dict(exclude_unset=True)
#
#     if update_data:
#         # Get current user data
#         user_data = users_collection.find_one({"_id": ObjectId(current_user.id)})
#
#         # Update with new data
#         for field, value in update_data.items():
#             if value is not None:
#                 user_data[field] = value
#
#         # Update timestamp
#         updated_user = UserModel.update_user(user_data)
#
#         # Save to database
#         users_collection.update_one(
#             {"_id": ObjectId(current_user.id)},
#             {"$set": updated_user}
#         )
#
#         # Get updated user
#         updated_user = users_collection.find_one({"_id": ObjectId(current_user.id)})
#         updated_user["_id"] = str(updated_user["_id"])
#
#         return updated_user
#
#     return current_user


@router.put("/me", response_model=User)
async def update_user_me(
    full_name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    profile_image: Union[UploadFile, None] = File(None),  # Ensure it accepts None
    current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Update current user's full name, phone, and optionally profile image.
    """
    users_collection = get_users_collection()
    update_data = {}

    # Update full_name and phone if provided
    if full_name:
        update_data["full_name"] = full_name
    if phone:
        update_data["phone"] = phone

    # Handle profile image upload only if a file is provided
    if profile_image and profile_image.filename:
        file_content = await profile_image.read()
        upload_result = await cloudinary_service.upload_image(
            file_data=file_content,
            folder="user_profiles",
            public_id=f"user_{current_user.id}"
        )
        update_data["profile_image"] = upload_result["public_id"]
        update_data["profile_image_url"] = upload_result["url"]

    # Update user in database if there are any changes
    if update_data:
        users_collection.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": update_data}
        )

        # Get updated user
        updated_user = users_collection.find_one({"_id": ObjectId(current_user.id)})
        updated_user["_id"] = str(updated_user["_id"])

        return updated_user

    return current_user  # Return current user if no updates were made


@router.get("/me", response_model=User)
async def read_user_me(current_user: UserInDB = Depends(get_current_user)) -> Any:
    """
    Get current user
    """
    user_data = current_user.dict()
    user_data["_id"] = str(current_user.id)  # Ensure _id is included
    return user_data



@router.get("/{user_id}", response_model=User)
async def read_user_by_id(
        user_id: str,
        current_user: UserInDB = Depends(get_current_admin_user)
) -> Any:
    """
    Get a specific user by id (admin only)
    """
    users_collection = get_users_collection()

    try:
        user = users_collection.find_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user["_id"] = str(user["_id"])
    return user


@router.get("/", response_model=list[User])
async def read_users(
        skip: int = 0,
        limit: int = 100,
        current_user: UserInDB = Depends(get_current_admin_user)
) -> Any:
    """
    Retrieve users (admin only)
    """
    users_collection = get_users_collection()
    users = list(users_collection.find().skip(skip).limit(limit))

    # Convert ObjectId to string for each user
    for user in users:
        user["_id"] = str(user["_id"])

    return users