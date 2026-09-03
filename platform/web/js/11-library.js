/* ---------- library ---------- */
function viewLibrary() {
  const sub = route.id;
  if (!sub) {
    let h = `<div class="wrap-wide"><h2 class="big">Library</h2><p class="sub" style="margin-bottom:22px">Reference material, worksheets and the plan documents. Everything here is also in your ${esc(CFG.folderLabel)} folder as files.</p>
    <div class="grid g3">
      <div class="card modelcard" onclick="go('#/library/glossary')"><h3>Glossary</h3><p class="sub">${DATA.library.glossary.length} terms in plain language. Starred ones first.</p></div>
      <div class="card modelcard" onclick="go('#/library/models')"><h3>Mental models</h3><p class="sub">The ${DATA.library.models.length} ideas worth memorising. Tap to flip.</p></div>
      <div class="card modelcard" onclick="go('#/library/resources')"><h3>Resources</h3><p class="sub">The short, opinionated list of what is worth your time.</p></div>
    </div>
    <p class="eyebrow" style="margin-top:26px">Worksheets</p>
    <p class="sub" style="margin-bottom:12px">Fill them in here. What you type stays with your progress.</p><div class="grid g3">`;
    DATA.library.templates.forEach(t => {
      const n = sheetFilled(t.slug);
      h += `<div class="card modelcard" onclick="go('#/library/t-${t.slug}')"><h3 style="font-size:16px">${esc(t.title)}</h3><p class="sub">${esc(t.blurb)}</p>
        ${t.fields ? `<div style="display:flex;gap:8px;align-items:center;margin-top:10px"><span class="bar" style="flex:1"><i style="width:${Math.round(n / t.fields * 100)}%"></i></span><span class="sub" style="font-size:11.5px">${n}/${t.fields}</span></div>` : ""}
        ${(t.uses || []).length ? `<p class="sub" style="font-size:11.5px;margin-top:6px">Used in ${t.uses.join(", ")}</p>` : ""}</div>`;
    });
    h += `</div>
    <p class="eyebrow" style="margin-top:26px">The plan</p><div class="grid g3">
      <div class="card modelcard" onclick="go('#/plan/curriculum')"><h3 style="font-size:16px">Curriculum</h3><p class="sub">All ${MODS.length} modules and the time budget.</p></div>
      <div class="card modelcard" onclick="go('#/plan/how')"><h3 style="font-size:16px">How to study</h3><p class="sub">How not to waste the ${CFG.hours} hours.</p></div>
      <div class="card modelcard" onclick="go('#/plan/expert')"><h3 style="font-size:16px">Path to expert</h3><p class="sub">What comes after the last module.</p></div>
    </div></div>`;
    $("#view").innerHTML = h;
    return;
  }
  if (sub === "glossary") return viewGlossary();
  if (sub === "models") return viewModels();
  if (sub === "resources") {
    $("#view").innerHTML = `<div class="wrap"><button class="btn sm" onclick="go('#/library')">← Library</button>
      <div class="prose" style="padding-left:0;margin-top:18px">${DATA.library.resources}</div></div>`;
    return;
  }
  if (sub.startsWith("t-")) {
    const t = DATA.library.templates.find(x => x.slug === sub.slice(2));
    if (!t) return go("#/library");
    viewWorksheet(t);
  }
}
let glossFilter = "", glossStar = false;
function viewGlossary() {
  const terms = DATA.library.glossary.filter(t =>
    (!glossStar || t.star) &&
    (!glossFilter || (t.term + " " + t.def).toLowerCase().includes(glossFilter.toLowerCase())));
  let h = `<div class="wrap"><button class="btn sm" onclick="go('#/library')">← Library</button>
    <h2 class="big" style="margin-top:14px">Glossary</h2>
    <p class="sub" style="margin-bottom:16px">${DATA.library.glossary.length} terms. The ${DATA.library.glossary.filter(t => t.star).length} starred ones are the ones to know cold.</p>
    <div style="display:flex;gap:9px;margin-bottom:18px;flex-wrap:wrap">
      <input type="text" id="gf" placeholder="Filter terms…" value="${esc(glossFilter)}" style="flex:1;min-width:200px">
      <button class="btn ${glossStar ? "primary" : ""}" onclick="glossStar=!glossStar;viewGlossary()">★ Core only</button>
    </div><div class="card">`;
  if (!terms.length) h += `<p class="sub">Nothing matches.</p>`;
  terms.forEach(t => {
    h += `<div class="glossrow">${t.star ? '<span class="star">★</span> ' : ""}<b>${esc(t.term)}</b> — ${esc(t.def)}</div>`;
  });
  h += `</div></div>`;
  $("#view").innerHTML = h;
  const gf = $("#gf");
  gf.addEventListener("input", e => { glossFilter = e.target.value; const p = gf.selectionStart; viewGlossary(); const n = $("#gf"); n.focus(); n.setSelectionRange(p, p); });
}
function viewModels() {
  const n = DATA.library.models.length;
  let h = `<div class="wrap-wide"><button class="btn sm" onclick="go('#/library')">← Library</button>
    <h2 class="big" style="margin-top:14px">Mental models</h2>
    <p class="sub" style="margin-bottom:20px">${n ? n + " idea" + (n === 1 ? "" : "s") + " that compress the whole course. Click any card to open it." : "This course ships no mental models yet."}</p><div class="grid g2">`;
  DATA.library.models.forEach((m, i) => {
    h += `<div class="card modelcard" onclick="toggleModel(${i})"><h3>${i + 1}. ${esc(m.title)}</h3>
      <div id="mm${i}" class="prose hidden" style="padding-left:0;font-size:15px;margin-top:8px">${m.html}</div>
      <p class="sub" id="mh${i}" style="margin-top:4px">Click to open</p></div>`;
  });
  h += `</div>${DATA.library.models_note ? `<div class="card" style="margin-top:20px"><div class="prose" style="padding-left:0">${DATA.library.models_note}</div></div>` : ""}</div>`;
  $("#view").innerHTML = h;
}
function toggleModel(i) {
  document.getElementById("mm" + i).classList.toggle("hidden");
  const hint = document.getElementById("mh" + i);
  hint.classList.toggle("hidden");
}
function viewPlan() {
  const map = { curriculum: DATA.library.plan.curriculum, how: DATA.library.plan.how, expert: DATA.library.plan.expert };
  const html = map[route.id] || map.curriculum;
  $("#view").innerHTML = `<div class="wrap"><button class="btn sm" onclick="go('#/library')">← Library</button>
    <div class="prose" style="padding-left:0;margin-top:18px">${html}</div></div>`;
}
