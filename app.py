import os

from dotenv import load_dotenv
from flask import Flask
from routes.users import users
from routes.academic import academic
from routes.admissions import admissions
from routes.registration import registration
from routes.dashboard import dashboard
from routes.attendance import attendance
from apscheduler.schedulers.background import BackgroundScheduler
from services.attendance_service import process_class_sessions
from zoneinfo import ZoneInfo
from routes.device_security import (
    device_security,
)

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

app.register_blueprint(users)
app.register_blueprint(academic)
app.register_blueprint(admissions)
app.register_blueprint(registration)
app.register_blueprint(dashboard)
app.register_blueprint(attendance)
app.register_blueprint(device_security)


print("\nREGISTERED ROUTES:")

for rule in app.url_map.iter_rules():
    print(f"{rule.rule:40} -> {rule.endpoint}")


if __name__ == "__main__":
    scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Manila"))

    scheduler.add_job(
        func=process_class_sessions,
        trigger="interval",
        seconds=30,
        id="class_session_scheduler",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()

    print("\nQR ATTENDANCE ROUTES:")
    for rule in app.url_map.iter_rules():
        if "attendance" in rule.rule:
            print(rule.rule, "->", rule.endpoint)

    try:
        app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
    finally:
        scheduler.shutdown()
