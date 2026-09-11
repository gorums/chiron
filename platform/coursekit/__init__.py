"""coursekit — build a self-contained study site from a folder of markdown.

The platform knows nothing about any particular subject. A course is a folder holding a
`course.json` manifest, module markdown, reference material and authored study data; the
engine turns it into one HTML file that tracks progress, runs spaced repetition, and asks
the tutor about whatever the reader is looking at.

Module map, in dependency order:

    errors            failure types
    config            course.json -> CourseConfig
    markdown_render   markdown -> html, and html -> plain text
    loader            module markdown -> Module/Section objects
    assessments       quizzes, flashcards and suggested questions
    library           glossary, mental models, worksheets, plan pages
    validate          cross-file consistency, all in one pass
    bundler           the front end: css + js + shell, concatenated
    renderer          DATA + CFG injected into the shell; writes both outputs
    scaffold          theme + hours -> an empty but valid course tree
    cli               the command line
"""

__version__ = "1.0.0"
