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
    next_expiry = now + timedelta(seconds=30)

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
@attendance.route("/get_attendance_sections", methods=["GET"])
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


@attendance.route("/record_attendance", methods=["POST"])
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

        if now >= scheduled_end:
            session_status = "Completed"
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
    token_expiry = now + timedelta(seconds=30)

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
        new_expiry = now + timedelta(seconds=30)

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
