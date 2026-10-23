//! Form dialog pop-up
const register_cta = document.getElementById("register_cta");
const login_cta = document.getElementById("login_cta");

const registration_form = document.getElementById("registration_form");
const login_form = document.getElementById("login_form");

const register_form_swap = document.getElementById("form_register_cta")
const login_form_swap = document.getElementById("form_login_cta")

register_cta.addEventListener("click", function () {
  login_form.close();
  registration_form.showModal();
});

login_cta.addEventListener("click", function () {
  registration_form.close();
  login_form.showModal();
});

registration_form.addEventListener("click", function (event) {
  if (event.target === registration_form) {
    registration_form.close();
  }
});

login_form.addEventListener("click", function (event) {
  if (event.target === login_form) {
    login_form.close();
  }
});

register_form_swap.addEventListener("click", function () {
  login_form.close();
  registration_form.showModal();
});

login_form_swap.addEventListener("click", function () {
  registration_form.close();
  login_form.showModal();
});

//! Registration form steps
const registration_step_1 = document.getElementById("registration_step_1");
const registration_step_2 = document.getElementById("registration_step_2");

const next_step = document.getElementById("next_step");
const previous_step = document.getElementById("previous_step");
const signup_button = document.getElementById("signup_button");

next_step.addEventListener("click", function () {
  const account_inputs = registration_step_1.querySelectorAll("input");

  for (const input of account_inputs) {
    if (!input.checkValidity()) {
      input.reportValidity();
      return;
    }
  }

  registration_step_1.hidden = true;
  registration_step_2.hidden = false;

  next_step.hidden = true;
  previous_step.hidden = false;
  signup_button.hidden = false;
});

previous_step.addEventListener("click", function () {
  registration_step_2.hidden = true;
  registration_step_1.hidden = false;

  previous_step.hidden = true;
  signup_button.hidden = true;
  next_step.hidden = false;
});

//! Load registered programs
const program_select = document.getElementById("program");
const year_level_select = document.getElementById("year_level");
const trimester_select = document.getElementById("trimester");
const section_select = document.getElementById("section");

let programs_data = [];
let sections_data = [];

async function loadPrograms() {
  try {
    const response = await fetch("/get_programs");

    if (!response.ok) {
      throw new Error("Failed to load programs.");
    }

    const result = await response.json();
    programs_data = result.programs;

    program_select.replaceChildren(
      new Option("Select Program", "", true, true)
    );

    program_select.options[0].disabled = true;

    programs_data.forEach((program) => {
      const option = new Option(
        `${program.program_code} - ${program.program_name}`,
        program.program_code
      );

      program_select.add(option);
    });
  } catch (error) {
    console.error("Error loading programs:", error);
  }
}

//! Student field
const student_fields = document.getElementById("student_fields");
const student_inputs = student_fields.querySelectorAll("input, select");
const id_number = document.getElementById("id_number");

student_fields.classList.add("enabled");

student_inputs.forEach((input) => {
  input.required = true;
});

program_select.disabled = false;
year_level_select.disabled = true;
trimester_select.disabled = true;
section_select.disabled = true;

id_number.pattern = "[A-Za-z]{2}[0-9]{9}";
id_number.minLength = 11;
id_number.maxLength = 11;
id_number.title =
  "Student ID must contain 2 letters followed by 9 digits.";

//! Load registered sections
async function loadSections() {
  try {
    const response = await fetch("/get_sections");

    if (!response.ok) {
      throw new Error("Failed to load sections.");
    }

    const result = await response.json();
    sections_data = result.sections;
  } catch (error) {
    console.error("Error loading sections:", error);
  }
}

program_select.addEventListener("change", function () {
  const selected_program = program_select.value;
  const program = programs_data.find(
    (item) => item.program_code === selected_program
  );

  year_level_select.replaceChildren(
    new Option("Select a year level", "", true, true)
  );

  year_level_select.options[0].disabled = true;
  year_level_select.disabled = true;

  trimester_select.value = "";
  trimester_select.disabled = true;

  section_select.replaceChildren(
    new Option("Select a section", "", true, true)
  );
  section_select.options[0].disabled = true;
  section_select.disabled = true;

  if (!program) {
    return;
  }

  for (let year = 1; year <= program.year_levels; year++) {
    year_level_select.add(new Option(`Year ${year}`, year));
  }

  year_level_select.disabled = false;
});

