from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, List, Optional
from bson import ObjectId
from core.database import (
    get_orders_collection,
    get_carts_collection,
    get_menu_items_collection,
    get_addresses_collection,
    get_users_collection,
    get_deliveries_collection
)
from schemas.order import Order, OrderCreate, OrderUpdate, OrderDetail, OrderStatus, PaymentStatus
from api.deps import get_current_user, get_current_admin_user
from schemas.user import UserInDB
from datetime import datetime

router = APIRouter()


@router.post("/", response_model=Order, status_code=status.HTTP_201_CREATED)
async def create_order(
        order_in: OrderCreate,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Create a new order from cart
    """
    orders_collection = get_orders_collection()
    carts_collection = get_carts_collection()
    menu_items_collection = get_menu_items_collection()
    addresses_collection = get_addresses_collection()

    # Check if cart exists and belongs to user
    try:
        cart = carts_collection.find_one({
            "_id": ObjectId(order_in.cart_id),
            "user_id": current_user.id
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found"
        )

    if not cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found"
        )

    # Check if cart has items
    if not cart.get("items") or len(cart["items"]) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cart is empty"
        )

    # Check if delivery address exists
    try:
        address = addresses_collection.find_one({
            "_id": ObjectId(order_in.delivery_address_id),
            "user_id": current_user.id
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery address not found"
        )

    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery address not found"
        )

    # Prepare order items and calculate totals
    order_items = []
    subtotal = 0

    for cart_item in cart["items"]:
        # Get menu item to ensure price is current
        try:
            menu_item = menu_items_collection.find_one({"_id": ObjectId(cart_item["menu_item_id"])})
        except:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Menu item not found: {cart_item['menu_item_id']}"
            )

        if not menu_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Menu item not found: {cart_item['menu_item_id']}"
            )

        # Check if item is available
        if not menu_item.get("is_available", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Menu item is not available: {menu_item['name']}"
            )

        # Calculate item subtotal
        item_price = menu_item["price"]
        item_subtotal = item_price * cart_item["quantity"]
        subtotal += item_subtotal

        # Create order item
        order_items.append({
            "_id": str(ObjectId()),
            "menu_item_id": str(menu_item["_id"]),
            "name": menu_item["name"],
            "price": item_price,
            "quantity": cart_item["quantity"],
            "subtotal": item_subtotal
        })

    # Calculate additional costs
    delivery_fee = 5.00  # Fixed delivery fee for now
    tax_rate = 0.075  # 7.5% tax rate
    tax = subtotal * tax_rate
    total_amount = subtotal + delivery_fee + tax

    # Create order
    now = datetime.utcnow()
    order_data = {
        "user_id": current_user.id,
        "items": order_items,
        "delivery_address_id": order_in.delivery_address_id,
        "special_instructions": order_in.special_instructions,
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "tax": tax,
        "total_amount": total_amount,
        "status": OrderStatus.PENDING.value,
        "payment_status": PaymentStatus.PENDING.value,
        "payment_reference": None,
        "delivery_status": None,
        "created_at": now,
        "updated_at": now
    }

    # Insert order
    result = orders_collection.insert_one(order_data)
    order_id = result.inserted_id

    # Clear cart after order is created
    carts_collection.update_one(
        {"_id": ObjectId(order_in.cart_id)},
        {"$set": {"items": [], "updated_at": now}}
    )

    # Get created order
    created_order = orders_collection.find_one({"_id": order_id})
    created_order["_id"] = str(created_order["_id"])

    return created_order


@router.get("/", response_model=List[Order])
async def get_user_orders(
        status: Optional[OrderStatus] = None,
        skip: int = 0,
        limit: int = 100,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Get user's orders
    """
    orders_collection = get_orders_collection()

    # Build filter
    filter_query = {"user_id": current_user.id}

    if status:
        filter_query["status"] = status.value

    # Get orders
    orders = list(orders_collection.find(filter_query).sort("created_at", -1).skip(skip).limit(limit))

    # Convert ObjectId to string
    for order in orders:
        order["_id"] = str(order["_id"])

    return orders


@router.get("/{order_id}", response_model=OrderDetail)
async def get_order_detail(
        order_id: str,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Get order details
    """
    orders_collection = get_orders_collection()
    addresses_collection = get_addresses_collection()
    users_collection = get_users_collection()

    # Check if order exists and belongs to user
    try:
        order = orders_collection.find_one({
            "_id": ObjectId(order_id),
            "user_id": current_user.id
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    # Convert ObjectId to string
    order["_id"] = str(order["_id"])

    # Get delivery address
    try:
        address = addresses_collection.find_one({"_id": ObjectId(order["delivery_address_id"])})
        if address:
            address["_id"] = str(address["_id"])
            order["delivery_address"] = address
        else:
            order["delivery_address"] = {"address": "Address not found"}
    except:
        order["delivery_address"] = {"address": "Address not found"}

    # Get user info
    try:
        user = users_collection.find_one({"_id": ObjectId(order["user_id"])})
        if user:
            # Remove sensitive info
            user.pop("hashed_password", None)
            user["_id"] = str(user["_id"])
            order["user"] = user
        else:
            order["user"] = {"full_name": "User not found"}
    except:
        order["user"] = {"full_name": "User not found"}

    return order


@router.put("/{order_id}/cancel", response_model=Order)
async def cancel_order(
        order_id: str,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Cancel an order
    """
    orders_collection = get_orders_collection()

    # Check if order exists and belongs to user
    try:
        order = orders_collection.find_one({
            "_id": ObjectId(order_id),
            "user_id": current_user.id
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    # Check if order can be cancelled
    if order["status"] not in [OrderStatus.PENDING.value, OrderStatus.CONFIRMED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order cannot be cancelled at this stage"
        )

    # Update order status
    now = datetime.utcnow()
    orders_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {
            "status": OrderStatus.CANCELLED.value,
            "updated_at": now
        }}
    )

    # Get updated order
    updated_order = orders_collection.find_one({"_id": ObjectId(order_id)})
    updated_order["_id"] = str(updated_order["_id"])

    return updated_order


@router.get("/admin/orders", response_model=List[Order])
async def get_all_orders(
        status: Optional[OrderStatus] = None,
        payment_status: Optional[PaymentStatus] = None,
        skip: int = 0,
        limit: int = 100,
        current_user: UserInDB = Depends(get_current_admin_user)
) -> Any:
    """
    Get all orders (admin only)
    """
    orders_collection = get_orders_collection()

    # Build filter
    filter_query = {}

    if status:
        filter_query["status"] = status.value

    if payment_status:
        filter_query["payment_status"] = payment_status.value

    # Get orders
    orders = list(orders_collection.find(filter_query).sort("created_at", -1).skip(skip).limit(limit))

    # Convert ObjectId to string
    for order in orders:
        order["_id"] = str(order["_id"])

    return orders


@router.put("/admin/{order_id}/status", response_model=Order)
async def update_order_status(
        order_id: str,
        status: OrderStatus,
        current_user: UserInDB = Depends(get_current_admin_user)
) -> Any:
    """
    Update order status (admin only)
    """
    orders_collection = get_orders_collection()

    # Check if order exists
    try:
        order = orders_collection.find_one({"_id": ObjectId(order_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    # Update order status
    now = datetime.utcnow()
    orders_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {
            "status": status.value,
            "updated_at": now
        }}
    )

    # Get updated order
    updated_order = orders_collection.find_one({"_id": ObjectId(order_id)})
    updated_order["_id"] = str(updated_order["_id"])

    return updated_order