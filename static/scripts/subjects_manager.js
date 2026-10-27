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