async function loadRegistrationData() {
  await Promise.all([loadPrograms(), loadSections()]);
  updateSections();
}

loadRegistrationData();

//! Update trimesters
function updateTrimesters() {
  trimester_select.replaceChildren(
    new Option("Select Trimester", "", true, true),
    new Option("Trimester 1", "1"),
    new Option("Trimester 2", "2"),
    new Option("Trimester 3", "3")
  );

  trimester_select.options[0].disabled = true;
}

updateTrimesters();

//! Update sections based on selected program, year level, and trimester
function updateSections() {
  const selected_program = program_select.value;
  const selected_year = Number(year_level_select.value);
  const selected_trimester = Number(trimester_select.value);

  section_select.replaceChildren(
  new Option("Select a section", "", true, true)
  );
  section_select.options[0].disabled = true;

  if (!selected_program || !selected_year || !selected_trimester) {
    return;
  }

  const matching_sections = sections_data.filter(
    (section) =>
      section.program_code === selected_program &&
      Number(section.year_level) === selected_year &&
      Number(section.current_trimester) === selected_trimester
  );

  matching_sections.forEach((section) => {
    section_select.add(
      new Option(section.section_name, section.section_name)
    );
  });
}

year_level_select.addEventListener("change", function () {
  trimester_select.value = "";
  trimester_select.disabled = !year_level_select.value;

  section_select.replaceChildren(
    new Option("Select a section", "", true, true)
  );
  section_select.options[0].disabled = true;
  section_select.disabled = true;

  updateSections();
});

trimester_select.addEventListener("change", function () {
  section_select.disabled = !trimester_select.value;
  updateSections();
});

program_select.addEventListener("change", updateSections);

//! Registration form response
const form = document.getElementById("registration_data");
const form_message = document.getElementById("form_message");

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const response = await fetch(form.action, {
    method: "POST",
    body: new FormData(form),
  });

  const result = await response.json();

  form_message.textContent = result.success
    ? "Registration successful! Your admission is pending review."
    : result.message;

  form_message.className = result.success
    ? "form_message success show"
    : "form_message error show";

  if (result.success) {
    setTimeout(() => {
      registration_form.close();
      form_message.classList.remove("show");
    }, 3000);
  } else {
    setTimeout(() => {
      form_message.classList.remove("show");
    }, 3000);
  }
});

//! Login form response
const form2 = document.getElementById("login_data");
const login_message = document.getElementById("login_message");

form2.addEventListener("submit", async (event) => {
  event.preventDefault();

  const response = await fetch(form2.action, {
    method: "POST",
    body: new FormData(form2),
  });

  const result = await response.json();

  login_message.textContent = result.message;
  login_message.className = result.success
    ? "form_message success show"
    : "form_message error show";

  if (result.success) {
    setTimeout(() => {
      window.location.href = "/dashboard"
    }, 3000);
  } else {

    setTimeout(() => {
      login_message.classList.remove("show")
    }, 3000);
  }
});

//! Latest ORF drag-and-drop
const file_drop_area = document.getElementById("file_drop_area");
const latest_orf = document.getElementById("latest_orf");
const file_name = document.getElementById("file_name");

file_drop_area.addEventListener("click", function (event) {
  if (event.target !== latest_orf) {
    latest_orf.click();
  }
});

latest_orf.addEventListener("change", function () {
  file_name.textContent = latest_orf.files.length
    ? latest_orf.files[0].name
    : "No file selected";
});

file_drop_area.addEventListener("dragover", function (event) {
  event.preventDefault();
  file_drop_area.classList.add("drag_over");
});

file_drop_area.addEventListener("dragleave", function () {
  file_drop_area.classList.remove("drag_over");
});

file_drop_area.addEventListener("drop", function (event) {
  event.preventDefault();
  file_drop_area.classList.remove("drag_over");

  const files = event.dataTransfer.files;

  if (files.length) {
    latest_orf.files = files;
    latest_orf.dispatchEvent(new Event("change"));
  }
});