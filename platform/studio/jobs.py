"""Background jobs with a replayable event log.

Writing a course takes minutes, so the HTTP request that starts it cannot be the one that
finishes it. A job runs on its own thread and appends events; the browser subscribes and
replays from wherever it left off. That replay-from-index design is what lets the page be
refreshed, or reopened in another tab, without losing the run.

Jobs are in-memory and die with the server. That is deliberate: the durable artefact is the
course on disk, not the job record. A run interrupted halfway leaves real files behind, and
the generator is written so a rerun overwrites them cleanly.
"""

from __future__ import annotations

import itertools
import threading
import time
import traceback
from typing import Any, Callable, Dict, List, Optional

PENDING, RUNNING, WAITING, DONE, FAILED, CANCELLED = (
    "pending", "running", "waiting", "done", "failed", "cancelled"
)
_ids = itertools.count(1)


class Cancelled(Exception):
    """Raised inside a job's thread when the user cancels it."""


class Job:
    """One unit of long-running work, observable from HTTP."""

    def __init__(self, kind: str, meta: Optional[Dict[str, Any]] = None):
        self.id = "job%d" % next(_ids)
        self.kind = kind
        self.meta: Dict[str, Any] = dict(meta or {})
        self.status = PENDING
        self.error = ""
        self.result: Any = None
        self.events: List[Dict[str, Any]] = []
        self.created = time.time()

        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._resume = threading.Event()
        self._answer: Any = None
        self._thread: Optional[threading.Thread] = None

    # ---- event log ----

    def emit(self, kind: str, **fields) -> None:
        """Append one event. `kind` is this method's own parameter, so an event may not
        carry a field of that name - pass it under a different key."""
        with self._lock:
            event = dict(fields)
            event.update(kind=kind, at=time.time(), i=len(self.events))
            self.events.append(event)

    def log(self, message: str) -> None:
        self.emit("log", message=message)

    def progress(self, done: int, total: int, label: str = "") -> None:
        self.emit("progress", done=done, total=total, label=label)

    def since(self, index: int) -> List[Dict[str, Any]]:
        with self._lock:
            return self.events[max(0, index):]

    # ---- control ----

    def cancel(self) -> None:
        self._cancel.set()
        self._resume.set()          # unblock a job parked at an approval gate

    def check_cancelled(self) -> None:
        """Call at every safe stopping point; a job that never calls this cannot be stopped."""
        if self._cancel.is_set():
            raise Cancelled()

    def await_input(self, prompt_kind: str, payload: Any) -> Any:
        """Park until the UI supplies an answer. This is the curriculum approval gate."""
        self._resume.clear()
        self.status = WAITING
        self.emit("await", prompt=prompt_kind, payload=payload)
        self._resume.wait()
        self.check_cancelled()
        self.status = RUNNING
        answer, self._answer = self._answer, None
        self.emit("resumed", prompt=prompt_kind)
        return answer

    def provide(self, answer: Any) -> bool:
        if self.status != WAITING:
            return False
        self._answer = answer
        self._resume.set()
        return True

    # ---- running ----

    def start(self, fn: Callable[["Job"], Any]) -> "Job":
        def run():
            # Everything, including the opening event, sits inside the try: an exception
            # escaping this function kills the thread with the job stuck at "running".
            try:
                self.status = RUNNING
                self.emit("started", job=self.kind)
                self.result = fn(self)
                self.status = DONE
                self.emit("done", result=self.result)
            except Cancelled:
                self.status = CANCELLED
                self.emit("cancelled")
            except Exception as exc:  # noqa: BLE001 - the point is to report, not crash
                self.status = FAILED
                self.error = str(exc)
                self.emit("failed", error=str(exc), trace=traceback.format_exc()[-1500:])
            finally:
                self.emit("end", status=self.status)

        self._thread = threading.Thread(target=run, daemon=True, name=self.id)
        self._thread.start()
        return self

    @property
    def finished(self) -> bool:
        return self.status in (DONE, FAILED, CANCELLED)

    def summary(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "error": self.error,
            "meta": self.meta,
            "events": len(self.events),
            "created": self.created,
        }


class Registry:
    """Every job this server has run. Small enough to keep; capped so it cannot grow forever."""

    LIMIT = 40

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def add(self, job: Job) -> Job:
        with self._lock:
            self._jobs[job.id] = job
            if len(self._jobs) > self.LIMIT:
                for jid, j in sorted(self._jobs.items(), key=lambda kv: kv[1].created):
                    if j.finished:
                        del self._jobs[jid]
                    if len(self._jobs) <= self.LIMIT:
                        break
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def active_for(self, course_id: str) -> Optional[Job]:
        for job in self._jobs.values():
            if job.meta.get("course") == course_id and not job.finished:
                return job
        return None

    def all(self) -> List[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)
