"""Watching a job run: the approval gate's answer, a cancel, and the event stream.

The stream is Server-Sent Events replayed from the client's last index, so a refresh in the
middle of a forty-minute run loses nothing.
"""

from __future__ import annotations

import json
import time

from ..store.runtime import REGISTRY
from .base import route


class JobRoutes:
    @route("POST", r"/api/jobs/(?P<job_id>[^/]+)/(?P<action>answer|cancel)")
    def job_action(self, job_id: str, action: str):
        job = REGISTRY.get(job_id)
        if not job:
            return self._fail("No such job", 404)
        if action == "cancel":
            job.cancel()
            return self._json({"ok": True})
        if not job.provide(self._body()):
            return self._fail("That job is not waiting for an answer.")
        self._json({"ok": True})

    @route("GET", r"/api/jobs/(?P<job_id>[^/]+)/events")
    def job_events(self, job_id: str):
        """Server-Sent Events, replayed from the client's last index so a refresh loses nothing."""
        job = REGISTRY.get(job_id)
        if not job:
            return self._fail("No such job", 404)
        cursor = int(self._param("from", "0"))

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        last_beat = time.time()
        try:
            while True:
                for event in job.since(cursor):
                    cursor = event["i"] + 1
                    self.wfile.write(("data: %s\n\n" % json.dumps(event, ensure_ascii=False)).encode("utf-8"))
                    self.wfile.flush()
                if job.finished and cursor >= len(job.events):
                    return
                if time.time() - last_beat > 15:      # keep proxies and the browser awake
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    last_beat = time.time()
                time.sleep(0.25)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return
