import os
import uuid
from flask import (
    Blueprint,
    render_template,
    request,
    session,
    redirect,
    url_for,
    jsonify,
    current_app,
    abort,
    send_from_directory,
)
from database.db import (
    students_collection,
    professors_collection,
    guidance_collection,
    programs_collection,
    sections_collection,
    subjects_collection,
)
from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

users = Blueprint("users", __name__)

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "uploads",
    "orf_documents",
)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


#! Routes Section


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
        result = students_collection.insert_one(user)
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

    return jsonify({"success": False, "message": "Invalid ID number or password."}), 401


#! Dashboard
@users.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("users.home"))

    from bson import ObjectId

    user_id = ObjectId(session["user_id"])

    if session.get("role") == "student":
        user = students_collection.find_one({"_id": user_id})
    elif session.get("role") == "professor":
        user = professors_collection.find_one({"_id": user_id})
    else:
        user = guidance_collection.find_one({"_id": user_id})

    subjects = list(subjects_collection.find())

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

    def get_next_class(subject):
        subject_day = days.get(subject.get("schedule"))

        if subject_day is None:
            return datetime.max

        try:
            subject_time = datetime.strptime(subject.get("time", ""), "%H:%M").time()
        except ValueError:
            return datetime.max

        days_until = (subject_day - now.weekday()) % 7

        next_class = datetime.combine(
            now.date() + timedelta(days=days_until), subject_time
        )

        if next_class <= now:
            next_class += timedelta(days=7)

        return next_class

    upcoming_subjects = sorted(subjects, key=get_next_class)

    return render_template(
        "overview_block.html",
        first_name=user["first_name"],
        page_title="Overview",
        subjects=subjects,
        upcoming_subjects=upcoming_subjects,
        now=now,
    )


#! Programs Manager
@users.route("/program_manager")
def program_manager():
    if "user_id" not in session:
        return redirect(url_for("users.home"))

    programs = list(programs_collection.find({}, {"_id": 0}))

    return render_template(
        "program_manager_block.html",
        page_title="Program Manager",
        programs=programs,
    )


@users.route("/register_program", methods=["POST"])
def register_program():
    program_code = request.form.get("program_code", "").strip().upper()
    program_name = request.form.get("program_name", "").strip()
    year_levels = request.form.get("year_levels", "")

    if not program_code or not program_name or not year_levels:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please complete all program fields.",
                }
            ),
            400,
        )

    try:
        year_levels = int(year_levels)
    except ValueError:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid number of year levels.",
                }
            ),
            400,
        )

    if year_levels not in range(1, 5):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Year levels must be between 1 and 4.",
                }
            ),
            400,
        )

    if programs_collection.find_one({"program_code": program_code}):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This program code is already registered.",
                }
            ),
            409,
        )

    programs_collection.insert_one(
        {
            "program_code": program_code,
            "program_name": program_name,
            "year_levels": year_levels,
        }
    )

    return jsonify(
        {
            "success": True,
            "message": "Program registered successfully.",
        }
    )


#! Pass programs
@users.route("/get_programs")
def get_programs():
    programs = list(
        programs_collection.find(
            {},
            {"_id": 0, "program_code": 1, "program_name": 1, "year_levels": 1},
        )
    )

    return jsonify({"programs": programs})


#! Register sections
@users.route("/register_section", methods=["POST"])
def register_section():
    if "user_id" not in session:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please log in first.",
                }
            ),
            401,
        )

    program_code = request.form.get("program", "").strip().upper()
    learning_modality = request.form.get("learning_modality", "").strip().upper()
    campus = request.form.get("campus", "").strip().upper()
    year_level = request.form.get("year_level", "").strip()
    current_trimester = request.form.get("current_trimester", "").strip()
    trimester_period = request.form.get("trimester_period", "").strip()
    section_session = request.form.get("session", "").strip().upper()
    section_number = request.form.get("section_number", "").strip()
    section_name = request.form.get("section_name", "").strip().upper()

    if not all(
        [
            program_code,
            learning_modality,
            campus,
            year_level,
            current_trimester,
            trimester_period,
            section_session,
            section_number,
            section_name,
        ]
    ):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please complete all section fields.",
                }
            ),
            400,
        )

    program = programs_collection.find_one({"program_code": program_code})

    if not program:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "The selected program does not exist.",
                }
            ),
            400,
        )

    try:
        year_level = int(year_level)
        current_trimester = int(current_trimester)
        trimester_period = int(trimester_period)
        section_number = int(section_number)
    except ValueError:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid section details.",
                }
            ),
            400,
        )

    if not 1 <= year_level <= program["year_levels"]:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid year level for the selected program.",
                }
            ),
            400,
        )

    if current_trimester not in range(1, 4) or trimester_period not in range(1, 4):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Trimester values must be between 1 and 3.",
                }
            ),
            400,
        )

    if section_number < 1 or section_number > 999:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Section number must be between 1 and 999.",
                }
            ),
            400,
        )

    if sections_collection.find_one({"section_name": section_name}):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This section is already registered.",
                }
            ),
            409,
        )

    sections_collection.insert_one(
        {
            "program_code": program_code,
            "learning_modality": learning_modality,
            "campus": campus,
            "year_level": year_level,
            "current_trimester": current_trimester,
            "trimester_period": trimester_period,
            "session": section_session,
            "section_number": section_number,
            "section_name": section_name,
        }
    )

    return jsonify(
        {
            "success": True,
            "message": "Section registered successfully.",
        }
    )


