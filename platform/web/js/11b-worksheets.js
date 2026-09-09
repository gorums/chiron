/* ---------- worksheets you can fill in ----------
   The build turned every natural blank in a template into an input with a data-f number.
   Values live in STATE.sheets[slug][n]; a worksheet is a deliverable, so it syncs with the
   rest of your progress and can be copied out as text or handed to the tutor for review. */
function sheetVals(slug) {
  if (!STATE.sheets[slug]) STATE.sheets[slug] = {};
  return STATE.sheets[slug];
}
function sheetFilled(slug) {
  const v = STATE.sheets[slug] || {};
  return Object.keys(v).filter(k => k !== "_fb" && v[k] !== "" && v[k] !== false && v[k] != null)
    .length;
}
let sheetTimer = null;
function viewWorksheet(t) {
  const v = sheetVals(t.slug),
    n = sheetFilled(t.slug),
    fb = v._fb;
  // The way back is to the exercise this worksheet belongs to, not just to the library:
  // a worksheet is opened from a module's Apply step and that is where it is finished.
  const from = (t.uses || []).map(byId).filter(Boolean)[0];
  $("#view").innerHTML = `<div class="wrap">
    <div class="rowline wrapped">
      ${from ? `<a class="btn sm" href="${stepHash(from.id, 4)}">← ${from.id} · Apply</a>` : ""}
      <a class="btn sm" href="#/library">← Library</a>
      <span class="spacer"></span>
      ${t.fields ? `<span class="sub" id="sheetcount">${n} of ${t.fields} filled</span>` : ""}
      <button class="btn sm" onclick="copySheet('${t.slug}')">Copy as text</button>
      ${t.fields && connMode() !== "none" ? `<button class="btn sm primary" id="sheetreview" onclick="reviewSheet('${t.slug}')">Ask the tutor to review it</button>` : ""}
      ${t.fields ? `<button class="btn sm" onclick="clearSheet('${t.slug}')">Clear</button>` : ""}
    </div>
    <h2 class="big gap-top">${esc(t.title)}</h2>
    ${(t.uses || []).length ? `<p class="sub">Used in ${t.uses.map(id => `<a href="${stepHash(id, 4)}">${id}</a>`).join(", ")}.</p>` : ""}
    <div class="prose sheet flat gap-top-lg" id="sheet">${t.html}</div>
    <div id="sheetfb">${fb ? `<div class="fb ${fb.verdict || ""}"><b>The tutor's review · ${new Date(fb.at).toLocaleDateString()}</b>${mdLite(fb.text)}</div>` : ""}</div>
  </div>`;
  const host = $("#sheet");
  host.querySelectorAll("[data-f]").forEach(el => {
    const k = el.dataset.f;
    if (el.type === "checkbox") el.checked = !!v[k];
    else el.value = v[k] || "";
    const onchange = () => {
      v[k] = el.type === "checkbox" ? el.checked : el.value;
      clearTimeout(sheetTimer);
      sheetTimer = setTimeout(() => {
        save();
        const c = $("#sheetcount");
        if (c) c.textContent = sheetFilled(t.slug) + " of " + t.fields + " filled";
      }, 500);
    };
    el.addEventListener("input", onchange);
    el.addEventListener("change", onchange);
  });
}
/* the worksheet as text, with what you typed in place of the blanks */
function sheetText(t) {
  const tmp = document.createElement("div");
  tmp.innerHTML = t.html;
  const v = STATE.sheets[t.slug] || {};
  tmp.querySelectorAll("[data-f]").forEach(el => {
    const k = el.dataset.f,
      val = v[k];
    const txt =
      el.type === "checkbox"
        ? val
          ? "[x]"
          : "[ ]"
        : val && String(val).trim()
          ? "[" + val + "]"
          : "____";
    el.replaceWith(document.createTextNode(txt));
  });
  tmp.querySelectorAll("tr").forEach(tr => {
    tr.querySelectorAll("td,th").forEach((c, i) => {
      if (i) c.insertAdjacentText("afterbegin", " | ");
    });
  });
  return (tmp.innerText || tmp.textContent || "").replace(/\n{3,}/g, "\n\n").trim();
}
function copySheet(slug) {
  const t = DATA.library.templates.find(x => x.slug === slug);
  if (!t) return;
  toast(clip(sheetText(t)) ? "Worksheet copied" : "Could not copy");
}
function clearSheet(slug) {
  confirmModal(
    "Clear this worksheet?",
    "Everything you typed into it goes. The tutor's last review of it stays.",
    "Clear it",
    () => {
      const fb = (STATE.sheets[slug] || {})._fb;
      STATE.sheets[slug] = fb ? { _fb: fb } : {};
      save();
      const t = DATA.library.templates.find(x => x.slug === slug);
      if (t) viewWorksheet(t);
    },
    true
  );
}
