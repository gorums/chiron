"""Background jobs with a replayable event log.

Writing a course takes minutes, so the HTTP request that starts it cannot be the one that
finishes it. A job runs on its own thread and appends events; the browser subscribes and
replays from wherever it left off. That replay-from-index design is what lets the page be
refreshed, or reopened in another tab, without losing the run.

Jobs run in memory. The durable artefact is the course on disk, not the job record — a run
interrupted halfway leaves real files behind, and the generator is written so a rerun
overwrites them cleanly. But the *record* of a run is worth keeping too: in Docker a restart
would otherwise erase what happened. So a finished job is written to `state/jobs/` and can
be listed and replayed from there after the process that ran it is gone.
"""

from __future__ import annotations

import itertools
import json
import os
import threading
import time
import traceback
from typing import Any, Callable, Dict, List, Optional

from .log import log

PENDING, RUNNING, WAITING, DONE, FAILED, CANCELLED = (
    "pending", "running", "waiting", "done", "failed", "cancelled"
)
_ids = itertools.count(1)
_BOOT = format(int(time.time()), "x")     # ids must not collide with jobs stored by an earlier run

# The job running on the current thread, so code that has no Job in hand (modelcall, which
# is also called by the tutor route with no job at all) can still report what it is doing.
_current = threading.local()


def current() -> Optional["Job"]:
    """The Job whose thread this is, or None on a request thread."""
    return getattr(_current, "job", None)


class Cancelled(Exception):
    """Raised inside a job's thread when the user cancels it."""


# Event payloads that are worth a log line, and how to say them. Big payloads (a whole
# plan, a result dict) are summarised rather than dumped.
def _log_event(job: "Job", event: Dict[str, Any]) -> None:
    kind = event["kind"]
    head = "%s %s" % (job.id, job.kind)
    if kind == "log":
        log.info("%s: %s", head, event.get("message", ""))
    elif kind == "progress":
        log.info("%s: step %s/%s %s", head, event.get("done"), event.get("total"), event.get("label", ""))
    elif kind == "failed":
        log.error("%s: FAILED %s\n%s", head, event.get("error", ""), event.get("trace", ""))
    elif kind == "plan":
        plan = event.get("plan") or {}
        log.info("%s: plan proposed - %d modules, %d parts", head,
                 len(plan.get("modules") or []), len(plan.get("parts") or []))
    elif kind in ("started", "cancelled", "await", "resumed", "end"):
        log.info("%s: %s %s", head, kind, event.get("status") or event.get("prompt") or "")
    elif kind in ("module", "studydata", "spec", "worksheet", "built"):
        brief = {k: v for k, v in event.items() if k not in ("kind", "at", "i", "path")}
        log.info("%s: %s %s", head, kind, brief)
    # "call" events are not logged here: modelcall already writes one line per CLI call.


class Job:
    """One unit of long-running work, observable from HTTP."""

    def __init__(self, kind: str, meta: Optional[Dict[str, Any]] = None):
        self.id = "j%s-%d" % (_BOOT, next(_ids))
        self.kind = kind
        self.meta: Dict[str, Any] = dict(meta or {})
        self.status = PENDING
        self.error = ""
        self.why = ""        # for a failure the model caused: its kind, from llm.failures
        self.result: Any = None
        self.events: List[Dict[str, Any]] = []
        self.created = time.time()
        self.started: Optional[float] = None
        self.step: Optional[Dict[str, Any]] = None    # the last progress event
        self.call: Optional[Dict[str, Any]] = None    # the model call in flight, if any

        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._resume = threading.Event()
        self._answer: Any = None
        self._thread: Optional[threading.Thread] = None
        self.on_end: Optional[Callable[["Job"], None]] = None

    # ---- event log ----

    def emit(self, kind: str, **fields) -> None:
        """Append one event. `kind` is this method's own parameter, so an event may not
        carry a field of that name - pass it under a different key."""
        with self._lock:
            event = dict(fields)
            event.update(kind=kind, at=time.time(), i=len(self.events))
            self.events.append(event)
            # What the listing shows without replaying the log: where the job is, and
            # whether it is inside a model call right now.
            if kind == "progress":
                self.step = event
            elif kind == "call":
                self.call = event if event.get("phase") == "start" else None
            elif kind == "started":
                self.started = event["at"]
        _log_event(self, event)

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
            _current.job = self
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
                # An LLMFailed carries the kind of trouble; the screen needs it to say
                # whether waiting, signing in or resuming is the thing to do.
                self.why = str(getattr(exc, "kind", "") or "")
                self.emit("failed", error=str(exc), why=self.why,
                          trace=traceback.format_exc()[-1500:])
            finally:
                self.call = None
                self.emit("end", status=self.status)
                _current.job = None
                if self.on_end:
                    try:
                        self.on_end(self)
                    except Exception:  # noqa: BLE001 - persistence must never fail the job
                        pass

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
            "why": self.why,
            "meta": self.meta,
            "events": len(self.events),
            "created": self.created,
            "started": self.started,
            "ended": self.events[-1]["at"] if self.finished and self.events else None,
            "progress": self.step,
            "call": self.call,
        }

    def record(self) -> Dict[str, Any]:
        """Everything worth keeping once the job is over."""
        with self._lock:
            return dict(self.summary(), result=self.result, events=list(self.events))


