/* Checks for the learner memory (web/js/tutor/learner.js), run inside a booted page by
   page_smoke.js --checks. The page's globals - STATE, MODS, learnerEvidence, ... - are in
   scope. Each check builds the state it needs and throws when the outcome is wrong. */
"use strict";
function assert(cond, msg) {
  if (!cond) throw new Error("learner check failed: " + msg);
}
const m = MODS[0];
const quizItem = m.assess.quiz[0];
STATE = blank();

/* a "certain" miss weighs more than a guess, and the missed question becomes a chip */
const p = progressOf(m.id);
p.quiz = {
  i: 1,
  a: [{ resp: 0, committed: true, answered: true, ok: false, conf: 3, hinted: 0, at: 5 }],
  finished: true,
  seed: 1,
};
p.elabFb = {
  0: {
    verdict: "partial",
    at: 9,
    text: "**Covered** — the gist.\n**Missing** — the second-order effect.\n**Wrong** — nothing\n**Ask yourself** — What changes if the price doubles?",
  },
};
let ev = learnerEvidence();
assert(ev.length === 2, "one quiz miss and one graded exercise: got " + ev.length);
assert(ev[0].kind === "graded" && ev[0].at === 9, "newest first");
assert(
  ev[0].text.indexOf("Missing: the second-order effect") >= 0,
  "grader findings are picked up"
);
assert(ev[0].text.indexOf("Wrong") < 0, "a finding of nothing is not a finding");
assert(
  ev[0].ask === "What changes if the price doubles?",
  "the Ask-yourself line is kept: " + ev[0].ask
);
assert(ev[1].weight === 3, "a certain miss weighs 3");
assert(weakSpots()[0].m.id === m.id, "the module is a weak spot");

let chips = gapChips(m.id);
assert(chips.length === Math.min(2, LEARNER.gapChips), "two chips: " + JSON.stringify(chips));
assert(chips[0] === "What changes if the price doubles?", "the newest evidence leads the chips");
// the topic is trimmed to fit a chip, so match on the opening of the question
assert(chips[1].indexOf(quizItem.q.slice(0, 60)) >= 0, "the missed question is a chip too");
assert(learnerContext(m.id).indexOf("What went wrong in this module") >= 0, "the tutor is told");
assert(learnerContext(MODS[MODS.length - 1].id) === "", "a module with no evidence gets nothing");

/* a model reply is checked before it is stored: bad module ids are dropped */
const good = {
  id: "g1",
  mid: m.id,
  topic: "Elasticity",
  why: "Missed twice.",
  ask: "When does a price cut lower revenue?",
};
const bad = { id: "g2", mid: "NOPE", topic: "x", why: "y", ask: "z" };
const replyJson = JSON.stringify({
  brief: "Terse and overconfident.",
  strengths: ["Definitions"],
  gaps: [good, bad],
  closed: [],
});
const reply = parseLearnerReply("Here you go:\n```json\n" + replyJson + "\n```");
assert(reply && reply.gaps.length === 1, "one valid gap kept");
assert(parseLearnerReply("no json here") === null, "junk is refused");
applyLearnerReply(reply);
assert(learner().brief === "Terse and overconfident.", "brief stored");
assert(openGaps().length === 1 && openGaps()[0].status === "open", "gap is open");
chips = gapChips(m.id);
assert(chips[0] === good.ask, "the gap's question leads the chips now");
assert(learnerContext(m.id).indexOf("Elasticity") >= 0, "the gap reaches the tutor prompt");

/* closing sticks through a refresh and through a merge */
closeGap("g1");
assert(openGaps().length === 0, "closed gap is gone");
applyLearnerReply(reply);
assert(openGaps().length === 0, "a refresh cannot reopen a gap the reader closed");
const other = blank();
other.learner = {
  brief: "older",
  strengths: [],
  gaps: [Object.assign({}, good, { status: "open", at: 1 })],
  closed: {},
  at: 1,
  events: 1,
};
other.updatedAt = 1;
STATE.updatedAt = 2;
const merged = mergeStates(other, STATE);
assert(merged.learner.brief === "Terse and overconfident.", "the later brief wins");
assert(merged.learner.gaps[0].status === "closed", "closed on one side stays closed");

/* a gap the model leaves out counts as closed, not lost */
reopenGap("g1");
applyLearnerReply({ brief: "b", strengths: [], gaps: [], closed: [] });
assert(openGaps().length === 0 && learner().gaps.length === 1, "left out means closed, not lost");

/* step 6: the module's gap items, closing one, and what that changes */
reopenGap("g1");
let items = gapItems(m.id);
assert(
  items.length === 3,
  "brief gap + quiz miss + graded exercise: " + JSON.stringify(items.map(i => i.key))
);
assert(items[0].key === "g1" && items[0].source === "brief", "the brief's gap leads");
const quizItem_ = items.find(i => i.source === "quiz");
assert(
  quizItem_ && quizItem_.key === "q:0" && quizItem_.answer,
  "a quiz miss carries the right answer for the grader"
);
assert(
  items.find(i => i.key === "e:0" && i.source === "graded"),
  "a partial exercise is an item under its grader key"
);
assert(!stepDone(m, 5), "the step is not done while items are open");
closeGapItem(m.id, quizItem_, "self");
assert(openGapItems(m.id).length === 2, "closing a quiz item takes it out");
assert(
  progressOf(m.id).gapWork["q:0"].closed === true,
  "and it is recorded in the module's progress"
);
assert(!gapChips(m.id).some(q => q.indexOf(quizItem.q) >= 0), "the chips skip a closed item");
closeGapItem(m.id, items[0], "drill");
assert(openGaps().length === 0, "closing a brief item closes the gap in the memory too");
reopenGapItem(m.id, "q:0");
assert(openGapItems(m.id).length === 2, "reopened");
progressOf(m.id).gapWork["q:0"].closed = true;
gapWorkOf(m.id, "e:0").closed = true;
progressOf(m.id).gapsAt = 1;
assert(stepDone(m, 5), "every item closed and the step visited: done");
assert(resumeStepIndex(m) !== 5, "nothing left to resume at the gaps step");
console.log("learner checks passed");
