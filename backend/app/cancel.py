"""Stopping a job that is already running.

Cancellation is cooperative rather than a kill. The work happens across a Celery
worker and a GPU on another machine, and tearing either down mid-write is how you
get a half-saved render or a job row that disagrees with storage. Instead the person
who started it sets the status, and the pipeline notices at the boundaries it already
has: every stage transition, and every poll of the renderer.

The cost is that a cancel is not instant. The gain is that the pipeline is never in a
state nobody wrote deliberately.
"""

from __future__ import annotations


class Cancelled(RuntimeError):
    """Raised inside the pipeline when the job has been cancelled.

    Carried to the top of the task, where it is recorded as a cancellation rather
    than a failure: nothing went wrong, someone changed their mind.
    """
