import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError("Please set MONGO_URI first. (from README.txt)")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

db = client["users_data"]

students_collection = db["students"]
professors_collection = db["professors"]
guidance_collection = db["guidance"]

programs_collection = db["programs"]
sections_collection = db["sections"]
subjects_collection = db["subjects"]

subject_assignments_collection = db["subject_assignments"]

attendance_records_collection = db["attendance_records"]
class_sessions_collection = db["class_sessions"]
