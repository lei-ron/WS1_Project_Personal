from datetime import datetime, timedelta
from bson import ObjectId
from flask import (
    Blueprint,
    redirect,
    render_template,
    session,
    url_for,
)
from database.db import (
    students_collection,
    professors_collection,
    guidance_collection,
    subject_assignments_collection,
)
from routes.permissions import role_required

dashboard = Blueprint("dashboard", __name__)


#! Dashboard
@dashboard.route("/dashboard")
@role_required("student", "professor", "guidance")
def dashboard_page():
    if "user_id" not in session:
        return redirect(url_for("users.home"))

    user_id = ObjectId(session["user_id"])
    role = session.get("role")

    if role == "professor":
        user = professors_collection.find_one({"_id": user_id})

        assignments = list(
            subject_assignments_collection.find({"professor_id": user_id})
        )

    elif role == "guidance":
        user = guidance_collection.find_one({"_id": user_id})
        assignments = []

    elif role == "student":
        user = students_collection.find_one({"_id": user_id})
        assignments = []

    else:
        session.clear()
        return redirect(url_for("users.home"))

    if not user:
        session.clear()
        return redirect(url_for("users.home"))

    # Students must have approved accounts.
    if role == "student" and user.get("admission_status", "Pending") != "Approved":
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
        role=role,
    )
