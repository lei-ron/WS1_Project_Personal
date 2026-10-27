import re

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from bson import ObjectId

from flask import Blueprint, jsonify, request, session, current_app

from database.db import (
    students_collection,
    programs_collection,
    sections_collection,
    subjects_collection,
    professors_collection,
    subject_assignments_collection,
    attendance_records_collection,
    class_sessions_collection,
)

from routes.permissions import role_required

academic = Blueprint("academic", __name__)

MANILA_TZ = ZoneInfo("Asia/Manila")


def to_manila_time(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(MANILA_TZ)


#! Programs Manager

@academic.route("/programs_manager")
@role_required("guidance")
def programs_manager():
    from flask import render_template

    return render_template(
        "programs_manager_block.html",
        page_title="Programs Manager",
    )


#! Sections Manager

@academic.route("/sections_manager")
@role_required("guidance")
def sections_manager():
    from flask import render_template

    return render_template(
        "sections_manager_block.html",
        page_title="Sections Manager",
    )


#! Subjects Manager

@academic.route("/subjects_manager")
@role_required("guidance")
def subjects_manager():
    from flask import render_template

    return render_template(
        "subjects_manager_block.html",
        page_title="Subjects Manager",
    )

#! Register Program
@academic.route("/register_program", methods=["POST"])
@role_required("guidance")
def register_program():
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


#! Register Subject
@academic.route("/register_subject", methods=["POST"])
@role_required("guidance")
def register_subject():
    program_codes = [
        code.strip().upper()
        for code in request.form.getlist("program_codes")
        if code.strip()
    ]

    subject_code = request.form.get("subject_code", "").strip().upper()
    subject_name = request.form.get("subject_name", "").strip()

    if not program_codes or not subject_code or not subject_name:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please complete all subject fields.",
                }
            ),
            400,
        )

    if len(program_codes) != len(set(program_codes)):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Duplicate program selections are not allowed.",
                }
            ),
            400,
        )

    for program_code in program_codes:
        program = programs_collection.find_one({"program_code": program_code})

        if not program:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Program {program_code} does not exist.",
                    }
                ),
                400,
            )

    existing_subject = subjects_collection.find_one(
        {
            "subject_code": subject_code,
            "$or": [
                {"program_codes": {"$in": program_codes}},
                {
                    "program_code": {"$in": program_codes},
                    "program_codes": {"$exists": False},
                },
            ],
        }
    )

    if existing_subject:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This subject code is already registered for one or more selected programs.",
                }
            ),
            409,
        )

    subjects_collection.insert_one(
        {
            "program_codes": program_codes,
            "subject_code": subject_code,
            "subject_name": subject_name,
        }
    )

    return jsonify(
        {
            "success": True,
            "message": "Subject registered successfully.",
        }
    )


#! Get Programs
@academic.route("/get_programs")
@role_required("guidance")
def get_programs():
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

    programs = list(
        programs_collection.find(
            {},
            {
                "_id": 0,
                "program_code": 1,
                "program_name": 1,
                "year_levels": 1,
            },
        )
    )

    return jsonify({"programs": programs})


#! Register Section
@academic.route("/register_section", methods=["POST"])
@role_required("guidance")
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

    if not 1 <= section_number <= 999:
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


#! Get Sections
@academic.route("/get_sections")
@role_required("guidance")
def get_sections():
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

    sections = list(sections_collection.find({}, {"_id": 0}))

    return jsonify({"sections": sections})


#! Get Subjects
@academic.route("/get_subjects")
@role_required("guidance")
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


#! Get Professors for Subject Assignment
@academic.route("/get_assignment_professors")
@role_required("guidance")
def get_assignment_professors():
    professors = list(
        professors_collection.find(
            {},
            {
                "_id": 1,
                "first_name": 1,
                "last_name": 1,
            },
        )
    )

    for professor in professors:
        professor["_id"] = str(professor["_id"])

    return jsonify({"professors": professors})


