from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import Any, Dict
from core.config import settings
from core.database import get_payments_collection, get_orders_collection
from api.deps import get_current_user
from schemas.user import UserInDB
import httpx
from bson import ObjectId
from datetime import datetime
import secrets

router = APIRouter()


@router.post("/paystack/initialize")
async def initialize_payment(
        order_id: str,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Initialize a Paystack payment for an order
    """
    orders_collection = get_orders_collection()
    payments_collection = get_payments_collection()

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
                "amount": int(order["total_amount"] * 100),  # Amount in kobo (smallest currency unit)
                "reference": reference,
                "callback_url": f"{settings.BASE_URL}/api/payments/paystack/callback",
                "metadata": {
                    "order_id": order_id,
                    "user_id": current_user.id
                }
            },
            headers={
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
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

    return {
        "success": True,
        "authorization_url": data["data"]["authorization_url"],
        "reference": reference
    }


@router.get("/paystack/verify/{reference}")
async def verify_payment(
        reference: str,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Verify a Paystack payment
    """
    payments_collection = get_payments_collection()
    orders_collection = get_orders_collection()

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
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
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

    return {
        "success": True,
        "status": payment_status,
        "data": data["data"]
    }


@router.get("/paystack/callback")
async def paystack_callback(request: Request) -> Any:
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
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
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

    # Redirect to frontend
    return {
        "success": True,
        "status": payment_status,
        "message": "Payment processed successfully"
    }