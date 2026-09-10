/* ---------- figures and notebooks: the choices every writing form offers ----------
   Every job that writes module text can also draw figures and write notebooks, one
   call each per module. Rather than assume, each form - a resumed run, an added
   module, a rewrite - shows the two switches (mediaChoices) and sends what was ticked
   (mediaBrief) as `figures` and `notebooks` in the request; the server honours both.
   Notebooks are offered only when the course declares them in its settings. The
   new-course form is the exception: there the planner decides (10-library.js). */

function mediaChoices(prefix, course, note) {
  const runtime = course && course.notebooks ? course.notebooks : null;
  const kernel = runtime && runtime.kernel ? ` (${esc(runtime.kernel)})` : "";
  const when = note ? ` ${note}` : "";
  const figures = `<label class="radio"><input type="checkbox" id="${prefix}-figures" checked> <b>Draw figures</b></label>
    <span class="fhint">SVG diagrams where a picture beats a paragraph${when}. One call per module.</span>`;
  const notebooks = runtime
    ? `<label class="radio"><input type="checkbox" id="${prefix}-notebooks" checked> <b>Write notebooks</b></label>
       <span class="fhint">A Jupyter notebook the reader runs inside the module${kernel}${when}. One call per module.</span>`
    : `<label class="radio off"><input type="checkbox" disabled> <b>Write notebooks</b></label>
       <span class="fhint">Off: this course declares no notebooks. Turn them on under Settings if its subject is learned by running code.</span>`;
  return `<div class="media">${figures}${notebooks}</div>`;
}

/* What the form asked for. A missing switch means the default: figures yes, notebooks
   only when the course declares them (the server checks that too). */
function mediaBrief(prefix) {
  const figures = document.getElementById(prefix + "-figures");
  const notebooks = document.getElementById(prefix + "-notebooks");
  return {
    figures: figures ? figures.checked : true,
    notebooks: notebooks ? notebooks.checked : false,
  };
}
