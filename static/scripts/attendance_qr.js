const startAttendanceButton = document.getElementById(
  "start_attendance_button",
);

const endAttendanceButton = document.getElementById("end_attendance_button");

const qrSessionStatus = document.getElementById("qr_session_status");

const qrCodeContainer = document.getElementById("qr_code_container");

const attendanceQrImage = document.getElementById("attendance_qr_image");

const qrCountdown = document.getElementById("qr_countdown");

let qrRefreshInterval = null;
let countdownInterval = null;
let currentQrToken = null;
let qrExpiresAt = null;
let qrRequestInProgress = false;

// Get the selected section and subject.
function getSelectedAttendanceClass() {
  const sectionName = sectionSelect.value;
  const subjectCode = subjectSelect.value;

  if (!sectionName || !subjectCode) {
    return null;
  }

  return {
    section_name: sectionName,
    subject_code: subjectCode,
  };
}

// Update the QR image and expiration time.
function updateAttendanceQr(result) {
  if (!result.success || !result.qr_image || !result.qr_token) {
    return;
  }

  // Only replace the image when the token changes.
  if (currentQrToken !== result.qr_token) {
    currentQrToken = result.qr_token;
    attendanceQrImage.src = result.qr_image;
  }

  qrExpiresAt = new Date(result.expires_at);

  qrCodeContainer.hidden = false;

  updateQrCountdown();
}

// Calculate the remaining time from the server expiration timestamp.
function updateQrCountdown() {
  if (!qrExpiresAt) {
    qrCountdown.textContent = "0";
    return;
  }

  const remainingSeconds = Math.max(
    0,
    Math.ceil((qrExpiresAt.getTime() - Date.now()) / 1000),
  );

  qrCountdown.textContent = remainingSeconds;
}

// Retrieve the current QR token from Flask.
async function refreshAttendanceQr() {
  if (qrRequestInProgress) {
    return;
  }

  const selectedClass = getSelectedAttendanceClass();

  if (!selectedClass) {
    return;
  }

  qrRequestInProgress = true;

  try {
    const query = new URLSearchParams(selectedClass);

    const response = await fetch(`/get_attendance_qr?${query.toString()}`);

    const result = await response.json();

    if (!response.ok || !result.success) {
      if (result.active === false) {
        stopQrRefresh();

        qrSessionStatus.textContent =
          result.message || "Attendance session is no longer active.";

        return;
      }

      qrSessionStatus.textContent =
        result.message || "Unable to refresh the QR code.";

      return;
    }

    updateAttendanceQr(result);

    qrSessionStatus.textContent =
      "Attendance is active. Students can scan the QR code.";
  } catch (error) {
    console.error("QR refresh error:", error);

    qrSessionStatus.textContent = "Unable to connect to the attendance server.";
  } finally {
    qrRequestInProgress = false;
  }
}

// Start polling for token changes and update the countdown.
function startQrRefresh() {
  stopQrRefresh();

  qrRefreshInterval = setInterval(() => {
    refreshAttendanceQr();
  }, 2000);

  countdownInterval = setInterval(() => {
    updateQrCountdown();
  }, 1000);
}

// Resume an existing attendance session after the page reloads.
async function resumeAttendanceSession() {
  const selectedClass = getSelectedAttendanceClass();

  if (!selectedClass) {
    return;
  }

  try {
    const query = new URLSearchParams(selectedClass);
    const response = await fetch(`/get_attendance_qr?${query.toString()}`);
    const result = await response.json();

    if (!response.ok || !result.success) {
      return;
    }

    updateAttendanceQr(result);

    startAttendanceButton.disabled = true;
    endAttendanceButton.disabled = false;

    qrSessionStatus.textContent =
      "Attendance is active. Students can scan the QR code.";

    startQrRefresh();
  } catch (error) {
    console.error("Error resuming attendance session:", error);
  }
}

// Stop all QR refresh timers.
function stopQrRefresh() {
  if (qrRefreshInterval) {
    clearInterval(qrRefreshInterval);
    qrRefreshInterval = null;
  }

  if (countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }

  currentQrToken = null;
  qrExpiresAt = null;

  qrCodeContainer.hidden = true;
  attendanceQrImage.src = "";
  qrCountdown.textContent = "3";

  startAttendanceButton.disabled = false;
  endAttendanceButton.disabled = true;
}

// Start an attendance session.
async function startAttendanceSession() {
  const selectedClass = getSelectedAttendanceClass();

  if (!selectedClass) {
    alert("Please select a section and subject first.");
    return;
  }

  startAttendanceButton.disabled = true;

  qrSessionStatus.textContent = "Starting attendance...";

  try {
    const response = await fetch("/start_attendance_session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(selectedClass),
    });

    const result = await response.json();

    if (!response.ok || !result.success) {
      alert(result.message || "Unable to start attendance.");

      qrSessionStatus.textContent =
        result.message || "Unable to start attendance.";

      startAttendanceButton.disabled = false;
      return;
    }

    updateAttendanceQr(result);

    endAttendanceButton.disabled = false;

    qrSessionStatus.textContent =
      "Attendance is active. Students can scan the QR code.";

    startQrRefresh();

    if (typeof loadAttendanceRecords === "function") {
      loadAttendanceRecords();
    }
  } catch (error) {
    console.error("Start attendance error:", error);

    alert("Unable to connect to the attendance server.");

    qrSessionStatus.textContent = "Unable to connect to the attendance server.";

    startAttendanceButton.disabled = false;
  }
}

// End an attendance session.
async function endAttendanceSession() {
  const selectedClass = getSelectedAttendanceClass();

  if (!selectedClass) {
    alert("Please select a section and subject first.");
    return;
  }

  const confirmed = confirm(
    "Are you sure you want to end this attendance session?",
  );

  if (!confirmed) {
    return;
  }

  endAttendanceButton.disabled = true;

  try {
    const response = await fetch("/end_attendance_session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(selectedClass),
    });

    const result = await response.json();

    if (!response.ok || !result.success) {
      alert(result.message || "Unable to end attendance.");

      endAttendanceButton.disabled = false;
      return;
    }

    stopQrRefresh();

    qrSessionStatus.textContent = result.message || "Attendance session ended.";

    if (typeof loadAttendanceRecords === "function") {
      loadAttendanceRecords();
    }
  } catch (error) {
    console.error("End attendance error:", error);

    alert("Unable to connect to the attendance server.");

    endAttendanceButton.disabled = false;
  }
}

// Event listeners.
startAttendanceButton.addEventListener("click", startAttendanceSession);
endAttendanceButton.addEventListener("click", endAttendanceSession);

// Stop refreshing if the professor changes the selected class.
sectionSelect.addEventListener("change", () => {
  stopQrRefresh();
  qrSessionStatus.textContent = "Select a subject and start attendance.";
});

subjectSelect.addEventListener("change", () => {
  stopQrRefresh();
  qrSessionStatus.textContent = "Ready to start attendance.";
});

// Resume an active session after the page loads.
initializeAttendancePage().then(() => {
  resumeAttendanceSession();
});
