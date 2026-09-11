/* Listening to a module: the Read step read aloud by the browser's own speech engine
   (the Web Speech API), one block at a time - a heading, a paragraph, a list item, a table
   row, a figure's caption - with the block being spoken highlighted and kept in view.
   A one-file course cannot carry audio and no model makes any, so the voice is whatever
   the operating system offers; the reader picks it, and the speed, in Settings
   (STATE.ui, device-side). Nothing else is stored. A section spoken to its end is ticked
   read, like one the reader scrolled through, and playback runs on into the next section
   until the module ends or the reader leaves the Read step. */

const audio = {
  mid: null, // the module being read aloud, or null while silent
  sec: -1, // the section being spoken
  chunk: -1, // which of `chunks` is in flight
  chunks: [], // what is left to say in this section: {sec, block, text} (see sectionSpeech)
  paused: false, // paused by the reader; resuming speaks the current chunk again
  token: 0, // bumped on every stop, so a late callback from a cancelled utterance is ignored
};
/* The blocks a section is read in, in document order. A loose list item holds paragraphs,
   which are read in its place; a figure's drawing is skipped and its caption read. */
const SPEECH_BLOCKS = "p, li, h3, h4, h5, h6, figcaption, tr, pre, .nb-title";

function audioSupported() {
  return "speechSynthesis" in window && typeof SpeechSynthesisUtterance === "function";
}
function audioActive(mid) {
  return audio.mid !== null && (!mid || audio.mid === mid);
}

/* ---- what to say ---- */

function blockText(el) {
  if (el.tagName === "TR") {
    return [...el.children]
      .map(c => c.textContent.replace(/\s+/g, " ").trim())
      .filter(Boolean)
      .join(", ");
  }
  return (el.textContent || "").replace(/\s+/g, " ").trim();
}
function speechBlocks(root) {
  return [...root.querySelectorAll(SPEECH_BLOCKS)].filter(el => {
    if (el.tagName === "LI" && el.querySelector("p")) return false;
    // a notebook's cells are code and output, not prose: its title is read, the rest skipped
    if (el.closest(".nb-static")) return false;
    return blockText(el) !== "";
  });
}
/* A long paragraph is spoken in sentence-sized pieces: some engines fall silent partway
   through a long utterance, and the pieces are where a pause lands anyway. */
