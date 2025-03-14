from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from core.config import settings
import logging

logger = logging.getLogger(__name__)


class MongoDB:
    client: MongoClient = None
    db: Database = None

    def connect_to_database(self):
        try:
            self.client = MongoClient(settings.MONGO_URI)
            self.db = self.client[settings.MONGO_DB]
            logger.info("Connected to MongoDB")
            return self.db
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise e

    def close_database_connection(self):
        if self.client:
            self.client.close()
            logger.info("Closed MongoDB connection")

    def get_collection(self, collection_name: str) -> Collection:
        if self.db is None:  # ✅ Corrected condition
            self.connect_to_database()
        return self.db[collection_name]


mongodb = MongoDB()


# Collections
def get_users_collection():
    return mongodb.get_collection("users")


def get_menu_categories_collection():
    return mongodb.get_collection("menu_categories")


def get_menu_items_collection():
    return mongodb.get_collection("menu_items")


def get_orders_collection():
    return mongodb.get_collection("orders")


def get_carts_collection():
    return mongodb.get_collection("carts")


def get_payments_collection():
    return mongodb.get_collection("payments")


def get_deliveries_collection():
    return mongodb.get_collection("deliveries")


def get_addresses_collection():
    return mongodb.get_collection("addresses")


def get_reviews_collection():
    return mongodb.get_collection("reviews")
