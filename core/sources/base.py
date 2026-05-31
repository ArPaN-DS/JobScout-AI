"""Job source adapter contract for the discovery pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from django.utils import timezone

from core.job_sources import ImportedJob
from core.logging_utils import get_logger
from core.models import JobSourceRun
from core.resilience import circuit_breaker

logger = get_logger(__name__)


@dataclass
class SourceHealth:
    source_id: str
    label: str
    tier: str
    available: bool
    cooldown_remaining_seconds: int = 0
    last_run_status: str = ""
    last_run_at: datetime | None = None
    last_discovered: int = 0
    last_imported: int = 0
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "label": self.label,
            "tier": self.tier,
            "available": self.available,
            "cooldown_remaining_seconds": self.cooldown_remaining_seconds,
            "last_run_status": self.last_run_status,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_discovered": self.last_discovered,
            "last_imported": self.last_imported,
            "last_error": self.last_error,
        }


@dataclass
class AdapterRunResult:
    source_id: str
    discovered_count: int = 0
    imported_count: int = 0
    run: JobSourceRun | None = None
    error: str = ""


class JobSourceAdapter(ABC):
    """One portal or API family. Each run creates a JobSourceRun row."""

    source_id: str
    source_name: str
    tier: str = "A"
    uses_hours_old: bool = True
    query_agnostic: bool = False

    def health(self) -> SourceHealth:
        last_run = (
            JobSourceRun.objects.filter(source_type=self.source_id)
            .order_by("-started_at")
            .first()
        )
        cooldown = circuit_breaker.cooldown_remaining(self.source_id)

        return SourceHealth(
            source_id=self.source_id,
            label=self.source_name,
            tier=self.tier,
            available=circuit_breaker.is_available(self.source_id),
            cooldown_remaining_seconds=cooldown,
            last_run_status=last_run.status if last_run else "",
            last_run_at=last_run.started_at if last_run else None,
            last_discovered=last_run.discovered_count if last_run else 0,
            last_imported=last_run.imported_count if last_run else 0,
            last_error=(last_run.error_message if last_run else "")[:200],
        )

    @abstractmethod
    def fetch_raw(self, query: str, hours_old: int) -> list[dict]:
        """Return normalized dicts: title, company, location, description, apply_url, source."""

    def to_imported_jobs(self, raw_jobs: list[dict]) -> list[ImportedJob]:
        imported: list[ImportedJob] = []
        for job in raw_jobs:
            url = str(job.get("apply_url") or job.get("job_url") or "").strip()
            title = str(job.get("title") or "").strip()
            if not url or not title:
                continue
            imported.append(
                ImportedJob(
                    title=title,
                    company=str(job.get("company") or "Unknown").strip(),
                    location=str(job.get("location") or "").strip(),
                    job_url=url,
                    description=str(job.get("description") or "")[:4000],
                    source_type="scraped",
                    source_name=str(job.get("source") or self.source_id),
                    raw_payload=job,
                )
            )
        return imported

    def run(self, queries: list[str], hours_old: int, import_fn: Callable) -> AdapterRunResult:
        """import_fn: (ImportedJob) -> tuple[JobLead, bool]"""
        source_run = JobSourceRun.objects.create(
            source_type=self.source_id,
            source_name=self.source_name,
            metadata={"hours_old": hours_old, "tier": self.tier},
        )
        if not circuit_breaker.is_available(self.source_id):
            message = f"Circuit open for {self.source_id}"
            source_run.fail(RuntimeError(message))
            logger.warning(message)
            return AdapterRunResult(source_id=self.source_id, run=source_run, error=message)

        try:
            raw_jobs: list[dict] = []
            active_queries = ["all"] if self.query_agnostic else queries
            for query in active_queries:
                batch = self.fetch_raw(query, hours_old)
                if batch:
                    raw_jobs.extend(batch)

            jobs = self.to_imported_jobs(raw_jobs)
            imported = 0
            for job in jobs:
                _, created = import_fn(job)
                imported += int(created)

            source_run.metadata = {
                **(source_run.metadata or {}),
                "queries_used": len(active_queries),
            }
            source_run.finish(discovered_count=len(jobs), imported_count=imported)
            circuit_breaker.record_success(self.source_id)
            logger.info(
                "[%s] discovered=%s imported=%s",
                self.source_id,
                len(jobs),
                imported,
            )
            return AdapterRunResult(
                source_id=self.source_id,
                discovered_count=len(jobs),
                imported_count=imported,
                run=source_run,
            )
        except Exception as exc:
            circuit_breaker.record_failure(self.source_id, str(exc))
            source_run.fail(exc)
            logger.exception("[%s] discovery failed", self.source_id)
            return AdapterRunResult(
                source_id=self.source_id,
                run=source_run,
                error=str(exc),
            )


class CallableSourceAdapter(JobSourceAdapter):
    """Wrap existing search_* functions from job_sources."""

    def __init__(
        self,
        source_id: str,
        source_name: str,
        fetch_fn: Callable,
        *,
        tier: str = "A",
        uses_hours_old: bool = True,
        query_agnostic: bool = False,
        query_filter: Callable[[str], bool] | None = None,
    ) -> None:
        self.source_id = source_id
        self.source_name = source_name
        self._fetch_fn = fetch_fn
        self.tier = tier
        self.uses_hours_old = uses_hours_old
        self.query_agnostic = query_agnostic
        self._query_filter = query_filter

    def fetch_raw(self, query: str, hours_old: int) -> list[dict]:
        if self._query_filter and not self._query_filter(query):
            return []
        if self.query_agnostic:
            query = "all"
        if self.uses_hours_old:
            return self._fetch_fn(query, hours_old)
        return self._fetch_fn(query)
