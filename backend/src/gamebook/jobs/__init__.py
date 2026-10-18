"""Background jobs: a persisted ``Job`` row per task, one worker thread, SSE progress.

Jobs run one at a time in a daemon thread (CPU-heavy work fans out to the
simulation process pool from inside the job). Progress is written to the row
at most every ``PROGRESS_INTERVAL`` seconds; the API streams it with SSE.
"""

from gamebook.jobs.runner import JobCancelledError, JobContext, JobRunner

__all__ = ["JobCancelledError", "JobContext", "JobRunner"]
