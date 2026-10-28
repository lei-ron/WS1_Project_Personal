import secrets

from flask import (
    Blueprint,
    render_template,
    request,
    session,
    jsonify,
    url_for,
    redirect,
)

from database.db import (
    students_collection,
    professors_collection,
    guidance_collection,
)

from werkzeug.security import check_password_hash

users = Blueprint("users", __name__)


#! Landing Page
@users.route("/")
def home():
    return render_template("index.html")


#! Login Form
@users.route("/login", methods=["POST"])
def login():
    id_number = request.form.get("id_number", "").strip().upper()
    password = request.form.get("password", "")
    device_id = request.form.get("device_id", "").strip()

    # Validate the browser identifier.
    if not device_id or len(device_id) > 128:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Device identification failed. Please refresh the page and try again.",
                }
            ),
            400,
        )

    # Find the account.
    user = students_collection.find_one({"id_number": id_number})

    if not user:
        user = professors_collection.find_one({"id_number": id_number})

    if not user:
        user = guidance_collection.find_one({"id_number": id_number})

    # Verify the password.
    if not user or not check_password_hash(user["password"], password):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid ID number or password.",
                }
            ),
            401,
        )

    # Determine the account role.
    role = (user.get("role") or "").strip().lower()

    if not role:
        if students_collection.find_one({"_id": user["_id"]}):
            role = "student"
        elif professors_collection.find_one({"_id": user["_id"]}):
            role = "professor"
        elif guidance_collection.find_one({"_id": user["_id"]}):
            role = "guidance"

    # Verify that the account has a supported role.
    user_collections = {
        "student": students_collection,
        "professor": professors_collection,
        "guidance": guidance_collection,
    }

    collection = user_collections.get(role)

    collection = user_collections.get(role)

    if collection is None:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid account role.",
                }
            ),
            403,
        )

    # Check student admission status.
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

    # Generate a new server-side session token.
    session_token = secrets.token_urlsafe(32)

    # Register the device if this is the account's first login.
    # Existing registrations can only be used by the same device.
    result = collection.update_one(
        {
            "_id": user["_id"],
            "$or": [
                {"registered_device_id": {"$exists": False}},
                {"registered_device_id": None},
                {"registered_device_id": device_id},
            ],
        },
        {
            "$set": {
                "registered_device_id": device_id,
                "active_session_token": session_token,
            }
        },
    )

    if result.matched_count == 0:
        return (
            jsonify(
                {
                    "success": False,
                    "message": (
                        "This account is registered to another device. "
                        "Please contact the guidance office to reset your device registration."
                    ),
                }
            ),
            403,
        )

    # Create the Flask login session.
    session.clear()

    session["user_id"] = str(user["_id"])
    session["id_number"] = user["id_number"]
    session["role"] = role
    session["first_name"] = user.get("first_name", "")
    session["device_id"] = device_id
    session["session_token"] = session_token

    # Redirect according to the account role.
    if role == "student":
        redirect_url = url_for("attendance.student_attendance")
        message = "Login successful! Redirecting to attendance."

    elif role == "professor":
        redirect_url = url_for("dashboard.dashboard_page")
        message = "Login successful! Redirecting to overview."

    elif role == "guidance":
        redirect_url = url_for("admissions.admissions_page")
        message = "Login successful! Redirecting to admissions."

    return jsonify(
        {
            "success": True,
            "message": message,
            "redirect_url": redirect_url,
        }
    )


#! Logout
@users.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()

    return redirect(url_for("users.home"))
