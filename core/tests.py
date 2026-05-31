import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .evidence_scanner import iter_candidate_files, scan_local_folder
from .ai_service import CareerAgentAI, KitValidationError, extract_json_object
from .match_policy import MatchThresholds, classify_application_status, thresholds_for_candidate
from .profile_readiness import assess_profile_readiness, assert_ready_for_kit_generation
from .profile_store import confirm_claims, update_candidate_preferences
from .prompts.registry import PROMPT_VERSION
from .job_sources import ImportedJob, import_job_lead
from .llm import (
    LLMExhaustedError,
    LLMProviderError,
    LLMRequest,
    LLMRouter,
    LLMTask,
    OllamaAdapter,
    provider_statuses,
)
from .models import Application, CandidateLink, CandidateProfile, EvidenceSource, ProfileClaim
from .profile_store import load_master_profile, save_master_profile
from .schemas import ApplicationKit, MasterProfile, MatchResult, validate_grounded_kit


PROFILE_DATA = {
    "name": "Alex Morgan",
    "email": "alex.morgan@example.test",
    "phone": "+15550101010",
    "skills": ["Python", "Django", "Machine Learning"],
    "experience": [
        {
            "company": "Example Labs",
            "role": "Software Engineer",
            "duration": "2024 - Present",
            "highlights": ["Built Django applications backed by LLM workflows."],
            "evidence": ["Resume lists Django applications backed by LLM workflows."],
        }
    ],
    "domains": ["Software Engineering"],
}


class AIParsingTests(TestCase):
    def test_extract_json_object_handles_wrapped_json(self):
        parsed = extract_json_object('notes before {"match_score": 91, "summary": "Good"} notes after')
        self.assertEqual(parsed["match_score"], 91)

    def test_grounding_rejects_skills_not_in_profile(self):
        profile = MasterProfile.model_validate(PROFILE_DATA)
        kit = ApplicationKit.model_validate(
            {
                "tailored_resume": {
                    "name": "Alex Morgan",
                    "skills": ["Python", "Kubernetes"],
                    "experience": PROFILE_DATA["experience"],
                },
                "cover_letter": "I am interested in this role.",
            }
        )

        with self.assertRaises(ValueError):
            validate_grounded_kit(profile, kit)


class FakeAdapter:
    configured = True
    enabled = True

    def __init__(self, name, responses):
        self.name = name
        self.model = f"{name}-model"
        self.responses = list(responses)

    def generate(self, request):
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response, {"total_tokens": 10}


class LLMRouterTests(TestCase):
    def tearDown(self):
        LLMRouter.reset_cooldowns()

    def test_router_falls_back_after_rate_limit(self):
        router = LLMRouter(
            [
                FakeAdapter(
                    "first",
                    [
                        LLMProviderError(
                            "quota reached",
                            rate_limited=True,
                            retry_after_seconds=3,
                        )
                    ],
                ),
                FakeAdapter("second", ['{"ok": true}']),
            ]
        )

        result = router.generate(LLMRequest(task=LLMTask.JOB_MATCH, prompt="Return JSON"))

        self.assertEqual(result.provider, "second")
        self.assertEqual(result.attempts[0].status, "failed")
        self.assertEqual(result.attempts[1].status, "success")
        self.assertGreaterEqual(LLMRouter.cooldown_remaining("first", "first-model"), 1)

    def test_router_reports_all_providers_exhausted(self):
        router = LLMRouter(
            [
                FakeAdapter("first", [LLMProviderError("down")]),
                FakeAdapter("second", [LLMProviderError("also down")]),
            ]
        )

        with self.assertRaises(LLMExhaustedError) as context:
            router.generate(LLMRequest(task=LLMTask.JOB_MATCH, prompt="Return JSON"))

        self.assertIn("Turn on Ollama", str(context.exception))
        self.assertEqual(len(context.exception.attempts), 2)

    def test_bad_json_blocks_provider_and_uses_next_adapter(self):
        from .ai_service import CareerAgentAI

        router = LLMRouter(
            [
                FakeAdapter("noisy", ["not json"]),
                FakeAdapter(
                    "clean",
                    [
                        json.dumps(
                            {
                                "match_score": 77,
                                "summary": "Good match.",
                                "matching_skills": ["Python"],
                                "missing_skills": [],
                                "confidence": 80,
                                "risk_flags": [],
                            }
                        )
                    ],
                ),
            ]
        )
        ai = CareerAgentAI(router=router, max_attempts=2)

        result = ai.match_job_to_profile(PROFILE_DATA, "Python role with Django and AI workflow ownership.")

        self.assertEqual(result.match_score, 77)
        self.assertEqual(ai.last_metadata()["provider"], "clean")

    @override_settings(LLM_PROVIDER_ORDER=["openai", "ollama"], OLLAMA_ENABLED=False)
    def test_provider_statuses_keep_missing_keys_disabled(self):
        with patch.dict("os.environ", {}, clear=True):
            statuses = provider_statuses()

        self.assertEqual([status.name for status in statuses], ["openai", "ollama"])
        self.assertFalse(any(status.enabled for status in statuses))

    @patch("core.llm.urllib.request.urlopen")
    def test_ollama_health_check_reads_local_models(self, urlopen):
        response = MagicMock()
        response.read.return_value = b'{"models": [{"name": "llama3.1"}]}'
        urlopen.return_value.__enter__.return_value = response

        health = OllamaAdapter("llama3.1", enabled=True).health()

        self.assertTrue(health["ok"])
        self.assertEqual(health["models"], ["llama3.1"])


