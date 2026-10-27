//! Subjects
const subjectForm = document.getElementById("subject_form");
const subjectProgramsSelect = document.getElementById("subject_programs");
const subjectList = document.getElementById("subject_list");

//! Program Loading
async function loadPrograms() {
  try {
    const response = await fetch("/get_programs");
    const result = await response.json();

    subjectProgramsSelect.innerHTML = "";

    if (!response.ok) {
      console.error(result.message || "Failed to load programs.");
      return;
    }

    if (!result.programs || result.programs.length === 0) {
      const option = document.createElement("option");
      option.textContent = "No programs registered";
      option.disabled = true;
      subjectProgramsSelect.appendChild(option);
      return;
    }

    result.programs.forEach((program) => {
      const option = document.createElement("option");
      option.value = program.program_code;
      option.textContent = `${program.program_code} - ${program.program_name}`;
      subjectProgramsSelect.appendChild(option);
    });
  } catch (error) {
    console.error("Error loading programs:", error);
  }
}

//! Subject Loading
async function loadSubjects() {
  try {
    const response = await fetch("/get_subjects");
    const result = await response.json();

    if (!response.ok) {
      console.error(result.message || "Failed to load subjects.");
      subjectList.innerHTML = `
        <tr>
          <td colspan="3">Failed to load subjects.</td>
        </tr>
      `;
      return;
    }

    subjectList.innerHTML = "";

    if (!result.subjects || result.subjects.length === 0) {
      subjectList.innerHTML = `
        <tr>
          <td colspan="3">No subjects registered yet.</td>
        </tr>
      `;
      return;
    }

    result.subjects.forEach((subject) => {
      const row = document.createElement("tr");

      const codeCell = document.createElement("td");
      codeCell.textContent = subject.subject_code;

      const nameCell = document.createElement("td");
      nameCell.textContent = subject.subject_name;

      const programsCell = document.createElement("td");
      const programCodes =
        subject.program_codes ||
        (subject.program_code ? [subject.program_code] : []);

      programsCell.textContent =
        programCodes.length > 0 ? programCodes.join(", ") : "None";

      row.append(codeCell, nameCell, programsCell);
      subjectList.appendChild(row);
    });
  } catch (error) {
    console.error("Error loading subjects:", error);

    subjectList.innerHTML = `
      <tr>
        <td colspan="3">Unable to load subjects. Check your connection.</td>
      </tr>
    `;
  }
}

//! Subject Registration
subjectForm.addEventListener("submit", async function (event) {
  event.preventDefault();

  if (subjectProgramsSelect.selectedOptions.length === 0) {
    alert("Please select at least one program.");
    subjectProgramsSelect.focus();
    return;
  }

  const formData = new FormData(subjectForm);

  try {
    const response = await fetch("/register_subject", {
      method: "POST",
      body: formData,
    });

    const result = await response.json();

    if (!response.ok) {
      alert(result.message || "Failed to register subject.");
      return;
    }

    alert(result.message);
    subjectForm.reset();

    await loadSubjects();
  } catch (error) {
    console.error("Subject registration error:", error);
    alert("Unable to register subject. Check your connection or server.");
  }
});

//! Initial Loading
loadPrograms();
loadSubjects();

//! Subject Assignment
const assignmentForm = document.getElementById("subject_assignment_form");
const assignmentSection = document.getElementById("assignment_section");
const assignmentSubject = document.getElementById("assignment_subject");
const assignmentProfessor = document.getElementById("assignment_professor");

//! Load Sections
async function loadSections() {
  try {
    const response = await fetch("/get_sections");
    const result = await response.json();

    assignmentSection.innerHTML = '<option value="">Select Section</option>';

    if (!response.ok) {
      console.error(result.message || "Failed to load sections.");
      return;
    }

    if (!result.sections || result.sections.length === 0) {
      assignmentSection.innerHTML =
        '<option value="">No sections registered</option>';
      return;
    }

    result.sections.forEach((section) => {
      const option = document.createElement("option");
      option.value = section.section_name;
      option.textContent = section.section_name;
      assignmentSection.appendChild(option);
    });
  } catch (error) {
    console.error("Error loading sections:", error);
    assignmentSection.innerHTML =
      '<option value="">Unable to load sections</option>';
  }
}

//! Load Subjects for Selected Section
async function loadAssignmentSubjects() {
  const sectionName = assignmentSection.value;

  assignmentSubject.innerHTML = '<option value="">Select Subject</option>';

  assignmentSubject.disabled = true;

  if (!sectionName) {
    assignmentSubject.innerHTML =
      '<option value="">Select Section First</option>';
    return;
  }

  try {
    const response = await fetch(
      `/get_section_subjects?section_name=${encodeURIComponent(sectionName)}`,
    );

    const result = await response.json();

    if (!response.ok) {
      console.error(result.message || "Failed to load section subjects.");
      return;
    }

    if (!result.subjects || result.subjects.length === 0) {
      assignmentSubject.innerHTML =
        '<option value="">No subjects available</option>';
      return;
    }

    result.subjects.forEach((subject) => {
      const option = document.createElement("option");
      option.value = subject.subject_code;
      option.textContent = `${subject.subject_code} - ${subject.subject_name}`;
      assignmentSubject.appendChild(option);
    });

    assignmentSubject.disabled = false;
  } catch (error) {
    console.error("Error loading section subjects:", error);
  }
}

//! Section Change
assignmentSection.addEventListener("change", loadAssignmentSubjects);

//! Load Professors
async function loadAssignmentProfessors() {
  try {
    const response = await fetch("/get_assignment_professors");
    const result = await response.json();

    assignmentProfessor.innerHTML =
      '<option value="">Select Professor</option>';

    if (!response.ok) {
      console.error(result.message || "Failed to load professors.");
      return;
    }

    if (!result.professors || result.professors.length === 0) {
      assignmentProfessor.innerHTML =
        '<option value="">No professors registered</option>';
      return;
    }

    result.professors.forEach((professor) => {
      const option = document.createElement("option");

      option.value = professor._id;
      option.textContent = `${professor.first_name} ${professor.last_name}`;

      assignmentProfessor.appendChild(option);
    });
  } catch (error) {
    console.error("Error loading professors:", error);

    assignmentProfessor.innerHTML =
      '<option value="">Unable to load professors</option>';
  }
}

//! Initial Loading
loadPrograms();
loadSubjects();
loadSections();
loadAssignmentProfessors();

//! Subject Assignment Submission
assignmentForm.addEventListener("submit", async function (event) {
  event.preventDefault();

  const selectedDays = assignmentForm.querySelectorAll(
    'input[name="days"]:checked',
  );

  if (selectedDays.length === 0) {
    alert("Please select at least one day.");
    return;
  }

  const formData = new FormData(assignmentForm);

  try {
    const response = await fetch("/register_subject_assignment", {
      method: "POST",
      body: formData,
    });

    const result = await response.json();

    if (!response.ok) {
      alert(result.message || "Failed to assign subject.");
      return;
    }

    alert(result.message || "Subject assigned successfully.");

    assignmentForm.reset();

    assignmentSubject.innerHTML =
      '<option value="">Select Section First</option>';
    assignmentSubject.disabled = true;
  } catch (error) {
    console.error("Subject assignment error:", error);
    alert("Unable to assign subject. Please check your connection.");
  }
});
