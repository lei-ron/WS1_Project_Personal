from functools import wraps
from bson import ObjectId

from flask import Blueprint, jsonify, request, session

from database.db import (
    students_collection,
    professors_collection,
    guidance_collection,
)

device_security = Blueprint("device_security", __name__)

USER_COLLECTIONS = {
    "student": students_collection,
    "professor": professors_collection,
    "guidance": guidance_collection,
}


def get_user_collection(role):
    return USER_COLLECTIONS.get(role)


def get_user_by_id(user_id, role):
    collection = get_user_collection(role)

    if collection is None:
        return None

    try:
        return collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None


def validate_active_session():
    user_id = session.get("user_id")
    role = session.get("role")
    session_token = session.get("session_token")
    device_id = session.get("device_id")

    if not all([user_id, role, session_token, device_id]):
        return False

    user = get_user_by_id(user_id, role)

    if not user:
        return False

    return (
        user.get("registered_device_id") == device_id
        and user.get("active_session_token") == session_token
    )


def device_session_required(view_function):
    @wraps(view_function)
    def wrapper(*args, **kwargs):
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

        if not validate_active_session():
            session.clear()

            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Your session is invalid or expired. Please log in again.",
                    }
                ),
                401,
            )

        return view_function(*args, **kwargs)

    return wrapper


@device_security.route("/reset-device/<user_id>", methods=["POST"])
@device_session_required
def reset_device(user_id):
    if session.get("role") != "guidance":
        return (
            jsonify(
                {
                    "success": False,
                    "message": "You are not authorized to reset device registrations.",
                }
            ),
            403,
        )

    target_role = request.form.get("role", "").strip().lower()
    target_collection = get_user_collection(target_role)

    if target_role == "guidance":
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Guidance account device registrations cannot be reset here.",
                }
            ),
            403,
        )

    if target_collection is None:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid account role.",
                }
            ),
            400,
        )

    try:
        target_id = ObjectId(user_id)
    except Exception:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid user ID.",
                }
            ),
            400,
        )

    target_user = target_collection.find_one({"_id": target_id})

    if not target_user:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Account not found.",
                }
            ),
            404,
        )

    target_collection.update_one(
        {"_id": target_id},
        {
            "$unset": {
                "registered_device_id": "",
                "active_session_token": "",
            }
        },
    )

    return jsonify(
        {
            "success": True,
            "message": "Device registration reset successfully.",
        }
    )


@device_security.route("/device-registrations", methods=["GET"])
@device_session_required
def get_device_registrations():
    if session.get("role") != "guidance":
        return (
            jsonify(
                {
                    "success": False,
                    "message": "You are not authorized to view device registrations.",
                }
            ),
            403,
        )

    accounts = []

    for role, collection in [
        ("student", students_collection),
        ("professor", professors_collection),
    ]:
        users = collection.find(
            {},
            {
                "_id": 1,
                "id_number": 1,
                "first_name": 1,
                "last_name": 1,
                "registered_device_id": 1,
            },
        )

        for user in users:
            accounts.append(
                {
                    "user_id": str(user["_id"]),
                    "id_number": user.get("id_number", ""),
                    "first_name": user.get("first_name", ""),
                    "last_name": user.get("last_name", ""),
                    "role": role,
                    "device_registered": bool(user.get("registered_device_id")),
                }
            )

    accounts.sort(
        key=lambda account: (
            account["role"],
            account["last_name"].lower(),
            account["first_name"].lower(),
        )
    )

    return jsonify(
        {
            "success": True,
            "accounts": accounts,
        }
    )
