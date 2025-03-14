from datetime import datetime
from typing import Optional, Dict, Any
from bson import ObjectId
from core.security import get_password_hash, verify_password


class UserModel:
    @staticmethod
    def create_user(
            email: str,
            password: str,
            full_name: str,
            phone: Optional[str] = None,
            is_admin: bool = False
    ) -> Dict[str, Any]:
        """Create a new user document"""
        now = datetime.utcnow()
        return {
            "email": email,
            "hashed_password": get_password_hash(password),
            "full_name": full_name,
            "phone": phone,
            "is_active": True,
            "is_admin": is_admin,
            "profile_image": None,
            "profile_image_url": None,
            "created_at": now,
            "updated_at": now
        }

    @staticmethod
    def update_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user document with new data"""
        user_data["updated_at"] = datetime.utcnow()
        return user_data

    @staticmethod
    def authenticate(user: Dict[str, Any], password: str) -> bool:
        """Verify password against stored hash"""
        if not user:
            return False
        if not verify_password(password, user["hashed_password"]):
            return False
        return True