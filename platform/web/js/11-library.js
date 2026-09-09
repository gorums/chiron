/* ---------- library ---------- */
function viewLibrary() {
  const sub = route.id;
  if (!sub) {
    let h = `<div class="wrap-wide"><h2 class="big">Library</h2><p class="lede">Reference material, worksheets and the plan documents. Everything here is also in your ${esc(CFG.folderLabel)} folder as files.</p>
    <div class="grid g3">
      <button class="card modelcard" onclick="go('#/library/glossary')"><h3>Glossary</h3><p class="sub">${DATA.library.glossary.length} terms in plain language. Starred ones first.</p></button>
      <button class="card modelcard" onclick="go('#/library/models')"><h3>Mental models</h3><p class="sub">The ${DATA.library.models.length} ideas worth memorising. Open to read.</p></button>
      <button class="card modelcard" onclick="go('#/library/resources')"><h3>Resources</h3><p class="sub">The short, opinionated list of what is worth your time.</p></button>
    </div>
    <h3 class="eyebrow gap-top-lg">Worksheets</h3>
    <p class="sub gap-bottom">Fill them in here. What you type stays with your progress.</p><div class="grid g3">`;
    DATA.library.templates.forEach(t => {
      const n = sheetFilled(t.slug);
      h += `<button class="card modelcard" onclick="go('#/library/t-${t.slug}')"><h3 class="h-sm">${esc(t.title)}</h3><p class="sub">${esc(t.blurb)}</p>
        ${t.fields ? `<div class="rowline"><span class="bar grow"><i style="width:${Math.round((n / t.fields) * 100)}%"></i></span><span class="sub tiny">${n}/${t.fields}</span></div>` : ""}
        ${(t.uses || []).length ? `<p class="sub tiny gap-top-sm">Used in ${t.uses.join(", ")}</p>` : ""}</button>`;
    });
    h += `</div>
    <h3 class="eyebrow gap-top-lg">The plan</h3><div class="grid g3">
      <button class="card modelcard" onclick="go('#/plan/curriculum')"><h3 class="h-sm">Curriculum</h3><p class="sub">All ${MODS.length} modules and the time budget.</p></button>
      <button class="card modelcard" onclick="go('#/plan/how')"><h3 class="h-sm">How to study</h3><p class="sub">How not to waste the ${CFG.hours} hours.</p></button>
      <button class="card modelcard" onclick="go('#/plan/expert')"><h3 class="h-sm">Path to expert</h3><p class="sub">What comes after the last module.</p></button>
    </div></div>`;
    $("#view").innerHTML = h;
    return;
  }
  if (sub === "glossary") return viewGlossary();
  if (sub === "models") return viewModels();
  if (sub === "resources") {
    $("#view").innerHTML =
      `<div class="wrap"><button class="btn sm" onclick="go('#/library')">← Library</button>
      <h2 class="big gap-top">Resources</h2>
      <p class="lede">What is worth your time after this course, and what is not.</p>
      <div class="prose flat gap-top-lg">${DATA.library.resources}</div></div>`;
    return;
  }
  if (sub.startsWith("t-")) {
    const t = DATA.library.templates.find(x => x.slug === sub.slice(2));
    if (!t) return go("#/library");
    viewWorksheet(t);
  }
}
let glossFilter = "",
  glossStar = false;
