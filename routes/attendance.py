import base64
import io
import secrets
import qrcode

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from bson import ObjectId
from pymongo import ReturnDocument
from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from database.db import (
    students_collection,
    subject_assignments_collection,
    attendance_records_collection,
    class_sessions_collection,
)
from routes.permissions import role_required

attendance = Blueprint("attendance", __name__)


MANILA_TZ = ZoneInfo("Asia/Manila")


def to_manila_time(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(MANILA_TZ)


def generate_qr_token():
    return secrets.token_urlsafe(32)


def generate_qr_image(token):
    qr = qrcode.make(token)

    image_buffer = io.BytesIO()
    qr.save(image_buffer, format="PNG")

    encoded_image = base64.b64encode(image_buffer.getvalue()).decode("utf-8")

    return f"data:image/png;base64,{encoded_image}"


def get_assignment_for_attendance(section_name, subject_code):
    assignment_query = {
        "section_name": section_name,
        "subject_code": subject_code,
    }

    if session.get("role") == "professor":
        try:
            assignment_query["professor_id"] = ObjectId(session["user_id"])
        except (KeyError, TypeError, ValueError):
            return None

    return subject_assignments_collection.find_one(assignment_query)


#! Attendance
@attendance.route("/attendance")
@role_required("professor", "guidance")
def attendance_page():
    return render_template("attendance_block.html")


@attendance.route("/student/attendance")
@role_required("student")
def student_attendance():
    try:
        user = students_collection.find_one({"_id": ObjectId(session["user_id"])})
    except (KeyError, TypeError, ValueError):
        session.clear()
        return redirect(url_for("users.home"))

    if not user:
        session.clear()
        return redirect(url_for("users.home"))

    if user.get("admission_status", "Pending") != "Approved":
        session.clear()
        return redirect(url_for("users.home"))

    return render_template(
        "student_attendance_block.html",
        page_title="Attendance",
        first_name=user.get("first_name", ""),
    )


@attendance.route("/scan_attendance_qr", methods=["POST"])
@role_required("student")
def scan_attendance_qr():
    data = request.get_json(silent=True) or {}
    token = data.get("token", "")

    if not isinstance(token, str) or not token:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid QR code.",
                }
            ),
            400,
        )

    try:
        student_object_id = ObjectId(session["user_id"])
    except (KeyError, TypeError, ValueError):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid login session.",
                }
            ),
            401,
        )

    student = students_collection.find_one(
        {
            "_id": student_object_id,
        }
    )

    if not student:
        session.clear()

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Student account not found.",
                }
            ),
            401,
        )

    if student.get("admission_status", "Pending") != "Approved":
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Your account is not approved for attendance.",
                }
            ),
            403,
        )

    now = datetime.now(MANILA_TZ)
    attendance_date = now.strftime("%Y-%m-%d")

    # Find the session containing this token.
    class_session = class_sessions_collection.find_one(
        {
            "qr_token": token,
            "qr_active": True,
            "status": "Ongoing",
            "qr_expires_at": {"$gt": now},
            "attendance_date": attendance_date,
        }
    )

    if not class_session:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This QR code has expired or is no longer valid.",
                }
            ),
            400,
        )

    scheduled_end = to_manila_time(class_session["scheduled_end"])

    if now >= scheduled_end:
        class_sessions_collection.update_one(
            {"_id": class_session["_id"]},
            {
                "$set": {
                    "status": "Completed",
                    "qr_active": False,
                    "qr_token": None,
                    "qr_expires_at": None,
                }
            },
        )

        return (
            jsonify(
                {
                    "success": False,
                    "message": "This class has ended.",
                }
            ),
            400,
        )

    assignment = subject_assignments_collection.find_one(
        {
            "_id": class_session["assignment_id"],
        }
    )

    if not assignment:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Subject assignment could not be found.",
                }
            ),
            404,
        )

    section_name = assignment.get("section_name", "")

    if student.get("section") != section_name:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "You do not belong to this class section.",
                }
            ),
            403,
        )

    student_id = student.get("id_number", "").strip().upper()

    if not student_id:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Your account does not have a valid student ID.",
                }
            ),
            400,
        )

    duplicate_query = {
        "assignment_id": assignment["_id"],
        "attendance_date": attendance_date,
        "student_id": student_id,
    }

    if attendance_records_collection.find_one(duplicate_query):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Your attendance has already been recorded for this class today.",
                }
            ),
            409,
        )

    # Atomically consume the current token and replace it.
    # Only one request can successfully match this exact token.
    next_token = generate_qr_token()
    next_expiry = now + timedelta(seconds=3)

    updated_session = class_sessions_collection.find_one_and_update(
        {
            "_id": class_session["_id"],
            "qr_active": True,
            "status": "Ongoing",
            "qr_token": token,
            "qr_expires_at": {"$gt": now},
        },
        {
            "$set": {
                "qr_token": next_token,
                "qr_expires_at": next_expiry,
            }
        },
        return_document=ReturnDocument.BEFORE,
    )

    if not updated_session:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This QR code has already been used. Scan the refreshed code.",
                }
            ),
            409,
        )

    scheduled_start = to_manila_time(class_session["scheduled_start"])

    if now <= scheduled_start + timedelta(minutes=20):
        attendance_status = "Present"
    else:
        attendance_status = "Late"

    student_name = (
        f"{student.get('first_name', '')} " f"{student.get('last_name', '')}"
    ).strip()

    attendance_record = {
        "assignment_id": assignment["_id"],
        "class_session_id": class_session["_id"],
        "section_name": section_name,
        "subject_code": assignment["subject_code"],
        "subject_name": assignment["subject_name"],
        "professor_id": assignment["professor_id"],
        "student_id": student_id,
        "student_name": student_name,
        "is_registered": True,
        "attendance_date": attendance_date,
        "time_in": now.strftime("%I:%M:%S %p"),
        "status": attendance_status,
        "recorded_by": str(student_object_id),
        "created_at": now,
    }

    try:
        attendance_records_collection.insert_one(attendance_record)

    except Exception:
        current_app.logger.exception("Failed to save QR attendance record.")

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
                    "student_id": student_id,
                    "student_name": student_name,
                    "time_in": now.strftime("%I:%M:%S %p"),
                    "status": attendance_status,
                },
            }
        ),
        201,
    )


