/* ---- usage: what the tutor has cost from this browser ----
   Every answer is counted here: the call, and the tokens in and out when the route says
   so. An HTTP provider reports them in its reply (wire.js `usage`, or `usage` from the
   bridge); a command-line tool on a subscription reports none, and then only the call
   counts. It is kept per device, like the key it is spent with: `usage` is stripped from
   the sync and kept through a pull the way `bridge` is.

   A cost is estimated only for a model whose row in `models.list` carries a `price`
   ({in, out}, USD per million tokens), which reaches the page as
   CFG.platform.models[].price. Without one the tokens are shown and the cost is not. */
function usageBlank() {
  return { calls: 0, byModel: {} }; // byModel[id] = { calls, in, out, unknown }
}
function usageOf() {
  if (!STATE.usage) STATE.usage = usageBlank();
  if (!STATE.usage.byModel) STATE.usage.byModel = {};
  return STATE.usage;
}
/* One answer arrived. `tokens` is {in, out} when the route reported them, else null. */
function recordUsage(model, tokens) {
  const usage = usageOf();
  const id = model || PLATFORM.defaultModel || "?";
  const row = usage.byModel[id] || (usage.byModel[id] = { calls: 0, in: 0, out: 0, unknown: 0 });
  usage.calls = (usage.calls || 0) + 1;
  row.calls += 1;
  if (tokens && tokens.in != null && tokens.out != null) {
    row.in += tokens.in;
    row.out += tokens.out;
  } else {
    row.unknown += 1;
  }
  save();
}
function priceOf(id) {
  const model = PLATFORM.models.find(m => m.id === id);
  const price = model && model.price;
  return price && price.in != null && price.out != null ? price : null;
}
/* USD for one model's row, or null when its price is not known. */
function usageCostUsd(id, row) {
  const price = priceOf(id);
  if (!price) return null;
  return (row.in * price.in + row.out * price.out) / 1e6;
}
function modelLabelOf(id) {
  const model = PLATFORM.models.find(m => m.id === id);
  return (model && model.label) || id;
}
function usageRows() {
  const usage = usageOf();
  return Object.keys(usage.byModel).map(id => {
    const row = usage.byModel[id];
    return Object.assign({ id, label: modelLabelOf(id), cost: usageCostUsd(id, row) }, row);
  });
}
function fmtCount(n) {
  return Number(n || 0).toLocaleString();
}
function fmtUsd(n) {
  return "$" + (n < 0.01 && n > 0 ? "<0.01" : n.toFixed(2));
}
function usageRowHtml(r) {
  const known = r.calls - r.unknown;
  const tokens = known ? `${fmtCount(r.in)} in · ${fmtCount(r.out)} out` : "tokens not reported";
  const partial = r.unknown && known ? ` (${r.unknown} not reported)` : "";
  const cost = r.cost != null && known ? ` · about ${fmtUsd(r.cost)}` : "";
  return `<div class="setrow"><span class="lab">${esc(r.label)}<small>${r.calls} question${r.calls === 1 ? "" : "s"}${partial}</small></span>
    <span class="sub">${tokens}${cost}</span></div>`;
}
function usageCard() {
  const rows = usageRows();
  const priced = rows.filter(r => r.cost != null && r.calls > r.unknown);
  const total = priced.reduce((a, r) => a + r.cost, 0);
  const body = rows.length
    ? rows.map(usageRowHtml).join("")
    : `<p class="sub">Nothing asked yet from this browser.</p>`;
  const sum = priced.length
    ? `<div class="setrow last"><span class="lab">Estimated so far</span><span class="sub">about ${fmtUsd(total)}${priced.length < rows.length ? ", for the models with a price" : ""}</span></div>`
    : "";
  return `<div class="card gap-bottom">
    <h3 class="eyebrow">Tutor usage</h3>
    <p class="sub gap-bottom">What the tutor has been asked from this browser. Tokens are counted when an API reports them; a command-line tool on a subscription reports none. A cost is an estimate from the price on the model's row in the platform's settings.</p>
    ${body}${sum}
    <div class="rowline gap-top"><button class="btn sm" onclick="askResetUsage()">Reset the count</button></div>
  </div>`;
}
function askResetUsage() {
  confirmModal(
    "Reset the count?",
    "The questions and tokens counted so far are forgotten.",
    "Reset",
    () => {
      STATE.usage = usageBlank();
      save();
      closeModal();
      viewSettings();
    }
  );
}
