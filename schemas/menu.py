from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class Category(CategoryBase):
    id: str = Field(..., alias="_id")
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True


class MenuItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    category_id: str
    is_available: bool = True
    is_featured: bool = False


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category_id: Optional[str] = None
    is_available: Optional[bool] = None
    is_featured: Optional[bool] = None


class MenuItem(MenuItemBase):
    id: str = Field(..., alias="_id")
    images: List[dict] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True


class MenuItemWithCategory(MenuItem):
    category: Category