#! Get attendance
def get_schedule_indicator(assignment, now):
    today = now.strftime("%Y-%m-%d")
    current_day = now.strftime("%A")

    tomorrow = now + timedelta(days=1)
    tomorrow_day = tomorrow.strftime("%A")

    days = assignment.get("days", [])

    try:
        start_time = datetime.strptime(assignment["start_time"], "%H:%M").time()

        end_time = datetime.strptime(assignment["end_time"], "%H:%M").time()
    except (KeyError, TypeError, ValueError):
        current_app.logger.exception(
            "Invalid schedule for assignment %s",
            assignment.get("_id"),
        )
        return "", 24 * 60

    start_minutes = start_time.hour * 60 + start_time.minute

    # Check today's class first.
    if current_day in days:
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

        class_session = class_sessions_collection.find_one(
            {
                "assignment_id": assignment["_id"],
                "attendance_date": today,
            }
        )

        # The scheduled end time determines whether the class has ended.
        if now >= scheduled_end:
            return "Ended", start_minutes

        # Attendance has been activated and the class is still within
        # its scheduled period.
        if (
            class_session
            and class_session.get("qr_active")
            and class_session.get("status") == "Ongoing"
        ):
            return "Started", start_minutes

        # The class period has begun, but attendance has not been activated.
        if now >= scheduled_start:
            return "Ongoing", start_minutes

        return "Today", start_minutes

    # If there is no class today, check tomorrow.
    if tomorrow_day in days:
        return "Tomorrow", start_minutes

    return "", start_minutes


