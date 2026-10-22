    from flask import Flask, request, jsonify
from flask_cors import CORS
from collections import deque

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

client = MongoClient("mongodb+srv://felipejrnoriel_db_user:aqwkTLilxErXraRO@fp-db.8nhcswv.mongodb.net/")
db = client[""]
attendance_records.create_index(
    [("student_id", 1), ("session_id", 1)],
    unique=True
query = {"student_id": student_id, "session_id": SESSION_ID}
)
query = {"student_id": student_id, "session_id": SESSION_ID}

attendance_queue = deque()
SESSION_ID = ""

#session ID

@app.route("/api/attendance", methods=["POST"])
def record_attendance():
    data = request.get_json(silent=True) or {}

    student_id = data.get("student_id", "").strip()
    name = data.get("name", "").strip()

 if not student_id or not name:
        return jsonify({
            "success": False,
            "message": "Provid Student ID or name"
        }), 400


#statement operation
while attendance_queue:
    student = attendance_queue.popleft()

try:
    attendance_records.insert_one(student)

            return jsonify({
                "success": True,
                "message": f"Attendance recorded: {student['name']}!",
                "student_id": student["student_id"]
            }), 201
    #di pa tapos need pa ng return except return blocks
