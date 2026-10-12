// Meedicoapp - small client-side enhancements

document.addEventListener("DOMContentLoaded", function () {
    // Auto-dismiss alerts after 5 seconds
    document.querySelectorAll(".alert").forEach(function (alertEl) {
        setTimeout(function () {
            const alert = bootstrap.Alert.getOrCreateInstance(alertEl);
            alert.close();
        }, 5000);
    });

    // Prevent booking a date in the past
    const dateInput = document.querySelector('input[name="appointment_date"]');
    if (dateInput) {
        const today = new Date().toISOString().split("T")[0];
        dateInput.setAttribute("min", today);
    }
});
