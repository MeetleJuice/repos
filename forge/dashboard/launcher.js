"use strict";
// A direct user gesture opens the window; no controller API or shared UI state.
(() => {
  const button = document.getElementById("open-dashboard");
  const fallback = document.getElementById("dashboard-popup-fallback");
  if (!button || !fallback) return;
  let dashboard = null;
  button.addEventListener("click", () => {
    try {
      if (!dashboard || dashboard.closed) {
        dashboard = window.open(
          "/dashboard",
          "IdeaFoundryDashboard",
          "popup=yes,width=1440,height=920,resizable=yes,scrollbars=yes",
        );
      }
      if (dashboard) {
        dashboard.opener = null;
        dashboard.focus();
        fallback.hidden = true;
        return;
      }
    } catch (_) {
      // A blocked or inaccessible window must leave a usable normal link.
      dashboard = null;
    }
    fallback.hidden = false;
    fallback.focus();
  });
})();