class JobSourceTests(TestCase):
    def test_import_job_lead_dedupes_by_url(self):
        job = ImportedJob(
            title="AI Engineer",
            company="Example Labs",
            location="Remote",
            job_url="https://example.com/jobs/ai",
            description="Python and Django AI engineering role.",
        )

        first, first_created = import_job_lead(job)
        second, second_created = import_job_lead(job)

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.id, second.id)


class CandidateProfileTests(TestCase):
    def test_save_master_profile_creates_candidate_workspace(self):
        profile = MasterProfile.model_validate(
            {
                **PROFILE_DATA,
                "linkedin_url": "https://linkedin.com/in/sample-candidate",
                "github_url": "https://github.com/sample-candidate",
                "job_preferences": {
                    "target_roles": ["Backend Developer"],
                    "locations": ["Remote"],
                    "must_have_skills": ["Python"],
                },
            }
        )

        candidate = save_master_profile(
            profile,
            manual_data={
                "full_name": "Alex Morgan",
                "portfolio_url": "https://portfolio.example.test",
            },
            document_info={
                "original_filename": "resume.pdf",
                "content_type": "application/pdf",
                "size_bytes": 128,
                "extracted_text_sample": "Sample resume text",
            },
        )

        loaded = load_master_profile()

        self.assertEqual(candidate.full_name, "Alex Morgan")
        self.assertEqual(loaded.name, "Alex Morgan")
        self.assertIn("Python", loaded.skills)
        self.assertTrue(CandidateLink.objects.filter(link_type=CandidateLink.LinkType.GITHUB).exists())
        self.assertTrue(ProfileClaim.objects.filter(category=ProfileClaim.Category.SKILL).exists())
        self.assertEqual(candidate.documents.get().original_filename, "resume.pdf")

    def test_candidate_preferences_generate_search_queries(self):
        candidate = save_master_profile(MasterProfile.model_validate(PROFILE_DATA))
        preferences = candidate.preferences
        preferences.target_roles = ["Data Engineer", "Backend Developer"]
        preferences.target_locations = ["Remote", "Berlin"]
        queries = preferences.generate_queries()

        self.assertIn("Data Engineer Remote", queries)
        self.assertIn("Backend Developer Berlin", queries)

    def test_local_folder_scanner_excludes_secrets_and_private_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Sample App\nBuilt with Django and Python.", encoding="utf-8")
            (root / ".env").write_text("SECRET=hidden", encoding="utf-8")
            (root / "db.sqlite3").write_text("private", encoding="utf-8")
            (root / "app.py").write_text("import django\n", encoding="utf-8")

            candidate = save_master_profile(MasterProfile.model_validate(PROFILE_DATA))
            files = [path.name for path in iter_candidate_files(root)]
            source = scan_local_folder(candidate, root)

        self.assertIn("README.md", files)
        self.assertIn("app.py", files)
        self.assertNotIn(".env", files)
        self.assertNotIn("db.sqlite3", files)
        self.assertEqual(source.source_type, EvidenceSource.SourceType.LOCAL_FOLDER)
        self.assertTrue(candidate.claims.filter(value="Django").exists())