class StoredJob:
    """A finished job read back from disk. Same face as Job for listing and replay."""

    finished = True

    def __init__(self, record: Dict[str, Any]):
        self.id = record.get("id", "")
        self.kind = record.get("kind", "")
        self.status = record.get("status", DONE)
        self.error = record.get("error", "")
        self.why = record.get("why", "")
        self.meta = record.get("meta") or {}
        self.result = record.get("result")
        self.events = record.get("events") or []
        self.created = record.get("created", 0)

    def since(self, index: int) -> List[Dict[str, Any]]:
        return self.events[max(0, index):]

    def provide(self, answer: Any) -> bool:
        return False

    def cancel(self) -> None:
        pass

    def summary(self) -> Dict[str, Any]:
        started = next((e["at"] for e in self.events if e.get("kind") == "started"), None)
        return {"id": self.id, "kind": self.kind, "status": self.status, "error": self.error,
                "why": self.why,
                "meta": self.meta, "events": len(self.events), "created": self.created,
                "started": started,
                "ended": self.events[-1]["at"] if self.events else None,
                "progress": None, "call": None}


class Registry:
    """Every job this server has run, plus the finished ones an earlier run wrote to disk.

    In memory it is capped so it cannot grow forever. On disk, `store_dir` keeps the last
    `KEEP` finished jobs; older files are pruned as new ones arrive.
    """

    LIMIT = 40
    KEEP = 60

    def __init__(self, store_dir: str = ""):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self.store_dir = store_dir

    def add(self, job: Job) -> Job:
        with self._lock:
            self._jobs[job.id] = job
            if len(self._jobs) > self.LIMIT:
                for jid, j in sorted(self._jobs.items(), key=lambda kv: kv[1].created):
                    if j.finished:
                        del self._jobs[jid]
                    if len(self._jobs) <= self.LIMIT:
                        break
        if self.store_dir:
            job.on_end = self._persist
        return job

    def get(self, job_id: str):
        job = self._jobs.get(job_id)
        if job is not None:
            return job
        return self._load(job_id)

    def active_for(self, course_id: str) -> Optional[Job]:
        for job in self._jobs.values():
            if job.meta.get("course") == course_id and not job.finished:
                return job
        return None

    def all(self) -> List[Any]:
        live = list(self._jobs.values())
        seen = {j.id for j in live}
        stored = [j for j in self._stored() if j.id not in seen]
        return sorted(live + stored, key=lambda j: j.created, reverse=True)

    # ---- disk ----

    def _path(self, job_id: str) -> str:
        safe = "".join(ch for ch in job_id if ch.isalnum() or ch in "-_")
        return os.path.join(self.store_dir, safe + ".json")

    def _persist(self, job: Job) -> None:
        os.makedirs(self.store_dir, exist_ok=True)
        tmp = self._path(job.id) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(job.record(), fh, ensure_ascii=False)
        os.replace(tmp, self._path(job.id))
        self._prune()

    def _prune(self) -> None:
        try:
            names = sorted(f for f in os.listdir(self.store_dir) if f.endswith(".json"))
        except OSError:
            return
        paths = sorted((os.path.join(self.store_dir, n) for n in names), key=os.path.getmtime)
        extra = paths[:-self.KEEP] if len(paths) > self.KEEP else []
        for path in extra:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _load(self, job_id: str) -> Optional[StoredJob]:
        if not self.store_dir:
            return None
        path = self._path(job_id)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
        except (OSError, ValueError):
            return None
        return StoredJob(record) if isinstance(record, dict) else None

    def _stored(self) -> List[StoredJob]:
        if not self.store_dir or not os.path.isdir(self.store_dir):
            return []
        out = []
        for name in os.listdir(self.store_dir):
            if name.endswith(".json"):
                job = self._load(name[:-5])
                if job:
                    out.append(job)
        return out
