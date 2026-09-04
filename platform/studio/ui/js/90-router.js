/* ---------- routing ---------- */

function parseRoute() {
  const raw = (location.hash || "#/").slice(1);
  const [path, qs] = raw.split("?");
  const query = {};
  new URLSearchParams(qs || "").forEach((v, k) => {
    query[k] = v;
  });
  const bits = path.split("/").filter(Boolean);
  if (bits[0] === "new") return { name: "new", id: null, query };
  if (bits[0] === "search") return { name: "search", id: null, query };
  if (bits[0] === "settings") return { name: "settings", id: null, query };
  if (bits[0] === "job" && bits[1]) return { name: "job", id: bits[1], query };
  if (bits[0] === "course" && bits[1]) {
    return { name: bits[2] === "edit" ? "edit" : "course", id: decodeURIComponent(bits[1]), query };
  }
  return { name: "library", id: null, query };
}

function render() {
  route = parseRoute();
  if (route.name !== "job" && stream) {
    stream.close();
    stream = null;
  }
  if (route.name !== "job") {
    clearInterval(jobTimer);
    document.title = "Course Studio";
  }
  if (route.name !== "settings") clearInterval(logTimer);
  document
    .querySelectorAll(".topnav a")
    .forEach(a =>
      a.classList.toggle(
        "active",
        (route.name === "library" && a.id === "nav-library") ||
          (route.name === "new" && a.id === "nav-new") ||
          (route.name === "settings" && a.id === "nav-settings")
      )
    );
  window.scrollTo(0, 0);
  if (route.name === "new") return viewNew();
  if (route.name === "search") return viewSearch();
  if (route.name === "settings") return viewSettingsPage();
  if (route.name === "job") return viewJob();
  if (route.name === "course") return viewCourse();
  if (route.name === "edit") return viewEdit();
  return viewLibrary();
}

window.addEventListener("hashchange", () => {
  refresh().then(render).catch(render);
});
$("#themebtn").onclick = cycleTheme;
$("#searchform").onsubmit = e => {
  e.preventDefault();
  const q = $("#searchq").value.trim();
  if (q) location.hash = "#/search?q=" + encodeURIComponent(q);
};

refresh()
  .then(() => {
    // Reattach to a run that is still going, so closing the tab is not the same as stopping.
    const live = (STATE.jobs || []).find(j => !FINISHED.includes(j.status));
    if (live && (!location.hash || location.hash === "#/" || location.hash === "#")) {
      location.hash = "#/job/" + live.id;
      return;
    }
    render();
  })
  .catch(err => {
    $("#view").innerHTML =
      `<div class="card"><h3>Cannot reach the Studio server</h3><p class="sub">${esc(err.message)}</p></div>`;
  });
