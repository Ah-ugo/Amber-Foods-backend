from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any
from bson import ObjectId
from core.database import get_carts_collection, get_menu_items_collection
from schemas.cart import Cart, CartItemCreate, CartItemUpdate
from api.deps import get_current_user
from schemas.user import UserInDB
from datetime import datetime

router = APIRouter()


@router.get("/", response_model=Cart)
async def get_user_cart(
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Get user's cart
    """
    carts_collection = get_carts_collection()

    # Get user's cart
    cart = carts_collection.find_one({"user_id": current_user.id})

    # If cart doesn't exist, create a new one
    if not cart:
        now = datetime.utcnow()
        cart_data = {
            "user_id": current_user.id,
            "items": [],
            "total": 0,
            "created_at": now,
            "updated_at": now
        }

        result = carts_collection.insert_one(cart_data)
        cart = carts_collection.find_one({"_id": result.inserted_id})

    # Convert ObjectId to string
    cart["_id"] = str(cart["_id"])

    # Calculate total
    total = 0
    for item in cart["items"]:
        total += item.get("subtotal", 0)

    cart["total"] = total

    return cart


@router.post("/items", response_model=Cart)
async def add_item_to_cart(
        item_in: CartItemCreate,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Add item to cart
    """
    carts_collection = get_carts_collection()
    menu_items_collection = get_menu_items_collection()

    # Check if menu item exists
    try:
        menu_item = menu_items_collection.find_one({"_id": ObjectId(item_in.menu_item_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    if not menu_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    # Check if item is available
    if not menu_item.get("is_available", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Menu item is not available"
        )

    # Get user's cart
    cart = carts_collection.find_one({"user_id": current_user.id})
    now = datetime.utcnow()

    # If cart doesn't exist, create a new one
    if not cart:
        cart_data = {
            "user_id": current_user.id,
            "items": [],
            "total": 0,
            "created_at": now,
            "updated_at": now
        }

        result = carts_collection.insert_one(cart_data)
        cart = carts_collection.find_one({"_id": result.inserted_id})

    # Check if item already exists in cart
    existing_item = None
    for item in cart["items"]:
        if item["menu_item_id"] == item_in.menu_item_id:
            existing_item = item
            break

    # Calculate subtotal
    item_price = menu_item["price"]
    item_subtotal = item_price * item_in.quantity

    # Get image URL if available
    image_url = None
    if menu_item.get("images") and len(menu_item["images"]) > 0:
        image_url = menu_item["images"][0].get("url")

    if existing_item:
        # Update existing item
        carts_collection.update_one(
            {
                "user_id": current_user.id,
                "items._id": existing_item["_id"]
            },
            {
                "$set": {
                    "items.$.quantity": item_in.quantity,
                    "items.$.price": item_price,
                    "items.$.subtotal": item_subtotal,
                    "updated_at": now
                }
            }
        )
    else:
        # Add new item
        new_item = {
            "_id": str(ObjectId()),
            "menu_item_id": item_in.menu_item_id,
            "name": menu_item["name"],
            "price": item_price,
            "quantity": item_in.quantity,
            "subtotal": item_subtotal,
            "image_url": image_url
        }

        carts_collection.update_one(
            {"user_id": current_user.id},
            {
                "$push": {"items": new_item},
                "$set": {"updated_at": now}
            }
        )

    # Get updated cart
    updated_cart = carts_collection.find_one({"user_id": current_user.id})
    updated_cart["_id"] = str(updated_cart["_id"])

    # Calculate total
    total = 0
    for item in updated_cart["items"]:
        total += item.get("subtotal", 0)

    updated_cart["total"] = total

    # Update total in database
    carts_collection.update_one(
        {"user_id": current_user.id},
        {"$set": {"total": total}}
    )

    return updated_cart


@router.put("/items/{item_id}", response_model=Cart)
async def update_cart_item(
        item_id: str,
        item_in: CartItemUpdate,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Update cart item
    """
    carts_collection = get_carts_collection()

    # Get user's cart
    cart = carts_collection.find_one({"user_id": current_user.id})

    if not cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found"
        )

    # Find item in cart
    item_to_update = None
    for item in cart["items"]:
        if item["_id"] == item_id:
            item_to_update = item
            break

    if not item_to_update:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found in cart"
        )

    # Calculate new subtotal
    item_price = item_to_update["price"]
    item_subtotal = item_price * item_in.quantity

    # Update item
    now = datetime.utcnow()
    carts_collection.update_one(
        {
            "user_id": current_user.id,
            "items._id": item_id
        },
        {
            "$set": {
                "items.$.quantity": item_in.quantity,
                "items.$.subtotal": item_subtotal,
                "updated_at": now
            }
        }
    )

    # Get updated cart
    updated_cart = carts_collection.find_one({"user_id": current_user.id})
    updated_cart["_id"] = str(updated_cart["_id"])

    # Calculate total
    total = 0
    for item in updated_cart["items"]:
        total += item.get("subtotal", 0)

    updated_cart["total"] = total

    # Update total in database
    carts_collection.update_one(
        {"user_id": current_user.id},
        {"$set": {"total": total}}
    )

    return updated_cart


@router.delete("/items/{item_id}", response_model=Cart)
async def remove_cart_item(
        item_id: str,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Remove item from cart
    """
    carts_collection = get_carts_collection()

    # Get user's cart
    cart = carts_collection.find_one({"user_id": current_user.id})

    if not cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found"
        )

    # Find item in cart
    item_to_remove = None
    for item in cart["items"]:
        if item["_id"] == item_id:
            item_to_remove = item
            break

    if not item_to_remove:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found in cart"
        )

    # Remove item
    now = datetime.utcnow()
    carts_collection.update_one(
        {"user_id": current_user.id},
        {
            "$pull": {"items": {"_id": item_id}},
            "$set": {"updated_at": now}
        }
    )

    # Get updated cart
    updated_cart = carts_collection.find_one({"user_id": current_user.id})
    updated_cart["_id"] = str(updated_cart["_id"])

    # Calculate total
    total = 0
    for item in updated_cart["items"]:
        total += item.get("subtotal", 0)

    updated_cart["total"] = total

    # Update total in database
    carts_collection.update_one(
        {"user_id": current_user.id},
        {"$set": {"total": total}}
    )

    return updated_cart


@router.delete("/", response_model=Cart)
async def clear_cart(
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Clear cart
    """
    carts_collection = get_carts_collection()

    # Get user's cart
    cart = carts_collection.find_one({"user_id": current_user.id})

    if not cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found"
        )

    # Clear cart
    now = datetime.utcnow()
    carts_collection.update_one(
        {"user_id": current_user.id},
        {
            "$set": {
                "items": [],
                "total": 0,
                "updated_at": now
            }
        }
    )

    # Get updated cart
    updated_cart = carts_collection.find_one({"user_id": current_user.id})
    updated_cart["_id"] = str(updated_cart["_id"])

    return updated_cart