const openDashboardBtn = document.querySelector("#open-dashboard-btn");
const statusEl = document.querySelector("#status");

openDashboardBtn.addEventListener("click", async () => {
  const result = await chrome.runtime.sendMessage({
    type: "rrtar:open-dashboard",
    formType: "keyperson",
  });
  statusEl.textContent = result?.ok ? "Dashboard opened." : result?.error || "Could not open dashboard.";
});
