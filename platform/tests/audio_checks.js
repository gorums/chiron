/* Checks for reading aloud (web/js/07d-audio.js), run inside a booted page by
   page_smoke.js --checks. The DOM is a stub there, so what a section says is checked on
   hand-made elements, and the player is driven by calling what the browser would call. */
"use strict";
function assert(cond, msg) {
  if (!cond) throw new Error("audio check failed: " + msg);
}
const m = MODS[0];
assert(m.sections.length >= 2, "a module with at least two sections");
assert(audioSupported(), "the smoke harness stubs speechSynthesis");
assert(AUDIO.rates.includes(AUDIO.rate), "the default speed is one of the offered speeds");

/* what a block says */
const el = (tagName, textContent, extra) =>
  Object.assign({ tagName, textContent, closest: () => null }, extra || {});
assert(blockText(el("P", "  Two   words.\n")) === "Two words.", "whitespace is folded");
const row = el("TR", "", { children: [el("TD", " Price "), el("TD", ""), el("TD", "high")] });
assert(
  blockText(row) === "Price, high",
  "a table row is its cells, in a breath: " + blockText(row)
);

/* which blocks a section is read in */
const loose = el("LI", "Inner.", { querySelector: () => el("P", "Inner.") });
const tight = el("LI", "Alone.", { querySelector: () => null });
const empty = el("P", "   ");
const cell = el("PRE", "x = 1", { closest: sel => (sel === ".nb-static" ? {} : null) });
const root = {
  querySelectorAll: () => [el("P", "First."), loose, el("P", "Inner."), tight, empty, cell],
};
const blocks = speechBlocks(root);
assert(
  blocks.length === 3,
  "a loose item yields to its paragraph, an empty block and a notebook cell are skipped"
);
assert(blocks[2] === tight, "a tight item is read itself");

/* a long paragraph is said in sentence-sized pieces that lose nothing */
const long = "One is short. Two is a little longer than one! Three asks a question? Four ends.";
const pieces = splitSpeech(long, 30);
assert(pieces.length >= 3, "split into pieces: " + JSON.stringify(pieces));
assert(
  pieces.every(p => p.length <= 45),
  "no piece is much over the limit"
);
assert(pieces.join(" ").replace(/\s+/g, " ") === long, "the pieces are the paragraph");
assert(splitSpeech("No end", 100).join("") === "No end", "a sentence without a stop is kept");

/* the player: it starts on a section, says its heading first, and ticks it when done */
STATE = blank();
route = { view: "m", id: m.id, step: 1 };
rail.section = 0;
audioPlay(m.id, 1);
assert(audio.mid === m.id && audio.sec === 1, "reading section 2 of " + m.id);
assert(audio.chunks[0].text === m.sections[1].h, "the heading is said first");
assert(audioActive(m.id) && !audio.paused, "playing");
audioPause();
assert(audio.paused, "paused");
audioResume();
assert(!audio.paused && audio.chunk === 0, "resumed on the same chunk");
while (audio.chunk < audio.chunks.length - 1) speakNext();
speakNext(); // past the last chunk: the section is done
assert(progressOf(m.id).secs[1] === true, "a section read to its end is ticked");
assert(audio.mid === m.id, "a middle section runs on into the next");

/* leaving the Read step stops it */
route = { view: "m", id: m.id, step: 2 };
audioRouteChanged();
assert(audio.mid === null && audio.chunks.length === 0, "silent off the Read step");

/* the last section ends the module */
route = { view: "m", id: m.id, step: 1 };
audioPlay(m.id, m.sections.length - 1);
audio.chunk = audio.chunks.length - 1;
speakNext();
assert(audio.mid === null, "the module ends after its last section");
assert(progressOf(m.id).secs[m.sections.length - 1] === true, "and the last section is ticked");

/* the bar and the settings card draw without a DOM */
assert(typeof audioBarHtml(m) === "string", "the bar renders");
assert(audioSettingsCard().includes("Listening"), "the settings card renders");
console.log("audio checks passed");
