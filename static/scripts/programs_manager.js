//! Programs
const programForm = document.getElementById("program_form");
const programList = document.getElementById("program_list");

async function loadPrograms() {
  try {
    const response = await fetch("/get_programs");
    const result = await response.json();

    if (!response.ok) {
      programList.innerHTML = `
        <tr>
          <td colspan="3">Failed to load programs.</td>
        </tr>
      `;
      console.error(result.message || "Failed to load programs.");
      return;
    }

    programList.innerHTML = "";

    if (result.programs.length === 0) {
      programList.innerHTML = `
        <tr>
          <td colspan="3">No programs registered yet.</td>
        </tr>
      `;
      return;
    }

    result.programs.forEach((program) => {
      const row = document.createElement("tr");

      const codeCell = document.createElement("td");
      codeCell.textContent = program.program_code;

      const nameCell = document.createElement("td");
      nameCell.textContent = program.program_name;

      const yearCell = document.createElement("td");
      yearCell.textContent = program.year_levels;

      row.append(codeCell, nameCell, yearCell);
      programList.appendChild(row);
    });
  } catch (error) {
    console.error("Error loading programs:", error);

    programList.innerHTML = `
      <tr>
        <td colspan="3">Unable to load programs. Check your connection.</td>
      </tr>
    `;
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
      alert(result.message || "Failed to register program.");
      return;
    }

    programForm.reset();

    await loadPrograms();

    alert(result.message);
  } catch (error) {
    console.error("Program registration error:", error);
    alert("Unable to register program. Check your connection or server.");
  }
});

loadPrograms();
