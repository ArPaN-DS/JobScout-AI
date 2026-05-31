from typing import Any

from .ai_service import CareerAgentAI


def extract_profile_from_pdf(pdf_path: str) -> dict[str, Any]:
    profile = CareerAgentAI().extract_profile_from_pdf(pdf_path)
    return profile.to_storage_dict()


def match_job_to_profile(master_profile: dict[str, Any], job_description: str) -> dict[str, Any]:
    result = CareerAgentAI().match_job_to_profile(master_profile, job_description)
    return result.model_dump(mode="json")


def generate_application_kit(master_profile: dict[str, Any], job_description: str) -> dict[str, Any]:
    kit = CareerAgentAI().generate_application_kit(master_profile, job_description)
    return kit.model_dump(mode="json")
