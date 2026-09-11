"""coursekit — build a self-contained study site from a folder of markdown.

The platform knows nothing about any particular subject. A course is a folder holding a
`course.json` manifest, module markdown, reference material and authored study data; the
engine turns it into one HTML file that tracks progress, runs spaced repetition, and asks
the tutor about whatever the reader is looking at.

The map, in dependency order. Three groups, because a module here does one of three
things: it reads a course, it renders one, or it is something all of them need.

    settings          every default the platform has, in layers (stdlib only: the bridge
                      imports it from outside the package)
    paths             where courses/ and dist/ are
    errors            failure types
    failures          why a model call failed, re-exported for the bridge

    course/           reading a course off disk
      config            course.json -> CourseConfig, and the CFG the page receives
      markdown_render   markdown -> html, and html -> plain text
      figures           SVG diagrams: sanitise, check, inline
      notebooks         Jupyter notebooks: check, render read-only
      loader            module markdown -> Module/Section objects
      assessments       quizzes, flashcards and suggested questions
      library           glossary, mental models, worksheets, plan pages
      validate          cross-file consistency, all in one pass

    render/           turning one into the file the reader opens
      bundler           the front end: the css + js named by web/bundle.json, concatenated
      renderer          DATA + CFG injected into the shell; writes both outputs

    llm/              reaching a model, whoever makes it (the bridge imports this too)

    scaffold          theme + hours -> an empty but valid course tree
    cli               the command line
"""

__version__ = "1.0.0"
