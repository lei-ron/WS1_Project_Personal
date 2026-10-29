const sectionSelect = document.getElementById("attendance_section");
const subjectSelect = document.getElementById("attendance_subject");
const attendanceForm = document.getElementById("attendance_form");
const studentIdInput = document.getElementById("student_id");
const notRegisteredCheckbox = document.getElementById("not_registered");
const manualNameContainer = document.getElementById("manual_name_container");
const manualFirstNameInput = document.getElementById("manual_first_name");
const manualLastNameInput = document.getElementById("manual_last_name");
const attendanceRecordsBody = document.getElementById(
  "attendance_records_body",
);

let previousAttendanceRecords = null;
let attendanceCheckInProgress = false;
let previousSubjectStatus = null;

// Load available sections.
async function loadSections() {
  try {
    const response = await fetch("/get_attendance_sections");
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message || "Failed to load sections.");
    }

    sectionSelect.innerHTML = '<option value="">Select a section</option>';

    data.sections.forEach((section) => {
      const option = document.createElement("option");

      option.value = section.section_name;

      const status = section.status || "";
      option.textContent = status
        ? `${section.section_name} (${status})`
        : section.section_name;

      sectionSelect.appendChild(option);
    });
  } catch (error) {
    console.error("Error loading sections:", error);
    alert(error.message);
  }
}

// Load subjects assigned to the selected section.
async function loadSubjects(sectionName) {
  subjectSelect.innerHTML = '<option value="">Select a subject</option>';
  subjectSelect.disabled = true;

  attendanceRecordsBody.innerHTML = `
    <tr>
      <td colspan="4">No attendance records.</td>
    </tr>
  `;

  if (!sectionName) {
    return;
  }

  try {
    const response = await fetch(
      `/get_attendance_subjects?section_name=${encodeURIComponent(sectionName)}`,
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message || "Failed to load subjects.");
    }

    if (data.subjects.length === 0) {
      subjectSelect.innerHTML =
        '<option value="">No assigned subjects</option>';
      return;
    }

    data.subjects.forEach((subject) => {
      const option = document.createElement("option");

      option.value = subject.subject_code;

      const status = subject.status || "";
      const subjectLabel = `${subject.subject_code}: ${subject.subject_name}`;

      option.textContent = status
        ? `${subjectLabel} (${status})`
        : subjectLabel;

      subjectSelect.appendChild(option);
    });

    subjectSelect.disabled = false;
  } catch (error) {
    console.error("Error loading subjects:", error);
    alert(error.message);
  }
}

// Load attendance records for the selected section and subject.
async function loadAttendanceRecords() {
  const sectionName = sectionSelect.value;
  const subjectCode = subjectSelect.value;

  if (!sectionName || !subjectCode) {
    attendanceRecordsBody.innerHTML = `
      <tr>
        <td colspan="4">No attendance records.</td>
      </tr>
    `;
    return;
  }

  try {
    const response = await fetch(
      `/get_attendance_records?section_name=${encodeURIComponent(sectionName)}&subject_code=${encodeURIComponent(subjectCode)}`,
    );

    const responseText = await response.text();

    console.log("Attendance response status:", response.status);
    console.log("Attendance response body:", responseText);

    let data;

    try {
      data = JSON.parse(responseText);
    } catch (error) {
      throw new Error(
        "The server returned an invalid response. Check the browser console for details.",
      );
    }

    if (!response.ok) {
      throw new Error(data.message || "Failed to load attendance records.");
    }

    attendanceRecordsBody.innerHTML = "";

    if (data.records.length === 0) {
      attendanceRecordsBody.innerHTML = `
        <tr>
          <td colspan="4">No attendance records.</td>
        </tr>
      `;
      return;
    }

    data.records.forEach((record) => {
      const row = document.createElement("tr");

      const studentIdCell = document.createElement("td");
      studentIdCell.textContent = record.student_id || "Not registered";

      const studentNameCell = document.createElement("td");
      studentNameCell.textContent = record.student_name;

      const timeInCell = document.createElement("td");
      timeInCell.textContent = record.time_in;

      const statusCell = document.createElement("td");
      statusCell.textContent = record.status;

      row.append(studentIdCell, studentNameCell, timeInCell, statusCell);

      attendanceRecordsBody.appendChild(row);
    });
  } catch (error) {
    console.error("Error loading attendance records:", error);
    alert(error.message);
  }
}

// Toggle manual input availability without hiding the fields.
function toggleManualInput() {
  const manualEntry = notRegisteredCheckbox.checked;

  // Keep the name inputs visible at all times.
  manualNameContainer.hidden = false;

  // Enable name inputs only when "Not registered?" is checked.
  manualFirstNameInput.disabled = !manualEntry;
  manualLastNameInput.disabled = !manualEntry;

  manualFirstNameInput.required = manualEntry;
  manualLastNameInput.required = manualEntry;

  // Enable Student ID only for registered students.
  studentIdInput.disabled = manualEntry;
  studentIdInput.required = !manualEntry;

  // Clear fields when switching input modes.
  if (manualEntry) {
    studentIdInput.value = "";
  } else {
    manualFirstNameInput.value = "";
    manualLastNameInput.value = "";
  }
}

