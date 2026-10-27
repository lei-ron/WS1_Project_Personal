//! Sections

const sectionForm = document.getElementById("section_form");

const programSelect = document.getElementById("program");
const yearLevelSelect = document.getElementById("year_level");

const learningModality = document.getElementById("learning_modality");
const campus = document.getElementById("campus");
const currentTrimester = document.getElementById("current_trimester");
const trimesterPeriod = document.getElementById("trimester_period");
const session = document.getElementById("session");
const sectionNumber = document.getElementById("section_number");
const sectionName = document.getElementById("section_name");

const sectionList = document.getElementById("section_list");

let programs = [];

//! Generate Section Name

function updateSectionName() {
  const sectionFields = [
    programSelect,
    learningModality,
    campus,
    yearLevelSelect,
    currentTrimester,
    trimesterPeriod,
    session,
    sectionNumber,
  ];

  if (sectionFields.some((field) => !field.value)) {
    sectionName.value = "";
    return;
  }

  const number = String(Number(sectionNumber.value)).padStart(3, "0");

  sectionName.value =
    learningModality.value +
    campus.value +
    yearLevelSelect.value +
    currentTrimester.value +
    trimesterPeriod.value +
    session.value +
    number;
}

//! Load Programs

async function loadPrograms() {
  try {
    const response = await fetch("/get_programs");
    const result = await response.json();

    if (!response.ok) {
      console.error(result.message || "Failed to load programs.");
      return;
    }

    programs = result.programs || [];

    programSelect.innerHTML = '<option value="">Select Program</option>';

    if (programs.length === 0) {
      programSelect.innerHTML =
        '<option value="">No programs registered</option>';

      return;
    }

    programs.forEach((program) => {
      const option = document.createElement("option");

      option.value = program.program_code;
      option.textContent = `${program.program_code} - ${program.program_name}`;

      programSelect.appendChild(option);
    });
  } catch (error) {
    console.error("Error loading programs:", error);
  }
}

//! Load Year Levels

function loadYearLevels() {
  yearLevelSelect.innerHTML = '<option value="">Select Year Level</option>';

  const selectedProgram = programs.find(
    (program) => program.program_code === programSelect.value,
  );

  if (!selectedProgram) {
    updateSectionName();
    return;
  }

  for (let year = 1; year <= Number(selectedProgram.year_levels); year++) {
    const option = document.createElement("option");

    option.value = year;

    const suffix =
      year === 1 ? "st" : year === 2 ? "nd" : year === 3 ? "rd" : "th";

    option.textContent = `${year}${suffix} Year`;

    yearLevelSelect.appendChild(option);
  }

  updateSectionName();
}

//! Load Registered Sections
async function loadSections() {
  try {
    const response = await fetch("/get_sections");
    const result = await response.json();

    if (!response.ok) {
      console.error(result.message || "Failed to load sections.");

      sectionList.innerHTML = `
        <tr>
          <td colspan="4">Failed to load sections.</td>
        </tr>
      `;
      return;
    }

    sectionList.innerHTML = "";

    const sections = result.sections || [];

    if (sections.length === 0) {
      sectionList.innerHTML = `
        <tr>
          <td colspan="4">No sections registered yet.</td>
        </tr>
      `;
      return;
    }

    sections.forEach((section) => {
      const row = document.createElement("tr");

      const values = [
        section.program_code,
        section.section_name,
        `${Number(section.year_level)}${
          Number(section.year_level) === 1
            ? "st"
            : Number(section.year_level) === 2
              ? "nd"
              : Number(section.year_level) === 3
                ? "rd"
                : "th"
        } Year`,
      ];

      values.forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value ?? "-";
        row.appendChild(cell);
      });

      sectionList.appendChild(row);
    });
  } catch (error) {
    console.error("Error loading sections:", error);

    sectionList.innerHTML = `
      <tr>
        <td colspan="4">Unable to load sections. Check your connection.</td>
      </tr>
    `;
  }
}

//! Event Listeners

programSelect.addEventListener("change", loadYearLevels);

[
  programSelect,
  learningModality,
  campus,
  yearLevelSelect,
  currentTrimester,
  trimesterPeriod,
  session,
  sectionNumber,
].forEach((field) => {
  field.addEventListener("change", updateSectionName);
  field.addEventListener("input", updateSectionName);
});

//! Register Section

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

    yearLevelSelect.innerHTML = '<option value="">Select Year Level</option>';

    sectionName.value = "";

    await loadSections();
  } catch (error) {
    console.error("Section registration error:", error);

    alert("Unable to register section. Check your connection or server.");
  }
});

//! Initial Loading

async function initializeSectionsManager() {
  await loadPrograms();
  await loadSections();
}

initializeSectionsManager();