@attendance.route("/get_attendance_sections", methods=["GET"])
@role_required("professor", "guidance")
def get_attendance_sections():
    query = {}

    if session.get("role") == "professor":
        try:
            query["professor_id"] = ObjectId(session["user_id"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"message": "Invalid professor session."}), 401

    assignments = list(subject_assignments_collection.find(query))
    now = datetime.now(MANILA_TZ)

    section_statuses = {}

    priority = {
        "Started": 0,
        "Ongoing": 1,
        "Today": 2,
        "Tomorrow": 3,
        "Ended": 4,
        "": 5,
    }

    for assignment in assignments:
        section_name = assignment.get("section_name")

        if not section_name:
            continue

        status, start_minutes = get_schedule_indicator(
            assignment,
            now,
        )

        if section_name not in section_statuses:
            section_statuses[section_name] = {
                "section_name": section_name,
                "status": status,
                "start_minutes": start_minutes,
            }
            continue

        existing = section_statuses[section_name]

        # Keep the highest-priority indicator when a section has
        # multiple assigned subjects.
        if priority[status] < priority[existing["status"]]:
            existing["status"] = status
            existing["start_minutes"] = start_minutes

        elif status == existing["status"] and start_minutes < existing["start_minutes"]:
            existing["start_minutes"] = start_minutes

    sections = list(section_statuses.values())

    sections.sort(
        key=lambda section: (
            priority[section["status"]],
            section["start_minutes"],
            section["section_name"],
        )
    )

    return jsonify({"sections": sections})


