/* Checks for flagging a quiz question (web/js/practice/flags.js, core/state.js), run inside
   a booted page by page_smoke.js --checks. The page's globals - STATE, MODS, byId, blank,
   mergeStates, addFlag, ... - are in scope. */
"use strict";
function assert(cond, msg) {
  if (!cond) throw new Error("flag check failed: " + msg);
}
const m = MODS[0];
assert(m.assess.quiz.length >= 1, "a module with a quiz");
STATE = blank();

/* a flag carries the question's text and the reader's note, once per question */
const f = addFlag(m.id, 0, "  the key is wrong  ");
assert(f && f.qi === 0 && f.q === m.assess.quiz[0].q, "the flag names the question");
assert(f.note === "the key is wrong", "the note is kept, trimmed");
assert(addFlag(m.id, 0, "again") === null, "a question is flagged once");
assert(addFlag(m.id, 99, "") === null, "a question that does not exist cannot be flagged");
assert(allFlags().length === 1 && allFlags()[0].mid === m.id, "listed with its module");
assert(flagButton(m.id, 0).indexOf("qUnflag") > 0, "the button offers to take it back");
assert(flagButton(m.id, 99).indexOf("qFlag(") > 0, "and to flag an unflagged one");

/* taking it back is remembered, so a stale copy cannot bring it back */
const id = f.id;
removeFlag(m.id, 0);
assert(allFlags().length === 0, "taken back");
assert(STATE.gone[id], "the deletion is remembered");

/* two copies merge like marks: the union by id, minus what either side deleted */
const older = Object.assign(blank(), { updatedAt: 1 });
older.flags = {
  [m.id]: [
    { id: "fa", qi: 0, q: "a", note: "", ts: 1 },
    { id: "fb", qi: 1, q: "b", note: "", ts: 1 },
  ],
};
const newer = Object.assign(blank(), { updatedAt: 2 });
newer.flags = { [m.id]: [{ id: "fa", qi: 0, q: "a", note: "later", ts: 2 }] };
newer.gone = { fb: 2 };
const merged = mergeStates(older, newer);
const rows = merged.flags[m.id];
assert(rows.length === 1 && rows[0].id === "fa", "fb deleted on the newer side stays gone");
assert(rows[0].note === "later", "the later copy wins the clash");

/* the Marks page's row for it names the question and offers the quiz */
STATE = blank();
const kept = addFlag(m.id, 0, "");
const html = flagRow(Object.assign({ mid: m.id }, kept));
assert(html.indexOf("flagged question 1") > 0, "the row says which question");
assert(html.indexOf(stepHash(m.id, 2)) > 0, "and links to the quiz");

console.log("flag checks passed");
