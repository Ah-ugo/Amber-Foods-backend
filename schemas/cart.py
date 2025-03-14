from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class CartItemBase(BaseModel):
    menu_item_id: str
    quantity: int


class CartItemCreate(CartItemBase):
    pass


class CartItemUpdate(BaseModel):
    quantity: int


class CartItem(CartItemBase):
    id: str = Field(..., alias="_id")
    name: str
    price: float
    subtotal: float
    image_url: Optional[str] = None

    class Config:
        allow_population_by_field_name = True


class Cart(BaseModel):
    id: str = Field(..., alias="_id")
    user_id: str
    items: List[CartItem]
    total: float
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True