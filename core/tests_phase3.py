import json
from pathlib import Path
from unittest.mock import patch

from django.test import LiveServerTestCase, TestCase, override_settings

from .ai_service import CareerAgentAI
from .errors import format_user_error
from .job_runner import complete_job, make_idempotency_key, run_tracked, start_job
from .llm import LLMExhaustedError, LLMAttempt, LLMRouter
from .metrics import funnel_stats
from .models import Application, JobLead, LLMUsageEvent, PipelineJob
from .cost_tracking import budget_status, record_llm_usage
from .schemas import MatchResult
from .tests import PROFILE_DATA, FakeAdapter, _prepare_ready_candidate
from .profile_store import save_master_profile
from .schemas import MasterProfile


FIXTURES = Path(__file__).parent / "fixtures"


@override_settings(DAILY_LLM_BUDGET_USD=50.0, KIT_CRITIC_ENABLED=False)
class ErrorFormatTests(TestCase):
    def test_llm_exhausted_includes_actions(self):
        exc = LLMExhaustedError([LLMAttempt("x", "m", "failed")])
        payload = format_user_error(exc)
        self.assertTrue(payload["retryable"])
        self.assertTrue(payload["compact_retry"])
        self.assertGreaterEqual(len(payload["actions"]), 2)

    @override_settings(DEBUG=False)
    def test_generic_error_hides_details_in_production(self):
        payload = format_user_error(RuntimeError("secret internal trace"))
        self.assertNotIn("secret", payload["message"].lower())


@override_settings(DAILY_LLM_BUDGET_USD=50.0)
class PipelineJobTests(TestCase):
    def test_run_tracked_completes_with_result(self):
        result = run_tracked(
            "score",
            make_idempotency_key("score", limit=1),
            lambda job: {"ok": True},
            progress_total=1,
        )
        self.assertFalse(result["deduplicated"])
        job = PipelineJob.objects.get(id=result["job_id"])
        self.assertEqual(job.status, PipelineJob.Status.COMPLETED)

    def test_duplicate_idempotency_skips_while_running(self):
        key = make_idempotency_key("score", limit=99)
        job, should_run = start_job("score", key, progress_total=1)
        self.assertTrue(should_run)
        job2, should_run2 = start_job("score", key, progress_total=1)
        self.assertFalse(should_run2)
        self.assertEqual(job.id, job2.id)
        complete_job(job, {"n": 1})


@override_settings(DAILY_LLM_BUDGET_USD=50.0)
class GoldenSnapshotTests(TestCase):
    def tearDown(self):
        LLMRouter.reset_cooldowns()

    def test_match_result_matches_golden_fixture(self):
        golden = json.loads((FIXTURES / "golden_match.json").read_text(encoding="utf-8"))
        router = LLMRouter([FakeAdapter("clean", [json.dumps(golden)])])
        ai = CareerAgentAI(router=router, max_attempts=1)
        result = ai.match_job_to_profile(PROFILE_DATA, "Python Django backend role with APIs and tests.")
        for key in ("match_score", "confidence", "summary"):
            self.assertEqual(getattr(result, key), golden[key])
        self.assertEqual(result.matching_skills, golden["matching_skills"])


@override_settings(DAILY_LLM_BUDGET_USD=50.0)
class MetricsAndBudgetTests(TestCase):
    def test_record_llm_usage_and_budget(self):
        record_llm_usage(
            {"provider": "test", "model": "m", "token_usage": {"input_tokens": 1000, "output_tokens": 200}},
            task_type="job_match",
        )
        status = budget_status()
        self.assertGreater(status["spent_usd"], 0)
        self.assertIn("remaining_usd", status)

    def test_funnel_stats_returns_conversion(self):
        JobLead.objects.create(
            title="Role",
            company="Co",
            description="Python Django backend engineer role with testing and deployment.",
            fingerprint=JobLead.make_fingerprint(title="Role", company="Co"),
            match_score=80,
            status=JobLead.Status.MATCHED,
        )
        stats = funnel_stats(days=30)
        self.assertIn("conversion", stats)
        self.assertGreaterEqual(stats["conversion"]["ingested"], 1)


@override_settings(DAILY_LLM_BUDGET_USD=50.0, KIT_CRITIC_ENABLED=False)
class WorkflowE2ETests(LiveServerTestCase):
    def setUp(self):
        save_master_profile(MasterProfile.model_validate(PROFILE_DATA))
        _prepare_ready_candidate()
        
        # Authenticate the client
        from django.contrib.auth.models import User
        self.test_user = User.objects.create_user(username="testuser", password="password123")
        self.client.login(username="testuser", password="password123")

    @patch("core.views.CareerAgentAI")
    def test_live_server_match_and_generate_kit(self, ai_class):
        ai_class.return_value.match_job_to_profile.return_value = MatchResult.model_validate(
            json.loads((FIXTURES / "golden_match.json").read_text(encoding="utf-8"))
        )
        from .schemas import ApplicationKit

        ai_class.return_value.generate_application_kit.return_value = ApplicationKit.model_validate(
            {
                "tailored_resume": {
                    "name": "Alex Morgan",
                    "skills": ["Python", "Django", "Machine Learning"],
                    "experience": PROFILE_DATA["experience"],
                },
                "cover_letter": "I am excited to apply.",
            }
        )
        ai_class.return_value.last_metadata.return_value = {"prompt_version": "1.0.0", "provider": "test"}

        job_description = (
            "We are hiring a backend developer to build Python services, Django APIs, "
            "data workflows, tests, and production integrations for our platform team."
        )
        response = self.client.post(
            "/jobs/",
            data={"job_url": "https://example.com/jobs/e2e", "job_description": job_description},
        )
        self.assertEqual(response.status_code, 200)
        app_id = response.json()["app_id"]

        gen = self.client.post("/jobs/generate/", data={"app_id": app_id})
        self.assertEqual(gen.status_code, 200)
        self.assertIn("cover_letter", gen.json()["data"])

    def test_discovery_status_endpoint(self):
        response = self.client.get("/jobs/discovery-status/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("budget", payload)
        self.assertIn("queue", payload)