#! Get Subjects for Selected Section
@academic.route("/get_section_subjects")
@role_required("guidance")
def get_section_subjects():
    section_name = request.args.get("section_name", "").strip().upper()

    if not section_name:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please select a section.",
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
            404,
        )

    subjects = list(
        subjects_collection.find(
            {
                "$or": [
                    {"program_codes": section["program_code"]},
                    {
                        "program_code": section["program_code"],
                        "program_codes": {"$exists": False},
                    },
                ]
            },
            {
                "_id": 0,
                "program_codes": 1,
                "program_code": 1,
                "subject_code": 1,
                "subject_name": 1,
            },
        )
    )

    return jsonify({"subjects": subjects})


#! Register Subject Assignment
@academic.route("/register_subject_assignment", methods=["POST"])
@role_required("guidance")
def register_subject_assignment():
    from bson import ObjectId
    from datetime import datetime

    section_name = request.form.get("section_name", "").strip().upper()
    subject_code = request.form.get("subject_code", "").strip().upper()
    professor_id = request.form.get("professor_id", "").strip()
    days = request.form.getlist("days")
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    building = request.form.get("building", "").strip().upper()
    room_number = request.form.get("room_number", "").strip()

    if not all(
        [
            section_name,
            subject_code,
            professor_id,
            days,
            start_time,
            end_time,
            building,
            room_number,
        ]
    ):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please complete all assignment fields.",
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

    subject = subjects_collection.find_one(
        {
            "subject_code": subject_code,
            "$or": [
                {"program_codes": section["program_code"]},
                {
                    "program_code": section["program_code"],
                    "program_codes": {"$exists": False},
                },
            ],
        }
    )

    if not subject:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "The selected subject does not belong to this section's program.",
                }
            ),
            400,
        )

    if not ObjectId.is_valid(professor_id):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid professor selection.",
                }
            ),
            400,
        )

    professor = professors_collection.find_one({"_id": ObjectId(professor_id)})

    if not professor:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "The selected professor does not exist.",
                }
            ),
            400,
        )

    valid_days = {
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    }

    if not set(days).issubset(valid_days):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid day selection.",
                }
            ),
            400,
        )

    if len(days) != len(set(days)):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Duplicate days are not allowed.",
                }
            ),
            400,
        )

    try:
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
    except ValueError:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid time format.",
                }
            ),
            400,
        )

    if start >= end:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Time Out must be later than Time In.",
                }
            ),
            400,
        )

    if building not in {"B1", "B2", "B3", "B4"}:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please select a valid building.",
                }
            ),
            400,
        )

    try:
        room_number = int(room_number)
    except ValueError:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Room number must be a valid number.",
                }
            ),
            400,
        )

    if room_number < 1:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Room number must be greater than zero.",
                }
            ),
            400,
        )

    existing_assignment = subject_assignments_collection.find_one(
        {
            "section_name": section_name,
            "subject_code": subject_code,
        }
    )

    if existing_assignment:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This subject already has an assignment in this section.",
                }
            ),
            409,
        )

    subject_assignments_collection.insert_one(
        {
            "section_name": section_name,
            "program_code": section["program_code"],
            "subject_code": subject_code,
            "subject_name": subject["subject_name"],
            "professor_id": ObjectId(professor_id),
            "days": days,
            "start_time": start_time,
            "end_time": end_time,
            "building": building,
            "room_number": room_number,
        }
    )

    return jsonify(
        {
            "success": True,
            "message": "Subject assignment registered successfully.",
        }
    )


