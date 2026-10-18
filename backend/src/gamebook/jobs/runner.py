"""In-process job runner (SPEC §3: in-process worker, persisted Job table)."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy import select

from gamebook.db.base import utcnow
from gamebook.db.models import Job
from gamebook.db.session import Database

log = logging.getLogger(__name__)

PROGRESS_INTERVAL = 0.25

#: A job body: does the work, reports through the context, returns the result.
JobFn = Callable[["JobContext"], dict[str, Any]]
#: Called with (session-less) job id and final status after the job ends.
Finisher = Callable[[str, str], None]


class JobCancelledError(Exception):
    """Raised inside a job body by ``JobContext.check`` after a cancel request."""


class JobContext:
    def __init__(self, runner: JobRunner, job_id: str) -> None:
        self.runner = runner
        self.job_id = job_id
        self._last = 0.0

    @property
    def db(self) -> Database:
        return self.runner.db

    def progress(self, done: int, total: int | None = None, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last < PROGRESS_INTERVAL:
            return
        self._last = now
        with self.db.session() as s:
            job = s.get(Job, self.job_id)
            if job is not None:
                job.progress = done
                if total is not None:
                    job.total = total

    def cancelled(self) -> bool:
        return self.job_id in self.runner._cancel

    def check(self) -> None:
        if self.cancelled():
            raise JobCancelledError


class JobRunner:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gamebook-job")
        self._cancel: set[str] = set()
        #: Submitted and not yet finished (in memory: shutdown must not need the DB).
        self._active: set[str] = set()
        self._lock = threading.Lock()

    def recover(self) -> int:
        """Mark jobs left queued/running by a previous process as failed."""
        session = self.db.session_factory()
        try:
            stale = list(session.scalars(select(Job).where(Job.status.in_(("queued", "running")))))
            for job in stale:
                job.status = "failed"
                job.error = "Interrupted: the server restarted"
                job.finished_at = utcnow()
            if stale:  # nothing to write is the common case: don't commit at all
                session.commit()
            return len(stale)
        finally:
            session.close()

    def submit(self, job_id: str, fn: JobFn, on_finish: Finisher | None = None) -> None:
        with self._lock:
            self._active.add(job_id)
        self._pool.submit(self._run, job_id, fn, on_finish)

    def cancel(self, job_id: str) -> None:
        with self._lock:
            if job_id in self._active:
                self._cancel.add(job_id)

    def _set(self, job_id: str, **fields: Any) -> None:
        with self.db.session() as s:
            job = s.get(Job, job_id)
            if job is not None:
                for k, v in fields.items():
                    setattr(job, k, v)

    def _run(self, job_id: str, fn: JobFn, on_finish: Finisher | None) -> None:
        status, result, error = "failed", None, None
        try:
            if job_id in self._cancel:
                status = "cancelled"
            else:
                self._set(job_id, status="running", started_at=utcnow())
                result = fn(JobContext(self, job_id))
                status = "done"
        except JobCancelledError:
            status = "cancelled"
        except Exception as exc:  # a job must never take the worker down
            log.exception("Job %s failed", job_id)
            error = str(exc) or type(exc).__name__
        # Owners (e.g. a batch) are updated *before* the job turns terminal, so a
        # client that sees the job finish never reads its owner as still running.
        if on_finish is not None:
            try:
                on_finish(job_id, status)
            except Exception:
                log.exception("Job %s finisher failed", job_id)
        try:
            self._set(job_id, status=status, result=result, error=error, finished_at=utcnow())
        except Exception:
            log.exception("Job %s: could not record its final status", job_id)
        finally:
            with self._lock:
                self._cancel.discard(job_id)
                self._active.discard(job_id)

    def shutdown(self) -> None:
        # Ask running jobs to stop at their next check; queued ones never start
        # (``recover`` marks them failed on the next start).
        with self._lock:
            self._cancel.update(self._active)
        self._pool.shutdown(wait=True, cancel_futures=True)
