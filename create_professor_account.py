from getpass import getpass

from werkzeug.security import generate_password_hash

from database.db import (
    students_collection,
    professors_collection,
    guidance_collection,
)

print("Create Professor Account")

first_name = input("First name: ").strip().upper()
last_name = input("Last name: ").strip().upper()
id_number = input("ID number: ").strip().upper()
email = input("Email: ").strip().lower()
password = getpass("Password: ")
confirm_password = getpass("Confirm password: ")

if not all([first_name, last_name, id_number, email, password]):
    print("Error: All fields are required.")

elif password != confirm_password:
    print("Error: Passwords do not match.")

elif len(password) < 8:
    print("Error: Password must contain at least 8 characters.")

elif (
    students_collection.find_one(
        {
            "$or": [
                {"id_number": id_number},
                {"email": email},
            ]
        }
    )
    or professors_collection.find_one(
        {
            "$or": [
                {"id_number": id_number},
                {"email": email},
            ]
        }
    )
    or guidance_collection.find_one(
        {
            "$or": [
                {"id_number": id_number},
                {"email": email},
            ]
        }
    )
):
    print("Error: The ID number or email is already registered.")

else:
    professors_collection.insert_one(
        {
            "first_name": first_name,
            "last_name": last_name,
            "id_number": id_number,
            "email": email,
            "password": generate_password_hash(password),
            "role": "professor",
        }
    )

    print("Professor account created successfully.")
