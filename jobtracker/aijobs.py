"""Background AI jobs.

Ollama answers one request at a time, and a 7B model on a laptop CPU writes roughly 4-10 tokens a second, so a
review can take minutes. Every AI task therefore runs here, in one worker thread, and reports live progress
(waiting / loading the model / reading / writing N tokens) that the interface polls. Interactive tasks (a review
you just asked for) jump ahead of batch tasks (ranking a list of saved jobs). Jobs can be cancelled; the HTTP
stream to Ollama is closed, which makes Ollama stop generating.
"""

from __future__ import annotations

import itertools
import threading
import time
import traceback
from typing import Callable

INTERACTIVE, BATCH = 0, 5


class Cancelled(Exception):
    pass


class Progress:
    """Handed to the task; the Ollama client calls it while streaming."""

    def __init__(self, job: dict, lock: threading.Lock):
        self._job, self._lock = job, lock

    def phase(self, phase: str, **extra) -> None:
        with self._lock:
            self._job.update(phase=phase, **extra)
        self.check()

    def step(self, label: str, index: int, total: int, expected_tokens: int | None = None) -> None:
        with self._lock:
            self._job.update(step=label, step_index=index, steps=total, tokens=0,
                             expected_tokens=expected_tokens, phase="reading")
        self.check()

    def token(self, n: int = 1) -> None:
        with self._lock:
            self._job["tokens"] = self._job.get("tokens", 0) + n
            self._job["total_tokens"] = self._job.get("total_tokens", 0) + n
            self._job["phase"] = "writing"
        self.check()

    def partial(self) -> None:
        """Part of the result has been saved; the interface can show it now."""
        with self._lock:
            self._job["partial"] = self._job.get("partial", 0) + 1

    def check(self) -> None:
        if self._job.get("cancel"):
            raise Cancelled()


class AIJobs:
    def __init__(self, on_change: Callable[[], None] | None = None, keep: int = 40):
        self.lock = threading.Lock()
        self.jobs: dict[int, dict] = {}
        self.queue: list[tuple[int, int, int]] = []  # (priority, seq, job id)
        self.ids = itertools.count(1)
        self.seq = itertools.count()
        self.worker: threading.Thread | None = None
        self.on_change = on_change
        self.keep = keep
        self.fns: dict[int, Callable[[Progress], object]] = {}

    # ------------------------------------------------------------------ submit / inspect
    def submit(self, key: str, label: str, fn: Callable[[Progress], object], priority: int = INTERACTIVE,
               group: str = "", meta: dict | None = None) -> dict:
        """Queue a task. A task with the same key that is still queued or running is returned instead."""
        with self.lock:
            for j in self.jobs.values():
                if j["key"] == key and j["status"] in ("queued", "running"):
                    return dict(j)
            jid = next(self.ids)
            job = {"id": jid, "key": key, "label": label, "group": group, "priority": priority, "status": "queued",
                   "phase": "waiting", "tokens": 0, "total_tokens": 0, "expected_tokens": None, "step": None,
                   "step_index": 0, "steps": 1, "partial": 0, "created": time.time(), "started": None,
                   "finished": None, "error": None, "cancel": False, "meta": meta or {}}
            self.jobs[jid] = job
            self.fns[jid] = fn
            self.queue.append((priority, next(self.seq), jid))
            self.queue.sort()
            self._trim()
            if not self.worker or not self.worker.is_alive():
                self.worker = threading.Thread(target=self._run, daemon=True)
                self.worker.start()
            return dict(job)

    def _trim(self) -> None:
        done = [j for j in self.jobs.values() if j["status"] in ("done", "error", "cancelled")]
        for j in sorted(done, key=lambda j: j["finished"] or 0)[:-self.keep]:
            self.jobs.pop(j["id"], None)

    def view(self, job: dict) -> dict:
        j = {k: v for k, v in job.items() if k not in ("cancel", "result")}
        now = time.time()
        j["elapsed"] = round((j["finished"] or now) - (j["started"] or now), 1) if j["started"] else 0
        j["waited"] = round((j["started"] or now) - j["created"], 1)
        j["ahead"] = self._ahead(j["id"]) if j["status"] == "queued" else 0
        return j

    def result(self, jid: int):
        with self.lock:
            j = self.jobs.get(jid)
            return j.get("result") if j else None

    def queue_order(self) -> list[int]:
        return [jid for _, _, jid in self.queue]

    def _ahead(self, jid: int) -> int:
        order = self.queue_order()
        running = sum(1 for j in self.jobs.values() if j["status"] == "running")
        return running + (order.index(jid) if jid in order else 0)

    def get(self, jid: int) -> dict | None:
        with self.lock:
            j = self.jobs.get(jid)
            return self.view(j) if j else None

    def find(self, key: str) -> dict | None:
        """The newest job with this key."""
        with self.lock:
            js = [j for j in self.jobs.values() if j["key"] == key]
            return self.view(max(js, key=lambda j: j["id"])) if js else None

    def list(self, active_only: bool = False, group: str | None = None) -> list[dict]:
        with self.lock:
            js = [self.view(j) for j in self.jobs.values()
                  if (not active_only or j["status"] in ("queued", "running")) and (group is None or j["group"] == group)]
        return sorted(js, key=lambda j: j["id"])

    def cancel(self, jid: int) -> dict | None:
        with self.lock:
            j = self.jobs.get(jid)
            if not j:
                return None
            if j["status"] == "queued":
                self.queue = [q for q in self.queue if q[2] != jid]
                j.update(status="cancelled", finished=time.time(), phase="cancelled")
            elif j["status"] == "running":
                j["cancel"] = True
            return self.view(j)

    def cancel_group(self, group: str, include_running: bool = False) -> None:
        with self.lock:
            ids = [j["id"] for j in self.jobs.values() if j["group"] == group and j["status"] == "queued"]
            run = [j for j in self.jobs.values() if j["group"] == group and j["status"] == "running"]
        for i in ids:
            self.cancel(i)
        if include_running:
            for j in run:
                self.cancel(j["id"])

    # ------------------------------------------------------------------ worker
    def _run(self) -> None:
        while True:
            with self.lock:
                if not self.queue:
                    self.worker = None
                    return
                _, _, jid = self.queue.pop(0)
                job = self.jobs.get(jid)
                fn = self.fns.pop(jid, None)
                if not job or not fn or job["status"] != "queued":
                    continue
                job.update(status="running", started=time.time(), phase="reading")
            prog = Progress(job, self.lock)
            try:
                result = fn(prog)
                with self.lock:
                    job.update(status="done", phase="done", finished=time.time(), result=result)
            except Cancelled:
                with self.lock:
                    job.update(status="cancelled", phase="cancelled", finished=time.time())
            except Exception as e:  # noqa: BLE001
                detail = getattr(e, "detail", None) or str(e) or e.__class__.__name__
                if not getattr(e, "detail", None) and not str(e):
                    traceback.print_exc()
                with self.lock:
                    job.update(status="error", phase="error", finished=time.time(), error=str(detail))
            if self.on_change:
                try:
                    self.on_change()
                except Exception:  # noqa: BLE001
                    pass
