"""Course Studio — a local web app for creating, generating and building courses.

The build engine (`coursekit`) is a library with a command line. Studio is a second front end
onto the same library, for the parts that are awkward in a terminal: watching a long
generation run, editing a proposed curriculum before committing to it, and reading validation
errors next to the course they belong to.

    modelcall    reaching a model, whichever provider answers - Studio's way in to coursekit.llm
    jobs         background work with a replayable event log
    prompts      every prompt Studio sends
    generator    the pipeline: plan -> approve -> write -> validate -> build
    server       HTTP, SSE, and the static UI in ui/
"""
