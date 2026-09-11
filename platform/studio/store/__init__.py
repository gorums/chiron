"""What one running Studio keeps: on disk under `state/`, and in memory between requests.

Everything here is generated and personal — a reader's progress, a run's event log, which
model was last picked. None of it belongs to a course, which is why none of it is written
into `courses/<id>/`.

    jobs        background work with a replayable event log, persisted per job
    progress    the platform-side copy of reader state, one JSON file per course and profile
    prefs       Studio-wide preferences in state/studio.json: the model, the reader profile
    runtime     the paths, the job registry and the preferences one process shares
"""
