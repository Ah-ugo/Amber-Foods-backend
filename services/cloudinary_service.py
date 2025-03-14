import cloudinary
import cloudinary.uploader
from core.config import settings
import logging
from typing import Optional, Dict, Any
import base64

logger = logging.getLogger(__name__)

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)


class CloudinaryService:
    @staticmethod
    async def upload_image(file_data: bytes, folder: str, public_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload an image to Cloudinary

        Args:
            file_data: The image file data
            folder: The folder to upload to
            public_id: Optional public ID for the image

        Returns:
            Dict containing the upload result
        """
        try:
            # Convert bytes to base64
            base64_data = base64.b64encode(file_data).decode("utf-8")

            # Upload to Cloudinary
            upload_result = cloudinary.uploader.upload(
                f"data:image/png;base64,{base64_data}",
                folder=folder,
                public_id=public_id,
                overwrite=True,
                resource_type="image"
            )

            return {
                "public_id": upload_result["public_id"],
                "url": upload_result["secure_url"],
                "format": upload_result["format"],
                "width": upload_result["width"],
                "height": upload_result["height"]
            }
        except Exception as e:
            logger.error(f"Error uploading image to Cloudinary: {e}")
            raise e

    @staticmethod
    async def delete_image(public_id: str) -> bool:
        """
        Delete an image from Cloudinary

        Args:
            public_id: The public ID of the image to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            result = cloudinary.uploader.destroy(public_id)
            return result.get("result") == "ok"
        except Exception as e:
            logger.error(f"Error deleting image from Cloudinary: {e}")
            return False

    @staticmethod
    def get_image_url(public_id: str, transformation: Optional[Dict[str, Any]] = None) -> str:
        """
        Get the URL for an image with optional transformations

        Args:
            public_id: The public ID of the image
            transformation: Optional transformations to apply

        Returns:
            The image URL
        """
        try:
            return cloudinary.CloudinaryImage(public_id).build_url(
                secure=True,
                transformation=transformation
            )
        except Exception as e:
            logger.error(f"Error generating image URL: {e}")
            raise e


cloudinary_service = CloudinaryService()