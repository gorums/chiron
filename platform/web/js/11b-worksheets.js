/* ---------- worksheets you can fill in ----------
   The build turned every natural blank in a template into an input with a data-f number.
   Values live in S.sheets[slug][n]; a worksheet is a deliverable, so it syncs with the
   rest of your progress and can be copied out as text or handed to Claude for review. */
function sheetVals(slug) { if (!S.sheets[slug]) S.sheets[slug] = {}; return S.sheets[slug]; }
function sheetFilled(slug) { const v = S.sheets[slug] || {}; return Object.keys(v).filter(k => k !== "_fb" && v[k] !== "" && v[k] !== false && v[k] != null).length; }
let sheetTimer = null;
function viewWorksheet(t) {
  const v = sheetVals(t.slug), n = sheetFilled(t.slug), fb = v._fb;
  $("#view").innerHTML = `<div class="wrap">
    <div style="display:flex;gap:9px;align-items:center;flex-wrap:wrap">
      <button class="btn sm" onclick="go('#/library')">← Library</button>
      <span style="flex:1"></span>
      ${t.fields ? `<span class="sub" id="sheetcount">${n} of ${t.fields} filled</span>` : ""}
      <button class="btn sm" onclick="copySheet('${t.slug}')">Copy as text</button>
      ${t.fields && connMode() !== "none" ? `<button class="btn sm primary" id="sheetreview" onclick="reviewSheet('${t.slug}')">Ask Claude to review</button>` : ""}
      ${t.fields ? `<button class="btn sm ghost" onclick="clearSheet('${t.slug}')">Clear</button>` : ""}
    </div>
    ${(t.uses || []).length ? `<p class="sub" style="margin-top:10px">Used in ${t.uses.map(id => `<a href="#/m/${id}/4">${id}</a>`).join(", ")}.</p>` : ""}
    <div class="prose sheet" id="sheet" style="padding-left:0;margin-top:18px">${t.html}</div>
    <div id="sheetfb">${fb ? `<div class="fb ${fb.verdict || ""}"><b>Claude's review · ${new Date(fb.at).toLocaleDateString()}</b>${mdLite(fb.text)}</div>` : ""}</div>
  </div>`;
  const host = $("#sheet");
  host.querySelectorAll("[data-f]").forEach(el => {
    const k = el.dataset.f;
    if (el.type === "checkbox") el.checked = !!v[k]; else el.value = v[k] || "";
    const onchange = () => {
      v[k] = el.type === "checkbox" ? el.checked : el.value;
      clearTimeout(sheetTimer); sheetTimer = setTimeout(() => { save(); const c = $("#sheetcount"); if (c) c.textContent = sheetFilled(t.slug) + " of " + t.fields + " filled"; }, 500);
    };
    el.addEventListener("input", onchange); el.addEventListener("change", onchange);
  });
}
/* the worksheet as text, with what you typed in place of the blanks */
function sheetText(t) {
  const tmp = document.createElement("div"); tmp.innerHTML = t.html;
  const v = S.sheets[t.slug] || {};
  tmp.querySelectorAll("[data-f]").forEach(el => {
    const k = el.dataset.f, val = v[k];
    const txt = el.type === "checkbox" ? (val ? "[x]" : "[ ]") : (val && String(val).trim() ? "[" + val + "]" : "____");
    el.replaceWith(document.createTextNode(txt));
  });
  tmp.querySelectorAll("tr").forEach(tr => { tr.querySelectorAll("td,th").forEach((c, i) => { if (i) c.insertAdjacentText("afterbegin", " | "); }); });
  return (tmp.innerText || tmp.textContent || "").replace(/\n{3,}/g, "\n\n").trim();
}
function copySheet(slug) {
  const t = DATA.library.templates.find(x => x.slug === slug); if (!t) return;
  toast(clip(sheetText(t)) ? "Worksheet copied" : "Could not copy");
}
function clearSheet(slug) {
  if (!confirm("Clear everything you typed into this worksheet?")) return;
  const fb = (S.sheets[slug] || {})._fb;
  S.sheets[slug] = fb ? { _fb: fb } : {}; save();
  const t = DATA.library.templates.find(x => x.slug === slug); if (t) viewWorksheet(t);
}