// Handle checkbox changes.
notRegisteredCheckbox.addEventListener("change", toggleManualInput);

// Load subjects and records when the selected section changes.
sectionSelect.addEventListener("change", async () => {
  sessionStorage.setItem("attendance_section", sectionSelect.value);

  // A different section may have different subjects.
  sessionStorage.removeItem("attendance_subject");

  await loadSubjects(sectionSelect.value);
  await loadAttendanceRecords();
});

// Load records when the selected subject changes.
subjectSelect.addEventListener("change", async () => {
  sessionStorage.setItem("attendance_subject", subjectSelect.value);

  await loadAttendanceRecords();
});

// Submit an attendance record.
attendanceForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const sectionName = sectionSelect.value;
  const subjectCode = subjectSelect.value;

  if (!sectionName || !subjectCode) {
    alert("Please select a section and subject.");
    return;
  }

  const payload = {
    section_name: sectionName,
    subject_code: subjectCode,
    not_registered: notRegisteredCheckbox.checked,
    student_id: studentIdInput.value.trim(),
    manual_first_name: manualFirstNameInput.value.trim(),
    manual_last_name: manualLastNameInput.value.trim(),
  };

  try {
    const response = await fetch("/record_attendance", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const responseText = await response.text();

    console.log("Record attendance status:", response.status);
    console.log("Record attendance response:", responseText);

    let data;

    try {
      data = JSON.parse(responseText);
    } catch (error) {
      throw new Error(
        "The server returned an invalid response. Check the Flask terminal for details.",
      );
    }

    if (!response.ok) {
      throw new Error(data.message || "Failed to record attendance.");
    }

    if (data.success) {
      alert(data.message || "Attendance recorded successfully!");

      // Preserve the current section and subject before reloading.
      sessionStorage.setItem("attendance_section", sectionName);
      sessionStorage.setItem("attendance_subject", subjectCode);

      // Reload after successfully recording attendance.
      window.location.reload();
    } else {
      alert(data.message || "Attendance could not be recorded.");
    }
  } catch (error) {
    console.error("Error recording attendance:", error);
    alert(error.message);
  }
});

// Initialize the attendance page.
async function initializeAttendancePage() {
  // Reset the checkbox.
  notRegisteredCheckbox.checked = false;

  // Reset manual student fields.
  manualFirstNameInput.value = "";
  manualLastNameInput.value = "";

  // Reset Student ID.
  studentIdInput.value = "";

  // Apply the default input state.
  toggleManualInput();

  // Retrieve previously selected options.
  const savedSection = sessionStorage.getItem("attendance_section");
  const savedSubject = sessionStorage.getItem("attendance_subject");

  // Load sections before restoring the saved selection.
  await loadSections();

  if (savedSection) {
    sectionSelect.value = savedSection;

    if (sectionSelect.value === savedSection) {
      await loadSubjects(savedSection);

      if (savedSubject) {
        subjectSelect.value = savedSubject;

        if (subjectSelect.value === savedSubject) {
          await loadAttendanceRecords();
        }
      }
    }
  }
}

// Check whether a new attendance record has been added.
async function checkForNewAttendance() {
  const sectionName = sectionSelect.value;
  const subjectCode = subjectSelect.value;
  if (!sectionName || !subjectCode || attendanceCheckInProgress) {
    return;
  }
  attendanceCheckInProgress = true;
  try {
    const query = new URLSearchParams({
      section_name: sectionName,
      subject_code: subjectCode,
    });
    const response = await fetch(
      `/get_attendance_records?${query.toString()}`,
      { cache: "no-store" },
    );
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    const currentStatus = data.status;
    if (previousSubjectStatus === "Ongoing" && currentStatus === "Completed") {
      previousSubjectStatus = currentStatus;
      await loadAttendanceRecords();
      return;
    }
    previousSubjectStatus = currentStatus;
    if (!Array.isArray(data.records)) {
      return;
    }
    const currentRecords = data.records.map((record) =>
      JSON.stringify([
        record.student_id,
        record.student_name,
        record.time_in,
        record.status,
      ]),
    );
    const hasNewRecord =
      previousAttendanceRecords !== null &&
      currentRecords.some(
        (record) => !previousAttendanceRecords.includes(record),
      );
    previousAttendanceRecords = currentRecords;
    if (hasNewRecord) {
      await loadAttendanceRecords();
    }
  } catch (error) {
    console.error("Error checking for new attendance:", error);
  } finally {
    attendanceCheckInProgress = false;
  }
}

// Start initialization after the script runs.
initializeAttendancePage().then(() => {
  if (sectionSelect.value && subjectSelect.value) {
    previousAttendanceRecords = null;
    checkForNewAttendance();
    setInterval(checkForNewAttendance, 2000);
  }
});
