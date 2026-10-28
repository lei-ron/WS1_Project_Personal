import os

from dotenv import load_dotenv
from flask import Flask
from routes.users import users
from routes.academic import academic
from routes.admissions import admissions
from routes.registration import registration
from routes.dashboard import dashboard
from routes.attendance import attendance

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

app.register_blueprint(users)
app.register_blueprint(academic)
app.register_blueprint(admissions)
app.register_blueprint(registration)
app.register_blueprint(dashboard)
app.register_blueprint(attendance)

print("\nREGISTERED ROUTES:")

for rule in app.url_map.iter_rules():
    print(f"{rule.rule:40} -> {rule.endpoint}")


if __name__ == "__main__":
    print("\nQR ATTENDANCE ROUTES:")

    for rule in app.url_map.iter_rules():
        if "attendance" in rule.rule:
            print(rule.rule, "->", rule.endpoint)

    app.run(debug=True)