#! Get attendance
@academic.route("/get_attendance_sections", methods=["GET"])
@role_required("professor", "guidance")
def get_attendance_sections():
    role = session.get("role")
    query = {}

    if role == "professor":
        try:
            query["professor_id"] = ObjectId(session["user_id"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"message": "Invalid professor session."}), 401

    assignments = list(subject_assignments_collection.find(query))

    now = datetime.now(ZoneInfo("Asia/Manila"))
    today = now.strftime("%Y-%m-%d")
    current_day = now.strftime("%A")

    section_statuses = {}

    for assignment in assignments:
        section_name = assignment.get("section_name")

        if not section_name:
            continue

        status = "Upcoming"
        start_minutes = 24 * 60

        if current_day in assignment.get("days", []):
            try:
                start = datetime.strptime(assignment["start_time"], "%H:%M").time()

                end = datetime.strptime(assignment["end_time"], "%H:%M").time()

                start_datetime = now.replace(
                    hour=start.hour,
                    minute=start.minute,
                    second=0,
                    microsecond=0,
                )

                end_datetime = now.replace(
                    hour=end.hour,
                    minute=end.minute,
                    second=0,
                    microsecond=0,
                )

                start_minutes = start.hour * 60 + start.minute

                class_session = class_sessions_collection.find_one(
                    {
                        "assignment_id": assignment["_id"],
                        "attendance_date": today,
                    }
                )

                if now >= end_datetime:
                    status = "Completed"

                elif class_session and now >= start_datetime:
                    status = "Ongoing"

                elif now >= start_datetime:
                    # The scheduled time has started, but no session
                    # has been started by a valid attendance scan.
                    status = "Upcoming"

            except (KeyError, TypeError, ValueError):
                current_app.logger.exception(
                    "Invalid schedule for assignment %s",
                    assignment.get("_id"),
                )

        if section_name not in section_statuses:
            section_statuses[section_name] = {
                "section_name": section_name,
                "status": status,
                "start_minutes": start_minutes,
            }
        else:
            existing = section_statuses[section_name]

            priority = {
                "Ongoing": 0,
                "Upcoming": 1,
                "Completed": 2,
            }

            if priority[status] < priority[existing["status"]]:
                existing["status"] = status
                existing["start_minutes"] = start_minutes

            elif (
                status == existing["status"] == "Upcoming"
                and start_minutes < existing["start_minutes"]
            ):
                existing["start_minutes"] = start_minutes

    sections = list(section_statuses.values())

    priority = {
        "Ongoing": 0,
        "Upcoming": 1,
        "Completed": 2,
    }

    sections.sort(
        key=lambda section: (
            priority[section["status"]],
            section["start_minutes"],
            section["section_name"],
        )
    )

    return jsonify({"sections": sections})


@academic.route("/get_attendance_subjects", methods=["GET"])
@role_required("professor", "guidance")
def get_attendance_subjects():
    section_name = request.args.get("section_name", "").strip()

    if not section_name:
        return jsonify({"message": "Section name is required."}), 400

    query = {"section_name": section_name}

    if session.get("role") == "professor":
        try:
            query["professor_id"] = ObjectId(session["user_id"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"message": "Invalid professor session."}), 401

    assignments = list(subject_assignments_collection.find(query))

    now = datetime.now(ZoneInfo("Asia/Manila"))
    today = now.strftime("%Y-%m-%d")
    current_day = now.strftime("%A")

    priority = {
        "Ongoing": 0,
        "Upcoming": 1,
        "Completed": 2,
    }

    subjects = []

    for assignment in assignments:
        status = "Upcoming"
        start_minutes = 24 * 60

        if current_day in assignment.get("days", []):
            try:
                start = datetime.strptime(assignment["start_time"], "%H:%M").time()

                end = datetime.strptime(assignment["end_time"], "%H:%M").time()

                start_datetime = now.replace(
                    hour=start.hour,
                    minute=start.minute,
                    second=0,
                    microsecond=0,
                )

                end_datetime = now.replace(
                    hour=end.hour,
                    minute=end.minute,
                    second=0,
                    microsecond=0,
                )

                start_minutes = start.hour * 60 + start.minute

                class_session = class_sessions_collection.find_one(
                    {
                        "assignment_id": assignment["_id"],
                        "attendance_date": today,
                    }
                )

                if now >= end_datetime:
                    status = "Completed"

                elif class_session and now >= start_datetime:
                    status = "Ongoing"

                elif now >= start_datetime:
                    status = "Upcoming"

            except (KeyError, TypeError, ValueError):
                current_app.logger.exception(
                    "Invalid schedule for assignment %s",
                    assignment.get("_id"),
                )

        subjects.append(
            {
                "subject_code": assignment["subject_code"],
                "subject_name": assignment["subject_name"],
                "section_name": assignment["section_name"],
                "days": assignment.get("days", []),
                "start_time": assignment["start_time"],
                "end_time": assignment["end_time"],
                "building": assignment.get("building", ""),
                "room_number": assignment.get("room_number", ""),
                "status": status,
                "start_minutes": start_minutes,
            }
        )

    subjects.sort(
        key=lambda subject: (
            priority[subject["status"]],
            subject["start_minutes"],
            subject["start_time"],
            subject["subject_name"],
        )
    )

    return jsonify({"subjects": subjects})


