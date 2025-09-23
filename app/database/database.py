import os

import motor.motor_asyncio
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://mongodb:27017")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client["code_review_db"]
