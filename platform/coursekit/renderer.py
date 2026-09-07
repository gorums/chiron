"""Producing the two output files.

Both hold the same application. They differ only in wrapper and therefore in what the
browser will let them do:

  <name>.html         fragment form, for publishing. A hosted page may not call
                      api.anthropic.com, so the tutor is unavailable there — reading,
                      quizzes and flashcards all still work.
  <name>-local.html   a complete document, for opening off disk. `file://` origins are
                      allowed to reach Anthropic, so this is the copy that can ask questions.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict

from . import bundler
from .config import CourseConfig
from .settings import SETTINGS

DOCTYPE_HEAD = (
    '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
)


@dataclass
class BuildResult:
    web_path: str
    local_path: str
    modules: int
    sections: int
    figures: int
    notebooks: int
    quiz_items: int
    cards: int
    glossary: int
    models: int
    templates: int
    kb: float

    def summary(self) -> str:
        return (
            "modules {0.modules} · sections {0.sections} · figures {0.figures} · "
            "notebooks {0.notebooks} · quiz {0.quiz_items} · "
            "cards {0.cards} · glossary {0.glossary} · models {0.models} · "
            "templates {0.templates} · {0.kb:.0f} KB".format(self)
        )


def payload(cfg: CourseConfig, modules, library: Dict[str, Any]) -> Dict[str, Any]:
    """The DATA object: the whole course, already rendered to HTML."""
    return {
        "parts": [p.public() for p in cfg.parts],
        "modules": [m.public() for m in modules],
        "library": library,
    }


def runtime_config(cfg: CourseConfig) -> Dict[str, Any]:
    """The CFG object: the course's presentation strings plus, under `platform`, the
    platform settings the page needs - bridge address, API endpoint, model list, study
    rules, layout sizes. Nothing in platform/web/ carries a default of its own."""
    return dict(cfg.runtime(), platform=SETTINGS.page())


def _inject(template: str, marker: str, value: str) -> str:
    if marker not in template:
        raise ValueError("shell.html has no %s placeholder" % marker)
    return template.replace(marker, value, 1)


def _embed_json(obj: Any) -> str:
    """`</` inside a string literal would close the script tag early."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def render(cfg: CourseConfig, modules, library: Dict[str, Any]) -> str:
    html = bundler.shell()
    html = html.replace("{{TITLE}}", cfg.title)
    html = _inject(html, "/*__CSS__*/", bundler.css())
    html = _inject(html, "/*__JS__*/", bundler.js())
    html = _inject(html, "/*__CONFIG__*/", _embed_json(runtime_config(cfg)))
    html = _inject(html, "/*__DATA__*/", _embed_json(payload(cfg, modules, library)))
    return html


def as_document(html: str) -> str:
    """Wrap the fragment in a real document so it renders in standards mode off disk."""
    end = html.index("</style>") + len("</style>")
    return DOCTYPE_HEAD + html[:end] + "\n</head>\n<body>" + html[end:] + "\n</body>\n</html>\n"


def write(cfg: CourseConfig, modules, library: Dict[str, Any], out_dir: str) -> BuildResult:
    os.makedirs(out_dir, exist_ok=True)
    html = render(cfg, modules, library)

    web_path = os.path.join(out_dir, cfg.web_file)
    local_path = os.path.join(out_dir, cfg.local_file)
    with open(web_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    with open(local_path, "w", encoding="utf-8") as fh:
        fh.write(as_document(html))

    return BuildResult(
        web_path=web_path,
        local_path=local_path,
        modules=len(modules),
        sections=sum(len(m.sections) for m in modules),
        figures=sum(len(m.figures) for m in modules),
        notebooks=sum(len(m.notebooks) for m in modules),
        quiz_items=sum(len(m.assess.get("quiz", [])) for m in modules),
        cards=sum(len(m.assess.get("cards", [])) for m in modules),
        glossary=len(library.get("glossary", [])),
        models=len(library.get("models", [])),
        templates=len(library.get("templates", [])),
        kb=len(html) / 1024,
    )