@academic.route("/record_attendance", methods=["POST"])
@role_required("professor", "guidance")
def record_attendance():
    data = request.get_json(silent=True) or {}

    section_name = data.get("section_name", "").strip()
    subject_code = data.get("subject_code", "").strip().upper()
    student_id = data.get("student_id", "").strip().upper()
    manual_first_name = data.get("manual_first_name", "").strip().upper()
    manual_last_name = data.get("manual_last_name", "").strip().upper()
    not_registered = data.get("not_registered", False)

    if not section_name or not subject_code:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please select a section and subject.",
                }
            ),
            400,
        )

    if not_registered and not (manual_first_name and manual_last_name):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please enter both the first name and last name.",
                }
            ),
            400,
        )

    if not not_registered and not student_id:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please enter a student ID.",
                }
            ),
            400,
        )

    # Verify subject assignment and permissions.
    assignment_query = {
        "section_name": section_name,
        "subject_code": subject_code,
    }

    if session.get("role") == "professor":
        try:
            assignment_query["professor_id"] = ObjectId(session["user_id"])
        except (KeyError, TypeError, ValueError):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Invalid professor session.",
                    }
                ),
                401,
            )

    assignment = subject_assignments_collection.find_one(assignment_query)

    if not assignment:
        return (
            jsonify(
                {
                    "success": False,
                    "message": (
                        "This subject is not assigned to the selected section "
                        "or you do not have permission to record its attendance."
                    ),
                }
            ),
            403,
        )

    # Use Philippine local time.
    now = datetime.now(ZoneInfo("Asia/Manila"))
    attendance_date = now.strftime("%Y-%m-%d")
    day_name = now.strftime("%A")

    # Validate the assigned class day.
    assigned_days = assignment.get("days", [])

    if day_name not in assigned_days:
        return (
            jsonify(
                {
                    "success": False,
                    "message": (f"This class is not scheduled for today ({day_name})."),
                }
            ),
            400,
        )

    # Parse the scheduled times.
    try:
        start_time = datetime.strptime(assignment["start_time"], "%H:%M").time()

        end_time = datetime.strptime(assignment["end_time"], "%H:%M").time()
    except (KeyError, TypeError, ValueError):
        current_app.logger.exception("Invalid subject assignment times.")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "The subject has an invalid schedule.",
                }
            ),
            500,
        )

    scheduled_start = now.replace(
        hour=start_time.hour,
        minute=start_time.minute,
        second=0,
        microsecond=0,
    )

    scheduled_end = now.replace(
        hour=end_time.hour,
        minute=end_time.minute,
        second=0,
        microsecond=0,
    )

    if now < scheduled_start:
        return (
            jsonify(
                {
                    "success": False,
                    "message": (
                        "Attendance cannot be recorded before the scheduled "
                        f"start time of {scheduled_start.strftime('%I:%M %p')}."
                    ),
                }
            ),
            400,
        )

    # Create or retrieve today's class session.
    session_query = {
        "assignment_id": assignment["_id"],
        "attendance_date": attendance_date,
    }

    class_session = class_sessions_collection.find_one(session_query)

    if not class_session:
        new_session = {
            "assignment_id": assignment["_id"],
            "section_name": section_name,
            "subject_code": subject_code,
            "subject_name": assignment["subject_name"],
            "attendance_date": attendance_date,
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end,
            "started_at": now,
            "status": "Ongoing",
            "created_at": now,
        }

        try:
            result = class_sessions_collection.insert_one(new_session)
            new_session["_id"] = result.inserted_id
            class_session = new_session
        except Exception:
            # Another scan may have created the session simultaneously.
            current_app.logger.exception("Failed to create class session.")
            class_session = class_sessions_collection.find_one(session_query)

            if not class_session:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Failed to start the class session.",
                        }
                    ),
                    500,
                )

    # A session's scheduled end time must remain authoritative.
    # A session's scheduled end time must remain authoritative.
    scheduled_end = to_manila_time(class_session["scheduled_end"])

    if now >= scheduled_end:
        class_sessions_collection.update_one(
            {"_id": class_session["_id"]},
            {"$set": {"status": "Completed"}},
        )
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This class has ended. Attendance is now closed.",
                }
            ),
            400,
        )

    # Determine attendance status using the scheduled start time.
    scheduled_start = to_manila_time(class_session["scheduled_start"])
    grace_period_end = scheduled_start + timedelta(minutes=20)

    if now <= grace_period_end:
        attendance_status = "Present"
    else:
        attendance_status = "Late"

    # Registered student.
    if not not_registered:
        student = students_collection.find_one(
            {
                "id_number": student_id,
            }
        )

        if not student:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": (
                            "Student ID not found. Check the ID or use "
                            "Not registered? for a student without an account."
                        ),
                    }
                ),
                404,
            )

        if student.get("section") != section_name:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": (
                            "This student does not belong to the selected section."
                        ),
                    }
                ),
                400,
            )

        student_name = (
            f"{student.get('first_name', '')} " f"{student.get('last_name', '')}"
        ).strip()

        if not student_name:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "The student's account has no valid name.",
                    }
                ),
                400,
            )

        duplicate_query = {
            "assignment_id": assignment["_id"],
            "attendance_date": attendance_date,
            "student_id": student_id,
        }

        is_registered = True

    # Manually entered student without an account.
    else:
        student_name = f"{manual_first_name} {manual_last_name}"
        student_id = None

        normalized_name = " ".join(student_name.split()).casefold()

        duplicate_query = {
            "assignment_id": assignment["_id"],
            "attendance_date": attendance_date,
            "is_registered": False,
            "manual_name_normalized": normalized_name,
        }

        is_registered = False

    # Prevent duplicate attendance entries.
    if attendance_records_collection.find_one(duplicate_query):
        return (
            jsonify(
                {
                    "success": False,
                    "message": (
                        "This student has already been recorded "
                        "for this subject today."
                    ),
                }
            ),
            409,
        )

    attendance_record = {
        "assignment_id": assignment["_id"],
        "class_session_id": class_session["_id"],
        "section_name": section_name,
        "subject_code": assignment["subject_code"],
        "subject_name": assignment["subject_name"],
        "professor_id": assignment["professor_id"],
        "student_id": student_id,
        "student_name": student_name,
        "is_registered": is_registered,
        "attendance_date": attendance_date,
        "time_in": now.strftime("%I:%M:%S %p"),
        "status": attendance_status,
        "recorded_by": session["user_id"],
        "created_at": now,
    }

    if not is_registered:
        attendance_record["manual_name_normalized"] = " ".join(
            student_name.split()
        ).casefold()

    try:
        attendance_records_collection.insert_one(attendance_record)
    except Exception:
        current_app.logger.exception("Failed to save attendance record.")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Failed to save attendance. Please try again.",
                }
            ),
            500,
        )

    return (
        jsonify(
            {
                "success": True,
                "message": (
                    f"Attendance recorded successfully. Status: {attendance_status}."
                ),
                "record": {
                    "student_id": student_id or "Not registered",
                    "student_name": student_name,
                    "time_in": now.strftime("%I:%M:%S %p"),
                    "status": attendance_status,
                },
                "session_status": "Ongoing",
            }
        ),
        201,
    )


