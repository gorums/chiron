/* ============================ router ============================ */
let route = { v: "home", id: null, step: 0 };
function go(hash) { location.hash = hash; }
function parseHash() {
  const h = (location.hash || "#/home").slice(2).split("/");
  route = { v: h[0] || "home", id: h[1] || null, step: h[2] ? +h[2] : 0 };
}
window.addEventListener("hashchange", () => { parseHash(); render(); window.scrollTo(0, 0); });
