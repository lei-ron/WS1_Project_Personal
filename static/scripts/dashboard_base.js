//! Side Navbar Toggle
const dashboard = document.getElementById("dashboard")
const toggle_sidebar = document.getElementById("sidebar_toggle")

if (sessionStorage.getItem("sidebar_expanded") === "true") {
    dashboard.classList.toggle("expanded");
}

toggle_sidebar.addEventListener("click", () => {
    dashboard.classList.toggle("expanded");

    sessionStorage.setItem("sidebar_expanded", 
        dashboard.classList.contains("expanded")
    );
});
