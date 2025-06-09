import os
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from typing import Any, Dict
from core.config import settings
from core.database import get_payments_collection, get_orders_collection, get_notifications_collection
from api.deps import get_current_user
from schemas.user import UserInDB
from schemas.notification import NotificationCreate, NotificationType
from schemas.order import PaymentStatus
import httpx
from bson import ObjectId
from datetime import datetime
import secrets
from dotenv import load_dotenv

load_dotenv()

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

router = APIRouter()

def create_payment_notification(
    user_id: str,
    order_id: str,
    payment_status: str,
    reference: str,
    notifications_collection: Any
):
    """
    Helper function to create a notification for payment-related events
    """
    status_messages = {
        "PENDING": ("Payment Initiated", f"Your payment for order #{order_id} (Ref: {reference}) is being processed."),
        "PAID": ("Payment Successful", f"Your payment for order #{order_id} (Ref: {reference}) was successful."),
        "FAILED": ("Payment Failed", f"Your payment for order #{order_id} (Ref: {reference}) failed. Please try again.")
    }

    title, message = status_messages.get(payment_status, ("Payment Update", f"Your payment for order #{order_id} (Ref: {reference}) has an update: {payment_status}."))

    notification_data = NotificationCreate(
        user_id=user_id,
        title=title,
        message=message,
        type=NotificationType.SYSTEM,
        order_id=order_id,
        is_read=False
    )

    now = datetime.utcnow()
    notifications_collection.insert_one({
        **notification_data.dict(),
        "created_at": now,
        "updated_at": now
    })

@router.post("/paystack/initialize")
async def initialize_payment(
        order_id: str,
        background_tasks: BackgroundTasks,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Initialize a Paystack payment for an order
    """
    orders_collection = get_orders_collection()
    payments_collection = get_payments_collection()
    notifications_collection = get_notifications_collection()

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

    # Check if order is already paid
    if order.get("payment_status") == "PAID":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order is already paid"
        )

    # Generate unique reference
    reference = f"order_{order_id}_{secrets.token_hex(4)}"

    # Initialize Paystack payment
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.paystack.co/transaction/initialize",
            json={
                "email": current_user.email,
                "amount": int(order["total_amount"] * 100),  # Amount in kobo
                "reference": reference,
                "callback_url": f"https://amberfoods.onrender.com/api/payments/paystack/callback",
                "metadata": {
                    "order_id": order_id,
                    "user_id": current_user.id
                }
            },
            headers={
                "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json"
            }
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize payment"
        )

    data = response.json()

    if not data["status"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=data["message"]
        )

    # Create payment record
    now = datetime.utcnow()
    payment_data = {
        "order_id": order_id,
        "user_id": current_user.id,
        "amount": order["total_amount"],
        "reference": reference,
        "provider": "PAYSTACK",
        "status": "PENDING",
        "authorization_url": data["data"]["authorization_url"],
        "created_at": now,
        "updated_at": now
    }

    payments_collection.insert_one(payment_data)

    # Update order with payment reference
    orders_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {
            "payment_reference": reference,
            "payment_status": "PENDING",
            "updated_at": now
        }}
    )

    # Create notification for payment initialization
    background_tasks.add_task(
        create_payment_notification,
        user_id=current_user.id,
        order_id=order_id,
        payment_status="PENDING",
        reference=reference,
        notifications_collection=notifications_collection
    )

    return {
        "success": True,
        "authorization_url": data["data"]["authorization_url"],
        "reference": reference
    }

@router.get("/paystack/verify/{reference}")
async def verify_payment(
        reference: str,
        background_tasks: BackgroundTasks,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Verify a Paystack payment
    """
    payments_collection = get_payments_collection()
    orders_collection = get_orders_collection()
    notifications_collection = get_notifications_collection()

    # Check if payment exists
    payment = payments_collection.find_one({
        "reference": reference,
        "user_id": current_user.id
    })

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )

    # Verify with Paystack
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={
                "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
            }
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify payment"
        )

    data = response.json()

    if not data["status"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=data["message"]
        )

    # Update payment status
    now = datetime.utcnow()
    payment_status = "PAID" if data["data"]["status"] == "success" else "FAILED"

    payments_collection.update_one(
        {"reference": reference},
        {"$set": {
            "status": payment_status,
            "transaction_data": data["data"],
            "updated_at": now
        }}
    )

    # Update order status
    orders_collection.update_one(
        {"payment_reference": reference},
        {"$set": {
            "payment_status": payment_status,
            "updated_at": now
        }}
    )

    # Create notification for payment verification
    background_tasks.add_task(
        create_payment_notification,
        user_id=current_user.id,
        order_id=payment["order_id"],
        payment_status=payment_status,
        reference=reference,
        notifications_collection=notifications_collection
    )

    return {
        "success": True,
        "status": payment_status,
        "data": data["data"]
    }

@router.get("/paystack/callback")
async def paystack_callback(
    request: Request,
    background_tasks: BackgroundTasks
) -> Any:
    """
    Handle Paystack callback
    """
    params = dict(request.query_params)
    reference = params.get("reference")

    if not reference:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No reference provided"
        )

    # Verify payment
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={
                "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
            }
        )

    if response.status_code != 200:
        return {"success": False, "message": "Failed to verify payment"}

    data = response.json()

    if not data["status"]:
        return {"success": False, "message": data["message"]}

    # Update payment and order status
    payments_collection = get_payments_collection()
    orders_collection = get_orders_collection()
    notifications_collection = get_notifications_collection()

    now = datetime.utcnow()
    payment_status = "PAID" if data["data"]["status"] == "success" else "FAILED"

    payments_collection.update_one(
        {"reference": reference},
        {"$set": {
            "status": payment_status,
            "transaction_data": data["data"],
            "updated_at": now
        }}
    )

    # Update order status
    orders_collection.update_one(
        {"payment_reference": reference},
        {"$set": {
            "payment_status": payment_status,
            "updated_at": now
        }}
    )

    # Create notification for payment callback
    payment = payments_collection.find_one({"reference": reference})
    if payment:
        background_tasks.add_task(
            create_payment_notification,
            user_id=payment["user_id"],
            order_id=payment["order_id"],
            payment_status=payment_status,
            reference=reference,
            notifications_collection=notifications_collection
        )

    # Redirect to frontend
    return {
        "success": True,
        "status": payment_status,
        "message": "Payment processed successfully"
    }