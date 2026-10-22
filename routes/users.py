from flask import (
    Blueprint,
    render_template,
    request,
    session,
    redirect,
    url_for,
    jsonify,
)
from database.db import (
    students_collection,
    professors_collection,
    programs_collection,
    sections_collection,
    subjects_collection,
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

users = Blueprint("users", __name__)


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

    if not all([first_name, last_name, id_number, email, password]):
        return (
            jsonify(
                {"success": False, "message": "Please complete all required fields."}
            ),
            400,
        )

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

        return jsonify({"success": False, "message": message}), 409

    user = {
        "first_name": first_name,
        "last_name": last_name,
        "id_number": id_number,
        "email": email,
        "password": generate_password_hash(password),
        "program": request.form.get("program", "").strip(),
        "year_level": request.form.get("year_level", "").strip(),
        "section": request.form.get("section", "").strip(),
        "role": "student",
    }

    result = students_collection.insert_one(user)

    session["user_id"] = str(result.inserted_id)
    session["id_number"] = id_number
    session["role"] = "student"

    return jsonify({"success": True, "message": "Success! Directing to overview."})


#! Login Form
@users.route("/login", methods=["POST"])
def login():
    id_number = request.form.get("id_number", "").strip().upper()
    password = request.form.get("password", "")

    user = students_collection.find_one({"id_number": id_number})

    if not user:
        user = professors_collection.find_one({"id_number": id_number})

    if user and check_password_hash(user["password"], password):
        role = user.get("role")

        # Support existing accounts that don't have a role field yet.
        if not role:
            if students_collection.find_one({"_id": user["_id"]}):
                role = "student"
            else:
                role = "professor"

        session["user_id"] = str(user["_id"])
        session["id_number"] = user["id_number"]
        session["role"] = role

        return jsonify(
            {"success": True, "message": "Login successful! Redirecting to overview."}
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
    else:
        user = professors_collection.find_one({"_id": user_id})

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
