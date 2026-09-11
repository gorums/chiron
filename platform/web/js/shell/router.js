/* ============================ router ============================
   A module's step is a name in the address — `#/m/M03/quiz` — because "step 3" is both
   unreadable and off by one against the pill the reader is looking at. Numbers are still
   accepted, so every link written before this, and every bookmark, still lands. */
let route = { view: "home", id: null, step: 0 };
const STEP_KEYS = ["predict", "read", "quiz", "elab", "apply", "gaps"];
function stepNumber(token) {
  if (token == null || token === "") return 0;
  const named = STEP_KEYS.indexOf(String(token));
  if (named >= 0) return named;
  const n = parseInt(token, 10);
  return isNaN(n) ? 0 : Math.max(0, Math.min(STEP_KEYS.length - 1, n));
}
function stepKey(i) {
  return STEP_KEYS[i] || STEP_KEYS[0];
}
/* The address of one step of one module. Everything that links to a step uses this. */
function stepHash(mid, i) {
  return `#/m/${mid}/${stepKey(i)}`;
}
function go(hash) {
  location.hash = hash;
}
function parseHash() {
  const h = (location.hash || "#/home").slice(2).split("/");
  route = { view: h[0] || "home", id: h[1] || null, step: stepNumber(h[2]) };
}
window.addEventListener("hashchange", () => {
  parseHash();
  render();
  window.scrollTo(0, 0);
});