/* The palette lands on a term rather than on the top of the list. */
function openGlossary(term) {
  glossFilter = term || "";
  glossStar = false;
  go("#/library/glossary");
}
function viewGlossary() {
  const terms = DATA.library.glossary.filter(
    t =>
      (!glossStar || t.star) &&
      (!glossFilter || (t.term + " " + t.def).toLowerCase().includes(glossFilter.toLowerCase()))
  );
  let h = `<div class="wrap"><button class="btn sm" onclick="go('#/library')">← Library</button>
    <h2 class="big gap-top">Glossary</h2>
    <p class="lede">${DATA.library.glossary.length} terms. The ${DATA.library.glossary.filter(t => t.star).length} starred ones are the ones to know cold.</p>
    <div class="rowline wrapped" style="margin:16px 0 18px">
      <label class="visually-hidden" for="gf">Filter terms</label>
      <input type="text" id="gf" class="grow wide-input" placeholder="Filter terms…" value="${esc(glossFilter)}">
      <button class="btn ${glossStar ? "primary" : ""}" aria-pressed="${glossStar}" onclick="glossStar=!glossStar;viewGlossary()">★ Core only</button>
    </div><div class="card">`;
  if (!terms.length) h += `<p class="sub">Nothing matches.</p>`;
  terms.forEach(t => {
    h += `<div class="glossrow">${t.star ? '<span class="star">★</span> ' : ""}<b>${esc(t.term)}</b> — ${esc(t.def)}</div>`;
  });
  h += `</div></div>`;
  $("#view").innerHTML = h;
  const gf = $("#gf");
  gf.addEventListener("input", e => {
    glossFilter = e.target.value;
    const p = gf.selectionStart;
    viewGlossary();
    const n = $("#gf");
    n.focus();
    n.setSelectionRange(p, p);
  });
}
let modelOpen = null; // index of the mental model the palette asked to open
function openModelCard(i) {
  modelOpen = i;
  go("#/library/models");
}
function viewModels() {
  const n = DATA.library.models.length;
  const opening = modelOpen;
  modelOpen = null;
  let h = `<div class="wrap-wide"><button class="btn sm" onclick="go('#/library')">← Library</button>
    <h2 class="big gap-top">Mental models</h2>
    <p class="lede">${n ? n + " idea" + (n === 1 ? "" : "s") + " that compress the whole course. Open any card to read it." : "This course ships no mental models yet."}</p><div class="grid g2 gap-top-lg">`;
  DATA.library.models.forEach((m, i) => {
    const on = opening === i;
    h += `<button class="card modelcard" id="mc${i}" aria-expanded="${on}" onclick="toggleModel(${i})"><h3>${i + 1}. ${esc(m.title)}</h3>
      <div id="mm${i}" class="prose ${on ? "" : "hidden"}" style="padding-left:0;font-size:15px;margin-top:8px">${m.html}</div>
      <p class="sub ${on ? "hidden" : ""}" id="mh${i}" style="margin-top:4px">Open to read</p></button>`;
  });
  h += `</div>${DATA.library.models_note ? `<div class="card gap-top-lg"><div class="prose flat">${DATA.library.models_note}</div></div>` : ""}</div>`;
  $("#view").innerHTML = h;
  if (opening != null) {
    const el = document.getElementById("mc" + opening);
    if (el) el.scrollIntoView({ block: "center" });
  }
}
function toggleModel(i) {
  const body = document.getElementById("mm" + i);
  body.classList.toggle("hidden");
  document.getElementById("mh" + i).classList.toggle("hidden");
  const card = document.getElementById("mc" + i);
  if (card) card.setAttribute("aria-expanded", String(!body.classList.contains("hidden")));
}
const PLAN_PAGES = {
  curriculum: {
    title: "Curriculum",
    lede: "Every module, in order, with the time it is budgeted.",
  },
  how: { title: "How to study", lede: "How to spend the hours so they hold." },
  expert: { title: "Path to expert", lede: "What comes after the last module." },
};
function viewPlan() {
  const map = {
    curriculum: DATA.library.plan.curriculum,
    how: DATA.library.plan.how,
    expert: DATA.library.plan.expert,
  };
  const key = map[route.id] ? route.id : "curriculum";
  const page = PLAN_PAGES[key];
  $("#view").innerHTML =
    `<div class="wrap"><button class="btn sm" onclick="go('#/library')">← Library</button>
    <h2 class="big gap-top">${esc(page.title)}</h2>
    <p class="lede">${esc(page.lede)}</p>
    <div class="prose flat gap-top-lg">${map[key]}</div></div>`;
}
