//! Programs
const programs = [];

const programForm = document.getElementById("program_form");
const sectionForm = document.getElementById("section_form");
const programSelect = document.getElementById("program");
const subjectProgramsSelect = document.getElementById("subject_programs");
const yearLevelSelect = document.getElementById("year_level");

async function loadPrograms() {
  try {
    const response = await fetch("/get_programs");
    const result = await response.json();

    if (!response.ok) {
      alert(result.message || "Failed to load programs.");
      return;
    }

    programs.length = 0;

    programSelect.innerHTML = '<option value="">Select Program</option>';
    subjectProgramsSelect.innerHTML = "";

    result.programs.forEach((program) => {
      programs.push({
        code: program.program_code,
        name: program.program_name,
        yearLevels: program.year_levels,
      });

      const sectionOption = document.createElement("option");
      sectionOption.value = program.program_code;
      sectionOption.textContent = `${program.program_code} - ${program.program_name}`;
      programSelect.appendChild(sectionOption);

      const subjectOption = document.createElement("option");
      subjectOption.value = program.program_code;
      subjectOption.textContent = `${program.program_code} - ${program.program_name}`;
      subjectProgramsSelect.appendChild(subjectOption);
    });
  } catch (error) {
    console.error("Error loading programs:", error);
  }
}

programForm.addEventListener("submit", async function (event) {
  event.preventDefault();

  const formData = new FormData(programForm);

  try {
    const response = await fetch("/register_program", {
      method: "POST",
      body: formData,
    });

    const result = await response.json();

    if (!response.ok) {
      alert(result.message);
      return;
    }

    await loadPrograms();
    programForm.reset();
    alert(result.message);
  } catch (error) {
    console.error("Program registration error:", error);
    alert("Unable to register program. Check your connection or server.");
  }
});

programSelect.addEventListener("change", function () {
  yearLevelSelect.innerHTML = '<option value="">Select Year Level</option>';

  const selectedProgram = programs.find(
    (program) => program.code === programSelect.value
  );

  if (!selectedProgram) {
    return;
  }

  for (let year = 1; year <= selectedProgram.yearLevels; year++) {
    const option = document.createElement("option");
    option.value = year;
    option.textContent = `${year}${getOrdinal(year)} Year`;
    yearLevelSelect.appendChild(option);
  }

  updateSectionName();
});

function getOrdinal(number) {
  if (number === 1) return "st";
  if (number === 2) return "nd";
  if (number === 3) return "rd";
  return "th";
}

loadPrograms();

//! Sections

const currentTrimester = document.getElementById("current_trimester");
const trimesterPeriod = document.getElementById("trimester_period");
const sectionNumber = document.getElementById("section_number");
const sectionName = document.getElementById("section_name");

const sectionFields = [
  programSelect,
  document.getElementById("learning_modality"),
  document.getElementById("campus"),
  yearLevelSelect,
  currentTrimester,
  trimesterPeriod,
  document.getElementById("session"),
  sectionNumber,
];

function updateSectionName() {
  if (sectionFields.some((field) => !field.value)) {
    sectionName.value = "";
    return;
  }

  const number = String(Number(sectionNumber.value)).padStart(3, "0");

  sectionName.value =
    document.getElementById("learning_modality").value +
    document.getElementById("campus").value +
    yearLevelSelect.value +
    currentTrimester.value +
    trimesterPeriod.value +
    document.getElementById("session").value +
    number;
}

sectionFields.forEach((field) => {
  field.addEventListener("change", updateSectionName);
  field.addEventListener("input", updateSectionName);
});

sectionForm.addEventListener("submit", async function (event) {
  event.preventDefault();

  updateSectionName();

  if (!sectionName.value) {
    alert("Please complete all section fields.");
    return;
  }

  const formData = new FormData(sectionForm);

  try {
    const response = await fetch("/register_section", {
      method: "POST",
      body: formData,
    });

    const result = await response.json();

    if (!response.ok) {
      alert(result.message || "Failed to register section.");
      return;
    }

    alert(result.message);
    sectionForm.reset();
    sectionName.value = "";
  } catch (error) {
    console.error("Section registration error:", error);
    alert("Unable to register section. Check your connection or server.");
  }
});

//! Subjects

const subjectForm = document.getElementById("subject_form");

