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

form_login_cta.addEventListener("click", function () {
  registration_form.close();
  login_form.showModal();
});


//! Student field inputs switch (Toggle select inputs)
const is_student = document.getElementById("is_student");
const student_fields = document.getElementById("student_fields");

const student_inputs = student_fields.querySelectorAll("input, select");

const id_number = document.getElementById("id_number");

function toggle_student_fields() {
  student_fields.classList.toggle("enabled", is_student.checked);

  student_inputs.forEach((input) => {
    input.disabled = !is_student.checked;
    input.required = is_student.checked;
  });

  if (is_student.checked) {
    id_number.pattern = "[A-Za-z]{2}[0-9]{9}";
    id_number.minLength = 11;
    id_number.maxLength = 11;
    id_number.title =
      "Student ID must contain 2 letters followed by 9 digits.";
  } else {
    id_number.removeAttribute("pattern");
    id_number.removeAttribute("minlength");
    id_number.removeAttribute("maxlength");
    id_number.removeAttribute("title");
  }
}

is_student.addEventListener("change", toggle_student_fields);

toggle_student_fields();


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

  form_message.textContent = result.message;
  form_message.className = result.success
    ? "form_message success show"
    : "form_message error show";

  if (result.success) {
    setTimeout(() => {
      window.location.href = "/dashboard"
    }, 3000);
  } else {

    setTimeout(() => {
      form_message.classList.remove("show")
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