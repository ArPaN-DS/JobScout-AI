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
    build_provider_chain,
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

    @patch("core.ai_service.pdfplumber.open")
    def test_extract_pdf_text(self, mock_open):
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Extracted PDF Text"
        mock_pdf.pages = [mock_page]
        mock_open.return_value.__enter__.return_value = mock_pdf

        from core.ai_service import extract_pdf_text
        text = extract_pdf_text("dummy.pdf")
        self.assertEqual(text, "Extracted PDF Text")

        # Test empty PDF raise ValueError
        mock_page.extract_text.return_value = ""
        with self.assertRaises(ValueError):
            extract_pdf_text("dummy.pdf")

    @patch("docx.Document")
    def test_extract_docx_text(self, mock_document_class):
        mock_doc = MagicMock()
        mock_para = MagicMock()
        mock_para.text = "Extracted DOCX Text"
        mock_doc.paragraphs = [mock_para]
        mock_document_class.return_value = mock_doc

        from core.ai_service import extract_docx_text
        text = extract_docx_text("dummy.docx")
        self.assertEqual(text, "Extracted DOCX Text")

        # Test empty DOCX raise ValueError
        mock_para.text = ""
        with self.assertRaises(ValueError):
            extract_docx_text("dummy.docx")

    @patch("core.ai_service.extract_pdf_text")
    @patch("core.ai_service.extract_docx_text")
    def test_extract_document_text(self, mock_extract_docx, mock_extract_pdf):
        mock_extract_pdf.return_value = "pdf text"
        mock_extract_docx.return_value = "docx text"

        from core.ai_service import extract_document_text
        self.assertEqual(extract_document_text("file.pdf"), "pdf text")
        self.assertEqual(extract_document_text("file.docx"), "docx text")
        with self.assertRaises(ValueError):
            extract_document_text("file.txt")



class FakeAdapter:
    configured = True
    enabled = True

    def __init__(self, name, responses):
        self.name = name
        self.model = f"{name}-model"
        self.responses = list(responses)

    def generate(self, request):
        if self.name == "kit" and request.task != LLMTask.APPLICATION_KIT:
            raise LLMProviderError("FakeAdapter kit only handles APPLICATION_KIT", retryable=False)
        if self.name == "critic" and request.task != LLMTask.CRITIC_VALIDATE:
            raise LLMProviderError("FakeAdapter critic only handles CRITIC_VALIDATE", retryable=False)

        if not self.responses:
            raise LLMProviderError("No more mock responses in FakeAdapter", retryable=False)
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
                    ] * 3,
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
                    ] * 3,
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
        
        # Authenticate the client
        from django.contrib.auth.models import User
        self.test_user = User.objects.create_user(username="testuser", password="password123")
        self.client.login(username="testuser", password="password123")

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


from .errors import format_user_error, exception_http_status
from .ai_service import AIResponseError
from .schemas import (
    normalize_claim,
    clean_text,
    clean_list,
    ExperienceItem,
    JobPreferences,
    MasterProfile,
    MatchResult,
    TailoredExperienceItem,
    TailoredResume,
    ApplicationKit,
    KitCriticVerdict,
    BaseJobExtraction,
    validate_grounded_kit,
)

class ErrorsTests(TestCase):
    def test_format_user_error_value_error(self):
        exc = ValueError("Invalid input value")
        payload = format_user_error(exc)
        self.assertEqual(payload["code"], "ValueError")
        self.assertEqual(payload["message"], "Invalid input value")
        self.assertIn("Fix the input and try again.", payload["actions"])
        self.assertFalse(payload["retryable"])

    def test_format_user_error_llm_exhausted_error(self):
        exc = LLMExhaustedError([])
        payload = format_user_error(exc)
        self.assertEqual(payload["code"], "LLMExhaustedError")
        self.assertTrue(payload["retryable"])
        self.assertTrue(payload["compact_retry"])
        self.assertIn("Turn on Ollama with a local model.", payload["actions"])

    def test_format_user_error_kit_validation_error(self):
        exc = KitValidationError("Grounding check failed")
        payload = format_user_error(exc)
        self.assertEqual(payload["code"], "KitValidationError")
        self.assertTrue(payload["retryable"])
        self.assertIn("Review your profile claims and confirm skills.", payload["actions"])

    def test_format_user_error_ai_response_error(self):
        exc = AIResponseError("API Key invalid")
        payload = format_user_error(exc)
        self.assertEqual(payload["code"], "AIResponseError")
        self.assertTrue(payload["retryable"])
        self.assertIn("Check provider API keys in Provider Settings.", payload["actions"])

    @override_settings(DEBUG=False)
    def test_format_user_error_generic_production(self):
        exc = RuntimeError("Internal db leak")
        payload = format_user_error(exc)
        self.assertNotIn("Internal db leak", payload["message"])
        self.assertIn("An unexpected error occurred", payload["message"])
        self.assertTrue(payload["retryable"])

    @override_settings(DEBUG=True)
    def test_format_user_error_generic_debug(self):
        exc = RuntimeError("Internal db leak")
        payload = format_user_error(exc)
        self.assertIn("RuntimeError: Internal db leak", payload["message"])

    def test_exception_http_status(self):
        self.assertEqual(exception_http_status(ValueError("")), 400)
        self.assertEqual(exception_http_status(FileNotFoundError("")), 400)
        self.assertEqual(exception_http_status(AIResponseError("")), 502)
        self.assertEqual(exception_http_status(LLMExhaustedError("")), 502)
        self.assertEqual(exception_http_status(KitValidationError("")), 502)
        self.assertEqual(exception_http_status(RuntimeError("")), 500)