function splitSpeech(text, max) {
  const sentences = text.match(/[^.!?…]+(?:[.!?…]+["”’)\]]*|$)\s*/g) || [text];
  const out = [];
  let cur = "";
  sentences.forEach(s => {
    if (cur && (cur + s).length > max) {
      out.push(cur.trim());
      cur = "";
    }
    cur += s;
  });
  if (cur.trim()) out.push(cur.trim());
  return out;
}
function sectionRoot(sec) {
  return document.querySelector("#sec" + sec + " .prose");
}
function sectionSpeech(m, sec) {
  const section = m.sections[sec];
  if (!section) return [];
  const chunks = [{ sec, block: -1, text: section.h }];
  const root = sectionRoot(sec);
  if (!root) return chunks;
  speechBlocks(root).forEach((el, block) => {
    splitSpeech(blockText(el), AUDIO.chunkChars).forEach(text => chunks.push({ sec, block, text }));
  });
  return chunks;
}
/* The element a chunk belongs to, looked up now: the Read step may have been redrawn
   (a section ticked by hand) since the chunk was made. */
function chunkEl(c) {
  if (c.block < 0) return document.querySelector("#sec" + c.sec + " .sechead h3");
  const root = sectionRoot(c.sec);
  return root ? speechBlocks(root)[c.block] || null : null;
}

/* ---- the voice ---- */

function audioVoices() {
  if (!audioSupported()) return [];
  const all = [...speechSynthesis.getVoices()];
  const lang = (CFG.lang || "").toLowerCase().split("-")[0];
  const own = all.filter(v => (v.lang || "").toLowerCase().split(/[-_]/)[0] === lang);
  return own.length ? own : all;
}
function audioVoice() {
  const want = uiPrefs().voice;
  const voices = audioVoices();
  return voices.find(v => v.voiceURI === want) || voices.find(v => v.default) || voices[0] || null;
}
function audioRate() {
  return Number(uiPrefs().rate) || AUDIO.rate;
}
function audioCycleRate() {
  const rates = AUDIO.rates;
  const at = rates.indexOf(audioRate());
  setReading("rate", rates[(at + 1) % rates.length]);
  audioRefresh();
}

/* ---- playing ---- */

/* The speaker button on a section: start reading there, pause if it is being read, resume
   if it is paused. */
function audioPlay(mid, sec) {
  if (!audioSupported()) return;
  if (audioActive(mid) && audio.sec === sec) {
    if (audio.paused) audioResume();
    else audioPause();
    return;
  }
  audioStop();
  audio.mid = mid;
  audioLoadSection(sec);
  speakNext();
}
/* The Listen button on the module: pause or resume what is playing, else start at the
   section under the reading line. */
function audioToggle(mid) {
  if (!audioActive(mid)) {
    audioPlay(mid, rail.section || 0);
    return;
  }
  if (audio.paused) audioResume();
  else audioPause();
}
function audioLoadSection(sec) {
  audio.sec = sec;
  audio.chunk = -1;
  audio.chunks = sectionSpeech(byId(audio.mid), sec);
}
function speakNext() {
  if (audio.mid === null) return;
  audio.chunk += 1;
  if (audio.chunk >= audio.chunks.length) {
    audioSectionDone(audio.sec);
    return;
  }
  const c = audio.chunks[audio.chunk];
  const token = ++audio.token;
  const u = new SpeechSynthesisUtterance(c.text);
  u.lang = CFG.lang || "";
  const voice = audioVoice();
  if (voice) u.voice = voice;
  u.rate = audioRate();
  u.onend = () => {
    if (token === audio.token) speakNext();
  };
  u.onerror = ev => {
    if (token !== audio.token) return;
    if (ev.error === "interrupted" || ev.error === "canceled") return;
    toast("The browser could not read aloud (" + (ev.error || "unknown") + ")");
    audioStop();
  };
  audioHighlight(chunkEl(c));
  lastActive = Date.now(); // listening is study; the reading clock must not pause
  audioRefresh();
  speechSynthesis.speak(u);
}
/* A section read to its end counts as read. Then on to the next one, after a breath. */
function audioSectionDone(sec) {
  const m = byId(audio.mid);
  const p = progressOf(m.id);
  if (!p.secs[sec]) {
    p.secs[sec] = true;
    save();
    markDay();
    const el = document.getElementById("sec" + sec);
    if (el) {
      el.classList.add("done");
      const check = el.querySelector(".check");
      if (check) check.classList.add("on");
    }
    refreshReadProgress(m);
    renderSidebar();
  }
  audioHighlight(null);
  if (sec + 1 >= m.sections.length) {
    audioStop();
    toast("End of the module");
    return;
  }
  const token = audio.token;
  audioLoadSection(sec + 1);
  setTimeout(() => {
    if (token === audio.token && !audio.paused) speakNext();
  }, AUDIO.sectionPauseMs);
}
/* Pause is a cancel that remembers the chunk: `speechSynthesis.pause()` does not resume
   reliably with every voice, and a chunk is short enough to say again. */
function audioPause() {
  audio.paused = true;
  audio.token += 1;
  speechSynthesis.cancel();
  audioRefresh();
}
function audioResume() {
  audio.paused = false;
  audio.chunk = Math.max(-1, audio.chunk - 1); // -1 while waiting between sections
  speakNext();
}
function audioStop() {
  if (audioSupported()) {
    audio.token += 1;
    speechSynthesis.cancel();
  }
  audioHighlight(null);
  audio.mid = null;
  audio.sec = -1;
  audio.chunk = -1;
  audio.chunks = [];
  audio.paused = false;
  audioRefresh();
}
/* Called by render(): reading aloud belongs to one module's Read step. */
function audioRouteChanged() {
  if (audio.mid === null) return;
  const here = route.view === "m" && route.id === audio.mid && (route.step || 0) === 1;
  if (!here) audioStop();
}
function audioHighlight(el) {
  document.querySelectorAll(".speaking").forEach(x => x.classList.remove("speaking"));
  if (!el) return;
  el.classList.add("speaking");
  const r = el.getBoundingClientRect();
  const bar = document.querySelector(".topbar");
  const top = bar ? bar.getBoundingClientRect().bottom : 0;
  if (r.top < top || r.bottom > window.innerHeight) {
    // The reader's own preference, and then the system's: either one turns it off.
    el.scrollIntoView({
      block: "center",
      behavior: uiPrefs().nomotion ? "auto" : scrollBehavior(),
    });
  }
}
/* Say a sentence in the chosen voice, from Settings. */
function audioSample() {
  if (!audioSupported()) return;
  audioStop();
  const u = new SpeechSynthesisUtterance("This is how the course will sound at this speed.");
  u.lang = CFG.lang || "";
  const voice = audioVoice();
  if (voice) u.voice = voice;
  u.rate = audioRate();
  speechSynthesis.speak(u);
}

/* ---- what the page shows ---- */

/* The bar under the reading-progress card: Listen / Pause, Stop, the speed, and where the
   reading is. Empty when the browser cannot speak, and the bar hides itself. */
function audioBarHtml(m) {
  if (!audioSupported()) return "";
  const on = audioActive(m.id);
  const label = !on ? "Listen" : audio.paused ? "Resume" : "Pause";
  const icon = on && !audio.paused ? "pause" : "speak";
  const where = on
    ? `Section ${audio.sec + 1} of ${m.sections.length} · ${esc(m.sections[audio.sec].h)}`
    : "Read aloud from the section you are on";
  const stop = on ? `<button class="btn sm ghost" onclick="audioStop()">Stop</button>` : "";
  return `<button class="btn sm ${on ? "primary" : ""}" onclick="audioToggle('${m.id}')">${ico(icon, 14)} ${label}</button>
    ${stop}
    <button class="btn sm ghost" onclick="audioCycleRate()" data-help="Speed">${audioRate()}×</button>
    <span class="where">${where}</span>`;
}
function sectionSpeakButton(mid, i) {
  if (!audioSupported()) return "";
  const on = audioActive(mid) && audio.sec === i && !audio.paused;
  return `<button class="askbtn speakbtn ${on ? "has on" : ""}" data-help="Read this section aloud" aria-label="Read this section aloud" onclick="audioPlay('${mid}',${i})">${ico(on ? "pause" : "speak", 14)}</button>`;
}
function audioRefresh() {
  const bar = document.getElementById("audiobar");
  if (bar && route.view === "m" && (route.step || 0) === 1)
    bar.innerHTML = audioBarHtml(byId(route.id));
  document.querySelectorAll(".speakbtn").forEach((b, i) => {
    const on = audioActive(route.id) && audio.sec === i && !audio.paused;
    b.classList.toggle("has", on);
    b.classList.toggle("on", on);
    b.innerHTML = ico(on ? "pause" : "speak", 14);
  });
}
/* The Listening card on the Settings page. */
function audioSettingsCard() {
  if (!audioSupported()) return "";
  const voices = audioVoices();
  const chosen = audioVoice();
  const options = voices
    .map(
      v =>
        `<option value="${esc(v.voiceURI)}" ${chosen && chosen.voiceURI === v.voiceURI ? "selected" : ""}>${esc(v.name)} (${esc(v.lang)})</option>`
    )
    .join("");
  const rates = AUDIO.rates
    .map(
      r =>
        `<button class="chip ${audioRate() === r ? "on" : ""}" onclick="setReading('rate',${r})">${r}×</button>`
    )
    .join("");
  const voiceRow = voices.length
    ? `<select onchange="setReading('voice',this.value)" style="padding:10px 12px;border-radius:10px;border:1px solid var(--line-2);background:var(--surface);color:var(--text);font-family:inherit;font-size:14px;max-width:100%">${options}</select>`
    : `<span class="sub">This browser offers no voices.</span>`;
  return `<div class="card gap-bottom-lg">
    <p class="eyebrow">Listening</p>
    <p class="sub gap-bottom-sm">The Read step can be read aloud by a voice your system provides. Kept in this browser only.</p>
    <div class="setrow"><span class="lab">Voice<small>Voices for the course's language; more come with the operating system or the browser.</small></span>${voiceRow}</div>
    <div class="setrow last"><span class="lab">Speed</span><div class="rowline wrapped"><div class="chips flush">${rates}</div>
      <button class="btn sm" onclick="audioSample()">Hear a sample</button></div></div>
  </div>`;
}
/* Voices arrive after the page in some browsers; redraw Settings when they do. */
if (audioSupported()) {
  speechSynthesis.onvoiceschanged = () => {
    if (route.view === "settings") viewSettings();
  };
}
window.addEventListener("pagehide", () => {
  if (audio.mid !== null) audioStop();
});
