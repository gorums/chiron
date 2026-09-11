"""Course Studio — a local web app for creating, generating and building courses.

The build engine (`coursekit`) is a library with a command line. Studio is a second front end
onto the same library, for the parts that are awkward in a terminal: watching a long
generation run, editing a proposed curriculum before committing to it, and reading validation
errors next to the course they belong to.

Four groups, because Studio does four things. It serves HTTP; it asks a model to write
courses; it keeps what a run and a reader leave behind; and a handful of helpers hold the
rest together. What is left at the top level is the work that fits none of them — a course
operation that needs no model, or a question about models themselves.

    server/       HTTP in, JSON out: the route table, SSE, and the static UI in ui/
    authoring/    writing a course with a model: the pipeline, the prompts, the coercions
    store/        what a running Studio keeps: jobs, reader progress, preferences
    support/      files, ids, errors, log — one copy of each, for everyone

    catalog       what the API reports: course_summary, course_detail, state, calendar
    manage        course operations that need no model: settings, move, remove, trash
    transfer      a course in or out as a zip or a git clone
    search        every course searched at once, through the build's own loader
    jupyter       is the notebook server up, and what a served page is told about it
    modelcall     Studio's way in to coursekit.llm: ask, ask_json, probe, and the Reporter
    models        the model list Studio offers, saved over the platform's
    discover      keeping that list current: every provider asked what it knows
"""
