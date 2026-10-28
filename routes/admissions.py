import os

from bson import ObjectId
from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from datetime import datetime

from database.db import students_collection

from email_service import send_email

from routes.permissions import role_required

admissions = Blueprint("admissions", __name__)

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "uploads",
    "orf_documents",
)


#! Admission Management
@admissions.route("/admissions")
@role_required("guidance")
def admissions_page():
    if "user_id" not in session:
        return redirect(url_for("users.home"))

    if session.get("role") != "guidance":
        abort(403)

    students = list(
        students_collection.find(
            {},
            {"password": 0},
        ).sort("last_name", 1)
    )

    return render_template(
        "admissions_block.html",
        page_title="Admissions",
        first_name=session.get("first_name", ""),
        students=students,
    )


#! View Student ORF
@admissions.route("/admissions/orf/<student_id>")
@role_required("guidance")
def view_orf(student_id):
    if "user_id" not in session:
        return redirect(url_for("users.home"))

    if session.get("role") != "guidance":
        abort(403)

    if not ObjectId.is_valid(student_id):
        abort(404)

    student = students_collection.find_one(
        {"_id": ObjectId(student_id)},
        {"latest_orf": 1},
    )

    if not student:
        abort(404)

    orf = student.get("latest_orf", {})
    filename = orf.get("filename") if orf else None

    if not filename or not filename.endswith(".pdf"):
        abort(404)

    return send_from_directory(
        UPLOAD_FOLDER,
        filename,
        mimetype="application/pdf",
        as_attachment=False,
    )


#! Review Student Admission
@admissions.route("/admissions/review/<student_id>", methods=["POST"])
@role_required("guidance")
def review_admission(student_id):
    if "user_id" not in session:
        return redirect(url_for("users.home"))

    if session.get("role") != "guidance":
        abort(403)

    if not ObjectId.is_valid(student_id):
        abort(404)

    status = request.form.get("status", "").strip()
    remarks = request.form.get("remarks", "").strip()

    if status not in ["Approved", "Rejected"]:
        abort(400)

    if status == "Rejected" and not remarks:
        return redirect(url_for("admissions.admissions_page"))

    student = students_collection.find_one(
        {
            "_id": ObjectId(student_id),
            "admission_status": "Pending",
        }
    )

    if not student:
        return redirect(url_for("admissions.admissions_page"))

    result = students_collection.update_one(
        {
            "_id": student["_id"],
            "admission_status": "Pending",
        },
        {
            "$set": {
                "admission_status": status,
                "admission_remarks": remarks if status == "Rejected" else "",
                "reviewed_by": session.get("user_id"),
                "reviewed_at": datetime.now(),
            }
        },
    )

    if result.modified_count == 1 and student.get("email"):
        first_name = student.get("first_name", "Student")

        if status == "Approved":
            subject = "Admission Approved - WS1 Attendance System"

            body = f"""
Hello, {first_name}!

Your admission application for the WS1 Attendance Management System
has been approved.

You can now log in to your account using your registered credentials.

Thank you for registering!

WS1 Attendance Management System
"""
        else:
            subject = "Admission Update - WS1 Attendance System"

            body = f"""
Hello, {first_name}!

Your admission application for the WS1 Attendance Management System
has been rejected.

Reason provided by the Guidance Office:
{remarks}

If you have questions regarding this decision, please contact the
Guidance Office.

WS1 Attendance Management System
"""

        try:
            send_email(
                student["email"],
                subject,
                body,
            )

        except Exception:
            current_app.logger.exception(
                "Admission status updated, but the notification email "
                "could not be sent to student %s.",
                student_id,
            )

    return redirect(url_for("admissions.admissions_page"))
