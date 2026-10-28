import os
import uuid

from flask import Blueprint, request, jsonify, current_app
from database.db import (
    students_collection,
    professors_collection,
)
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

registration = Blueprint("registration", __name__)

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "uploads",
    "orf_documents",
)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


#! Registration Form
@registration.route("/submit", methods=["POST"])
def submit():
    first_name = request.form.get("first_name", "").strip().upper()
    last_name = request.form.get("last_name", "").strip().upper()
    id_number = request.form.get("id_number", "").strip().upper()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    program = request.form.get("program", "").strip()
    year_level = request.form.get("year_level", "").strip()
    trimester = request.form.get("trimester", "").strip()
    section = request.form.get("section", "").strip()

    # Check required fields
    if not all(
        [
            first_name,
            last_name,
            id_number,
            email,
            password,
            program,
            year_level,
            trimester,
            section,
        ]
    ):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please complete all required fields.",
                }
            ),
            400,
        )

    # Check for existing accounts
    existing_student = students_collection.find_one(
        {"$or": [{"id_number": id_number}, {"email": email}]}
    )

    existing_professor = professors_collection.find_one(
        {"$or": [{"id_number": id_number}, {"email": email}]}
    )

    if existing_student or existing_professor:
        if (existing_student and existing_student.get("id_number") == id_number) or (
            existing_professor and existing_professor.get("id_number") == id_number
        ):
            message = "ID number is already registered."
        else:
            message = "Email is already registered."

        return (
            jsonify(
                {
                    "success": False,
                    "message": message,
                }
            ),
            409,
        )

    # Get the uploaded ORF
    orf_file = request.files.get("latest_orf")

    if not orf_file or not orf_file.filename:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please upload your Latest ORF PDF.",
                }
            ),
            400,
        )

    # Check the file extension
    if not orf_file.filename.lower().endswith(".pdf"):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Only PDF files are allowed.",
                }
            ),
            400,
        )

    # Check the file size
    orf_file.stream.seek(0, os.SEEK_END)
    file_size = orf_file.stream.tell()
    orf_file.stream.seek(0)

    if file_size > MAX_FILE_SIZE:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "The PDF must not exceed 5 MB.",
                }
            ),
            400,
        )

    # Check the PDF file signature
    if orf_file.stream.read(5) != b"%PDF-":
        return (
            jsonify(
                {
                    "success": False,
                    "message": "The uploaded file is not a valid PDF.",
                }
            ),
            400,
        )

    orf_file.stream.seek(0)

    # Create the upload folder if it doesn't exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Generate a unique filename
    generated_filename = f"{uuid.uuid4().hex}.pdf"
    file_path = os.path.join(UPLOAD_FOLDER, generated_filename)

    # Save the PDF
    orf_file.save(file_path)

    # Create the student record
    user = {
        "first_name": first_name,
        "last_name": last_name,
        "id_number": id_number,
        "email": email,
        "password": generate_password_hash(password),
        "program": program,
        "year_level": year_level,
        "trimester": trimester,
        "section": section,
        "role": "student",
        # Admission details
        "admission_status": "Pending",
        "admission_remarks": "",
        "reviewed_by": None,
        "reviewed_at": None,
        # ORF document reference
        "latest_orf": {
            "filename": generated_filename,
            "original_filename": secure_filename(orf_file.filename),
        },
    }

    try:
        students_collection.insert_one(user)

    except Exception:
        # Remove the uploaded file if saving the database record fails
        if os.path.exists(file_path):
            os.remove(file_path)

        current_app.logger.exception("Failed to save student registration.")

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Registration failed. Please try again.",
                }
            ),
            500,
        )

    return jsonify(
        {
            "success": True,
            "message": "Registration successful! Your admission is pending review.",
        }
    )
