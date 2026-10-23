import os

from dotenv import load_dotenv
from flask import Flask

from routes.users import users
from routes.academic import academic
from routes.admissions import admissions

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

app.register_blueprint(users)
app.register_blueprint(academic)
app.register_blueprint(admissions)

if __name__ == "__main__":
    app.run(debug=True)
