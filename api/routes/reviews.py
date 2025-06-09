from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, List, Optional
from bson import ObjectId
from core.database import get_reviews_collection, get_menu_items_collection, get_users_collection, \
    get_orders_collection
from schemas.review import Review, ReviewCreate, ReviewUpdate
from api.deps import get_current_user, get_current_admin_user
from schemas.user import UserInDB
from datetime import datetime

router = APIRouter()


@router.get("/", response_model=List[Review])
async def get_reviews(
        menu_item_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
) -> Any:
    """
    Get reviews, optionally filtered by menu item
    """
    reviews_collection = get_reviews_collection()

    # Build filter
    filter_query = {}

    if menu_item_id:
        filter_query["menu_item_id"] = menu_item_id

    # Get reviews
    reviews = list(reviews_collection.find(filter_query).sort("created_at", -1).skip(skip).limit(limit))

    # Convert ObjectId to string
    for review in reviews:
        review["_id"] = str(review["_id"])

    return reviews


@router.get("/my-reviews", response_model=List[Review])
async def get_current_user_reviews(
        current_user: UserInDB = Depends(get_current_user),
        skip: int = 0,
        limit: int = 100
) -> Any:
    """
    Get all reviews created by the current user
    """
    reviews_collection = get_reviews_collection()

    # Get reviews for current user
    reviews = list(reviews_collection.find({"user_id": current_user.id})
                   .sort("created_at", -1)
                   .skip(skip)
                   .limit(limit))

    # Convert ObjectId to string
    for review in reviews:
        review["_id"] = str(review["_id"])

    return reviews


@router.get("/items/{menu_item_id}", response_model=List[Review])
async def get_menu_item_reviews(
        menu_item_id: str,
        skip: int = 0,
        limit: int = 100
) -> Any:
    """
    Get reviews for a specific menu item
    """
    reviews_collection = get_reviews_collection()
    menu_items_collection = get_menu_items_collection()

    # Check if menu item exists
    try:
        menu_item = menu_items_collection.find_one({"_id": ObjectId(menu_item_id)})
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

    # Get reviews
    reviews = list(
        reviews_collection.find({"menu_item_id": menu_item_id}).sort("created_at", -1).skip(skip).limit(limit))

    # Convert ObjectId to string
    for review in reviews:
        review["_id"] = str(review["_id"])

    return reviews


@router.post("/", response_model=Review, status_code=status.HTTP_201_CREATED)
async def create_review(
        review_in: ReviewCreate,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Create a new review
    """
    reviews_collection = get_reviews_collection()
    menu_items_collection = get_menu_items_collection()
    orders_collection = get_orders_collection()

    # Check if menu item exists
    try:
        menu_item = menu_items_collection.find_one({"_id": ObjectId(review_in.menu_item_id)})
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

    # Check if user has ordered this item (optional validation)
    has_ordered = orders_collection.find_one({
        "user_id": current_user.id,
        "status": "DELIVERED",
        "items.menu_item_id": review_in.menu_item_id
    })

    if not has_ordered:
        # For demo purposes, we'll allow reviews without orders
        # In a real app, you might want to enforce this
        pass

    # Check if user has already reviewed this item
    existing_review = reviews_collection.find_one({
        "user_id": current_user.id,
        "menu_item_id": review_in.menu_item_id
    })

    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already reviewed this item"
        )

    # Create review
    now = datetime.utcnow()
    review_data = {
        **review_in.dict(),
        "user_id": current_user.id,
        "user_name": current_user.full_name,
        "user_image": current_user.profile_image_url,
        "created_at": now,
        "updated_at": now
    }

    result = reviews_collection.insert_one(review_data)
    review_id = result.inserted_id

    # Get created review
    created_review = reviews_collection.find_one({"_id": review_id})
    created_review["_id"] = str(created_review["_id"])

    # Update menu item rating
    # Calculate average rating
    all_reviews = list(reviews_collection.find({"menu_item_id": review_in.menu_item_id}))
    total_rating = sum(review.get("rating", 0) for review in all_reviews)
    avg_rating = total_rating / len(all_reviews) if all_reviews else 0

    # Update menu item
    menu_items_collection.update_one(
        {"_id": ObjectId(review_in.menu_item_id)},
        {
            "$set": {
                "avg_rating": avg_rating,
                "review_count": len(all_reviews)
            }
        }
    )

    return created_review


@router.put("/{review_id}", response_model=Review)
async def update_review(
        review_id: str,
        review_in: ReviewUpdate,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Update a review
    """
    reviews_collection = get_reviews_collection()
    menu_items_collection = get_menu_items_collection()

    # Check if review exists and belongs to user
    try:
        review = reviews_collection.find_one({
            "_id": ObjectId(review_id),
            "user_id": current_user.id
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    # Update review
    update_data = review_in.dict(exclude_unset=True)

    if update_data:
        # Update timestamp
        update_data["updated_at"] = datetime.utcnow()

        # Update in database
        reviews_collection.update_one(
            {"_id": ObjectId(review_id)},
            {"$set": update_data}
        )

        # If rating was updated, recalculate menu item average rating
        if "rating" in update_data:
            menu_item_id = review["menu_item_id"]

            # Calculate average rating
            all_reviews = list(reviews_collection.find({"menu_item_id": menu_item_id}))
            total_rating = sum(review.get("rating", 0) for review in all_reviews)
            avg_rating = total_rating / len(all_reviews) if all_reviews else 0

            # Update menu item
            menu_items_collection.update_one(
                {"_id": ObjectId(menu_item_id)},
                {"$set": {"avg_rating": avg_rating}}
            )

    # Get updated review
    updated_review = reviews_collection.find_one({"_id": ObjectId(review_id)})
    updated_review["_id"] = str(updated_review["_id"])

    return updated_review


@router.delete("/{review_id}", status_code=status.HTTP_200_OK)
async def delete_review(
        review_id: str,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Delete a review
    """
    reviews_collection = get_reviews_collection()
    menu_items_collection = get_menu_items_collection()

    # Check if review exists and belongs to user (or user is admin)
    try:
        if current_user.is_admin:
            review = reviews_collection.find_one({"_id": ObjectId(review_id)})
        else:
            review = reviews_collection.find_one({
                "_id": ObjectId(review_id),
                "user_id": current_user.id
            })
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    # Store menu item ID for recalculating average
    menu_item_id = review["menu_item_id"]

    # Delete review
    reviews_collection.delete_one({"_id": ObjectId(review_id)})

    # Recalculate menu item average rating
    all_reviews = list(reviews_collection.find({"menu_item_id": menu_item_id}))

    if all_reviews:
        total_rating = sum(review.get("rating", 0) for review in all_reviews)
        avg_rating = total_rating / len(all_reviews)

        # Update menu item
        menu_items_collection.update_one(
            {"_id": ObjectId(menu_item_id)},
            {
                "$set": {
                    "avg_rating": avg_rating,
                    "review_count": len(all_reviews)
                }
            }
        )
    else:
        # No reviews left, reset rating
        menu_items_collection.update_one(
            {"_id": ObjectId(menu_item_id)},
            {
                "$set": {
                    "avg_rating": 0,
                    "review_count": 0
                }
            }
        )

    return None