@attendance.route("/get_attendance_subjects", methods=["GET"])
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
    now = datetime.now(MANILA_TZ)

    priority = {
        "Started": 0,
        "Ongoing": 1,
        "Today": 2,
        "Tomorrow": 3,
        "Ended": 4,
        "": 5,
    }

    subjects = []

    for assignment in assignments:
        status, start_minutes = get_schedule_indicator(
            assignment,
            now,
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


@attendance.route("/record_attendance", methods=["POST"])
@role_required("professor", "guidance")
def record_attendance():
    data = request.get_json(silent=True) or {}

    section_name = str(data.get("section_name", "")).strip()
    subject_code = str(data.get("subject_code", "")).strip().upper()
    student_id = str(data.get("student_id", "")).strip().upper()
    manual_first_name = str(data.get("manual_first_name", "")).strip().upper()
    manual_last_name = str(data.get("manual_last_name", "")).strip().upper()
    not_registered = data.get("not_registered", False) is True

    if not section_name or not subject_code:
        return (
            jsonify(
                {"success": False, "message": "Please select a section and subject."}
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
        return jsonify({"success": False, "message": "Please enter a student ID."}), 400

    # Verify the assignment and the current user's permission first.
    assignment_query = {
        "section_name": section_name,
        "subject_code": subject_code,
    }

    if session.get("role") == "professor":
        try:
            assignment_query["professor_id"] = ObjectId(session["user_id"])
        except (KeyError, TypeError, ValueError):
            return (
                jsonify({"success": False, "message": "Invalid professor session."}),
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

    now = datetime.now(MANILA_TZ)
    attendance_date = now.strftime("%Y-%m-%d")
    day_name = now.strftime("%A")

    if day_name not in assignment.get("days", []):
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"This class is not scheduled for today ({day_name}).",
                }
            ),
            400,
        )

    try:
        start_time = datetime.strptime(assignment["start_time"], "%H:%M").time()
        end_time = datetime.strptime(assignment["end_time"], "%H:%M").time()
    except (KeyError, TypeError, ValueError):
        current_app.logger.exception("Invalid subject assignment times.")
        return (
            jsonify(
                {"success": False, "message": "The subject has an invalid schedule."}
            ),
            500,
        )

    scheduled_start = now.replace(
        hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0
    )
    scheduled_end = now.replace(
        hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0
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

    # Validate the student and duplicates BEFORE creating a class session.
    # Invalid IDs and duplicate submissions must not leave empty sessions behind.
    if not not_registered:
        student = students_collection.find_one({"id_number": student_id})

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

        if student.get("admission_status", "Pending") != "Approved":
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "This student account is not approved for attendance.",
                    }
                ),
                403,
            )

        if student.get("section") != section_name:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "This student does not belong to the selected section.",
                    }
                ),
                400,
            )

        student_name = (
            f"{student.get('first_name', '')} {student.get('last_name', '')}"
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

    if attendance_records_collection.find_one(duplicate_query):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This student has already been recorded for this subject today.",
                }
            ),
            409,
        )

    session_query = {
        "assignment_id": assignment["_id"],
        "attendance_date": attendance_date,
    }
    class_session = class_sessions_collection.find_one(session_query)

    # Do not allow manual attendance after the professor has ended the session.
    if class_session and class_session.get("status") == "Completed":
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Attendance for this class has already ended.",
                }
            ),
            400,
        )

    if now >= scheduled_end:
        if class_session:
            class_sessions_collection.update_one(
                {"_id": class_session["_id"]},
                {
                    "$set": {
                        "status": "Completed",
                        "qr_active": False,
                        "qr_token": None,
                        "qr_expires_at": None,
                    }
                },
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

    # Use the saved session's schedule as the source of truth.
    saved_scheduled_end = to_manila_time(class_session["scheduled_end"])
    if now >= saved_scheduled_end:
        class_sessions_collection.update_one(
            {"_id": class_session["_id"]},
            {
                "$set": {
                    "status": "Completed",
                    "qr_active": False,
                    "qr_token": None,
                    "qr_expires_at": None,
                }
            },
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

    saved_scheduled_start = to_manila_time(class_session["scheduled_start"])
    if now <= saved_scheduled_start + timedelta(minutes=20):
        attendance_status = "Present"
    else:
        attendance_status = "Late"

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
        "recorded_by": session.get("user_id", ""),
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
                "message": f"Attendance recorded successfully. Status: {attendance_status}.",
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


@attendance.route("/get_attendance_records", methods=["GET"])
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

    class_session = class_sessions_collection.find_one(
        {
            "assignment_id": assignment["_id"],
            "attendance_date": today,
        }
    )

    session_status = "Upcoming"

    if class_session:
        scheduled_end = to_manila_time(class_session["scheduled_end"])

        if class_session.get("status") == "Completed" or now >= scheduled_end:
            session_status = "Completed"
            # Keep the stored state and QR token consistent with the schedule.
            if class_session.get("status") != "Completed" or class_session.get(
                "qr_active"
            ):
                class_sessions_collection.update_one(
                    {"_id": class_session["_id"]},
                    {
                        "$set": {
                            "status": "Completed",
                            "qr_active": False,
                            "qr_token": None,
                            "qr_expires_at": None,
                        }
                    },
                )
        else:
            session_status = "Ongoing"

    elif assignment.get("days") and now.strftime("%A") in assignment["days"]:
        try:
            end_time = datetime.strptime(assignment["end_time"], "%H:%M").time()
            scheduled_end = now.replace(
                hour=end_time.hour,
                minute=end_time.minute,
                second=0,
                microsecond=0,
            )
            if now >= scheduled_end:
                session_status = "Completed"
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


@attendance.route("/start_attendance_session", methods=["POST"])
@role_required("professor", "guidance")
def start_attendance_session():
    data = request.get_json(silent=True) or {}

    section_name = data.get("section_name", "").strip()
    subject_code = data.get("subject_code", "").strip().upper()

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

    assignment = get_assignment_for_attendance(
        section_name,
        subject_code,
    )

    if not assignment:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Subject assignment not found or access denied.",
                }
            ),
            403,
        )

    now = datetime.now(MANILA_TZ)
    attendance_date = now.strftime("%Y-%m-%d")
    current_day = now.strftime("%A")

    if current_day not in assignment.get("days", []):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This class is not scheduled for today.",
                }
            ),
            400,
        )

    try:
        start_time = datetime.strptime(
            assignment["start_time"],
            "%H:%M",
        ).time()

        end_time = datetime.strptime(
            assignment["end_time"],
            "%H:%M",
        ).time()

    except (KeyError, TypeError, ValueError):
        current_app.logger.exception("Invalid subject assignment schedule.")

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
                    "message": "Attendance cannot start before the scheduled class time.",
                }
            ),
            400,
        )

    if now >= scheduled_end:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This class has already ended.",
                }
            ),
            400,
        )

    session_query = {
        "assignment_id": assignment["_id"],
        "attendance_date": attendance_date,
    }

    class_session = class_sessions_collection.find_one(session_query)

    if class_session and class_session.get("status") == "Completed":
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Attendance for this class has already ended.",
                }
            ),
            400,
        )

    # Reuse an existing active QR session if it is still valid.
    if class_session and class_session.get("qr_active"):
        existing_token = class_session.get("qr_token")
        expires_at = class_session.get("qr_expires_at")

        if existing_token and expires_at and to_manila_time(expires_at) > now:
            return jsonify(
                {
                    "success": True,
                    "message": "Attendance is already active.",
                    "session_id": str(class_session["_id"]),
                    "qr_token": existing_token,
                    "qr_image": generate_qr_image(existing_token),
                    "expires_at": to_manila_time(expires_at).isoformat(),
                }
            )

    token = generate_qr_token()
    token_expiry = now + timedelta(seconds=3)

    if class_session:
        class_sessions_collection.update_one(
            {"_id": class_session["_id"]},
            {
                "$set": {
                    "status": "Ongoing",
                    "qr_active": True,
                    "qr_token": token,
                    "qr_expires_at": token_expiry,
                    "scheduled_start": scheduled_start,
                    "scheduled_end": scheduled_end,
                }
            },
        )

        class_session_id = class_session["_id"]

    else:
        new_session = {
            "assignment_id": assignment["_id"],
            "section_name": section_name,
            "subject_code": assignment["subject_code"],
            "subject_name": assignment["subject_name"],
            "attendance_date": attendance_date,
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end,
            "started_at": now,
            "status": "Ongoing",
            "qr_active": True,
            "qr_token": token,
            "qr_expires_at": token_expiry,
            "created_at": now,
        }

        result = class_sessions_collection.insert_one(new_session)

        class_session_id = result.inserted_id

    return (
        jsonify(
            {
                "success": True,
                "message": "Attendance session started.",
                "session_id": str(class_session_id),
                "qr_token": token,
                "qr_image": generate_qr_image(token),
                "expires_at": token_expiry.isoformat(),
            }
        ),
        201,
    )


