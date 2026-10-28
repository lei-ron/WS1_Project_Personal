const classList = document.getElementById("class_list");
const classSessionCount = document.getElementById("class_session_count");

const selectedClassLabel = document.getElementById("selected_class_label");

const presentCount = document.getElementById("present_count");
const absentCount = document.getElementById("absent_count");
const registeredCount = document.getElementById("registered_count");

const attendanceTableBody = document.getElementById("attendance_table_body");

let selectedSessionId = null;

async function loadAttendanceHistory() {
  classList.innerHTML = `
    <p class="empty_state">Loading class sessions...</p>
  `;

  try {
    const response = await fetch("/get_attendance_history");
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.message || "Failed to load attendance history.");
    }

    classList.innerHTML = "";
    classSessionCount.textContent = `${data.sessions.length} classes`;

    if (data.sessions.length === 0) {
      classList.innerHTML = `
        <p class="empty_state">No class sessions available.</p>
      `;
      return;
    }

    data.sessions.forEach((classSession) => {
      const item = document.createElement("button");

      item.type = "button";
      item.className = "class_session_item";

      item.dataset.sessionId = classSession.session_id;

      const attendanceTotal = `${classSession.present_count}/${classSession.registered_count}`;

      item.innerHTML = `
        <div class="class_session_info">
          <strong class="class_session_subject"></strong>
          <span class="class_session_section"></span>
          <span class="class_session_date"></span>
        </div>

        <div class="class_session_meta">
          <span class="class_session_status"></span>
          <span class="class_session_total"></span>
        </div>
      `;

      item.querySelector(".class_session_subject").textContent =
        `${classSession.subject_code} - ${classSession.subject_name}`;

      item.querySelector(".class_session_section").textContent =
        classSession.section_name;

      item.querySelector(".class_session_date").textContent =
        classSession.attendance_date;

      const statusElement = item.querySelector(".class_session_status");

      statusElement.textContent = classSession.status;
      statusElement.classList.add(
        `status_${classSession.status.toLowerCase()}`,
      );

      item.querySelector(".class_session_total").textContent = attendanceTotal;

      item.addEventListener("click", () => {
        selectClassSession(classSession.session_id, item);
      });

      classList.appendChild(item);
    });

    // Automatically display the newest session.
    const firstSession = classList.querySelector(".class_session_item");

    if (firstSession) {
      firstSession.click();
    }
  } catch (error) {
    console.error("Attendance history error:", error);

    classList.innerHTML = `
      <p class="empty_state">Failed to load class sessions.</p>
    `;
  }
}

async function selectClassSession(sessionId, selectedItem) {
  selectedSessionId = sessionId;

  document.querySelectorAll(".class_session_item").forEach((item) => {
    item.classList.remove("selected");
  });

  selectedItem.classList.add("selected");

  selectedClassLabel.textContent = "Loading attendance details...";

  attendanceTableBody.innerHTML = `
    <tr>
      <td colspan="4" class="empty_state">
        Loading attendance records...
      </td>
    </tr>
  `;

  try {
    const response = await fetch(
      `/get_attendance_history_records?session_id=${encodeURIComponent(sessionId)}`,
    );

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.message || "Failed to load attendance records.");
    }

    const classSession = data.session;

    selectedClassLabel.textContent =
      `${classSession.subject_code} - ${classSession.subject_name} | ` +
      `${classSession.section_name} | ${classSession.attendance_date}`;

    presentCount.textContent = data.summary.present;
    absentCount.textContent = data.summary.absent;
    registeredCount.textContent = data.summary.registered;

    attendanceTableBody.innerHTML = "";

    if (data.records.length === 0) {
      attendanceTableBody.innerHTML = `
        <tr>
          <td colspan="4" class="empty_state">
            No registered students found for this section.
          </td>
        </tr>
      `;
      return;
    }

    data.records.forEach((record) => {
      const row = document.createElement("tr");

      row.innerHTML = `
        <td class="student_name"></td>
        <td class="student_id"></td>
        <td class="time_recorded"></td>
        <td class="attendance_status"></td>
      `;

      row.querySelector(".student_name").textContent = record.student_name;

      row.querySelector(".student_id").textContent = record.student_id;

      row.querySelector(".time_recorded").textContent = record.time_in;

      const statusCell = row.querySelector(".attendance_status");

      statusCell.textContent = record.status;
      statusCell.classList.add(`status_${record.status.toLowerCase()}`);

      attendanceTableBody.appendChild(row);
    });
  } catch (error) {
    console.error("Attendance details error:", error);

    selectedClassLabel.textContent = "Failed to load attendance details.";

    attendanceTableBody.innerHTML = `
      <tr>
        <td colspan="4" class="empty_state">
          Failed to load attendance records.
        </td>
      </tr>
    `;
  }
}

loadAttendanceHistory();
