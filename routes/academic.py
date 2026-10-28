from datetime import datetime
from bson import ObjectId
from flask import Blueprint, jsonify, render_template, request, session

from database.db import (
    programs_collection,
    sections_collection,
    subjects_collection,
    professors_collection,
    subject_assignments_collection,
)

from routes.permissions import role_required

academic = Blueprint("academic", __name__)


#! Programs Manager


@academic.route("/programs_manager")
@role_required("guidance")
def programs_manager():

    return render_template(
        "programs_manager_block.html",
        page_title="Programs Manager",
    )


#! Sections Manager


@academic.route("/sections_manager")
@role_required("guidance")
def sections_manager():

    return render_template(
        "sections_manager_block.html",
        page_title="Sections Manager",
    )


#! Subjects Manager


@academic.route("/subjects_manager")
@role_required("guidance")
def subjects_manager():

    return render_template(
        "subjects_manager_block.html",
        page_title="Subjects Manager",
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


#! Register Subject
@academic.route("/register_subject", methods=["POST"])
@role_required("guidance")
def register_subject():
    program_codes = [
        code.strip().upper()
        for code in request.form.getlist("program_codes")
        if code.strip()
    ]

    subject_code = request.form.get("subject_code", "").strip().upper()
    subject_name = request.form.get("subject_name", "").strip()

    if not program_codes or not subject_code or not subject_name:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please complete all subject fields.",
                }
            ),
            400,
        )

    if len(program_codes) != len(set(program_codes)):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Duplicate program selections are not allowed.",
                }
            ),
            400,
        )

    for program_code in program_codes:
        program = programs_collection.find_one({"program_code": program_code})

        if not program:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Program {program_code} does not exist.",
                    }
                ),
                400,
            )

    existing_subject = subjects_collection.find_one(
        {
            "subject_code": subject_code,
            "$or": [
                {"program_codes": {"$in": program_codes}},
                {
                    "program_code": {"$in": program_codes},
                    "program_codes": {"$exists": False},
                },
            ],
        }
    )

    if existing_subject:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This subject code is already registered for one or more selected programs.",
                }
            ),
            409,
        )

    subjects_collection.insert_one(
        {
            "program_codes": program_codes,
            "subject_code": subject_code,
            "subject_name": subject_name,
        }
    )

    return jsonify(
        {
            "success": True,
            "message": "Subject registered successfully.",
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


#! Get Professors for Subject Assignment
@academic.route("/get_assignment_professors")
@role_required("guidance")
def get_assignment_professors():
    professors = list(
        professors_collection.find(
            {},
            {
                "_id": 1,
                "first_name": 1,
                "last_name": 1,
            },
        )
    )

    for professor in professors:
        professor["_id"] = str(professor["_id"])

    return jsonify({"professors": professors})


#! Get Subjects for Selected Section
@academic.route("/get_section_subjects")
@role_required("guidance")
def get_section_subjects():
    section_name = request.args.get("section_name", "").strip().upper()

    if not section_name:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please select a section.",
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
            404,
        )

    subjects = list(
        subjects_collection.find(
            {
                "$or": [
                    {"program_codes": section["program_code"]},
                    {
                        "program_code": section["program_code"],
                        "program_codes": {"$exists": False},
                    },
                ]
            },
            {
                "_id": 0,
                "program_codes": 1,
                "program_code": 1,
                "subject_code": 1,
                "subject_name": 1,
            },
        )
    )

    return jsonify({"subjects": subjects})


#! Register Subject Assignment
@academic.route("/register_subject_assignment", methods=["POST"])
@role_required("guidance")
def register_subject_assignment():

    section_name = request.form.get("section_name", "").strip().upper()
    subject_code = request.form.get("subject_code", "").strip().upper()
    professor_id = request.form.get("professor_id", "").strip()
    days = request.form.getlist("days")
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    building = request.form.get("building", "").strip().upper()
    room_number = request.form.get("room_number", "").strip()

    if not all(
        [
            section_name,
            subject_code,
            professor_id,
            days,
            start_time,
            end_time,
            building,
            room_number,
        ]
    ):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please complete all assignment fields.",
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

    subject = subjects_collection.find_one(
        {
            "subject_code": subject_code,
            "$or": [
                {"program_codes": section["program_code"]},
                {
                    "program_code": section["program_code"],
                    "program_codes": {"$exists": False},
                },
            ],
        }
    )

    if not subject:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "The selected subject does not belong to this section's program.",
                }
            ),
            400,
        )

    if not ObjectId.is_valid(professor_id):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid professor selection.",
                }
            ),
            400,
        )

    professor = professors_collection.find_one({"_id": ObjectId(professor_id)})

    if not professor:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "The selected professor does not exist.",
                }
            ),
            400,
        )

    valid_days = {
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    }

    if not set(days).issubset(valid_days):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid day selection.",
                }
            ),
            400,
        )

    if len(days) != len(set(days)):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Duplicate days are not allowed.",
                }
            ),
            400,
        )

    try:
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
    except ValueError:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid time format.",
                }
            ),
            400,
        )

    if start >= end:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Time Out must be later than Time In.",
                }
            ),
            400,
        )

    if building not in {"B1", "B2", "B3", "B4"}:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please select a valid building.",
                }
            ),
            400,
        )

    try:
        room_number = int(room_number)
    except ValueError:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Room number must be a valid number.",
                }
            ),
            400,
        )

    if room_number < 1:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Room number must be greater than zero.",
                }
            ),
            400,
        )

    existing_assignment = subject_assignments_collection.find_one(
        {
            "section_name": section_name,
            "subject_code": subject_code,
        }
    )

    if existing_assignment:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "This subject already has an assignment in this section.",
                }
            ),
            409,
        )

    subject_assignments_collection.insert_one(
        {
            "section_name": section_name,
            "program_code": section["program_code"],
            "subject_code": subject_code,
            "subject_name": subject["subject_name"],
            "professor_id": ObjectId(professor_id),
            "days": days,
            "start_time": start_time,
            "end_time": end_time,
            "building": building,
            "room_number": room_number,
        }
    )

    return jsonify(
        {
            "success": True,
            "message": "Subject assignment registered successfully.",
        }
    )


# Get Programs for Registration
@academic.route("/get_registration_programs")
def get_registration_programs():
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


# Get Sections for Registration
@academic.route("/get_registration_sections")
def get_registration_sections():
    sections = list(
        sections_collection.find(
            {},
            {
                "_id": 0,
                "program_code": 1,
                "year_level": 1,
                "current_trimester": 1,
                "section_name": 1,
            },
        )
    )

    return jsonify({"sections": sections})
