/* ---- flags: quiz questions the reader thinks are wrong ----
   A quiz item is model output, and a wrong answer key is the defect a reader meets most
   often. A flag is the reader's way of saying so: it is kept in STATE.flags, syncs to
   Studio with the rest of the state, and comes back on the course's Questions tab as a
   patch brief. A flag is {id, qi, q, note, ts}, keyed by module like a mark. */
function flagsOf(mid) {
  if (!STATE.flags) STATE.flags = {};
  if (!STATE.flags[mid]) STATE.flags[mid] = [];
  return STATE.flags[mid];
}
function allFlags() {
  const out = [];
  Object.keys(STATE.flags || {}).forEach(mid =>
    flagsOf(mid).forEach(f => out.push(Object.assign({ mid }, f)))
  );
  return out.sort((a, b) => b.ts - a.ts);
}
function findFlag(mid, qi) {
  return flagsOf(mid).find(f => f.qi === qi);
}
function addFlag(mid, qi, note) {
  const item = (byId(mid).assess.quiz || [])[qi];
  if (!item || findFlag(mid, qi)) return null;
  const f = {
    id: "f" + Date.now().toString(36) + Math.floor(Math.random() * 999),
    qi,
    q: item.q || "",
    note: String(note || "").trim(),
    ts: Date.now(),
  };
  flagsOf(mid).push(f);
  save();
  return f;
}
function removeFlag(mid, qi) {
  const f = findFlag(mid, qi);
  if (!f) return;
  STATE.flags[mid] = flagsOf(mid).filter(x => x.qi !== qi);
  forget(f.id);
  save();
}

/* The control under a quiz verdict: flag it, or take the flag back. */
function flagButton(mid, qi) {
  const hint = esc(help("flagged question"));
  if (findFlag(mid, qi))
    return `<button class="btn sm ghost" data-help="${hint}" onclick="qUnflag('${mid}',${qi})">Flagged · take it back</button>`;
  return `<button class="btn sm ghost" data-help="${hint}" onclick="qFlag('${mid}',${qi})">${ico("flag", 14)} Flag this question</button>`;
}
function qFlag(mid, qi) {
  promptModal("What is wrong with this question?", "", "Flag it", note => {
    addFlag(mid, qi, note);
    toast("Flagged for the course's owner");
    drawQuiz();
  });
}
function qUnflag(mid, qi) {
  removeFlag(mid, qi);
  drawQuiz();
}
