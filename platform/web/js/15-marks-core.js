/* ---- marks: highlights, notes and open questions on a passage ----
   status: "hl" a plain highlight · "open" a question you still need answered
         · "answered" one that got its answer (from the tutor, or from you) */
function marksOf(mid) {
  if (!STATE.marks) STATE.marks = {};
  if (!STATE.marks[mid]) STATE.marks[mid] = [];
  return STATE.marks[mid];
}
function allMarks() {
  const out = [];
  Object.keys(STATE.marks || {}).forEach(mid =>
    marksOf(mid).forEach(m => out.push(Object.assign({ mid }, m)))
  );
  return out.sort((a, b) => b.ts - a.ts);
}
function openQs() {
  return allMarks().filter(m => m.status === "open").length;
}
function findMark(mid, id) {
  return marksOf(mid).find(x => x.id === id);
}
function addMark(mid, sec, text, status) {
  const m = {
    id: "k" + Date.now().toString(36) + Math.floor(Math.random() * 999),
    sec,
    text,
    note: "",
    q: "",
    ans: "",
    status: status || "hl",
    ts: Date.now(),
  };
  marksOf(mid).push(m);
  save();
  return m;
}
function setMarkStatus(mid, id, status) {
  const m = findMark(mid, id);
  if (!m || m.status === status) return;
  m.status = status;
  save();
  if (route.view === "m" && route.id === mid && route.step === 1) applyMarksFresh(mid);
  renderSidebar();
}
function delMark(mid, id) {
  STATE.marks[mid] = marksOf(mid).filter(x => x.id !== id);
  forget(id);
  save();
  if (route.view === "m") renderStep(byId(mid), 1);
  else render();
  closePanel();
  toast("Removed");
}
function markClass(m) {
  return m.status === "open" ? "q" : m.status === "answered" ? "answered" : "";
}

function applyMarks(mid) {
  marksOf(mid).forEach(mk => {
    const host = document.querySelector("#sec" + mk.sec + " .prose");
    if (!host) return;
    wrapText(host, mk.text, markClass(mk), mk.id);
  });
}
/* re-tint marks already in the page without re-rendering the step */
function applyMarksFresh(mid) {
  marksOf(mid).forEach(mk => {
    document.querySelectorAll(`mark.hl[data-k="${mk.id}"]`).forEach(el => {
      el.className = "hl " + markClass(mk);
    });
  });
}
function wrapText(el, text, cls, id) {
  if (!text) return false;
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
  const nodes = [];
  let full = "";
  while (walker.nextNode()) {
    const n = walker.currentNode;
    if (n.parentElement && n.parentElement.closest("mark")) continue;
    nodes.push([n, full.length]);
    full += n.textContent;
  }
  if (!nodes.length) return false;
  // whitespace-tolerant match: normalise, keep a map back to raw offsets
  let norm = "",
    map = [],
    prevSp = false;
  for (let k = 0; k < full.length; k++) {
    const c = full[k];
    if (c === " " || c === "\n" || c === "\t" || c === "\r") {
      if (prevSp) continue;
      norm += " ";
      map.push(k);
      prevSp = true;
    } else {
      norm += c;
      map.push(k);
      prevSp = false;
    }
  }
  const needle = String(text).replace(/\s+/g, " ").trim();
  if (!needle) return false;
  const ni = norm.indexOf(needle);
  if (ni < 0) return false;
  const i = map[ni],
    j = map[ni + needle.length - 1] + 1;
  let sN = null,
    sO = 0,
    eN = null,
    eO = 0;
  for (const [n, off] of nodes) {
    const len = n.textContent.length;
    if (sN === null && i >= off && i < off + len) {
      sN = n;
      sO = i - off;
    }
    if (eN === null && j > off && j <= off + len) {
      eN = n;
      eO = j - off;
    }
  }
  if (!sN || !eN) return false;
  try {
    const r = document.createRange();
    r.setStart(sN, sO);
    r.setEnd(eN, eO);
    const mk = document.createElement("mark");
    mk.className = "hl " + cls;
    mk.dataset.k = id;
    mk.appendChild(r.extractContents());
    r.insertNode(mk);
    return true;
  } catch (e) {
    return false;
  }
}
