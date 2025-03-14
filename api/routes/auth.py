from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from typing import Any
from datetime import timedelta
from core.config import settings
from core.security import create_access_token
from core.database import get_users_collection
from models.user import UserModel
from schemas.user import User, UserCreate, Token, UserInDB
from api.deps import get_current_user
from bson import ObjectId

router = APIRouter()


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate) -> Any:
    """
    Register a new user
    """
    users_collection = get_users_collection()

    # Check if user already exists
    if users_collection.find_one({"email": user_in.email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    user_data = UserModel.create_user(
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        phone=user_in.phone
    )

    result = users_collection.insert_one(user_data)
    user_id = result.inserted_id

    # Get created user
    created_user = users_collection.find_one({"_id": user_id})
    created_user["_id"] = str(created_user["_id"])

    return created_user


@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    users_collection = get_users_collection()
    user = users_collection.find_one({"email": form_data.username})

    if not user or not UserModel.authenticate(user, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(user["_id"]), expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh-token", response_model=Token)
async def refresh_token(current_user: UserInDB = Depends(get_current_user)) -> Any:
    """
    Refresh access token
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=current_user.id, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=User)
async def read_users_me(current_user: UserInDB = Depends(get_current_user)) -> Any:
    """
    Get current user
    """
    # Ensure _id is properly returned as a string
    current_user_dict = current_user.dict(by_alias=True)
    current_user_dict["_id"] = str(current_user_dict["_id"])  # Ensure it's a string
    return current_user_dict