class SchemasTests(TestCase):
    def test_clean_list_edge_cases(self):
        self.assertEqual(clean_list(None), [])
        self.assertEqual(clean_list("SingleItem"), ["SingleItem"])

    def test_master_profile_clean_experience(self):
        profile_dict = {
            "name": "Alex",
            "experience": None
        }
        profile = MasterProfile.model_validate(profile_dict)
        self.assertEqual(profile.experience, [])

        profile_dict_2 = {
            "name": "Alex",
            "experience": {
                "company": "ACME",
                "role": "Eng",
                "duration": "1 yr",
            }
        }
        profile_2 = MasterProfile.model_validate(profile_dict_2)
        self.assertEqual(len(profile_2.experience), 1)
        self.assertEqual(profile_2.experience[0].company, "ACME")

    def test_tailored_resume_clean_experience(self):
        resume_dict = {
            "name": "Alex",
            "skills": [],
            "experience": None
        }
        resume = TailoredResume.model_validate(resume_dict)
        self.assertEqual(resume.experience, [])

        resume_dict_2 = {
            "name": "Alex",
            "skills": [],
            "experience": {
                "company": "ACME",
                "role": "Eng",
                "duration": "1 yr",
            }
        }
        resume_2 = TailoredResume.model_validate(resume_dict_2)
        self.assertEqual(len(resume_2.experience), 1)
        self.assertEqual(resume_2.experience[0].company, "ACME")

    def test_application_kit_clean_notes(self):
        kit_dict = {
            "tailored_resume": {
                "name": "Alex",
                "skills": [],
                "experience": []
            },
            "cover_letter": "Letter",
            "interview_prep_notes": "Note String"
        }
        kit = ApplicationKit.model_validate(kit_dict)
        self.assertEqual(kit.interview_prep_notes, ["Note String"])

    def test_base_job_extraction_clean_string(self):
        job = BaseJobExtraction.model_validate({
            "title": 12345,
            "company": "ACME",
        })
        self.assertEqual(job.title, "12345")

    def test_validate_grounded_kit_unsupported_experience(self):
        profile = MasterProfile.model_validate(PROFILE_DATA)
        kit = ApplicationKit.model_validate({
            "tailored_resume": {
                "name": "Alex Morgan",
                "skills": ["Python"],
                "experience": [
                    {
                        "company": "Fake Corp",
                        "role": "CEO",
                        "duration": "10 yrs"
                    }
                ]
            },
            "cover_letter": "I am interested."
        })
        with self.assertRaises(ValueError) as context:
            validate_grounded_kit(profile, kit)
        self.assertIn("unsupported experience entries", str(context.exception))


