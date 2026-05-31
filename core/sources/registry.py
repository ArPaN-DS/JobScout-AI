"""Registry of discovery source adapters (Tier A APIs first)."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

import httpx
from django.conf import settings

from core.job_sources import (
    search_career_pages,
    search_foundit,
    search_greenhouse_boards,
    search_hirist,
    search_internshala,
    search_jobspy,
    search_lever_boards,
    search_naukri,
    search_remoteok,
    search_wellfound,
    search_yc_jobs,
)
from core.sources.base import CallableSourceAdapter, JobSourceAdapter, SourceHealth

DEFAULT_SOURCE_IDS = [
    "jobspy",
    "remoteok",
    "naukri",
    "internshala",
    "foundit",
    "hirist",
    "wellfound",
    "ycombinator",
    "greenhouse",
    "lever",
    "career_pages",
]

WELLFOUND_QUERIES = {
    "ML Engineer",
    "AI Engineer",
    "NLP Engineer",
    "GenAI Engineer",
    "LLM Engineer",
    "Machine Learning Engineer",
}


class AsyncClientSourceAdapter(JobSourceAdapter):
    """Adapter for httpx-based async fetchers (one call per run)."""

    query_agnostic = True
    uses_hours_old = False

    def __init__(
        self,
        source_id: str,
        source_name: str,
        async_fn: Callable[[httpx.AsyncClient], Awaitable[list[dict]]],
        *,
        tier: str = "A",
    ) -> None:
        self.source_id = source_id
        self.source_name = source_name
        self._async_fn = async_fn
        self.tier = tier

    def fetch_raw(self, query: str, hours_old: int) -> list[dict]:
        return asyncio.run(self._fetch())

    async def _fetch(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await self._async_fn(client)


def build_adapters(enabled_ids: list[str] | None = None) -> list[JobSourceAdapter]:
    enabled = set(enabled_ids or getattr(settings, "DISCOVERY_SOURCES", DEFAULT_SOURCE_IDS))
    registry: list[JobSourceAdapter] = [
        CallableSourceAdapter("jobspy", "JobSpy (LinkedIn/Indeed/Glassdoor)", search_jobspy, tier="A"),
        AsyncClientSourceAdapter("remoteok", "RemoteOK", search_remoteok),
        CallableSourceAdapter("naukri", "Naukri", search_naukri, tier="B", uses_hours_old=False),
        CallableSourceAdapter("internshala", "Internshala", search_internshala, tier="B", uses_hours_old=False),
        CallableSourceAdapter("foundit", "Foundit", search_foundit, tier="B", uses_hours_old=False),
        CallableSourceAdapter("hirist", "Hirist", search_hirist, tier="B", uses_hours_old=False),
        CallableSourceAdapter(
            "wellfound",
            "Wellfound",
            search_wellfound,
            tier="B",
            uses_hours_old=False,
            query_filter=lambda q: q in WELLFOUND_QUERIES,
        ),
        AsyncClientSourceAdapter("ycombinator", "Y Combinator Jobs", search_yc_jobs),
        AsyncClientSourceAdapter("greenhouse", "Greenhouse Boards", search_greenhouse_boards),
        AsyncClientSourceAdapter("lever", "Lever Boards", search_lever_boards),
        AsyncClientSourceAdapter("career_pages", "Career Pages", search_career_pages, tier="B"),
    ]
    return [adapter for adapter in registry if adapter.source_id in enabled]


def get_adapter(source_id: str) -> JobSourceAdapter | None:
    for adapter in build_adapters():
        if adapter.source_id == source_id:
            return adapter
    return None


def get_all_source_health(enabled_ids: list[str] | None = None) -> list[dict[str, Any]]:
    return [adapter.health().to_dict() for adapter in build_adapters(enabled_ids)]
