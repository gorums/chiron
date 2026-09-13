/* Checks for the tutor usage count (web/js/tutor/usage.js, core/state.js), run inside a
   booted page by page_smoke.js --checks. The page's globals - STATE, PLATFORM, blank,
   recordUsage, syncBody, ... - are in scope. */
"use strict";
function assert(cond, msg) {
  if (!cond) throw new Error("usage check failed: " + msg);
}
STATE = blank();
const id = PLATFORM.models[0].id;

/* a call is counted with its tokens when the route reports them, without when it does not */
recordUsage(id, { in: 1000, out: 500 });
recordUsage(id, null);
recordUsage("some-other-model", { in: 10, out: 10 });
assert(usageOf().calls === 3, "three questions");
const row = usageOf().byModel[id];
assert(row.calls === 2 && row.in === 1000 && row.out === 500, "the tokens add up");
assert(row.unknown === 1, "the call that reported none is counted as such");

/* a cost only where the model's row carries a price */
assert(usageCostUsd(id, row) === null, "no price, no cost");
PLATFORM.models[0].price = { in: 3, out: 15 };
const cost = usageCostUsd(id, row);
assert(Math.abs(cost - 0.0105) < 1e-9, "USD per million tokens: " + cost);
assert(
  usageCostUsd("some-other-model", usageOf().byModel["some-other-model"]) === null,
  "unpriced"
);
const html = usageCard();
assert(html.indexOf("2 questions") > 0, "the card counts the questions per model");
assert(html.indexOf("1,000 in") > 0, "and shows the tokens");
assert(html.indexOf("$0.01") > 0, "and the estimate: " + html);
delete PLATFORM.models[0].price;

/* it is a device setting: never synced, kept through a pull */
assert(!("usage" in JSON.parse(syncBody()).state), "usage does not leave the browser");
const remote = Object.assign(blank(), { updatedAt: Date.now() + 1000 });
const merged = Object.assign(mergeStates(STATE, remote), { usage: STATE.usage });
assert(merged.usage.calls === 3, "this browser's count survives a merge the way the pull keeps it");

/* an empty count still draws */
STATE = blank();
assert(usageCard().indexOf("Nothing asked yet") > 0, "the empty card says so");

console.log("usage checks passed");