class SecurityHardeningTests(TestCase):
    def test_unauthenticated_redirects_to_login(self):
        # Protected views should redirect
        response = self.client.get("/jobs/queue/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

        # Protected view API requests should return 401
        response = self.client.post(
            "/jobs/generate/",
            data={"app_id": 1},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()["success"])
        self.assertEqual(response.json()["error"], "Authentication required.")

    def test_authenticated_access_allowed(self):
        from django.contrib.auth.models import User
        User.objects.create_user(username="testuser", password="password123")
        self.client.login(username="testuser", password="password123")
        
        # Now access should be allowed and not redirect to accounts/login
        response = self.client.get("/jobs/queue/")
        if response.status_code == 302:
            self.assertNotIn("/accounts/login/", response.url)
        else:
            self.assertEqual(response.status_code, 200)

    def test_encryption_roundtrip(self):
        from .encryption import encrypt_value, decrypt_value
        secret = "super-secret-api-key-123"
        encrypted = encrypt_value(secret)
        self.assertNotEqual(secret, encrypted)
        
        decrypted = decrypt_value(encrypted)
        self.assertEqual(secret, decrypted)

    def test_secure_credential_model(self):
        from .models import SecureCredential
        # Set credential
        SecureCredential.set_val("TEST_API_KEY", "my-secret-key")
        
        # Verify it is encrypted in DB
        db_record = SecureCredential.objects.get(name="TEST_API_KEY")
        self.assertNotEqual(db_record.encrypted_value, "my-secret-key")
        
        # Verify get_val decrypts it correctly
        self.assertEqual(SecureCredential.get_val("TEST_API_KEY"), "my-secret-key")
        
        # Delete credential
        SecureCredential.set_val("TEST_API_KEY", "")
        self.assertFalse(SecureCredential.objects.filter(name="TEST_API_KEY").exists())


class RobustLLMRouterTests(TestCase):
    def tearDown(self):
        LLMRouter.reset_cooldowns()

    def test_auth_failure_blocks_whole_provider(self):
        adapter1 = FakeAdapter("first", [LLMProviderError("invalid key", auth_error=True, retryable=False)])
        adapter1.model = "first-model-1"
        adapter2 = FakeAdapter("first", ["not reached"])
        adapter2.model = "first-model-2"
        adapter3 = FakeAdapter("second", ['{"ok": true}'])
        adapter3.model = "second-model"

        router = LLMRouter(adapters=[adapter1, adapter2, adapter3])
        result = router.generate(LLMRequest(task=LLMTask.JOB_MATCH, prompt="test"))
        self.assertEqual(result.provider, "second")
        # Check that adapter2 was skipped
        self.assertEqual(result.attempts[0].status, "failed")
        self.assertEqual(result.attempts[1].status, "skipped")
        self.assertEqual(result.attempts[2].status, "success")

    @patch("core.llm.build_provider_chain")
    def test_schema_validation_failure_promotes_to_pro(self, mock_build_chain):
        from core.llm import GeminiAdapter
        gemini_adapter = GeminiAdapter(model="gemini-2.5-flash", api_key="mock-key")
        mock_build_chain.return_value = [gemini_adapter]

        models_used = []
        responses = [
            ("not-json", {}),
            ('{"match_score": 90, "summary": "Good", "matching_skills": [], "missing_skills": [], "confidence": 90, "risk_flags": []}', {})
        ]

        def dummy_generate(adapter_self, request):
            models_used.append(adapter_self.model)
            res = responses.pop(0)
            if isinstance(res, Exception):
                raise res
            return res

        with patch.object(GeminiAdapter, "generate", dummy_generate):
            ai = CareerAgentAI(flash_model="gemini-2.5-flash", pro_model="gemini-2.5-pro", max_attempts=2)
            result = ai.match_job_to_profile(PROFILE_DATA, "job description")

        self.assertEqual(result.match_score, 90)
        self.assertEqual(len(models_used), 2)
        self.assertEqual(models_used[0], "gemini-2.5-flash")
        self.assertEqual(models_used[1], "gemini-2.5-pro")

    @patch("core.llm.build_provider_chain")
    def test_context_limit_exceeded_triggers_compaction_and_retries(self, mock_build_chain):
        from core.llm import GeminiAdapter, LLMProviderError
        gemini_adapter = GeminiAdapter(model="gemini-2.5-flash", api_key="mock-key")
        mock_build_chain.return_value = [gemini_adapter]

        prompts_used = []
        responses = [
            LLMProviderError("context length exceeded", retryable=False),
            ('{"match_score": 95, "summary": "Good after compact", "matching_skills": [], "missing_skills": [], "confidence": 90, "risk_flags": []}', {})
        ]

        def dummy_generate(adapter_self, request):
            prompts_used.append(request.prompt)
            res = responses.pop(0)
            if isinstance(res, Exception):
                raise res
            return res

        with patch.object(GeminiAdapter, "generate", dummy_generate):
            ai = CareerAgentAI(flash_model="gemini-2.5-flash", max_attempts=2)
            job_desc = "A" * 2000
            result = ai.match_job_to_profile(PROFILE_DATA, job_desc)

        self.assertEqual(result.match_score, 95)
        self.assertEqual(len(prompts_used), 2)
        self.assertIn("[Description truncated for compact retry.]", prompts_used[1])


class AdditionalSubsystemTests(TestCase):
    def test_tailored_experience_item_evidence_refs(self):
        # Verify schema validation with evidence_refs
        data = {
            "company": "Google",
            "role": "Software Engineer",
            "duration": "2 years",
            "highlights": ["Designed API schemas", "Improved search indexing"],
            "evidence_refs": ["claim_1", "claim_2"]
        }
        item = TailoredExperienceItem.model_validate(data)
        self.assertEqual(item.company, "Google")
        self.assertEqual(item.evidence_refs, ["claim_1", "claim_2"])

    def test_validate_grounded_kit_validation_with_evidence_refs(self):
        # We can also test validate_grounded_kit
        profile = MasterProfile.model_validate(PROFILE_DATA)
        kit = ApplicationKit.model_validate({
            "tailored_resume": {
                "name": "Alex Morgan",
                "skills": ["Python"],
                "experience": [
                    {
                        "company": "Example Labs",
                        "role": "Software Engineer",
                        "duration": "2024 - Present",
                        "highlights": ["Built Django applications"],
                        "evidence_refs": ["claim_1"]
                    }
                ]
            },
            "cover_letter": "I am interested."
        })
        validate_grounded_kit(profile, kit)

    @patch("core.tasks.CareerAgentAI")
    def test_smart_multi_profile_selector_picks_highest_scoring(self, mock_ai_class):
        from core.models import CandidatePreference, JobLead

        # Clean up existing profiles/leads to isolate the test
        CandidateProfile.objects.all().delete()
        JobLead.objects.all().delete()
        
        # Create profile A (Web Developer)
        profile_a = CandidateProfile.objects.create(
            full_name="Profile Web",
            is_active=True,
            status=CandidateProfile.Status.READY
        )
        CandidatePreference.objects.create(
            profile=profile_a,
            min_match_score=60,
            min_match_confidence=50
        )
        
        # Create profile B (Embedded Engineer)
        profile_b = CandidateProfile.objects.create(
            full_name="Profile Embedded",
            is_active=True,
            status=CandidateProfile.Status.READY
        )
        CandidatePreference.objects.create(
            profile=profile_b,
            min_match_score=60,
            min_match_confidence=50
        )

        # Create a new unscored lead
        lead = JobLead.objects.create(
            title="Embedded developer",
            company="MicroTech",
            description="C/C++ embedded systems engineer for microcontrollers.",
            status=JobLead.Status.NEW
        )

        def match_side_effect(master_profile, job_description):
            res = 90 if master_profile.name == "Profile Embedded" else 45
            return MatchResult.model_validate({
                "match_score": res,
                "summary": "Mock match result summary",
                "matching_skills": [],
                "missing_skills": [],
                "confidence": 80,
                "risk_flags": [],
            })

        mock_ai_instance = mock_ai_class.return_value
        mock_ai_instance.match_job_to_profile.side_effect = match_side_effect
        mock_ai_instance.last_metadata.return_value = {"provider": "mock"}

        from core.tasks import score_unscored_leads
        scored_count = score_unscored_leads(limit=1)

        self.assertEqual(scored_count, 1)
        lead.refresh_from_db()
        
        self.assertEqual(lead.matched_profile, profile_b)
        self.assertEqual(lead.match_score, 90)
        self.assertEqual(lead.status, JobLead.Status.MATCHED)

        app = Application.objects.get(source_lead=lead)
        self.assertEqual(app.profile, profile_b)
        self.assertEqual(app.match_score, 90)

    @patch("core.resume_tailor.async_playwright")
    def test_resume_theme_compilation_and_playwright_margins(self, mock_playwright):
        from unittest.mock import AsyncMock
        from core.models import CandidatePreference
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_playwright.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        
        profile = CandidateProfile.objects.create(
            full_name="Alex ThemeTester",
            email="alex@theme.com",
            phone="123-456-7890",
            location="SF"
        )
        pref = CandidatePreference.objects.create(
            profile=profile,
            resume_theme="classic_serif",
            resume_font_size=11.5,
            resume_line_height=1.4,
            resume_margin_top=0.6,
            resume_margin_bottom=0.6,
            resume_margin_left=0.8,
            resume_margin_right=0.8
        )
        
        app_record = Application.objects.create(
            profile=profile,
            job_description="Standard Job",
            tailored_resume={
                "name": "Alex ThemeTester",
                "skills": ["Python", "Django"],
                "experience": [
                    {
                        "company": "ThemeCorp",
                        "role": "Designer",
                        "duration": "1 year",
                        "highlights": ["Built dynamic themes"]
                    }
                ]
            }
        )

        import asyncio
        from core.resume_tailor import compile_tailored_resume_to_pdf
        
        pdf_path = asyncio.run(compile_tailored_resume_to_pdf(app_record, profile))
        self.assertTrue(pdf_path.endswith(".pdf"))
        
        mock_page.set_content.assert_called_once()
        html_arg = mock_page.set_content.call_args[0][0]
        self.assertIn("Georgia", html_arg)
        self.assertIn("11.5pt", html_arg)
        self.assertIn("line-height: 1.4", html_arg)
        
        mock_page.pdf.assert_called_once()
        pdf_kwargs = mock_page.pdf.call_args[1]
        self.assertEqual(pdf_kwargs["format"], "A4")
        self.assertEqual(pdf_kwargs["margin"], {
            "top": "0.6in",
            "bottom": "0.6in",
            "left": "0.8in",
            "right": "0.8in"
        })

        # Test minimalist theme
        mock_page.reset_mock()
        pref.resume_theme = "minimalist"
        pref.save()
        
        asyncio.run(compile_tailored_resume_to_pdf(app_record, profile))
        html_arg_minimalist = mock_page.set_content.call_args[0][0]
        self.assertIn("Courier New", html_arg_minimalist)


class ProviderFallbackTests(TestCase):
    def setUp(self):
        from core.models import ProviderConfig, SecureCredential
        ProviderConfig.objects.all().delete()
        SecureCredential.objects.all().delete()
        LLMRouter.reset_cooldowns()
        SecureCredential.set_val("GEMINI_API_KEY", "mock-gemini-key")
        SecureCredential.set_val("OPENAI_API_KEY", "mock-openai-key")

    def test_fallback_to_settings(self):
        chain = build_provider_chain(LLMTask.JOB_MATCH)
        self.assertTrue(len(chain) > 0)
        self.assertEqual(chain[0].name, "gemini")

    def test_provider_reorder(self):
        from core.models import ProviderConfig
        c1 = ProviderConfig.objects.create(
            provider_name="openai",
            display_name="OpenAI",
            api_key_name="OPENAI_API_KEY",
            adapter_type="openai_compatible",
            models=["gpt-4.1-mini"],
            priority=0,
            is_enabled=True
        )
        c2 = ProviderConfig.objects.create(
            provider_name="gemini",
            display_name="Gemini",
            api_key_name="GEMINI_API_KEY",
            adapter_type="gemini",
            models=["gemini-2.5-flash"],
            priority=1,
            is_enabled=True
        )
        
        chain = build_provider_chain(LLMTask.JOB_MATCH)
        self.assertEqual(chain[0].name, "openai")
        self.assertEqual(chain[1].name, "gemini")

    @patch("core.llm.GeminiAdapter.generate")
    def test_multi_model_cascade_and_switch_event(self, mock_gemini_generate):
        from core.models import ProviderConfig
        c1 = ProviderConfig.objects.create(
            provider_name="gemini",
            display_name="Gemini",
            api_key_name="GEMINI_API_KEY",
            adapter_type="gemini",
            models=["gemini-2.5-flash", "gemini-2.5-pro"],
            priority=0,
            is_enabled=True
        )
        
        from core.llm import LLMProviderError
        mock_gemini_generate.side_effect = [
            LLMProviderError("Flash rate limit", rate_limited=True),
            ("pro success response", {"prompt_tokens": 10})
        ]
        
        router = LLMRouter()
        req = LLMRequest(task=LLMTask.JOB_MATCH, prompt="test prompt")
        res = router.generate(req)
        
        self.assertEqual(res.text, "pro success response")
        self.assertEqual(res.provider, "gemini")
        self.assertEqual(res.model, "gemini-2.5-pro")
        self.assertIn("gemini-2.5-flash) failed", res.switch_event)

    @patch("core.llm.GeminiAdapter.generate")
    def test_credit_exhausted_detection(self, mock_gemini_generate):
        from core.models import ProviderConfig
        c1 = ProviderConfig.objects.create(
            provider_name="gemini",
            display_name="Gemini",
            api_key_name="GEMINI_API_KEY",
            adapter_type="gemini",
            models=["gemini-2.5-flash"],
            priority=0,
            is_enabled=True
        )
        
        from core.llm import LLMProviderError
        mock_gemini_generate.side_effect = LLMProviderError("insufficient_quota: billing limit reached", credit_exhausted=True)
        
        router = LLMRouter()
        req = LLMRequest(task=LLMTask.JOB_MATCH, prompt="test prompt")
        
        with self.assertRaises(LLMExhaustedError):
            router.generate(req)
            
        c1.refresh_from_db()
        self.assertEqual(c1.credit_status, "exhausted")
        self.assertFalse(c1.is_available())






