import os
import uuid

from datetime import datetime, timedelta

from flask import (
    Blueprint,
    render_template,
    request,
    session,
    redirect,
    url_for,
    jsonify,
    current_app,
)

from database.db import (
    students_collection,
    professors_collection,
    guidance_collection,
    subjects_collection,
    subject_assignments_collection,
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)

from werkzeug.utils import secure_filename

from routes.permissions import role_required

users = Blueprint("users", __name__)

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "uploads",
    "orf_documents",
)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@users.route("/")
def home():
    return render_template("index.html")


#! Registration Form
@users.route("/submit", methods=["POST"])
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


#! Login Form
@users.route("/login", methods=["POST"])
def login():
    id_number = request.form.get("id_number", "").strip().upper()
    password = request.form.get("password", "")

    user = students_collection.find_one({"id_number": id_number})

    if not user:
        user = professors_collection.find_one({"id_number": id_number})

    if not user:
        user = guidance_collection.find_one({"id_number": id_number})

    if user and check_password_hash(user["password"], password):
        role = user.get("role")

        # Support existing accounts without a role field.
        if not role:
            if students_collection.find_one({"_id": user["_id"]}):
                role = "student"
            elif professors_collection.find_one({"_id": user["_id"]}):
                role = "professor"
            else:
                role = "guidance"

        # Check student admission status before allowing login.
        if role == "student":
            admission_status = user.get("admission_status", "Pending")

            if admission_status != "Approved":
                if admission_status == "Rejected":
                    message = "Your admission application was rejected."
                    remarks = user.get("admission_remarks", "")
                    if remarks:
                        message += f" Reason: {remarks}"
                else:
                    message = "Your account is awaiting admission approval."

                return (
                    jsonify(
                        {
                            "success": False,
                            "message": message,
                        }
                    ),
                    403,
                )

        # Create the login session.
        session["user_id"] = str(user["_id"])
        session["id_number"] = user["id_number"]
        session["role"] = role
        session["first_name"] = user.get("first_name", "")

        return jsonify(
            {
                "success": True,
                "message": "Login successful! Redirecting to overview.",
            }
        )

    return (
        jsonify(
            {
                "success": False,
                "message": "Invalid ID number or password.",
            }
        ),
        401,
    )


#! Dashboard
@users.route("/dashboard")
@role_required("professor", "guidance")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("users.home"))

    from bson import ObjectId

    user_id = ObjectId(session["user_id"])
    role = session.get("role")

    if role == "professor":
        user = professors_collection.find_one({"_id": user_id})

        assignments = list(
            subject_assignments_collection.find({"professor_id": user_id})
        )
    else:
        user = guidance_collection.find_one({"_id": user_id})

        # Guidance can access the page, but does not have
        # professor-specific assignments.
        assignments = []

    if not user:
        session.clear()
        return redirect(url_for("users.home"))

    days = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6,
    }

    now = datetime.now()
    upcoming_subjects = []

    for assignment in assignments:
        assignment["schedule"] = ", ".join(assignment.get("days", []))
        assignment["section"] = assignment.get("section_name", "")

        assignment["building"] = assignment.get("building", "")
        assignment["room_number"] = assignment.get("room_number", "")

        for day in assignment.get("days", []):
            if day not in days:
                continue

            try:
                start_time = datetime.strptime(
                    assignment.get("start_time", ""),
                    "%H:%M",
                ).time()

                end_time = datetime.strptime(
                    assignment.get("end_time", ""),
                    "%H:%M",
                ).time()

            except ValueError:
                continue

            days_until = (days[day] - now.weekday()) % 7

            next_class = datetime.combine(
                now.date() + timedelta(days=days_until),
                start_time,
            )

            class_end = datetime.combine(
                now.date() + timedelta(days=days_until),
                end_time,
            )

            if class_end <= now:
                next_class += timedelta(days=7)
                class_end += timedelta(days=7)

            upcoming_subjects.append(
                {
                    **assignment,
                    "schedule": day,
                    "next_class": next_class,
                    "class_end": class_end,
                }
            )

    upcoming_subjects.sort(key=lambda subject: subject["next_class"])

    return render_template(
        "overview_block.html",
        first_name=user.get("first_name", ""),
        page_title="Overview",
        subjects=assignments,
        upcoming_subjects=upcoming_subjects,
        now=now,
    )


@users.route("/attendance")
@role_required("professor", "guidance")
def attendance():
    if "user_id" not in session:
        return redirect(url_for("users.home"))

    return render_template("attendance_block.html")
