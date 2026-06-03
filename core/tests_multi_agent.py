import json
from unittest.mock import patch, MagicMock
from django.test import TransactionTestCase, override_settings
from django.contrib.auth.models import User

from .ai_service import CareerAgentAI, KitValidationError
from .auto_applier import smart_fill_form
from .models import AgentRunLog, CandidateQuestionAnswer, CandidateProfile, Application
from .schemas import MasterProfile, ApplicationKit, KitCriticVerdict, AgentCriticIssue
from .profile_store import save_master_profile
from .tests import PROFILE_DATA, _prepare_ready_candidate


@override_settings(DAILY_LLM_BUDGET_USD=50.0)
class MultiAgentCoreTests(TransactionTestCase):
    def setUp(self):
        save_master_profile(MasterProfile.model_validate(PROFILE_DATA))
        self.candidate = _prepare_ready_candidate()
        self.test_user = User.objects.create_user(username="testuser", password="password123")
        self.client.login(username="testuser", password="password123")

    def test_agent_run_log_creation(self):
        app = Application.objects.create(
            job_description="Sample job description",
            profile_snapshot=PROFILE_DATA,
        )
        log = AgentRunLog.objects.create(
            application=app,
            agent_name="TestAgent",
            status=AgentRunLog.Status.INFO,
            message="Test run started.",
            detail_data={"test": True}
        )
        self.assertEqual(log.agent_name, "TestAgent")
        self.assertEqual(log.status, "info")
        self.assertEqual(log.detail_data["test"], True)

    def test_qa_item_creation_and_normalization(self):
        qa = CandidateQuestionAnswer.objects.create(
            profile=self.candidate,
            question_text="Why do you want this job?",
            answer_text="I am highly qualified.",
            category="general"
        )
        self.assertEqual(qa.normalized_question, "why do you want this job")
        self.assertFalse(qa.is_verified)

    def test_agent_logs_view(self):
        app = Application.objects.create(
            job_description="Sample job description",
            profile_snapshot=PROFILE_DATA,
        )
        AgentRunLog.objects.create(
            application=app,
            agent_name="MatchAnalyst",
            status=AgentRunLog.Status.SUCCESS,
            message="Score is 85%"
        )
        
        response = self.client.get(f"/jobs/agent-logs/app/{app.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["logs"]), 1)
        self.assertEqual(data["logs"][0]["agent_name"], "MatchAnalyst")
        self.assertEqual(data["logs"][0]["message"], "Score is 85%")

    def test_verify_qa_item_view(self):
        qa = CandidateQuestionAnswer.objects.create(
            profile=self.candidate,
            question_text="Why are you qualified?",
            answer_text="Many years of experience.",
            category="technical"
        )
        self.assertFalse(qa.is_verified)
        
        response = self.client.post("/profile/qa/verify/", data={
            "qa_id": qa.id,
            "answer_text": "Many years of experience with Django."
        })
        self.assertEqual(response.status_code, 200)
        qa.refresh_from_db()
        self.assertTrue(qa.is_verified)
        self.assertEqual(qa.answer_text, "Many years of experience with Django.")

    @patch("core.auto_applier.LLMRouter")
    def test_smart_fill_form_with_qa_memory(self, mock_router_class):
        # 1. Setup a verified Q&A in the database
        qa = CandidateQuestionAnswer.objects.create(
            profile=self.candidate,
            question_text="Why are you interested in this role?",
            answer_text="I love building career assistants.",
            category="general",
            is_verified=True
        )
        
        # Form fields presented to the agent
        fields = [
            {"name": "fullname", "id": "fullname_id", "label": "Full Name", "tag": "input", "type": "text"},
            {"name": "why_role", "id": "why_role_id", "label": "Why are you interested in this role?", "tag": "textarea"}
        ]
        
        # Test direct database match
        import asyncio
        mapping = asyncio.run(smart_fill_form(fields, PROFILE_DATA))
        self.assertEqual(mapping["fullname"], PROFILE_DATA["name"])
        self.assertEqual(mapping["why_role"], "I love building career assistants.")
        
        # 2. Test LLM fallback drafting when question is not found
        fields_unseen = [
            {"name": "salary", "id": "salary_id", "label": "What is your target salary?", "tag": "input", "type": "text"}
        ]
        
        mock_router_instance = MagicMock()
        mock_router_class.return_value = mock_router_instance
        mock_result = MagicMock()
        mock_result.text = '{"salary": "$120,000 USD"}'
        mock_result.provider = "test"
        mock_result.model = "test-model"
        mock_router_instance.generate.return_value = mock_result
        
        mapping_drafted = asyncio.run(smart_fill_form(fields_unseen, PROFILE_DATA))
        self.assertEqual(mapping_drafted["salary"], "$120,000 USD")
        
        # Verify it was saved to CandidateQuestionAnswer as unverified
        saved_draft = CandidateQuestionAnswer.objects.get(profile=self.candidate, question_text="What is your target salary?")
        self.assertFalse(saved_draft.is_verified)
        self.assertEqual(saved_draft.answer_text, "$120,000 USD")

    @patch.object(CareerAgentAI, "critic_validate_kit")
    @patch.object(CareerAgentAI, "_generate_json")
    def test_generate_application_kit_self_correction_loop(self, mock_generate_json, mock_critic_validate):
        app = Application.objects.create(
            job_description="Need a backend engineer with Python and Django experience.",
            profile_snapshot=PROFILE_DATA,
        )
        
        # Mock generator return value
        mock_kit = ApplicationKit.model_validate({
            "tailored_resume": {
                "name": "Alex Morgan",
                "skills": ["Python", "Django"],
                "experience": [],
            },
            "cover_letter": "Excited to apply.",
        })
        mock_generate_json.return_value = mock_kit
        
        # Mock Critic to reject the first time, and accept the second time
        mock_verdict_1 = KitCriticVerdict(
            approved=False,
            issues=["Missing citation for skill Django."],
            critic_issues=[
                AgentCriticIssue(
                    type="hallucination",
                    target="resume",
                    fix_instruction="Provide exact context for Django experience."
                )
            ]
        )
        mock_verdict_2 = KitCriticVerdict(approved=True)
        
        mock_critic_validate.side_effect = [mock_verdict_1, mock_verdict_2]
        
        ai = CareerAgentAI(critic_enabled=True)
        kit = ai.generate_application_kit(PROFILE_DATA, app.job_description, application=app)
        
        self.assertIsNotNone(kit)
        
        # Verify AgentRunLog contains steps showing self-correction
        logs = list(AgentRunLog.objects.filter(application=app).order_by("created_at"))
        
        # Logs should record: 
        # 1. Starting tailoring
        # 2. Turn 1 generation
        # 3. QualityCritic audit
        # 4. Audit failed warning
        # 5. Turn 2 generation
        # 6. QualityCritic audit
        # 7. Audit passed success
        self.assertGreaterEqual(len(logs), 6)
        self.assertEqual(logs[0].agent_name, "TailoringExpert")
        self.assertEqual(logs[2].agent_name, "QualityCritic")
        self.assertEqual(logs[3].status, "warning")
        self.assertEqual(logs[-1].status, "success")
