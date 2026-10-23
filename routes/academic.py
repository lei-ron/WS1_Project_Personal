import re

from flask import Blueprint, jsonify, request, session

from database.db import (
    programs_collection,
    sections_collection,
    subjects_collection,
)

from routes.permissions import role_required

academic = Blueprint("academic", __name__)


#! Programs Manager
@academic.route("/program_manager")
@role_required("guidance")
def program_manager():
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

    programs = list(programs_collection.find({}, {"_id": 0}))

    from flask import render_template

    return render_template(
        "program_manager_block.html",
        page_title="Program Manager",
        programs=programs,
    )


#! Register Program
@academic.route("/register_program", methods=["POST"])
@role_required("guidance")
def register_program():
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

    program_code = request.form.get("program_code", "").strip().upper()
    program_name = request.form.get("program_name", "").strip()
    year_levels = request.form.get("year_levels", "")

    if not program_code or not program_name or not year_levels:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please complete all program fields.",
                }
            ),
            400,
        )

    try:
        year_levels = int(year_levels)
    except ValueError:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid number of year levels.",
                }
            ),
            400,
        )

    if year_levels not in range(1, 5):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Year levels must be between 1 and 4.",
                }
            ),
            400,
        )

    if programs_collection.find_one({"program_code": program_code}):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This program code is already registered.",
                }
            ),
            409,
        )

    programs_collection.insert_one(
        {
            "program_code": program_code,
            "program_name": program_name,
            "year_levels": year_levels,
        }
    )

    return jsonify(
        {
            "success": True,
            "message": "Program registered successfully.",
        }
    )


#! Get Programs
@academic.route("/get_programs")
@role_required("guidance")
def get_programs():
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

    programs = list(
        programs_collection.find(
            {},
            {
                "_id": 0,
                "program_code": 1,
                "program_name": 1,
                "year_levels": 1,
            },
        )
    )

    return jsonify({"programs": programs})


#! Register Section
@academic.route("/register_section", methods=["POST"])
@role_required("guidance")
def register_section():
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

    program_code = request.form.get("program", "").strip().upper()
    learning_modality = request.form.get("learning_modality", "").strip().upper()
    campus = request.form.get("campus", "").strip().upper()
    year_level = request.form.get("year_level", "").strip()
    current_trimester = request.form.get("current_trimester", "").strip()
    trimester_period = request.form.get("trimester_period", "").strip()
    section_session = request.form.get("session", "").strip().upper()
    section_number = request.form.get("section_number", "").strip()
    section_name = request.form.get("section_name", "").strip().upper()

    if not all(
        [
            program_code,
            learning_modality,
            campus,
            year_level,
            current_trimester,
            trimester_period,
            section_session,
            section_number,
            section_name,
        ]
    ):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please complete all section fields.",
                }
            ),
            400,
        )

    program = programs_collection.find_one({"program_code": program_code})

    if not program:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "The selected program does not exist.",
                }
            ),
            400,
        )

    try:
        year_level = int(year_level)
        current_trimester = int(current_trimester)
        trimester_period = int(trimester_period)
        section_number = int(section_number)
    except ValueError:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid section details.",
                }
            ),
            400,
        )

    if not 1 <= year_level <= program["year_levels"]:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid year level for the selected program.",
                }
            ),
            400,
        )

    if current_trimester not in range(1, 4) or trimester_period not in range(1, 4):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Trimester values must be between 1 and 3.",
                }
            ),
            400,
        )

    if not 1 <= section_number <= 999:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Section number must be between 1 and 999.",
                }
            ),
            400,
        )

    if sections_collection.find_one({"section_name": section_name}):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This section is already registered.",
                }
            ),
            409,
        )

    sections_collection.insert_one(
        {
            "program_code": program_code,
            "learning_modality": learning_modality,
            "campus": campus,
            "year_level": year_level,
            "current_trimester": current_trimester,
            "trimester_period": trimester_period,
            "session": section_session,
            "section_number": section_number,
            "section_name": section_name,
        }
    )

    return jsonify(
        {
            "success": True,
            "message": "Section registered successfully.",
        }
    )


#! Get Sections
@academic.route("/get_sections")
@role_required("guidance")
def get_sections():
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

    sections = list(sections_collection.find({}, {"_id": 0}))

    return jsonify({"sections": sections})


#! Register Subject
@academic.route("/register_subject", methods=["POST"])
@role_required("guidance")
def register_subject():
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

    subject_code = request.form.get("subject_code", "").strip().upper()
    subject_name = request.form.get("subject_name", "").strip()
    schedule = request.form.get("schedule", "").strip()
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    building = request.form.get("building", "").strip().upper()
    room_number = request.form.get("room_number", "").strip()
    section_name = request.form.get("section", "").strip().upper()

    if not all(
        [
            subject_code,
            subject_name,
            schedule,
            start_time,
            end_time,
            building,
            room_number,
            section_name,
        ]
    ):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please complete all subject fields.",
                }
            ),
            400,
        )

    if building not in ["B1", "B2", "B3", "B4"]:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid building selection.",
                }
            ),
            400,
        )

    if not room_number.isdigit() or int(room_number) < 1:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Room number must be a positive number.",
                }
            ),
            400,
        )

    # Validate 24-hour HH:MM time format.
    time_pattern = r"^(?:[01]\d|2[0-3]):[0-5]\d$"

    if not re.fullmatch(time_pattern, start_time) or not re.fullmatch(
        time_pattern, end_time
    ):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please enter valid start and end times.",
                }
            ),
            400,
        )

    if start_time >= end_time:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "End time must be later than start time.",
                }
            ),
            400,
        )

    section = sections_collection.find_one({"section_name": section_name})

    if not section:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "The selected section does not exist.",
                }
            ),
            400,
        )

    if subjects_collection.find_one({"subject_code": subject_code}):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This subject code is already registered.",
                }
            ),
            409,
        )

    subjects_collection.insert_one(
        {
            "subject_code": subject_code,
            "subject_name": subject_name,
            "schedule": schedule,
            "start_time": start_time,
            "end_time": end_time,
            "building": building,
            "room_number": int(room_number),
            "section": section_name,
        }
    )

    return jsonify(
        {
            "success": True,
            "message": "Subject registered successfully.",
        }
    )


#! Get Subjects
@academic.route("/get_subjects")
@role_required("guidance")
def get_subjects():
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

    subjects = list(subjects_collection.find({}, {"_id": 0}))

    return jsonify({"subjects": subjects})
