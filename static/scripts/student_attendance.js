const qrReader = document.getElementById("qr_reader");
const scanMessage = document.getElementById("scan_message");

let scanner = null;
let scanInProgress = false;

function showMessage(message) {
  scanMessage.textContent = message;
}

async function handleScan(decodedText) {
  if (scanInProgress) {
    return;
  }

  scanInProgress = true;

  try {
    showMessage("QR code detected. Recording attendance...");

    const response = await fetch("/scan_attendance_qr", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        token: decodedText,
      }),
    });

    const result = await response.json();

    if (!response.ok || !result.success) {
      showMessage(result.message || "Unable to record attendance.");
      return;
    }

    showMessage(result.message || "Attendance recorded successfully.");

    if (scanner) {
      await scanner.stop();
      await scanner.clear();
      scanner = null;
    }
  } catch (error) {
    console.error("Attendance scan error:", error);
    showMessage("Something went wrong. Please try scanning again.");
  } finally {
    scanInProgress = false;
  }
}

async function startScanner() {
  if (typeof Html5Qrcode === "undefined") {
    showMessage("The QR scanner library could not be loaded.");
    return;
  }

  try {
    scanner = new Html5Qrcode("qr_reader");

    await scanner.start(
      { facingMode: "environment" },
      {
        fps: 10,
        qrbox: { width: 250, height: 250 },
      },
      handleScan,
      () => {},
    );

    showMessage("Point your camera at your professor's QR code.");
  } catch (error) {
    console.error("Camera error:", error);
    showMessage("Unable to access the camera. Check your browser permissions.");
  }
}

startScanner();
