from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, List
from bson import ObjectId
from core.database import get_addresses_collection
from schemas.address import Address, AddressCreate, AddressUpdate
from api.deps import get_current_user
from schemas.user import UserInDB
from datetime import datetime

router = APIRouter()


@router.get("/", response_model=List[Address])
async def get_user_addresses(
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Get user's addresses
    """
    addresses_collection = get_addresses_collection()

    # Get user's addresses
    addresses = list(addresses_collection.find({"user_id": current_user.id}))

    # Convert ObjectId to string
    for address in addresses:
        address["_id"] = str(address["_id"])

    return addresses


@router.post("/", response_model=Address, status_code=status.HTTP_201_CREATED)
async def create_address(
        address_in: AddressCreate,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Create a new address
    """
    addresses_collection = get_addresses_collection()

    # Check if this is the first address (make it default)
    address_count = addresses_collection.count_documents({"user_id": current_user.id})
    if address_count == 0:
        address_in.is_default = True

    # If this address is set as default, unset default for other addresses
    if address_in.is_default:
        addresses_collection.update_many(
            {"user_id": current_user.id},
            {"$set": {"is_default": False}}
        )

    # Create address
    now = datetime.utcnow()
    address_data = {
        **address_in.dict(),
        "user_id": current_user.id,
        "created_at": now,
        "updated_at": now
    }

    result = addresses_collection.insert_one(address_data)
    address_id = result.inserted_id

    # Get created address
    created_address = addresses_collection.find_one({"_id": address_id})
    created_address["_id"] = str(created_address["_id"])

    return created_address


@router.get("/{address_id}", response_model=Address)
async def get_address(
        address_id: str,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Get a specific address
    """
    addresses_collection = get_addresses_collection()

    # Check if address exists and belongs to user
    try:
        address = addresses_collection.find_one({
            "_id": ObjectId(address_id),
            "user_id": current_user.id
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )

    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )

    # Convert ObjectId to string
    address["_id"] = str(address["_id"])

    return address


@router.put("/{address_id}", response_model=Address)
async def update_address(
        address_id: str,
        address_in: AddressUpdate,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Update an address
    """
    addresses_collection = get_addresses_collection()

    # Check if address exists and belongs to user
    try:
        address = addresses_collection.find_one({
            "_id": ObjectId(address_id),
            "user_id": current_user.id
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )

    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )

    # Update address
    update_data = address_in.dict(exclude_unset=True)

    if update_data:
        # If this address is set as default, unset default for other addresses
        if update_data.get("is_default"):
            addresses_collection.update_many(
                {"user_id": current_user.id, "_id": {"$ne": ObjectId(address_id)}},
                {"$set": {"is_default": False}}
            )

        # Update timestamp
        update_data["updated_at"] = datetime.utcnow()

        # Update in database
        addresses_collection.update_one(
            {"_id": ObjectId(address_id)},
            {"$set": update_data}
        )

    # Get updated address
    updated_address = addresses_collection.find_one({"_id": ObjectId(address_id)})
    updated_address["_id"] = str(updated_address["_id"])

    return updated_address


@router.delete("/{address_id}", status_code=status.HTTP_200_OK)
async def delete_address(
        address_id: str,
        current_user: UserInDB = Depends(get_current_user)
) -> Any:
    """
    Delete an address
    """
    addresses_collection = get_addresses_collection()

    # Check if address exists and belongs to user
    try:
        address = addresses_collection.find_one({
            "_id": ObjectId(address_id),
            "user_id": current_user.id
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )

    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )

    # Check if this is the default address
    if address.get("is_default", False):
        # Find another address to make default
        other_address = addresses_collection.find_one({
            "user_id": current_user.id,
            "_id": {"$ne": ObjectId(address_id)}
        })

        if other_address:
            # Make another address default
            addresses_collection.update_one(
                {"_id": other_address["_id"]},
                {"$set": {"is_default": True}}
            )

    # Delete address
    addresses_collection.delete_one({"_id": ObjectId(address_id)})

    return None