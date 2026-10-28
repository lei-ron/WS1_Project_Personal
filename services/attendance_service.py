from datetime import datetime, time
from zoneinfo import ZoneInfo

from database.db import (
    subject_assignments_collection,
    class_sessions_collection,
    attendance_records_collection,
)

MANILA_TZ = ZoneInfo("Asia/Manila")


def process_class_sessions():
    now = datetime.now(MANILA_TZ)
    today = now.strftime("%Y-%m-%d")
    current_day = now.strftime("%A")

    assignments = subject_assignments_collection.find(
        {
            "days": current_day,
        }
    )

    for assignment in assignments:
        try:
            start_time = datetime.strptime(assignment["start_time"], "%H:%M").time()

            end_time = datetime.strptime(assignment["end_time"], "%H:%M").time()

            scheduled_start = datetime.combine(
                now.date(),
                start_time,
                tzinfo=MANILA_TZ,
            )

            scheduled_end = datetime.combine(
                now.date(),
                end_time,
                tzinfo=MANILA_TZ,
            )

            # Ignore classes that have not started yet.
            if now < scheduled_start:
                continue

            session_query = {
                "assignment_id": assignment["_id"],
                "attendance_date": today,
            }

            class_session = class_sessions_collection.find_one(session_query)

            # Create a session if one does not exist.
            if not class_session:
                initial_status = "Ongoing" if now < scheduled_end else "DNR"

                new_session = {
                    "assignment_id": assignment["_id"],
                    "section_name": assignment["section_name"],
                    "subject_code": assignment["subject_code"],
                    "subject_name": assignment["subject_name"],
                    "attendance_date": today,
                    "scheduled_start": scheduled_start,
                    "scheduled_end": scheduled_end,
                    "started_at": scheduled_start,
                    "status": initial_status,
                    "qr_active": False,
                    "qr_token": None,
                    "qr_expires_at": None,
                    "created_at": now,
                }

                class_sessions_collection.update_one(
                    session_query,
                    {"$setOnInsert": new_session},
                    upsert=True,
                )

                class_session = class_sessions_collection.find_one(session_query)

            if not class_session:
                continue

            # Do not change sessions that the professor manually ended.
            if class_session.get("status") != "Ongoing":
                continue

            # Keep the session active until its scheduled end.
            if now < scheduled_end:
                continue

            # Check whether any attendance records exist for this class.
            has_records = (
                attendance_records_collection.find_one(
                    {
                        "assignment_id": assignment["_id"],
                        "attendance_date": today,
                    }
                )
                is not None
            )

            final_status = "Completed" if has_records else "DNR"

            class_sessions_collection.update_one(
                {
                    "_id": class_session["_id"],
                    "status": "Ongoing",
                },
                {
                    "$set": {
                        "status": final_status,
                        "qr_active": False,
                        "qr_token": None,
                        "qr_expires_at": None,
                        "ended_at": now,
                    }
                },
            )

        except (KeyError, TypeError, ValueError):
            # Skip assignments with incomplete or invalid schedules.
            continue
