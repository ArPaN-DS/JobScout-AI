from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone

from .discovery import archive_stale_leads, estimate_llm_cost_usd, queue_stats, resolve_discovery_config
from .job_sources import ImportedJob, import_job_lead
from .models import CandidateProfile, JobLead
from .profile_store import save_master_profile, update_candidate_preferences
from .schemas import MasterProfile
from .sources.base import CallableSourceAdapter
from .sources.registry import build_adapters, get_all_source_health
from .tests import PROFILE_DATA, _prepare_ready_candidate


class DiscoveryConfigTests(TestCase):
    def test_resolve_discovery_config_uses_preferences(self):
        save_master_profile(MasterProfile.model_validate(PROFILE_DATA))
        candidate = _prepare_ready_candidate()
        update_candidate_preferences(
            candidate,
            {
                "job_freshness_hours": 48,
                "discovery_sources": ["jobspy", "remoteok"],
                "target_roles": ["ML Engineer"],
                "target_locations": ["Remote"],
            },
        )
        config = resolve_discovery_config(candidate)
        self.assertEqual(config["hours_old"], 48)
        self.assertEqual(config["enabled_sources"], ["jobspy", "remoteok"])
        self.assertTrue(config["queries"])


class ArchiveStaleTests(TestCase):
    def test_archive_stale_marks_old_new_leads_dismissed(self):
        lead = JobLead.objects.create(
            title="Stale",
            company="Co",
            description="Python role with enough text for testing archive behavior in pipeline.",
            fingerprint=JobLead.make_fingerprint(title="Stale", company="Co"),
            discovered_at=timezone.now() - timedelta(hours=48),
        )
        count = archive_stale_leads(hours_old=24)
        self.assertGreaterEqual(count, 1)
        lead.refresh_from_db()
        self.assertEqual(lead.status, JobLead.Status.DISMISSED)


class AdapterTests(TestCase):
    def test_callable_adapter_imports_jobs(self):
        adapter = CallableSourceAdapter(
            "test_source",
            "Test",
            lambda query, hours_old: [
                {
                    "title": "Engineer",
                    "company": "TestCo",
                    "location": "Remote",
                    "description": "Python Django",
                    "apply_url": "https://example.com/jobs/1",
                    "source": "test_source",
                }
            ],
            query_agnostic=True,
        )
        result = adapter.run(["all"], 24, import_job_lead)
        self.assertEqual(result.imported_count, 1)
        self.assertTrue(JobLead.objects.filter(source_type="scraped").exists())

    @override_settings(DISCOVERY_SOURCES=["jobspy"])
    def test_build_adapters_respects_settings(self):
        adapters = build_adapters()
        self.assertEqual(len(adapters), 1)
        self.assertEqual(adapters[0].source_id, "jobspy")

    def test_source_health_returns_serializable_dict(self):
        health = get_all_source_health(["jobspy"])
        self.assertEqual(health[0]["source_id"], "jobspy")
        self.assertIn("available", health[0])


class CostEstimateTests(TestCase):
    def test_estimate_llm_cost_scales_with_count(self):
        est = estimate_llm_cost_usd(match_count=10, kit_count=3)
        self.assertGreater(est["total_usd"], 0)
        self.assertEqual(est["match_count"], 10)
