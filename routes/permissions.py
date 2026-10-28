from functools import wraps

from flask import abort, redirect, url_for, session

from routes.device_security import validate_active_session


def role_required(*allowed_roles):
    def decorator(view_function):
        @wraps(view_function)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("users.home"))

            if not validate_active_session():
                session.clear()
                return redirect(url_for("users.home"))

            if session.get("role") not in allowed_roles:
                abort(403)

            return view_function(*args, **kwargs)

        return wrapper

    return decorator
