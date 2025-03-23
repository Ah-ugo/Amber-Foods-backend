from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import Any, Optional, List, Union
from bson import ObjectId
from core.database import get_menu_categories_collection, get_menu_items_collection
from schemas.menu import (
    Category, CategoryCreate, CategoryUpdate,
    MenuItem, MenuItemCreate, MenuItemUpdate, MenuItemWithCategory
)
from api.deps import get_current_user, get_current_admin_user
from services.cloudinary_service import cloudinary_service
from schemas.user import UserInDB
import json
from datetime import datetime

router = APIRouter()

def convert_empty_to_none(value: Optional[str]) -> Optional[str]:
    return None if value == "" else value


# Category endpoints
@router.get("/categories", response_model=List[Category])
async def get_categories() -> Any:
    """
    Get all menu categories
    """
    categories_collection = get_menu_categories_collection()
    categories = list(categories_collection.find())

    # Convert ObjectId to string
    for category in categories:
        category["_id"] = str(category["_id"])

    return categories


@router.get("/categories/{category_id}", response_model=Category)
async def get_category(category_id: str) -> Any:
    """
    Get a specific category
    """
    categories_collection = get_menu_categories_collection()

    try:
        category = categories_collection.find_one({"_id": ObjectId(category_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    category["_id"] = str(category["_id"])
    return category


@router.post("/categories", response_model=Category, status_code=status.HTTP_201_CREATED)
async def create_category(
        category_in: CategoryCreate,
        current_user: UserInDB = Depends(get_current_admin_user)
) -> Any:
    """
    Create a new menu category (admin only)
    """
    categories_collection = get_menu_categories_collection()

    # Check if category with same name already exists
    if categories_collection.find_one({"name": category_in.name}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this name already exists"
        )

    # Create category
    now = datetime.utcnow()
    category_data = {
        **category_in.dict(),
        "created_at": now,
        "updated_at": now
    }

    result = categories_collection.insert_one(category_data)
    category_id = result.inserted_id

    # Get created category
    created_category = categories_collection.find_one({"_id": category_id})
    created_category["_id"] = str(created_category["_id"])

    return created_category


@router.put("/categories/{category_id}", response_model=Category)
async def update_category(
        category_id: str,
        category_in: CategoryUpdate,
        current_user: UserInDB = Depends(get_current_admin_user)
) -> Any:
    """
    Update a menu category (admin only)
    """
    categories_collection = get_menu_categories_collection()

    # Check if category exists
    try:
        category = categories_collection.find_one({"_id": ObjectId(category_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    # Update category
    update_data = category_in.dict(exclude_unset=True)

    if update_data:
        # Check if name is being updated and if it already exists
        if "name" in update_data and update_data["name"] != category["name"]:
            if categories_collection.find_one({"name": update_data["name"]}):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Category with this name already exists"
                )

        # Update timestamp
        update_data["updated_at"] = datetime.utcnow()

        # Update in database
        categories_collection.update_one(
            {"_id": ObjectId(category_id)},
            {"$set": update_data}
        )

    # Get updated category
    updated_category = categories_collection.find_one({"_id": ObjectId(category_id)})
    updated_category["_id"] = str(updated_category["_id"])

    return updated_category


@router.delete("/categories/{category_id}", status_code=status.HTTP_200_OK)
async def delete_category(
        category_id: str,
        current_user: UserInDB = Depends(get_current_admin_user)
) -> Any:
    """
    Delete a menu category (admin only)
    """
    categories_collection = get_menu_categories_collection()
    items_collection = get_menu_items_collection()

    # Check if category exists
    try:
        category = categories_collection.find_one({"_id": ObjectId(category_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    # Check if there are menu items in this category
    if items_collection.find_one({"category_id": category_id}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete category with menu items. Remove or reassign items first."
        )

    # Delete category
    categories_collection.delete_one({"_id": ObjectId(category_id)})

    return None


# Menu item endpoints
@router.get("/items", response_model=List[MenuItemWithCategory])
async def get_menu_items(
        category: Optional[str] = None,
        search: Optional[str] = None,
        featured: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
) -> Any:
    """
    Get all menu items with optional filtering
    """
    items_collection = get_menu_items_collection()
    categories_collection = get_menu_categories_collection()

    # Build filter
    filter_query = {}

    if category:
        filter_query["category_id"] = category

    if search:
        filter_query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]

    if featured is not None:
        filter_query["is_featured"] = featured

    # Get items
    items = list(items_collection.find(filter_query).skip(skip).limit(limit))

    # Convert ObjectId to string and add category info
    result = []
    for item in items:
        item["_id"] = str(item["_id"])

        # Get category
        category = categories_collection.find_one({"_id": ObjectId(item["category_id"])})
        if category:
            category["_id"] = str(category["_id"])
            item["category"] = category

        result.append(item)

    return result


@router.get("/items/{item_id}", response_model=MenuItemWithCategory)
async def get_menu_item(item_id: str) -> Any:
    """
    Get a specific menu item
    """
    items_collection = get_menu_items_collection()
    categories_collection = get_menu_categories_collection()

    try:
        item = items_collection.find_one({"_id": ObjectId(item_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    # Convert ObjectId to string
    item["_id"] = str(item["_id"])

    # Get category
    category = categories_collection.find_one({"_id": ObjectId(item["category_id"])})
    if category:
        category["_id"] = str(category["_id"])
        item["category"] = category

    return item


@router.get("/best-selling", response_model=List[MenuItemWithCategory])
async def get_best_selling_items(limit: int = 10) -> Any:
    """
    Get best-selling menu items
    """
    items_collection = get_menu_items_collection()
    categories_collection = get_menu_categories_collection()

    # This would typically involve aggregation with order data
    # For simplicity, we'll just return featured items for now
    items = list(items_collection.find({"is_featured": True}).limit(limit))

    # Convert ObjectId to string and add category info
    result = []
    for item in items:
        item["_id"] = str(item["_id"])

        # Get category
        category = categories_collection.find_one({"_id": ObjectId(item["category_id"])})
        if category:
            category["_id"] = str(category["_id"])
            item["category"] = category

        result.append(item)

    return result


@router.get("/recommended", response_model=List[MenuItemWithCategory])
async def get_recommended_items(limit: int = 10) -> Any:
    """
    Get recommended menu items
    """
    # In a real app, this would use user preferences or ML
    # For now, just return featured items
    return await get_best_selling_items(limit)


@router.get("/refreshing-drinks", response_model=List[MenuItemWithCategory])
async def get_refreshing_drinks(limit: int = 10) -> Any:
    """
    Get refreshing drinks category items
    """
    items_collection = get_menu_items_collection()
    categories_collection = get_menu_categories_collection()

    # Find drinks category
    drinks_category = categories_collection.find_one({"name": {"$regex": "drink", "$options": "i"}})

    if not drinks_category:
        # Return empty list if no drinks category
        return []

    # Get items in drinks category
    items = list(items_collection.find({"category_id": str(drinks_category["_id"])}).limit(limit))

    # Convert ObjectId to string and add category info
    result = []
    for item in items:
        item["_id"] = str(item["_id"])

        # Add category
        drinks_category["_id"] = str(drinks_category["_id"])
        item["category"] = drinks_category

        result.append(item)

    return result


@router.post("/items", response_model=MenuItem, status_code=status.HTTP_201_CREATED)
async def create_menu_item(
        name: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        price: Optional[float] = Form(None),
        category_id: Optional[str] = Form(None),
        is_available: Optional[bool] = Form(None),
        is_featured: Optional[bool] = Form(None),
        images: List[UploadFile] = File(None),
        current_user: UserInDB = Depends(get_current_admin_user)
) -> Any:
    """
    Create a new menu item with images (admin only)
    """
    items_collection = get_menu_items_collection()
    categories_collection = get_menu_categories_collection()

    # Validate category if category_id is provided
    category = None
    if category_id:
        try:
            category = categories_collection.find_one({"_id": ObjectId(category_id)})
        except:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )

    # Prepare item data
    now = datetime.utcnow()
    item_data = {
        "name": name,
        "description": description,
        "price": price,
        "category_id": category_id,
        "is_available": is_available,
        "is_featured": is_featured,
        "images": [],
        "created_at": now,
        "updated_at": now
    }

    # Remove keys that have None values
    item_data = {k: v for k, v in item_data.items() if v is not None}

    # Insert item into database
    result = items_collection.insert_one(item_data)
    item_id = result.inserted_id

    # Upload images if provided
    uploaded_images = []
    if images:
        for i, image in enumerate(images):
            if image.filename:  # Ensure it's not an empty file
                file_content = await image.read()

                # Upload to Cloudinary
                upload_result = await cloudinary_service.upload_image(
                    file_data=file_content,
                    folder="menu_items",
                    public_id=f"item_{item_id}_{i}"
                )

                uploaded_images.append({
                    "public_id": upload_result["public_id"],
                    "url": upload_result["url"],
                    "width": upload_result["width"],
                    "height": upload_result["height"]
                })

    # Update item with images
    if uploaded_images:
        items_collection.update_one(
            {"_id": item_id},
            {"$set": {"images": uploaded_images}}
        )

    # Get created item
    created_item = items_collection.find_one({"_id": item_id})
    created_item["_id"] = str(created_item["_id"])

    return created_item


from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body
from typing import Any, Optional, List, Union
import json

# ... other imports ...

@router.put("/items/{item_id}", response_model=MenuItem)
async def update_menu_item(
        item_id: str,
        name: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        price: Optional[str] = Form(None),
        category_id: Optional[str] = Form(None),
        is_available: Optional[bool] = Form(None),
        is_featured: Optional[bool] = Form(None),
        images: Optional[str] = Form(None),
        # Use Form instead of File for image_files to handle empty strings
        image_files: Optional[str] = Form(None),
        current_user: UserInDB = Depends(get_current_admin_user),
):
    """
    Update an existing menu item (all fields optional).
    Convert empty strings to None.
    """
    items_collection = get_menu_items_collection()
    categories_collection = get_menu_categories_collection()

    # Convert empty strings to None
    name = convert_empty_to_none(name)
    description = convert_empty_to_none(description)
    price = convert_empty_to_none(price)
    category_id = convert_empty_to_none(category_id)
    images_str = convert_empty_to_none(images)

    # Initialize update data
    update_data = {}

    # Handle existing images parameter
    if images_str is not None:
        try:
            # Try to parse as JSON if it's a string representation of a list
            images_data = json.loads(images_str)
            update_data["images"] = images_data
        except json.JSONDecodeError:
            # If it's not valid JSON, it might be a single image or empty
            if images_str == "":
                update_data["images"] = []
            else:
                update_data["images"] = [images_str]

    if name is not None:
        update_data["name"] = name
    if description is not None:
        update_data["description"] = description
    if price is not None:
        try:
            update_data["price"] = float(price)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid price format")
    if category_id is not None:
        try:
            category = categories_collection.find_one({"_id": ObjectId(category_id)})
            if not category:
                raise HTTPException(status_code=404, detail="Category not found")
            update_data["category_id"] = category_id
        except:
            raise HTTPException(status_code=400, detail="Invalid category ID format")

    # Handle boolean values
    if is_available is not None:
        update_data["is_available"] = is_available
    if is_featured is not None:
        update_data["is_featured"] = is_featured

    # Only update if there's data to update
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        items_collection.update_one({"_id": ObjectId(item_id)}, {"$set": update_data})

    # Fetch updated item
    try:
        updated_item = items_collection.find_one({"_id": ObjectId(item_id)})
        if not updated_item:
            raise HTTPException(status_code=404, detail="Menu item not found")
    except:
        raise HTTPException(status_code=404, detail="Menu item not found")

    updated_item["_id"] = str(updated_item["_id"])

    return updated_item


@router.post("/items/{item_id}/upload-images", response_model=MenuItem)
async def upload_menu_item_images(
        item_id: str,
        image_files: List[UploadFile] = File(...),  # Required here, but endpoint itself is optional to use
        current_user: UserInDB = Depends(get_current_admin_user),
):
    """
    Upload images for an existing menu item
    """
    items_collection = get_menu_items_collection()

    # Find existing item
    try:
        existing_item = items_collection.find_one({"_id": ObjectId(item_id)})
        if not existing_item:
            raise HTTPException(status_code=404, detail="Menu item not found")
    except:
        raise HTTPException(status_code=404, detail="Menu item not found")

    # Handle image uploads
    uploaded_images = []
    for i, image in enumerate(image_files):
        if image.filename:  # Ensure it's not an empty file
            file_content = await image.read()

            # Upload to Cloudinary
            upload_result = await cloudinary_service.upload_image(
                file_data=file_content,
                folder="menu_items",
                public_id=f"item_{item_id}_{i}"
            )

            uploaded_images.append({
                "public_id": upload_result["public_id"],
                "url": upload_result["url"],
                "width": upload_result["width"],
                "height": upload_result["height"]
            })

    # Update item with new images
    if uploaded_images:
        # Get existing images
        existing_images = existing_item.get("images", [])
        # Append new images
        all_images = existing_images + uploaded_images

        # Update in database
        items_collection.update_one(
            {"_id": ObjectId(item_id)},
            {"$set": {"images": all_images, "updated_at": datetime.utcnow()}}
        )

    # Get updated item
    updated_item = items_collection.find_one({"_id": ObjectId(item_id)})
    updated_item["_id"] = str(updated_item["_id"])

    return updated_item


@router.delete("/items/{item_id}", response_model=dict, status_code=status.HTTP_200_OK)
async def delete_menu_item(
        item_id: str,
        current_user: UserInDB = Depends(get_current_admin_user)
) -> Any:
    """
    Delete a menu item (admin only)
    """
    items_collection = get_menu_items_collection()

    # Find existing item
    existing_item = items_collection.find_one({"_id": ObjectId(item_id)})
    if not existing_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    # Delete associated images from Cloudinary
    if "images" in existing_item and existing_item["images"]:
        for image in existing_item["images"]:
            public_id = image["public_id"]
            await cloudinary_service.delete_image(public_id)

    # Delete item from the database
    items_collection.delete_one({"_id": ObjectId(item_id)})

    return {"message": "Menu item deleted successfully"}