@attendance.route("/get_attendance_qr", methods=["GET"])
@role_required("professor", "guidance")
def get_attendance_qr():
    section_name = request.args.get("section_name", "").strip()

    subject_code = request.args.get("subject_code", "").strip().upper()

    if not section_name or not subject_code:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Section and subject are required.",
                }
            ),
            400,
        )

    assignment = get_assignment_for_attendance(
        section_name,
        subject_code,
    )

    if not assignment:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Subject assignment not found or access denied.",
                }
            ),
            403,
        )

    now = datetime.now(MANILA_TZ)

    class_session = class_sessions_collection.find_one(
        {
            "assignment_id": assignment["_id"],
            "attendance_date": now.strftime("%Y-%m-%d"),
        }
    )

    if (
        not class_session
        or not class_session.get("qr_active")
        or class_session.get("status") != "Ongoing"
    ):
        return (
            jsonify(
                {
                    "success": False,
                    "active": False,
                    "message": "No active QR attendance session.",
                }
            ),
            404,
        )

    scheduled_end = to_manila_time(class_session["scheduled_end"])

    if now >= scheduled_end:
        class_sessions_collection.update_one(
            {"_id": class_session["_id"]},
            {
                "$set": {
                    "status": "Completed",
                    "qr_active": False,
                    "qr_token": None,
                    "qr_expires_at": None,
                }
            },
        )

        return (
            jsonify(
                {
                    "success": False,
                    "active": False,
                    "message": "The scheduled class has ended.",
                }
            ),
            400,
        )

    expires_at = class_session.get("qr_expires_at")
    token = class_session.get("qr_token")

    if not token or not expires_at or to_manila_time(expires_at) <= now:
        new_token = generate_qr_token()
        new_expiry = now + timedelta(seconds=3)

        # Replace only the expired token. Concurrent requests
        # cannot overwrite a token that another request replaced.
        updated_session = class_sessions_collection.find_one_and_update(
            {
                "_id": class_session["_id"],
                "qr_active": True,
                "status": "Ongoing",
                "qr_token": token,
                "qr_expires_at": expires_at,
            },
            {
                "$set": {
                    "qr_token": new_token,
                    "qr_expires_at": new_expiry,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if updated_session:
            class_session = updated_session
        else:
            class_session = class_sessions_collection.find_one(
                {
                    "_id": class_session["_id"],
                    "qr_active": True,
                    "status": "Ongoing",
                }
            )

            if not class_session:
                return (
                    jsonify(
                        {
                            "success": False,
                            "active": False,
                            "message": "The attendance session is no longer active.",
                        }
                    ),
                    400,
                )

        token = class_session.get("qr_token")
        expires_at = class_session.get("qr_expires_at")

    if not token or not expires_at:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Unable to retrieve the current QR token.",
                }
            ),
            500,
        )

    return jsonify(
        {
            "success": True,
            "active": True,
            "qr_token": token,
            "qr_image": generate_qr_image(token),
            "expires_at": to_manila_time(expires_at).isoformat(),
        }
    )


