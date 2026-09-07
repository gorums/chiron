/* ---- where the reader is, and what the tutor is told about it ----

   The chat is always about the place the reader is looking at, and that place is read
   off the page at the moment it is needed - never tracked, never stored:
     placeNow() = { mid, step, sec }
   `step` is the module step from the route; `sec` is the section under the reading line
   (07-module.js keeps `rail.section` up to date on the Read step) or the section of a
   pinned passage. Everything else here turns a place into words: a label for the rail,
   the text the tutor is shown, the questions worth suggesting. */
function stepIndexOf(key) {
  return Math.max(
    0,
    STEPS.findIndex(s => s.k === key)
  );
}
function stepNamed(key) {
  const s = STEPS.find(x => x.k === key);
  return s ? s.n : "";
}
function placeNow() {
  const m = route.view === "m" ? byId(route.id) : null;
  if (!m) return null;
  const step = STEPS[Math.max(0, Math.min(STEPS.length - 1, route.step || 0))].k;
  let sec = null;
  if (rail.pinned && rail.pinned.mid === m.id) sec = rail.pinned.sec;
  else if (step === "read") sec = Math.min(rail.section, m.sections.length - 1);
  return { mid: m.id, step: sec != null ? "read" : step, sec };
}
function placeLabel(place) {
  const m = byId(place.mid);
  if (!m) return "";
  if (place.step === "read") {
    const s = m.sections[place.sec];
    return s ? s.h : m.title;
  }
  return place.step ? stepNamed(place.step) : m.short || m.title;
}
/* the section number and heading, for menus and message labels */
function placeShort(place) {
  if (place.step === "read") return `§${place.sec + 1} ${placeLabel(place)}`;
  return placeLabel(place);
}

/* ---- what the tutor is shown for a place ----
   On the Read step, the passage; on every other step, what that step asks and what the
   reader has written so far, so "is this right?" needs no pasting. The model answers the
   page hides are hidden from the tutor's instructions too. */
const PLACE_TEXT_CHARS = 2400;
function placeText(m, place) {
  if (rail.pinned && rail.pinned.mid === m.id) return rail.pinned.text;
  const p = progressOf(m.id);
  const a = m.assess;
  let text = "";
  if (place.step === "read") {
    const s = m.sections[place.sec];
    text = s ? s.text.slice(0, 1200) + notebookPlaceText(s) : "";
  } else if (place.step === "predict") {
    text = `The question they were asked to guess at before reading: ${a.predict}\nTheir guess so far: ${(p.predict || "").trim() || "(nothing written yet)"}`;
  } else if (place.step === "quiz") {
    text = quizPlaceText(m);
  } else if (place.step === "elab") {
    text = a.elaborate
      .map((q, i) => {
        const fb = p.elabFb[i];
        return `Prompt ${i + 1}: ${q}\nTheir answer: ${(p.elab[i] || "").trim() || "(nothing yet)"}${fb ? `\nYour earlier verdict: ${fb.verdict}` : ""}`;
      })
      .join("\n\n");
  } else if (place.step === "apply") {
    const t = a.transfer,
      st = p.transfer || {};
    text = `Scenario: ${t.scenario}\nTask: ${t.prompt}\nTheir draft: ${(st.answer || "").trim() || "(nothing yet)"}`;
    text += st.revealed
      ? `\nThe model answer, which they have now seen: ${t.model}`
      : "\nThe model answer is hidden from them until they have written their own. Do not write the answer for them: question, nudge, point at what they are not considering.";
  } else if (place.step === "gaps") {
    const items = openGapItems(m.id);
    text = items.length
      ? "What this module's record says they still get wrong:\n" +
        items.map(it => `- ${it.topic}: ${it.why}`).join("\n")
      : "Nothing is open in this module's record.";
  }
  return text.slice(0, PLACE_TEXT_CHARS);
}
function quizPlaceText(m) {
  const live = QUIZ && QUIZ.kind === "m" && QUIZ.mid === m.id && !QUIZ.qs.finished;
  if (!live) return "They are between questions, or have finished the quiz.";
  const { it } = qItem(),
    st = qState();
  let text = `Question ${QUIZ.qs.i + 1}: ${it.q}`;
  if (Array.isArray(it.options) && it.options.every(o => typeof o === "string"))
    text += "\nOptions: " + it.options.join(" | ");
  if (st.answered) {
    text += `\nThey answered${st.ok ? " correctly" : " wrongly"}: ${respText(it, st.resp)}`;
    if (it.why) text += `\nWhy the right answer is right: ${it.why}`;
  } else
    text +=
      "\nThey have not answered yet. Do not give the answer away: help them reason towards it.";
  return text;
}

