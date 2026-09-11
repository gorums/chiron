"""Reading a course off disk: the manifest, the markdown, the study data, and the checks.

Everything here answers one question — what does this folder of files actually say? —
and nothing here knows how a page is built or how a model is asked.

In dependency order:

    config            course.json -> CourseConfig, and the CFG the page receives
    markdown_render   markdown -> html, and html -> plain text for search and the tutor
    figures           SVG diagrams: sanitise, check, inline, count the build-up steps
    notebooks         Jupyter notebooks: check, render read-only, refuse one without the runtime
    loader            module markdown -> Module/Section objects, figures and notebooks inlined
    assessments       quizzes, flashcards and suggested questions
    library           glossary, mental models, worksheets, plan pages
    validate          every cross-file check, collected into one report
"""
