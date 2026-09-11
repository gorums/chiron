/* Figures on the Read step: an SVG the build inlined for a section (coursekit/figures.py).
   A figure with <g data-step="n"> groups is a build-up. The page shows the steps one at a
   time - Prev, Next, and a Play that advances on a timer - which is the animated GIF a
   one-file course cannot carry, with the reader in charge of the pace. Nothing here is
   stored: a figure starts at its first step every time the section is drawn. */

const figureTimers = {}; // figure name -> the Play interval running for it, if any

function setupFigures() {
  document.querySelectorAll(".figure[data-steps]").forEach(fig => {
    const total = Number(fig.getAttribute("data-steps")) || 0;
    if (!total || fig.querySelector(".figsteps")) return;
    const bar = document.createElement("div");
    bar.className = "figsteps";
    bar.innerHTML = `<button type="button" data-act="prev" aria-label="Previous step">‹ Back</button>
      <button type="button" data-act="next" aria-label="Next step">Next ›</button>
      <button type="button" data-act="play" aria-label="Play every step">▶ Play</button>
      <span class="where"></span>`;
    fig.appendChild(bar);
    bar.addEventListener("click", ev => {
      const btn = ev.target.closest("button");
      if (!btn) return;
      const act = btn.getAttribute("data-act");
      if (act === "play") figurePlay(fig);
      else figureStep(fig, act === "next" ? 1 : -1);
    });
    figureShow(fig, 1);
  });
}

/* Reveal every step up to `k`, and say where we are. */
function figureShow(fig, k) {
  const total = Number(fig.getAttribute("data-steps")) || 0;
  const at = Math.max(1, Math.min(total, k));
  fig.setAttribute("data-at", String(at));
  fig.querySelectorAll("g[data-step]").forEach(g => {
    const n = Number(g.getAttribute("data-step")) || 0;
    g.classList.toggle("on", n <= at);
  });
  const where = fig.querySelector(".figsteps .where");
  if (where) where.textContent = `Step ${at} of ${total}`;
  const prev = fig.querySelector('[data-act="prev"]');
  const next = fig.querySelector('[data-act="next"]');
  if (prev) prev.disabled = at <= 1;
  if (next) next.disabled = at >= total;
}

function figureStep(fig, delta) {
  figureStop(fig);
  figureShow(fig, (Number(fig.getAttribute("data-at")) || 1) + delta);
}

/* Play from the first step to the last, one every FIGURES.playMs; a second press stops. */
function figurePlay(fig) {
  const name = fig.getAttribute("data-fig") || "";
  if (figureTimers[name]) {
    figureStop(fig);
    return;
  }
  const total = Number(fig.getAttribute("data-steps")) || 0;
  const play = fig.querySelector('[data-act="play"]');
  if (play) play.textContent = "■ Stop";
  figureShow(fig, 1);
  figureTimers[name] = setInterval(() => {
    const at = Number(fig.getAttribute("data-at")) || 1;
    if (at >= total) {
      figureStop(fig);
      return;
    }
    figureShow(fig, at + 1);
  }, FIGURES.playMs);
}

function figureStop(fig) {
  const name = fig.getAttribute("data-fig") || "";
  if (figureTimers[name]) clearInterval(figureTimers[name]);
  delete figureTimers[name];
  const play = fig.querySelector('[data-act="play"]');
  if (play) play.textContent = "▶ Play";
}