/* ---- questions worth suggesting at a place ---- */
const STEP_SUGGESTIONS = {
  predict: [
    "What should I look for while reading, to test my guess?",
    "Is my guess on the right track? Do not spoil the answer.",
  ],
  quiz: ["Give me a hint without the answer.", "Ask me a similar question."],
  elab: [
    "Is my explanation right, and what did I leave out?",
    "What would an expert add to my answer?",
    "Give me a sharper example to use.",
  ],
  apply: [
    "Am I on the right track? Do not give me the answer.",
    "What am I not considering in this scenario?",
    "Which part of the module is this scenario really testing?",
  ],
  gaps: ["Explain my first open gap a different way.", "Quiz me on my open gaps, one at a time."],
};
function anchorQuestion() {
  return STATE.biz
    ? "How does this apply to " + STATE.biz + "?"
    : "How would I apply this to " + ((CFG.anchor || {}).noun || "my own case") + "?";
}
function placeSuggestions(m, place) {
  if (rail.pinned && rail.pinned.mid === m.id)
    return rail.pinnedQuestions || localQuestions(rail.pinned.text);
  if (place.step === "read") {
    const set = (m.suggest && m.suggest[place.sec]) || [];
    return set.concat([anchorQuestion()]);
  }
  if (place.step === "quiz") {
    const live = QUIZ && QUIZ.kind === "m" && QUIZ.mid === m.id && !QUIZ.qs.finished;
    const answered = live && qState().answered;
    return [
      answered ? "Why is the right answer right, and mine wrong?" : STEP_SUGGESTIONS.quiz[0],
      STEP_SUGGESTIONS.quiz[1],
    ];
  }
  return (STEP_SUGGESTIONS[place.step] || []).concat([anchorQuestion()]);
}

/* ---- the tutor's instructions for one question at one place ---- */
function systemForRail(m, c, place) {
  if (c && c.kind === "rp" && m.assess.roleplay) return roleplaySystem(m, m.assess.roleplay);
  const pinned = rail.pinned && rail.pinned.mid === m.id;
  const where =
    place.step === "read"
      ? `reading the section "${placeLabel(place)}"`
      : `on the "${placeLabel(place)}" step (${STEPS[stepIndexOf(place.step)].d.toLowerCase()})`;
  const lead = pinned
    ? "They selected this passage and are asking about it:"
    : place.step === "read"
      ? "The part of the text they are looking at:"
      : "What this step asks, and what they have done on it so far:";
  return `${CFG.tutorPersona} The person is ${CFG.audience} working through a ${CFG.hours}-hour ${CFG.subject} course. Right now they are in module ${m.id}, "${m.title}", ${where}.

${lead}
"""
${placeText(m, place)}
"""
${STATE.biz ? `\n${(CFG.anchor || {}).label}, which examples should be aimed at: ${STATE.biz}` : ""}
${c && c.summary ? `\nWhat happened in your earlier conversation with them, carried over. Do not repeat it; build on it:\n"""\n${c.summary}\n"""` : ""}

How to answer:
- Be concise. Two or three short paragraphs is plenty; a short list only when it genuinely helps.
- Be concrete: real numbers, real examples, a real first step.
- Tie it back to what they are looking at.
- If the course text is a simplification, or you disagree with it, say so and explain where it breaks down.
- No preamble, no flattery. Answer the question.
${learnerContext(m.id)}`;
}
