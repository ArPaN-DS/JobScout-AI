import json
from unittest.mock import patch, MagicMock
from django.test import TestCase

from .ai_service import CareerAgentAI
from .llm import LLMResult, LLMAttempt
from .schemas import ApplicationKit, KitCriticVerdict, AgentCriticIssue
from .tests import PROFILE_DATA

class TokenAggregationTests(TestCase):
    @patch.object(CareerAgentAI, "critic_validate_kit")
    @patch.object(CareerAgentAI, "_generate_json")
    def test_metadata_aggregation_across_multiple_turns(self, mock_generate_json, mock_critic_validate):
        # Setup mock responses for two generations
        # We need two distinct ApplicationKits (or reuse)
        mock_kit = ApplicationKit.model_validate({
            "tailored_resume": {
                "name": "Alex Morgan",
                "skills": ["Python", "Django"],
                "experience": [],
            },
            "cover_letter": "Excited to apply.",
        })
        
        # We simulate the _generate_json method behavior. Since CareerAgentAI._generate_json
        # modifies self.last_result and self._all_results, we can simulate the side effects
        # of _generate_json or just mock the router/llm results.
        # But wait, CareerAgentAI._generate_json calls `router.generate()`!
        # It's cleaner to mock `LLMRouter.generate` directly, so we execute the real CareerAgentAI._generate_json logic.
        pass

    @patch("core.llm.LLMRouter.generate")
    def test_router_based_metadata_aggregation(self, mock_router_generate):
        # We want to test that calling generate_application_kit triggers multiple router.generate calls,
        # and all_metadata aggregates the tokens correctly.
        
        # First call to router.generate (Turn 1: Generation): gemini
        result_1 = LLMResult(
            text=json.dumps({
                "tailored_resume": {"name": "Alex Morgan", "skills": ["Python"], "experience": []},
                "cover_letter": "Letter 1"
            }),
            provider="gemini",
            model="gemini-2.5-pro",
            attempts=[LLMAttempt("gemini", "gemini-2.5-pro", "success")],
            token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        )

        # Second call to router.generate (Turn 1: Critic rejection): anthropic
        result_2 = LLMResult(
            text=json.dumps({
                "approved": False,
                "issues": ["Need Django skill."],
                "critic_issues": [{"type": "hallucination", "target": "resume", "fix_instruction": "Add Django"}]
            }),
            provider="anthropic",
            model="claude-3-5-haiku-latest",
            attempts=[LLMAttempt("anthropic", "claude-3-5-haiku-latest", "success")],
            token_usage={"prompt_tokens": 200, "completion_tokens": 80, "total_tokens": 280}
        )

        # Third call to router.generate (Turn 2: Re-generation): openai
        result_3 = LLMResult(
            text=json.dumps({
                "tailored_resume": {"name": "Alex Morgan", "skills": ["Python", "Django"], "experience": []},
                "cover_letter": "Letter 2"
            }),
            provider="openai",
            model="gpt-4.1-mini",
            attempts=[LLMAttempt("openai", "gpt-4.1-mini", "success")],
            token_usage={"prompt_tokens": 120, "completion_tokens": 60, "total_tokens": 180}
        )

        # Fourth call to router.generate (Turn 2: Critic approval): anthropic
        result_4 = LLMResult(
            text=json.dumps({
                "approved": True,
                "issues": [],
                "critic_issues": []
            }),
            provider="anthropic",
            model="claude-3-5-haiku-latest",
            attempts=[LLMAttempt("anthropic", "claude-3-5-haiku-latest", "success")],
            token_usage={"prompt_tokens": 220, "completion_tokens": 40, "total_tokens": 260}
        )

        # Configure mock to return these in sequence
        mock_router_generate.side_effect = [result_1, result_2, result_3, result_4]

        # Initialize CareerAgentAI
        ai = CareerAgentAI(critic_enabled=True, max_attempts=2)
        
        # Run kit generation
        kit = ai.generate_application_kit(PROFILE_DATA, "Job Description needing Python and Django.")
        
        # Verify the final kit is returned
        self.assertIsNotNone(kit)
        self.assertEqual(kit.tailored_resume.skills, ["Python", "Django"])

        # Fetch aggregated metadata
        metadata = ai.all_metadata()

        # We had 4 LLM calls:
        # Gemini (100 in, 50 out)
        # Anthropic (200 in, 80 out)
        # OpenAI (120 in, 60 out)
        # Anthropic (220 in, 40 out)
        # Sums: 
        # prompt: 100 + 200 + 120 + 220 = 640
        # completion: 50 + 80 + 60 + 40 = 230
        # total: 150 + 280 + 180 + 260 = 870
        self.assertEqual(metadata["total_token_usage"]["prompt_tokens"], 640)
        self.assertEqual(metadata["total_token_usage"]["completion_tokens"], 230)
        self.assertEqual(metadata["total_token_usage"]["total_tokens"], 870)

        # Verify providers listed
        providers = sorted(metadata["providers_used"])
        self.assertEqual(providers, ["anthropic:claude-3-5-haiku-latest", "gemini:gemini-2.5-pro", "openai:gpt-4.1-mini"])

        # Verify total calls
        self.assertEqual(metadata["total_llm_calls"], 4)

        # Verify attempts list length
        self.assertEqual(len(metadata["all_attempts"]), 4)
