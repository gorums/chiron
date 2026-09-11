"""Writing a course with a model: the pipeline, the prompts, and the shapes they come back in.

Nothing here serves HTTP and nothing here knows what a screen looks like. Each module is
given a `jobs.Job` to report progress to, asks `modelcall` for text or JSON, and writes
files. That is what makes a generation run replayable from its event log and testable by
stubbing one function.

    prompts/      every prompt Studio sends, one module per stage
    overrides     the prompts a course sends instead of the platform's (plan/prompts.json)
    curriculum    the plan a course is written from: propose, normalise, reload for a resume
    coerce        model output into shapes `coursekit.course.validate` accepts
    generator     the pipeline: plan -> approve -> write -> validate -> build
    figures       figures for one module: parse the reply, write the SVGs, reference them
    notebooks     the same for Jupyter notebooks
    editing       one module of a course that already exists: extend, rewrite, patch
    reviews       what the model thinks of a module, and what its owner thinks
    promptview    every stage's prompt for one module, gathered for reading and editing
"""
