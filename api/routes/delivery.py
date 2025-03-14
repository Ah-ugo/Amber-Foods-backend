from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, Optional
from core.database import get_deliveries_collection, get_orders_collection
from api.deps import get_current_user, get_current_admin_user
from schemas.user import UserInDB
from bson import ObjectId
from datetime import datetime

router = APIRouter()


@router.get("/tracking/{order_id}")
async def get_delivery_status(
        order_id: str,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Get delivery status for an order
    """
    orders_collection = get_orders_collection()
    deliveries_collection = get_deliveries_collection()

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

    # Get delivery
    delivery = deliveries_collection.find_one({"order_id": order_id})

    if not delivery:
        return {
            "order_id": order_id,
            "status": "NOT_STARTED",
            "message": "Delivery not yet started"
        }

    # Convert ObjectId to string
    delivery["_id"] = str(delivery["_id"])

    return delivery


@router.get("/estimate")
async def get_delivery_estimate(
        address_id: Optional[str] = None,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Get estimated delivery time
    """
    # In a real app, this would calculate based on distance, traffic, etc.
    # For now, return a fixed estimate
    return {
        "min_minutes": 30,
        "max_minutes": 45,
        "message": "Your order will arrive in 30-45 minutes"
    }


# Admin routes for delivery management
@router.put("/admin/{order_id}/status/preparing")
async def update_status_preparing(
        order_id: str,
        current_user: UserInDB = Depends(get_current_admin_user)
) -> Any:
    """
    Update delivery status to PREPARING (admin only)
    """
    return await update_delivery_status(order_id, "PREPARING", "Your order is being prepared")


@router.put("/admin/{order_id}/status/en-route")
async def update_status_en_route(
        order_id: str,
        current_user: UserInDB = Depends(get_current_admin_user)
) -> Any:
    """
    Update delivery status to EN_ROUTE (admin only)
    """
    return await update_delivery_status(order_id, "EN_ROUTE", "Your order is on the way")


@router.put("/admin/{order_id}/status/arrived")
async def update_status_arrived(
        order_id: str,
        current_user: UserInDB = Depends(get_current_admin_user)
) -> Any:
    """
    Update delivery status to ARRIVED (admin only)
    """
    return await update_delivery_status(order_id, "ARRIVED", "Your delivery has arrived at your location")


@router.put("/admin/{order_id}/status/delivered")
async def update_status_delivered(
        order_id: str,
        current_user: UserInDB = Depends(get_current_admin_user)
) -> Any:
    """
    Update delivery status to DELIVERED (admin only)
    """
    return await update_delivery_status(order_id, "DELIVERED", "Your order has been delivered")


async def update_delivery_status(order_id: str, status: str, message: str) -> Any:
    """
    Helper function to update delivery status
    """
    orders_collection = get_orders_collection()
    deliveries_collection = get_deliveries_collection()

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

    # Check if delivery exists
    delivery = deliveries_collection.find_one({"order_id": order_id})
    now = datetime.utcnow()

    if delivery:
        # Update existing delivery
        deliveries_collection.update_one(
            {"order_id": order_id},
            {"$set": {
                "status": status,
                "message": message,
                "status_updated_at": now,
                "updated_at": now,
                f"status_history.{status}": now
            }}
        )
    else:
        # Create new delivery
        delivery_data = {
            "order_id": order_id,
            "user_id": order["user_id"],
            "status": status,
            "message": message,
            "driver_id": None,
            "driver_name": None,
            "driver_phone": None,
            "status_updated_at": now,
            "created_at": now,
            "updated_at": now,
            "status_history": {
                status: now
            }
        }
        deliveries_collection.insert_one(delivery_data)

    # Update order status
    orders_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {
            "delivery_status": status,
            "updated_at": now
        }}
    )

    # Get updated delivery
    updated_delivery = deliveries_collection.find_one({"order_id": order_id})
    updated_delivery["_id"] = str(updated_delivery["_id"])

    return updated_delivery


@router.put("/admin/{order_id}/assign")
async def assign_driver(
        order_id: str,
        driver_id: str,
        driver_name: str,
        driver_phone: str,
        current_user: UserInDB = Depends(get_current_admin_user)
) -> Any:
    """
    Assign a delivery driver to an order (admin only)
    """
    orders_collection = get_orders_collection()
    deliveries_collection = get_deliveries_collection()

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

    # Check if delivery exists
    delivery = deliveries_collection.find_one({"order_id": order_id})
    now = datetime.utcnow()

    if delivery:
        # Update existing delivery
        deliveries_collection.update_one(
            {"order_id": order_id},
            {"$set": {
                "driver_id": driver_id,
                "driver_name": driver_name,
                "driver_phone": driver_phone,
                "updated_at": now
            }}
        )
    else:
        # Create new delivery
        delivery_data = {
            "order_id": order_id,
            "user_id": order["user_id"],
            "status": "ASSIGNED",
            "message": "A driver has been assigned to your order",
            "driver_id": driver_id,
            "driver_name": driver_name,
            "driver_phone": driver_phone,
            "status_updated_at": now,
            "created_at": now,
            "updated_at": now,
            "status_history": {
                "ASSIGNED": now
            }
        }
        deliveries_collection.insert_one(delivery_data)

        # Update order status
        orders_collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {
                "delivery_status": "ASSIGNED",
                "updated_at": now
            }}
        )

    # Get updated delivery
    updated_delivery = deliveries_collection.find_one({"order_id": order_id})
    updated_delivery["_id"] = str(updated_delivery["_id"])

    return updated_delivery