subjectForm.addEventListener("submit", async function (event) {
  event.preventDefault();

  const formData = new FormData(subjectForm);

  try {
    const response = await fetch("/register_subject", {
      method: "POST",
      body: formData,
    });

    const responseText = await response.text();
    let result;

    try {
      result = JSON.parse(responseText);
    } catch {
      console.error("Server returned a non-JSON response:", responseText);
      alert(
        "The server returned an unexpected response. Check the Flask terminal and browser console."
      );
      return;
    }

    if (!response.ok) {
      alert(result.message || "Failed to register subject.");
      return;
    }

    alert(result.message);
    subjectForm.reset();
  } catch (error) {
    console.error("Subject registration error:", error);
    alert("Request failed: " + error.message);
  }
});

//! Subject Assignments

const assignmentForm = document.getElementById("subject_assignment_form");
const assignmentSection = document.getElementById("assignment_section");
const assignmentSubject = document.getElementById("assignment_subject");
const assignmentProfessor = document.getElementById("assignment_professor");

async function loadAssignmentSections() {
  try {
    const response = await fetch("/get_sections");
    const result = await response.json();

    if (!response.ok) {
      console.error("Failed to load sections:", result);
      return;
    }

    assignmentSection.innerHTML =
      '<option value="">Select Section</option>';

    result.sections.forEach((section) => {
      const option = document.createElement("option");
      option.value = section.section_name;
      option.textContent = section.section_name;
      assignmentSection.appendChild(option);
    });
  } catch (error) {
    console.error("Error loading assignment sections:", error);
  }
}

async function loadAssignmentProfessors() {
  try {
    const response = await fetch("/get_assignment_professors");
    const result = await response.json();

    if (!response.ok) {
      console.error("Failed to load professors:", result);
      return;
    }

    assignmentProfessor.innerHTML =
      '<option value="">Select Professor</option>';

    result.professors.forEach((professor) => {
      const option = document.createElement("option");
      option.value = professor._id;
      option.textContent =
        `${professor.first_name} ${professor.last_name}`;
      assignmentProfessor.appendChild(option);
    });
  } catch (error) {
    console.error("Error loading professors:", error);
  }
}

async function loadAssignmentSubjects(sectionName) {
  assignmentSubject.innerHTML =
    '<option value="">Loading Subjects...</option>';

  assignmentSubject.disabled = true;

  if (!sectionName) {
    assignmentSubject.innerHTML =
      '<option value="">Select Section First</option>';
    return;
  }

  try {
    const response = await fetch(
      `/get_section_subjects?section_name=${encodeURIComponent(sectionName)}`
    );

    const result = await response.json();

    if (!response.ok) {
      assignmentSubject.innerHTML =
        '<option value="">Failed to Load Subjects</option>';

      alert(result.message || "Failed to load subjects.");
      return;
    }

    assignmentSubject.innerHTML =
      '<option value="">Select Subject</option>';

    result.subjects.forEach((subject) => {
      const option = document.createElement("option");
      option.value = subject.subject_code;
      option.textContent =
        `${subject.subject_code} - ${subject.subject_name}`;
      assignmentSubject.appendChild(option);
    });

    assignmentSubject.disabled = result.subjects.length === 0;

    if (result.subjects.length === 0) {
      assignmentSubject.innerHTML =
        '<option value="">No Subjects Registered for This Program</option>';
    }
  } catch (error) {
    console.error("Error loading assignment subjects:", error);

    assignmentSubject.innerHTML =
      '<option value="">Failed to Load Subjects</option>';
  }
}

assignmentSection.addEventListener("change", function () {
  loadAssignmentSubjects(assignmentSection.value);
});

assignmentForm.addEventListener("submit", async function (event) {
  event.preventDefault();

  const selectedDays = assignmentForm.querySelectorAll(
    'input[name="days"]:checked'
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
      alert(result.message || "Failed to register subject assignment.");
      return;
    }

    alert(result.message);
    assignmentForm.reset();

    assignmentSubject.innerHTML =
      '<option value="">Select Section First</option>';

    assignmentSubject.disabled = true;
  } catch (error) {
    console.error("Subject assignment error:", error);
    alert("Unable to register assignment. Check your connection or server.");
  }
});

loadAssignmentSections();
loadAssignmentProfessors();