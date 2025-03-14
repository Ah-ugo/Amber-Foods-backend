from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY = "READY"
    EN_ROUTE = "EN_ROUTE"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class OrderItemBase(BaseModel):
    menu_item_id: str
    quantity: int
    price: float
    name: str


class OrderItemCreate(OrderItemBase):
    pass


class OrderItem(OrderItemBase):
    id: str = Field(..., alias="_id")
    subtotal: float

    class Config:
        allow_population_by_field_name = True


class OrderBase(BaseModel):
    delivery_address_id: str
    special_instructions: Optional[str] = None


class OrderCreate(OrderBase):
    cart_id: str


class OrderUpdate(BaseModel):
    special_instructions: Optional[str] = None
    status: Optional[OrderStatus] = None


class Order(OrderBase):
    id: str = Field(..., alias="_id")
    user_id: str
    items: List[OrderItem]
    subtotal: float
    delivery_fee: float
    tax: float
    total_amount: float
    status: OrderStatus
    payment_status: PaymentStatus
    payment_reference: Optional[str] = None
    delivery_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True


class OrderDetail(Order):
    delivery_address: Dict[str, Any]
    user: Dict[str, Any]