@users.route("/get_sections")
def get_sections():
    sections = list(
        sections_collection.find(
            {},
            {"_id": 0},
        )
    )

    return jsonify({"sections": sections})


#! Register Subjects
@users.route("/register_subject", methods=["POST"])
def register_subject():
    if "user_id" not in session:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please log in first.",
                }
            ),
            401,
        )

    subject_code = request.form.get("subject_code", "").strip().upper()
    subject_name = request.form.get("subject_name", "").strip()
    schedule = request.form.get("schedule", "").strip()
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    building = request.form.get("building", "").strip().upper()
    room_number = request.form.get("room_number", "").strip()
    section_name = request.form.get("section", "").strip().upper()

    if not all(
        [
            subject_code,
            subject_name,
            schedule,
            start_time,
            end_time,
            building,
            room_number,
            section_name,
        ]
    ):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please complete all subject fields.",
                }
            ),
            400,
        )

    if building not in ["B1", "B2", "B3", "B4"]:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid building selection.",
                }
            ),
            400,
        )

    if not room_number.isdigit() or int(room_number) < 1:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Room number must be a positive number.",
                }
            ),
            400,
        )

    if start_time >= end_time:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "End time must be later than start time.",
                }
            ),
            400,
        )

    section = sections_collection.find_one({"section_name": section_name})

    if not section:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "The selected section does not exist.",
                }
            ),
            400,
        )

    if subjects_collection.find_one({"subject_code": subject_code}):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This subject code is already registered.",
                }
            ),
            409,
        )

    subjects_collection.insert_one(
        {
            "subject_code": subject_code,
            "subject_name": subject_name,
            "schedule": schedule,
            "start_time": start_time,
            "end_time": end_time,
            "building": building,
            "room_number": int(room_number),
            "section": section_name,
        }
    )

    return jsonify(
        {
            "success": True,
            "message": "Subject registered successfully.",
        }
    )


@users.route("/get_subjects")
def get_subjects():
    if "user_id" not in session:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please log in first.",
                }
            ),
            401,
        )

    subjects = list(subjects_collection.find({}, {"_id": 0}))

    return jsonify({"subjects": subjects})


# TODO Add subjects testing (rename)
@users.route("/testing_subjects", methods=["POST"])
def testing_subjects():
    subject = {
        "subject_code": request.form.get("subject_code", "").strip().upper(),
        "subject_name": request.form.get("subject_name", "").strip(),
        "schedule": request.form.get("schedule", "").strip(),
        "time": request.form.get("time", "").strip(),
        "room": request.form.get("room", "").strip(),
        "student_count": int(request.form.get("student_count", 0)),
    }

    subjects_collection.insert_one(subject)

    return redirect(url_for("users.dashboard"))


@users.route("/attendance")
def attendance():
    if "user_id" not in session:
        return redirect(url_for("users.home"))

    return render_template("attendance_block.html")


#! Admission Management
@users.route("/admissions")
def admissions():
    if "user_id" not in session:
        return redirect(url_for("users.home"))

    if session.get("role") != "guidance":
        return "Access denied.", 403

    students = list(
        students_collection.find(
            {},
            {
                "password": 0,
            },
        ).sort("last_name", 1)
    )

    return render_template(
        "admissions_block.html",
        page_title="Admission Management",
        first_name=session.get("first_name", ""),
        students=students,
    )


#! View Student ORF
@users.route("/admissions/orf/<student_id>")
def view_orf(student_id):
    # Require login
    if "user_id" not in session:
        return redirect(url_for("users.home"))

    # Only Guidance can view student ORFs
    if session.get("role") != "guidance":
        abort(403)

    from bson import ObjectId

    # Validate the student ID
    if not ObjectId.is_valid(student_id):
        abort(404)

    # Find the student
    student = students_collection.find_one(
        {"_id": ObjectId(student_id)},
        {"latest_orf": 1},
    )

    if not student:
        abort(404)

    # Get the uploaded ORF filename
    orf = student.get("latest_orf", {})
    filename = orf.get("filename") if orf else None

    if not filename or not filename.endswith(".pdf"):
        abort(404)

    # Open the PDF in the browser
    return send_from_directory(
        UPLOAD_FOLDER,
        filename,
        mimetype="application/pdf",
        as_attachment=False,
    )


# TODO Pending lines
# @users.route("/student/profile")
# def student_profile():
#     return render_template("student_profile.html")


# @users.route("/settings")
# def settings():
#     return render_template("settings.html")


# @users.route("/student/overview")
# def student_overview():
#     return render_template("student/overview.html")
