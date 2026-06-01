"""Tracked background jobs with idempotency and progress."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from django.utils import timezone

from .logging_utils import get_logger
from .models import PipelineJob

logger = get_logger(__name__)


def make_idempotency_key(kind: str, **params: Any) -> str:
    basis = json.dumps({"kind": kind, **params}, sort_keys=True, default=str)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:48]


def get_active_job(kind: str, idempotency_key: str) -> PipelineJob | None:
    return (
        PipelineJob.objects.filter(
            kind=kind,
            idempotency_key=idempotency_key,
            status__in=[PipelineJob.Status.QUEUED, PipelineJob.Status.RUNNING],
        )
        .order_by("-created_at")
        .first()
    )


def start_job(
    kind: str,
    idempotency_key: str,
    *,
    progress_total: int = 0,
    metadata: dict | None = None,
) -> tuple[PipelineJob, bool]:
    """
    Returns (job, should_run). If False, an identical job is already running.
    """
    existing = get_active_job(kind, idempotency_key)
    if existing:
        return existing, False

    job = PipelineJob.objects.create(
        kind=kind,
        idempotency_key=idempotency_key,
        status=PipelineJob.Status.RUNNING,
        progress_total=max(0, progress_total),
        progress_current=0,
        message="Starting…",
        metadata=metadata or {},
        started_at=timezone.now(),
    )
    return job, True


def update_progress(job: PipelineJob, current: int, message: str = "") -> PipelineJob:
    job.refresh_from_db()
    if job.status == PipelineJob.Status.CANCELLED:
        raise JobCancelledError("Job was cancelled.")
    job.progress_current = current
    if message:
        job.message = message[:240]
    job.save(update_fields=["progress_current", "message", "updated_at"])
    return job


def complete_job(job: PipelineJob, result: dict | None = None) -> PipelineJob:
    job.status = PipelineJob.Status.COMPLETED
    job.finished_at = timezone.now()
    job.result = result or {}
    job.message = job.message or "Completed"
    job.save(update_fields=["status", "finished_at", "result", "message", "updated_at"])
    logger.info("Pipeline job %s completed (%s)", job.id, job.kind)
    return job


def fail_job(job: PipelineJob, exc: Exception) -> PipelineJob:
    job.status = PipelineJob.Status.FAILED
    job.finished_at = timezone.now()
    job.error_message = str(exc)[:2000]
    job.message = "Failed"
    job.save(update_fields=["status", "finished_at", "error_message", "message", "updated_at"])
    logger.warning("Pipeline job %s failed: %s", job.id, exc)
    return job


def cancel_job(job_id: int) -> PipelineJob:
    job = PipelineJob.objects.get(id=job_id)
    if job.status in (PipelineJob.Status.COMPLETED, PipelineJob.Status.FAILED):
        return job
    job.status = PipelineJob.Status.CANCELLED
    job.finished_at = timezone.now()
    job.message = "Cancelled by user"
    job.save(update_fields=["status", "finished_at", "message", "updated_at"])
    return job


class JobCancelledError(RuntimeError):
    pass


def run_tracked(
    kind: str,
    idempotency_key: str,
    func: Callable[[PipelineJob], Any],
    *,
    progress_total: int = 0,
    metadata: dict | None = None,
) -> dict[str, Any]:
    job, should_run = start_job(kind, idempotency_key, progress_total=progress_total, metadata=metadata)
    if not should_run:
        return {
            "job_id": job.id,
            "deduplicated": True,
            "status": job.status,
            "message": "An identical job is already running.",
        }
    try:
        result = func(job)
        complete_job(job, result if isinstance(result, dict) else {"result": result})
        return {"job_id": job.id, "deduplicated": False, "status": job.status, "result": job.result}
    except JobCancelledError:
        return {"job_id": job.id, "status": job.status, "cancelled": True}
    except Exception as exc:
        fail_job(job, exc)
        raise
