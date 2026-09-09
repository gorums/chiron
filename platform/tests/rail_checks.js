/* Checks for the chat rail's place logic (web/js/17-convos.js, 17a-place.js, 17-rail.js),
   run inside a booted page by page_smoke.js --checks. The page's globals - STATE, MODS,
   route, rail, placeNow, convoShown, ... - are in scope. Each check sets the route and
   the section in view the way the page would, then asks what the rail would show. */
"use strict";
function assert(cond, msg) {
  if (!cond) throw new Error("rail check failed: " + msg);
}
const m = MODS[0];
const other = MODS[1];
/* section indexes that exist in any course: the first and the last */
const A = 0;
const B = m.sections.length - 1;
assert(B >= 1, "a module with at least two sections");
STATE = blank();
rail.showing = null;
rail.pinned = null;

/* off a module there is no place, and the rail shows nothing */
route = { view: "home", id: null, step: 0 };
assert(placeNow() === null, "no place off a module");
assert(convoShown() === null, "nothing shown off a module");

/* the place is the route's step, and on the Read step the section in view */
route = { view: "m", id: m.id, step: 1 };
rail.section = B;
let place = placeNow();
assert(
  place.step === "read" && place.sec === B,
  "Read step, last section: " + JSON.stringify(place)
);
route.step = 3;
place = placeNow();
assert(place.step === "elab" && place.sec === null, "Elaborate has no section");
assert(placeLabel(place) === "Elaborate", "a step's label is its name: " + placeLabel(place));

/* a chat made on Elaborate is shown there, and nowhere else */
assert(convoShown() === null, "no chat yet: nothing to show");
const elab = newConvo(placeNow());
assert(convoShown() === elab, "the new chat is the one at this place");
assert(convoTitle(elab) === "Elaborate", "a placed chat is titled by its place");
route.step = 1;
assert(convoShown() === null, "the Elaborate chat does not leak into the Read step");
route.step = 3;
assert(convoShown() === elab, "and is back on Elaborate");

/* a section chat from an older save (`sec` only, no `step`) is a Read-step chat */
route.step = 1;
const old = newConvo({ mid: m.id, step: "read", sec: B });
delete old.step;
assert(placeOf(old).step === "read", "an older section chat is a Read chat");
assert(convoShown() === old, "and is found by its section");
assert(convoTitle(old) === m.sections[B].h, "titled by its section heading");
rail.section = A;
assert(convoShown() === null, "the first section has no chat");
assert(convoAt({ mid: m.id, step: "read", sec: B }) === old, "the last section still has one");

/* the newest chat at a place wins, so "New chat" and a compaction take over */
rail.section = B;
const fresh = newConvo({ mid: m.id, step: "read", sec: B });
fresh.updated = old.updated + 1;
assert(convoShown() === fresh, "the newest chat at the place is shown");

/* a chat picked by hand stays until the reader moves somewhere else */
rail.showing = old.id;
assert(convoShown() === old, "a hand-picked chat is shown");
railPlaceChanged();
assert(convoShown() === old, "and stays while the place is the same");
rail.section = A;
railPlaceChanged();
assert(rail.showing === null && convoShown() === null, "moving to another section lets it go");

/* a chat with no place - a role-play, a whole-module chat - stays put while scrolling */
const rp = newConvo({ mid: m.id, step: null, sec: null }, { kind: "rp" });
rail.showing = rp.id;
rail.section = B;
railPlaceChanged();
assert(convoShown() === rp, "a role-play stays on show across sections");
assert(convoAt({ mid: m.id, step: "read", sec: A }) === null, "but is never the chat at a place");
assert(!hasPlace(rp), "a role-play has no place");

/* leaving the module lets go of whatever was picked */
route = { view: "m", id: other.id, step: 1 };
rail.section = 0;
assert(convoShown() !== rp && rail.showing === null, "another module: the pick is forgotten");
route = { view: "m", id: m.id, step: 1 };

/* a pinned passage fixes the place, and does not survive leaving the Read step */
rail.section = A;
rail.pinned = { mid: m.id, sec: B, text: "a passage", markId: null };
assert(placeNow().sec === B, "the pin's section is the place");
assert(placeText(m, placeNow()) === "a passage", "the tutor sees the pinned passage");
route.step = 3;
railRouteChanged();
assert(rail.pinned === null, "leaving the Read step unpins");

/* what the tutor is told on a step: what it asks, and what the reader wrote */
const p = progressOf(m.id);
p.elab[0] = "my own words about it";
const elabSystem = systemForRail(m, null, placeNow());
assert(elabSystem.indexOf("my own words about it") >= 0, "the Elaborate answer is in the prompt");
assert(elabSystem.indexOf(m.assess.elaborate[0]) >= 0, "and the prompt it answers");
route.step = 4;
p.transfer = { answer: "my draft" };
let applySystem = systemForRail(m, null, placeNow());
assert(applySystem.indexOf("my draft") >= 0, "the Apply draft is in the prompt");
assert(applySystem.indexOf(m.assess.transfer.model) < 0, "the model answer is not, before reveal");
p.transfer.revealed = true;
applySystem = systemForRail(m, null, placeNow());
assert(applySystem.indexOf(m.assess.transfer.model) >= 0, "after the reveal it is");
route.step = 1;
rail.section = B;
assert(systemForRail(m, null, placeNow()).indexOf(m.sections[B].h) >= 0, "Read: the section");

/* a message remembers where it was asked, for the label above it */
assert(messageLabel(m, { r: "u", t: "q", sec: B }) === m.sections[B].h, "section label");
assert(messageLabel(m, { r: "u", t: "q", step: "apply" }) === "Apply", "step label");
assert(messageLabel(m, { r: "u", t: "q" }) === "", "no place, no label");

/* the rail's menu lets the reader pick the tutor's model: the build's list, the current
   one marked, and an id this build does not offer leaves the choice alone */
const listed = PLATFORM.models.map(x => x.id);
assert(listed.length >= 2, "a build lists more than one model");
conn().model = "";
assert(modelFor(conn()) === PLATFORM.defaultModel, "an empty pick means the default");
assert(modelOptions().split("<option").length - 1 === listed.length, "every model is offered");
setTutorModel(listed[1]);
assert(conn().model === listed[1], "a pick from the menu is kept");
assert(modelOptions().indexOf(`value="${listed[1]}" selected`) >= 0, "and shown as selected");
setTutorModel("not-a-model");
assert(conn().model === listed[1], "an unknown id changes nothing");

console.log("rail checks passed");
