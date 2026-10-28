from flask import Blueprint, render_template, request, session, jsonify, url_for
from database.db import (
    students_collection,
    professors_collection,
    guidance_collection,
)
from werkzeug.security import check_password_hash

users = Blueprint("users", __name__)


@users.route("/")
def home():
    return render_template("index.html")


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

        # Redirect users based on their role.
        if role == "student":
            redirect_url = url_for("attendance.student_attendance")
            message = "Login successful! Redirecting to attendance."

        elif role == "professor":
            redirect_url = url_for("dashboard.dashboard_page")
            message = "Login successful! Redirecting to overview."

        elif role == "guidance":
            redirect_url = url_for("dashboard.dashboard_page")
            message = "Login successful! Redirecting to overview."

        else:
            return jsonify({"success": False, "message": "Invalid account role."}), 403

        return jsonify(
            {
                "success": True,
                "message": message,
                "redirect_url": redirect_url,
            }
        )