@attendance.route("/end_attendance_session", methods=["POST"])
@role_required("professor", "guidance")
def end_attendance_session():
    data = request.get_json(silent=True) or {}

    section_name = data.get("section_name", "").strip()
    subject_code = data.get("subject_code", "").strip().upper()

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

    assignment = get_assignment_for_attendance(
        section_name,
        subject_code,
    )

    if not assignment:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Subject assignment not found or access denied.",
                }
            ),
            403,
        )

    now = datetime.now(MANILA_TZ)

    class_session = class_sessions_collection.find_one(
        {
            "assignment_id": assignment["_id"],
            "attendance_date": now.strftime("%Y-%m-%d"),
            "qr_active": True,
            "status": "Ongoing",
        }
    )

    if not class_session:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "There is no active QR attendance session to end.",
                }
            ),
            404,
        )

    class_sessions_collection.update_one(
        {"_id": class_session["_id"]},
        {
            "$set": {
                "status": "Completed",
                "qr_active": False,
                "qr_token": None,
                "qr_expires_at": None,
                "ended_at": now,
            }
        },
    )

    return jsonify(
        {
            "success": True,
            "message": "Attendance session ended successfully.",
        }
    )


#! Attendance History
@attendance.route("/attendance_history")
@role_required("professor", "guidance")
def attendance_history_page():
    return render_template(
        "attendance_history_block.html",
        page_title="Attendance History",
        first_name=session.get("first_name", ""),
    )


@attendance.route("/get_attendance_history", methods=["GET"])
@role_required("professor", "guidance")
def get_attendance_history():
    assignment_query = {}

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

    assignments = list(subject_assignments_collection.find(assignment_query))

    assignment_ids = [assignment["_id"] for assignment in assignments]

    if not assignment_ids:
        return jsonify(
            {
                "success": True,
                "sessions": [],
            }
        )

    sessions = list(
        class_sessions_collection.find({"assignment_id": {"$in": assignment_ids}}).sort(
            [
                ("attendance_date", -1),
                ("scheduled_start", -1),
            ]
        )
    )

    now = datetime.now(MANILA_TZ)
    history = []

    for class_session in sessions:
        section_name = class_session.get("section_name", "")
        assignment_id = class_session["assignment_id"]
        attendance_date = class_session["attendance_date"]

        # Only approved students count as registered students.
        registered_students = list(
            students_collection.find(
                {
                    "section": section_name,
                    "admission_status": "Approved",
                },
                {
                    "_id": 0,
                    "id_number": 1,
                    "first_name": 1,
                    "last_name": 1,
                },
            )
        )

        registered_ids = {
            student.get("id_number", "").strip().upper()
            for student in registered_students
            if student.get("id_number")
        }

        # Unregistered visitors must not count toward attendance totals.
        records = list(
            attendance_records_collection.find(
                {
                    "assignment_id": assignment_id,
                    "attendance_date": attendance_date,
                    "is_registered": True,
                    "student_id": {"$ne": None},
                }
            )
        )

        recorded_ids = {
            str(record.get("student_id", "")).strip().upper()
            for record in records
            if str(record.get("student_id", "")).strip().upper() in registered_ids
        }

        registered_count = len(registered_ids)
        present_count = len(recorded_ids)

        scheduled_end = class_session.get("scheduled_end")

        if scheduled_end:
            scheduled_end = to_manila_time(scheduled_end)

        # Determine the displayed status from the session and records.
        if (
            class_session.get("status") == "Ongoing"
            and scheduled_end
            and now < scheduled_end
        ):
            status = "Ongoing"
        elif present_count > 0:
            status = "Completed"
        else:
            status = "DNR"

        history.append(
            {
                "session_id": str(class_session["_id"]),
                "section_name": section_name,
                "subject_code": class_session.get("subject_code", ""),
                "subject_name": class_session.get("subject_name", ""),
                "attendance_date": attendance_date,
                "status": status,
                "present_count": present_count,
                "registered_count": registered_count,
            }
        )

    return jsonify(
        {
            "success": True,
            "sessions": history,
        }
    )