class ChannelWebhookTests(TestCase):
    @override_settings(TELEGRAM_ALLOWED_CHAT_IDS=["123"])
    def test_telegram_webhook_accepts_allowed_chat(self):
        response = self.client.post(
            "/integrations/telegram/webhook/",
            data=json.dumps({"message": {"chat": {"id": 123}, "text": "/status"}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["method"], "sendMessage")

    @override_settings(DISCORD_ALLOWED_IDS=["42"])
    def test_discord_interaction_rejects_unlisted_user(self):
        response = self.client.post(
            "/integrations/discord/interactions/",
            data=json.dumps(
                {
                    "type": 2,
                    "data": {"name": "status", "options": []},
                    "user": {"id": "99"},
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("not allowed", response.json()["data"]["content"])


def _prepare_ready_candidate() -> CandidateProfile:
    candidate = CandidateProfile.objects.get(is_active=True)
    confirm_claims(candidate)
    if not candidate.documents.exists():
        from .models import CandidateDocument

        CandidateDocument.objects.create(
            profile=candidate,
            original_filename="resume.pdf",
            content_type="application/pdf",
            status=CandidateDocument.Status.EXTRACTED,
        )
    update_candidate_preferences(
        candidate,
        {
            "target_roles": ["Backend Developer"],
            "target_locations": ["Remote"],
            "min_match_score": 60,
            "min_match_confidence": 50,
        },
    )
    candidate.email = candidate.email or PROFILE_DATA["email"]
    candidate.status = CandidateProfile.Status.READY
    candidate.save(update_fields=["email", "status", "updated_at"])
    return candidate


class MatchPolicyTests(TestCase):
    def test_strong_match_requires_score_and_confidence(self):
        thresholds = MatchThresholds(min_match_score=70, min_match_confidence=60)
        self.assertTrue(thresholds.is_strong_match(80, 65))
        self.assertFalse(thresholds.is_strong_match(69, 65))
        self.assertFalse(thresholds.is_strong_match(80, 59))

    def test_application_status_reflects_thresholds(self):
        thresholds = MatchThresholds(min_match_score=70, min_match_confidence=50)
        self.assertEqual(
            classify_application_status(69, 80, thresholds),
            Application.Status.LOW_MATCH,
        )
        self.assertEqual(
            classify_application_status(75, 80, thresholds),
            Application.Status.MATCHED,
        )


class ProfileReadinessTests(TestCase):
    def test_missing_candidate_is_not_ready(self):
        readiness = assess_profile_readiness(None)
        self.assertFalse(readiness.ready)
        self.assertIn("Create a candidate profile", readiness.blockers[0])

    def test_ready_candidate_passes_gate(self):
        save_master_profile(MasterProfile.model_validate(PROFILE_DATA))
        candidate = _prepare_ready_candidate()
        readiness = assess_profile_readiness(candidate)
        self.assertTrue(readiness.ready)
        assert_ready_for_kit_generation(candidate)


class KitGenerationTests(TestCase):
    def tearDown(self):
        LLMRouter.reset_cooldowns()

    @override_settings(KIT_CRITIC_ENABLED=True)
    def test_critic_rejection_blocks_kit(self):
        router = LLMRouter(
            [
                FakeAdapter(
                    "kit",
                    [
                        json.dumps(
                            {
                                "tailored_resume": {
                                    "name": "Alex Morgan",
                                    "skills": ["Python", "Django", "Machine Learning"],
                                    "experience": PROFILE_DATA["experience"],
                                },
                                "cover_letter": "I am excited to apply for this role.",
                            }
                        )
                    ],
                ),
                FakeAdapter(
                    "critic",
                    [
                        json.dumps(
                            {
                                "approved": False,
                                "issues": ["Invented Kubernetes experience"],
                                "unsupported_claims": ["Kubernetes"],
                            }
                        )
                    ],
                ),
            ]
        )
        ai = CareerAgentAI(router=router, critic_enabled=True, max_attempts=1)

        with self.assertRaises(KitValidationError):
            ai.generate_application_kit(PROFILE_DATA, "Python Django role with ML workflows.")

    @override_settings(KIT_CRITIC_ENABLED=True)
    def test_critic_approval_returns_kit_with_metadata(self):
        router = LLMRouter(
            [
                FakeAdapter(
                    "kit",
                    [
                        json.dumps(
                            {
                                "tailored_resume": {
                                    "name": "Alex Morgan",
                                    "skills": ["Python", "Django", "Machine Learning"],
                                    "experience": PROFILE_DATA["experience"],
                                },
                                "cover_letter": "I am excited to apply for this role.",
                            }
                        )
                    ],
                ),
                FakeAdapter(
                    "critic",
                    [json.dumps({"approved": True, "issues": [], "unsupported_claims": []})],
                ),
            ]
        )
        ai = CareerAgentAI(router=router, critic_enabled=True, max_attempts=1)
        kit = ai.generate_application_kit(PROFILE_DATA, "Python Django role with ML workflows.")
        metadata = ai.last_metadata()

        self.assertEqual(kit.cover_letter, "I am excited to apply for this role.")
        self.assertTrue(metadata["critic"]["approved"])
        self.assertEqual(metadata["prompt_version"], PROMPT_VERSION)


class WorkflowViewTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.override = override_settings(
            BASE_DIR=self.base_dir,
            UPLOAD_TEMP_DIR=self.base_dir / "tmp_uploads",
            KIT_CRITIC_ENABLED=False,
        )
        self.override.enable()
        save_master_profile(MasterProfile.model_validate(PROFILE_DATA))
        _prepare_ready_candidate()

    def tearDown(self):
        self.override.disable()
        self.tmp.cleanup()

    @patch("core.views.CareerAgentAI")
    def test_profile_upload_saves_validated_profile(self, ai_class):
        ai_class.return_value.extract_profile_from_document.return_value = MasterProfile.model_validate(PROFILE_DATA)
        resume = SimpleUploadedFile(
            "resume.pdf",
            b"%PDF-1.4\nplaceholder",
            content_type="application/pdf",
        )

        response = self.client.post(
            "/",
            data={
                "resume": resume,
                "linkedin_url": "https://linkedin.com/in/example",
                "github_url": "https://github.com/example",
                "full_name": "Alex Morgan",
            },
        )

        self.assertEqual(response.status_code, 200)
        candidate = CandidateProfile.objects.get(is_active=True)
        self.assertEqual(candidate.full_name, "Alex Morgan")
        self.assertEqual(candidate.linkedin_url, "https://linkedin.com/in/example")
        self.assertTrue(candidate.documents.filter(original_filename="resume.pdf").exists())

    @patch("core.views.CareerAgentAI")
    def test_job_match_creates_application_with_status_and_snapshot(self, ai_class):
        ai_class.return_value.match_job_to_profile.return_value = MatchResult.model_validate(
            {
                "match_score": 88,
                "summary": "Strong Django and AI alignment.",
                "matching_skills": ["Python", "Django"],
                "missing_skills": ["AWS"],
                "confidence": 82,
                "risk_flags": ["Cloud depth is unclear."],
            }
        )

        response = self.client.post(
            "/jobs/",
            data={
                "job_url": "https://example.com/job",
                "job_description": "We need a Python and Django engineer for AI workflow development. "
                "The role includes API design, LLM integration, testing, deployment, and collaboration.",
            },
        )

        self.assertEqual(response.status_code, 200)
        app = Application.objects.get()
        self.assertEqual(app.status, Application.Status.MATCHED)
        self.assertEqual(app.match_score, 88)
        self.assertEqual(app.profile_snapshot["name"], PROFILE_DATA["name"])
        self.assertEqual(app.ai_metadata["match_confidence"], 82)

    @patch("core.views.CareerAgentAI")
    def test_low_match_score_sets_low_match_status(self, ai_class):
        ai_class.return_value.match_job_to_profile.return_value = MatchResult.model_validate(
            {
                "match_score": 55,
                "summary": "Partial overlap only.",
                "matching_skills": ["Python"],
                "missing_skills": ["Kubernetes"],
                "confidence": 80,
                "risk_flags": [],
            }
        )

        response = self.client.post(
            "/jobs/",
            data={
                "job_url": "https://example.com/job-low",
                "job_description": "We need a Python and Django engineer for AI workflow development. "
                "The role includes API design, LLM integration, testing, deployment, and collaboration.",
            },
        )

        self.assertEqual(response.status_code, 200)
        app = Application.objects.get(job_url="https://example.com/job-low")
        self.assertEqual(app.status, Application.Status.LOW_MATCH)

    @patch("core.views.CareerAgentAI")
    def test_generate_kit_blocked_when_profile_not_ready(self, ai_class):
        app = Application.objects.create(
            job_description="Python Django AI role with LLM workflow ownership and careful product writing.",
            profile_snapshot=PROFILE_DATA,
            status=Application.Status.MATCHED,
            match_score=88,
        )
        candidate = CandidateProfile.objects.get(is_active=True)
        candidate.status = CandidateProfile.Status.REVIEW_REQUIRED
        candidate.save(update_fields=["status", "updated_at"])

        response = self.client.post("/jobs/generate/", data={"app_id": app.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn("not ready", response.json()["error"].lower())
        ai_class.assert_not_called()

    @patch("core.views.CareerAgentAI")
    def test_generate_kit_updates_application_status(self, ai_class):
        app = Application.objects.create(
            job_description="Python Django AI role with LLM workflow ownership and careful product writing.",
            profile_snapshot=PROFILE_DATA,
            status=Application.Status.MATCHED,
            match_score=88,
        )
        ai_instance = ai_class.return_value
        ai_instance.generate_application_kit.return_value = ApplicationKit.model_validate(
            {
                "tailored_resume": {
                    "name": "Alex Morgan",
                    "skills": ["Python", "Django", "Machine Learning"],
                    "experience": PROFILE_DATA["experience"],
                },
                "cover_letter": "I am excited to apply for this role.",
            }
        )
        ai_instance.last_metadata.return_value = {
            "prompt_version": PROMPT_VERSION,
            "critic": {"approved": True, "skipped": False},
        }

        response = self.client.post("/jobs/generate/", data={"app_id": app.id})

        self.assertEqual(response.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, Application.Status.KIT_GENERATED)
        self.assertIn("cover_letter", response.json()["data"])
        self.assertEqual(response.json()["metadata"]["prompt_version"], PROMPT_VERSION)
        self.assertEqual(app.ai_metadata.get("prompt_version"), PROMPT_VERSION)


class JobLeadThresholdTests(TestCase):
    def test_record_score_uses_preference_thresholds(self):
        save_master_profile(MasterProfile.model_validate(PROFILE_DATA))
        candidate = _prepare_ready_candidate()
        update_candidate_preferences(candidate, {"min_match_score": 80, "min_match_confidence": 50})

        from .models import JobLead

        lead = JobLead.objects.create(
            title="Engineer",
            company="Example",
            description="Python role",
            fingerprint=JobLead.make_fingerprint(title="Engineer", company="Example"),
        )
        thresholds = thresholds_for_candidate(candidate)
        lead.record_score(
            {"match_score": 75, "summary": "Good", "confidence": 90},
            thresholds=thresholds,
        )
        self.assertEqual(lead.status, JobLead.Status.LOW_MATCH)