@academic.route("/get_attendance_records", methods=["GET"])
@role_required("professor", "guidance")
def get_attendance_records():
    section_name = request.args.get("section_name", "").strip()
    subject_code = request.args.get("subject_code", "").strip().upper()

    if not section_name or not subject_code:
        return (
            jsonify(
                {
                    "message": "Section and subject are required.",
                }
            ),
            400,
        )

    assignment_query = {
        "section_name": section_name,
        "subject_code": subject_code,
    }

    if session.get("role") == "professor":
        try:
            assignment_query["professor_id"] = ObjectId(session["user_id"])
        except (KeyError, TypeError, ValueError):
            return (
                jsonify(
                    {
                        "message": "Invalid professor session.",
                    }
                ),
                401,
            )

    assignment = subject_assignments_collection.find_one(assignment_query)

    if not assignment:
        return (
            jsonify(
                {
                    "message": "Subject assignment not found or access denied.",
                }
            ),
            403,
        )

    now = datetime.now(ZoneInfo("Asia/Manila"))
    today = now.strftime("%Y-%m-%d")
    current_day = now.strftime("%A")
    now_naive = now.replace(tzinfo=None)

    class_session = class_sessions_collection.find_one(
        {
            "assignment_id": assignment["_id"],
            "attendance_date": today,
        }
    )

    session_status = "Upcoming"

    if class_session:
        scheduled_end = class_session["scheduled_end"]

        if scheduled_end.tzinfo is not None:
            scheduled_end = scheduled_end.astimezone(ZoneInfo("Asia/Manila")).replace(
                tzinfo=None
            )
        else:
            scheduled_end = scheduled_end.replace(tzinfo=None)

        if now_naive >= scheduled_end:
            session_status = "Completed"

            class_sessions_collection.update_one(
                {"_id": class_session["_id"]},
                {"$set": {"status": "Completed"}},
            )
        else:
            session_status = "Ongoing"

    else:
        if today and assignment.get("days"):
            if now.strftime("%A") in assignment["days"]:
                try:
                    start_time = datetime.strptime(
                        assignment["start_time"], "%H:%M"
                    ).time()

                    end_time = datetime.strptime(assignment["end_time"], "%H:%M").time()

                    scheduled_start = now.replace(
                        hour=start_time.hour,
                        minute=start_time.minute,
                        second=0,
                        microsecond=0,
                    )

                    scheduled_end = now.replace(
                        hour=end_time.hour,
                        minute=end_time.minute,
                        second=0,
                        microsecond=0,
                    )

                    if now >= scheduled_end:
                        session_status = "Completed"
                    elif now >= scheduled_start:
                        session_status = "Upcoming"

                except (KeyError, TypeError, ValueError):
                    current_app.logger.exception("Invalid subject schedule.")

    records = attendance_records_collection.find(
        {
            "assignment_id": assignment["_id"],
            "attendance_date": today,
        },
        {
            "_id": 0,
            "student_id": 1,
            "student_name": 1,
            "time_in": 1,
            "status": 1,
        },
    ).sort("created_at", 1)

    return jsonify(
        {
            "records": list(records),
            "session_status": session_status,
        }
    )


# Get Programs for Registration
@academic.route("/get_registration_programs")
def get_registration_programs():
    programs = list(
        programs_collection.find(
            {},
            {
                "_id": 0,
                "program_code": 1,
                "program_name": 1,
                "year_levels": 1,
            },
        )
    )

    return jsonify({"programs": programs})


# Get Sections for Registration
@academic.route("/get_registration_sections")
def get_registration_sections():
    sections = list(
        sections_collection.find(
            {},
            {
                "_id": 0,
                "program_code": 1,
                "year_level": 1,
                "current_trimester": 1,
                "section_name": 1,
            },
        )
    )

    return jsonify({"sections": sections})
