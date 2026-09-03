/* Boots the built course page under node with a stand-in DOM.

   Usage: node page_smoke.js <built -local.html>

   Everything the page reaches for in the browser - document, localStorage, fetch, timers -
   is a permissive stub that swallows calls and returns itself, so the whole load sequence
   (state, sync, router, first render, layout) runs to completion. What it does *not* stub
   is any other name: a ReferenceError for an identifier the bundle never declared is exactly
   what this exists to catch, because `node --check` only parses. Exit 0 when the page booted;
   otherwise the error, and exit 1. Nothing here needs npm. */
"use strict";
const fs = require("fs");
const vm = require("vm");

const file = process.argv[2];
if (!file) { console.error("usage: node page_smoke.js <built html>"); process.exit(2); }
const html = fs.readFileSync(file, "utf8");
/* The shell holds two blocks - CFG + DATA, then the bundle - run as one script. */
const blocks = [];
const re = /<script>([\s\S]*?)<\/script>/g;
for (let m; (m = re.exec(html));) blocks.push(m[1]);
if (!blocks.length) { console.error("no <script> block in " + file); process.exit(2); }
const source = blocks.join("\n");

/* One stub for everything DOM-shaped: any property is the stub, any call returns the stub,
   it coerces to "" / 0 / false-ish in string and number contexts, and it is not thenable. */
const stub = new Proxy(function () {}, {
  get(target, prop) {
    if (prop === Symbol.toPrimitive) return () => "";
    if (prop === Symbol.iterator) return function* () {};
    if (prop === "then") return undefined;
    if (prop === "length") return 0;
    return stub;
  },
  set() { return true; },
  has() { return true; },
  apply() { return stub; },
  construct() { return stub; },
});

const sandbox = {
  console, JSON, Math, Date, Object, Array, String, Number, Boolean, RegExp, Error, Promise,
  Map, Set, Symbol, parseInt, parseFloat, isNaN, isFinite, encodeURIComponent, decodeURIComponent,
  TextDecoder, TextEncoder, AbortController, Blob, URL, Uint8Array,
  setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
  requestAnimationFrame: () => 0, cancelAnimationFrame: () => {},
  fetch: () => Promise.reject(new Error("no network in the smoke test")),
  window: stub, document: stub, location: stub, navigator: stub, history: stub, screen: stub,
  localStorage: stub, sessionStorage: stub, Notification: stub, matchMedia: stub,
  getComputedStyle: stub, getSelection: stub, scrollTo: stub, alert: stub, confirm: stub,
  prompt: stub, open: stub, print: stub, innerWidth: 1400, innerHeight: 900, devicePixelRatio: 1,
  HTMLElement: stub, Element: stub, Node: stub, Event: stub, KeyboardEvent: stub, CustomEvent: stub,
  MutationObserver: stub, ResizeObserver: stub, IntersectionObserver: stub, DOMParser: stub,
  Image: stub, Audio: stub, FileReader: stub, Range: stub, performance: { now: () => 0 },
  speechSynthesis: stub, SpeechSynthesisUtterance: stub, crypto: { randomUUID: () => "0" },
};
sandbox.globalThis = sandbox;
sandbox.self = sandbox;

const failures = [];
process.on("unhandledRejection", err => failures.push(err));
try {
  vm.runInNewContext(source, vm.createContext(sandbox), { filename: file, timeout: 20000 });
} catch (err) {
  failures.push(err);
}
/* Let the boot's promise chain (syncPull().finally(render)) settle before judging. */
setImmediate(() => {
  const real = failures.filter(e => !(e && /no network in the smoke test/.test(e.message || "")));
  if (real.length) {
    for (const e of real) console.error(e && e.stack || e);
    process.exit(1);
  }
  console.log("booted");
});
