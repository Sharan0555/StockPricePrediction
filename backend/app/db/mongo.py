from pymongo import MongoClient

from app.core.config import settings


mongo_client = MongoClient(
    settings.MONGO_DSN,
    serverSelectionTimeoutMS=1000,
    connectTimeoutMS=1000,
    socketTimeoutMS=1000,
)
mongo_db = mongo_client.get_default_database()
