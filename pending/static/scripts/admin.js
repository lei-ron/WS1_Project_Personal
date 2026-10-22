const API_BASE = "mongodb://felipejrnoriel_db_user:<db_password>@ac-wdhm5g7-shard-00-00.8nhcswv.mongodb.net:27017,ac-wdhm5g7-shard-00-01.8nhcswv.mongodb.net:27017,ac-wdhm5g7-shard-00-02.8nhcswv.mongodb.net:27017/?ssl=true&replicaSet=atlas-w225k0-shard-0&authSource=admin";

const studentTableBody = document.getElementById("student_table_body");
const studentForm = document.getElementById("student_form");
const studentFormPanel = document.getElementById("student_form_panel");

const showFormButton = document.getElementById("show_student_form");
const cancelFormButton = document.getElementById("cancel_student_form");
const saveButton = document.getElementById("save_student_button");

const formHeading = document.getElementById("student_form_heading");
const formMessage = document.getElementById("student_form_message");
const recordIdInput = document.getElementById("student_record_id");

const studentIdInput = document.getElementById("student_id");
const studentNameInput = document.getElementById("student_name");
const programInput = document.getElementById("student_program");
const yearInput = document.getElementById("student_year");
const sectionInput = document.getElementById("student_section");
const emailInput = document.getElementById("student_email");
const statusInput = document.getElementById("student_account_status");

const statusFilter = document.getElementById("student_status_filter");

const totalStudentsElement = document.getElementById("total_students");
const activeStudentsElement = document.getElementById("active_students");
const studentCountLabel = document.getElementById("student_count_label");

let students = [];
let editingId = null;
let isLoading = false;

function escapeHTML(value = "") {
    return String(value).replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[character]);
}

function normalizeStatus(status) {
    return String(status || "active").toLowerCase() === "inactive"
        ? "inactive"
        : "active";
}

function getStudentRecordId(student) {
    return String(
        student.record_id ??
        student._id ??
        student.id ??
        student.student_id ??
        ""
    );
}

function getStudentName(student) {
    return student.student_name ?? student.name ?? "";
}

function getStudentId(student) {
    return student.student_id ?? "";
}

function getStudentProgram(student) {
    return student.program ?? "";
}

function getStudentYear(student) {
    return student.year_level ?? "";
}

function getStudentSection(student) {
    return student.section ?? "";
}

function getStudentEmail(student) {
    return student.email ?? "";
}

function getStudentStatus(student) {
    return normalizeStatus(student.status);
}

function extractStudents(data) {
    if (Array.isArray(data)) {
        return data;
    }

    if (Array.isArray(data.students)) {
        return data.students;
    }

    return [];
}

async function readResponse(response) {
    const text = await response.text();

    if (!text) {
        return {};
    }

    try {
        return JSON.parse(text);
    } catch {
        throw new Error(
            "The server returned an invalid response. Check your Flask API."
        );
    }
}

function showMessage(message, type = "success") {
    formMessage.textContent = message;
    formMessage.className = `form-message ${type}`;
}

function clearMessage() {
    formMessage.textContent = "";
    formMessage.className = "form-message";
}

function updateStudentCounters() {
    totalStudentsElement.textContent = students.length;

    activeStudentsElement.textContent = students.filter(
        student => getStudentStatus(student) === "active"
    ).length;
}

function getVisibleStudents() {
    const selectedStatus = statusFilter.value;

    return students.filter(student => {
        return selectedStatus === "all" ||
            getStudentStatus(student) === selectedStatus;
    });
}

function renderStudents() {
    updateStudentCounters();

    const visibleStudents = getVisibleStudents();

    studentCountLabel.textContent =
        `Showing ${visibleStudents.length} of ${students.length} students`;

    if (visibleStudents.length === 0) {
        studentTableBody.innerHTML = `
            <tr>
                <td colspan="6" class="table-empty">
                    ${
                        students.length === 0
                            ? "No student accounts available."
                            : "No students match the selected filter."
                    }
                </td>
            </tr>
        `;

        return;
    }

    studentTableBody.innerHTML = visibleStudents.map(student => {
        const recordId = getStudentRecordId(student);
        const studentId = getStudentId(student);
        const name = getStudentName(student);
        const program = getStudentProgram(student);
        const year = getStudentYear(student);
        const section = getStudentSection(student);
        const status = getStudentStatus(student);

        return `
            <tr>
                <td>${escapeHTML(studentId)}</td>
                <td>${escapeHTML(name)}</td>
                <td>${escapeHTML(program)}</td>
                <td>
                    ${escapeHTML(year)}
                    ${year && section ? " / " : ""}
                    ${escapeHTML(section)}
                </td>
                <td>
                    <span class="status ${status}">
                        ${status === "active" ? "Active" : "Inactive"}
                    </span>
                </td>
                <td>
                    <div class="actions">
                        <button
                            class="icon-button edit-button"
                            type="button"
                            data-action="edit"
                            data-id="${escapeHTML(recordId)}"
                            aria-label="Edit ${escapeHTML(name)}"
                            title="Edit student"
                        >✎</button>
                        <button
                            class="icon-button delete-button"
                            type="button"
                            data-action="delete"
                            data-id="${escapeHTML(recordId)}"
                            aria-label="Delete ${escapeHTML(name)}"
                            title="Delete student"
                        >🗑</button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");
}

async function loadStudents() {
    if (isLoading) {
        return;
    }
}