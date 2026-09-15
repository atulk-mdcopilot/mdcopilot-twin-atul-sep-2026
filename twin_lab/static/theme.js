// Apply before styles paint. Only the appearance preference enters browser storage.
(() => {
  const key = "twin-lab-theme";
  const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
  const root = document.documentElement;
  const validPreference = value => value === "light" || value === "dark" ? value : null;
  let preference = null;
  let storageMessage = "";
  let button;
  let status;

  try {
    preference = validPreference(window.localStorage.getItem(key));
  } catch {
    storageMessage = "Theme preference could not be loaded. Using your system appearance.";
  }

  function applyTheme() {
    const dark = preference ? preference === "dark" : systemTheme.matches;
    root.dataset.theme = dark ? "dark" : "light";
    if (button) {
      button.setAttribute("aria-pressed", String(dark));
      button.title = dark ? "Switch to light mode" : "Switch to dark mode";
    }
    if (status) {
      status.textContent = storageMessage;
      status.hidden = !storageMessage;
    }
  }

  applyTheme();
  systemTheme.addEventListener("change", () => {
    if (preference === null) applyTheme();
  });
  window.addEventListener("storage", event => {
    if (event.key === key || event.key === null) {
      preference = validPreference(event.newValue);
      applyTheme();
    }
  });

  document.addEventListener("DOMContentLoaded", () => {
    button = document.getElementById("theme-toggle");
    status = document.getElementById("theme-status");
    button.addEventListener("click", () => {
      preference = root.dataset.theme === "dark" ? "light" : "dark";
      try {
        window.localStorage.setItem(key, preference);
        storageMessage = "";
      } catch {
        storageMessage = "Theme changed for this tab only. Browser storage is unavailable.";
      }
      applyTheme();
    });
    applyTheme();
  });
})();
