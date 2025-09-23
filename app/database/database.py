import os
import logging

import motor.motor_asyncio
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get MongoDB URI from environment
MONGO_URI = os.getenv("MONGODB_URI")

# Log the MongoDB URI (without password for security)
if MONGO_URI:
    safe_uri = MONGO_URI.split('@')[-1] if '@' in MONGO_URI else MONGO_URI
    logger.info(f"Connecting to MongoDB: {safe_uri}")
else:
    logger.warning("MONGODB_URI not set")

# Initialize MongoDB client
try:
    if MONGO_URI:
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        db = client["code_review_db"]
        logger.info("MongoDB client initialized successfully")
    else:
        logger.error("MONGODB_URI is required but not set")
        client = None
        db = None
except Exception as e:
    logger.error(f"Failed to initialize MongoDB client: {e}")
    client = None
    db = None