@attendance.route(
    "/get_attendance_history_records",
    methods=["GET"],
)
@role_required("professor", "guidance")
def get_attendance_history_records():
    session_id = request.args.get("session_id", "").strip()

    if not ObjectId.is_valid(session_id):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid class session.",
                }
            ),
            400,
        )

    class_session = class_sessions_collection.find_one(
        {
            "_id": ObjectId(session_id),
        }
    )

    if not class_session:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Class session not found.",
                }
            ),
            404,
        )

    # Professors may only view sessions belonging to their assignments.
    if session.get("role") == "professor":
        try:
            professor_id = ObjectId(session["user_id"])
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

        assignment = subject_assignments_collection.find_one(
            {
                "_id": class_session["assignment_id"],
                "professor_id": professor_id,
            }
        )

        if not assignment:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "You do not have access to this class session.",
                    }
                ),
                403,
            )

    section_name = class_session.get("section_name", "")
    assignment_id = class_session["assignment_id"]
    attendance_date = class_session["attendance_date"]

    registered_students = list(
        students_collection.find(
            {
                "section": section_name,
                "admission_status": "Approved",
            },
            {
                "_id": 0,
                "id_number": 1,
                "first_name": 1,
                "last_name": 1,
            },
        ).sort("last_name", 1)
    )

    records = list(
        attendance_records_collection.find(
            {
                "assignment_id": assignment_id,
                "attendance_date": attendance_date,
                "is_registered": True,
                "student_id": {"$ne": None},
            }
        )
    )

    registered_ids = {
        student.get("id_number", "").strip().upper()
        for student in registered_students
        if student.get("id_number")
    }

    records_by_student = {}

    for record in records:
        student_id = str(record.get("student_id", "")).strip().upper()

        if student_id in registered_ids:
            # One attendance entry per registered student.
            records_by_student.setdefault(student_id, record)

    attendance_list = []

    for student in registered_students:
        student_id = student.get("id_number", "").strip().upper()

        if not student_id:
            continue

        record = records_by_student.get(student_id)

        student_name = (
            f"{student.get('first_name', '')} " f"{student.get('last_name', '')}"
        ).strip()

        attendance_list.append(
            {
                "student_name": student_name,
                "student_id": student_id,
                "time_in": record.get("time_in", "-") if record else "-",
                "status": record.get("status", "Absent") if record else "Absent",
            }
        )

    present_count = len(records_by_student)
    registered_count = len(attendance_list)

    return jsonify(
        {
            "success": True,
            "session": {
                "section_name": section_name,
                "subject_code": class_session.get("subject_code", ""),
                "subject_name": class_session.get("subject_name", ""),
                "attendance_date": attendance_date,
                "status": class_session.get("status", ""),
            },
            "summary": {
                "present": present_count,
                "absent": registered_count - present_count,
                "registered": registered_count,
            },
            "records": attendance_list,
        }
    )
