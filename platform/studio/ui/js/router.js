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
  if (bits[0] === "jobs") return { name: "jobs", id: null, query };
  if (bits[0] === "job" && bits[1]) return { name: "job", id: bits[1], query };
  if (bits[0] === "course" && bits[1]) {
    return { name: bits[2] === "edit" ? "edit" : "course", id: decodeURIComponent(bits[1]), query };
  }
  return { name: "library", id: null, query };
}

/* Which nav item is the parent of the route being shown. Courses owns everything that is
   about one course — the page, its editor, a job it started, a search across them all. */
const NAV_OWNER = {
  library: "nav-library",
  course: "nav-library",
  edit: "nav-library",
  search: "nav-library",
  job: "nav-library",
  jobs: "nav-library",
  new: "nav-new",
  settings: "nav-settings",
};
function paintNav() {
  const owner = NAV_OWNER[route.name] || "nav-library";
  document.querySelectorAll(".topnav a").forEach(a => {
    const on = a.id === owner;
    a.classList.toggle("active", on);
    if (on) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
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
  paintNav();
  closeNavMenu();
  window.scrollTo(0, 0);
  if (route.name === "new") return viewNew();
  if (route.name === "search") return viewSearch();
  if (route.name === "settings") return viewSettingsPage();
  if (route.name === "jobs") return viewJobs();
  if (route.name === "job") return viewJob();
  if (route.name === "course") return viewCourse();
  if (route.name === "edit") return viewEdit();
  return viewLibrary();
}

window.addEventListener("hashchange", () => {
  refresh().then(render).catch(render);
});
$("#themebtn").onclick = cycleTheme;
$("#navmenubtn").onclick = toggleNavMenu;
$("#searchform").onsubmit = e => {
  e.preventDefault();
  const q = $("#searchq").value.trim();
  if (q) location.hash = "#/search?q=" + encodeURIComponent(q);
};

refresh()
  .then(render)
  .catch(err => {
    $("#view").innerHTML =
      `<div class="card"><h3>Cannot reach the Studio server</h3><p class="sub">${esc(err.message)}</p>
       <div class="rowline gap-top"><button class="btn primary" onclick="location.reload()">Try again</button></div></div>`;
  });
