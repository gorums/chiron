"""Command line for the course platform.

    build.py list                       what courses exist
    build.py where                      which directories the platform is using
    build.py new  --theme X --hours 30  scaffold an empty course
    build.py check <course>             validate without writing anything
    build.py build <course>             validate, then write dist/<course>/
    build.py studio                     open the Studio UI in a browser
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List

from . import assessments, config, library, loader, renderer, scaffold, validate
from .errors import CourseError
from .paths import COURSES_DIR, DIST_DIR
from .settings import SETTINGS


def _course_root(name: str) -> str:
    root = name if os.path.isdir(name) else os.path.join(COURSES_DIR, name)
    if not os.path.isdir(root):
        raise CourseError("No course '%s'. Run `build.py list` to see what is there." % name)
    return root


def _assemble(root: str):
    """Load, validate and return everything a build needs. Raises on any inconsistency."""
    cfg = config.load(root)
    modules = loader.load_modules(cfg)
    assess = assessments.load_assessments(cfg)
    suggest = assessments.load_suggestions(cfg)
    validate.raise_if_broken(validate.check(modules, assess, suggest))
    assessments.attach(modules, assess, suggest)
    return cfg, modules, library.build(cfg)


def cmd_list(_args) -> int:
    if not os.path.isdir(COURSES_DIR):
        print("No courses directory yet at %s" % COURSES_DIR)
        return 0
    print("Courses in %s" % COURSES_DIR)
    found = False
    for name in sorted(os.listdir(COURSES_DIR)):
        root = os.path.join(COURSES_DIR, name)
        if not os.path.isfile(os.path.join(root, "course.json")):
            continue
        found = True
        try:
            cfg = config.load(root)
            print("  %-16s %s — %g hours, %d parts" % (name, cfg.title, cfg.hours, len(cfg.parts)))
        except CourseError as exc:
            print("  %-16s [broken manifest] %s" % (name, exc))
    if not found:
        print("No courses yet. Try: build.py new --theme \"negotiation\" --hours 20")
    return 0


def cmd_new(args) -> int:
    root = scaffold.create(COURSES_DIR, args.theme, args.hours, course_id=args.id, force=args.force)
    cfg = config.load(root)
    counts = scaffold.module_counts([p.__dict__ for p in cfg.parts])
    print("Scaffolded %s" % root)
    print("Plan: %g hours across %d parts" % (cfg.hours, len(cfg.parts)))
    for part, n in zip(cfg.parts, counts):
        print("  %-16s %gh · about %d modules → modules/%s/" % (part.name, part.hours, n, part.dir))
    print("\nNext: write the content, then `build.py build %s`." % cfg.id)
    print("The course-author skill does this end to end.")
    print("A course is its own repository: `git init` inside %s when you are ready." % root)
    return 0


def cmd_check(args) -> int:
    root = _course_root(args.course)
    cfg = config.load(root)
    mods = loader.load_modules(cfg)
    problems = validate.check(
        mods, assessments.load_assessments(cfg), assessments.load_suggestions(cfg)
    )
    if problems:
        print("%s: %d problem(s)" % (cfg.id, len(problems)))
        for p in problems:
            print("  - %s" % p)
        return 1
    print("%s is consistent: %d modules, %d sections."
          % (cfg.id, len(mods), sum(len(m.sections) for m in mods)))
    return 0


def cmd_build(args) -> int:
    cfg, modules, lib = _assemble(_course_root(args.course))
    out_dir = args.out or os.path.join(DIST_DIR, cfg.id)
    result = renderer.write(cfg, modules, lib, out_dir)
    print(result.summary())
    print("  published copy: %s" % result.web_path)
    print("  local copy:     %s   (this is the one that can ask questions)" % result.local_path)
    return 0


def cmd_where(_args) -> int:
    from .paths import ENV_FILE, REPO_ROOT
    print("platform  %s" % REPO_ROOT)
    print("courses   %s" % COURSES_DIR)
    print("dist      %s" % DIST_DIR)
    print("settings  %s" % SETTINGS.path)
    if SETTINGS.overlay:
        print("overlay   %s" % SETTINGS.overlay)
    print("config    %s%s" % (ENV_FILE, "" if os.path.isfile(ENV_FILE) else "  (absent)"))
    for key, source in sorted(SETTINGS.overrides.items()):
        print("  %-24s = %-28s from %s" % (key, SETTINGS.get(key), source))
    return 0


def cmd_studio(args) -> int:
    """Studio is imported lazily: the build path must not depend on the server or on Claude."""
    from studio.server import serve
    return serve(port=args.port or int(SETTINGS.get("studio.port")), open_browser=not args.no_open,
                 host=args.host)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build.py", description="Build a self-contained study site from a course folder."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list courses").set_defaults(func=cmd_list)
    sub.add_parser("where", help="print the resolved courses and dist directories").set_defaults(func=cmd_where)

    new = sub.add_parser("new", help="scaffold an empty course")
    new.add_argument("--theme", required=True, help='subject, e.g. "negotiation"')
    new.add_argument("--hours", required=True, type=float, help="total study budget")
    new.add_argument("--id", default="", help="folder name (default: slug of the theme)")
    new.add_argument("--force", action="store_true", help="write into an existing folder")
    new.set_defaults(func=cmd_new)

    check = sub.add_parser("check", help="validate a course without building")
    check.add_argument("course")
    check.set_defaults(func=cmd_check)

    build = sub.add_parser("build", help="build a course to dist/")
    build.add_argument("course")
    build.add_argument("--out", default="", help="output directory (default: dist/<course>)")
    build.set_defaults(func=cmd_build)

    studio = sub.add_parser("studio", help="open the Studio UI in a browser")
    studio.add_argument("--port", type=int, default=0,
                        help="port (default: %s)" % SETTINGS.get("studio.port"))
    studio.add_argument("--no-open", action="store_true", help="do not open a browser")
    studio.add_argument("--host", default="",
                        help="bind address (default: %s)" % SETTINGS.get("studio.host"))
    studio.set_defaults(func=cmd_studio)
    return parser


def main(argv: List[str] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except CourseError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
