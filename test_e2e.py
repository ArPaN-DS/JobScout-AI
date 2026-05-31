import json
import os

import requests


BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000")
RESUME_PATH = os.getenv("E2E_RESUME_PATH", "")


def run_test():
    if not RESUME_PATH:
        raise SystemExit("Set E2E_RESUME_PATH to a local PDF or DOCX before running this script.")

    session = requests.Session()

    response = session.get(f"{BASE_URL}/")
    csrf_token = session.cookies.get("csrftoken")
    headers = {"X-CSRFToken": csrf_token or "", "Referer": f"{BASE_URL}/"}

    with open(RESUME_PATH, "rb") as handle:
        response = session.post(
            f"{BASE_URL}/",
            files={"resume": handle},
            data={
                "linkedin_url": "https://linkedin.com/in/sample-candidate",
                "github_url": "https://github.com/sample-candidate",
                "target_roles": "Backend Developer, Data Engineer",
                "locations": "Remote",
            },
            headers=headers,
        )

    if response.status_code != 200:
        raise SystemExit(f"Profile setup failed: {response.status_code} {response.text}")
    print("Profile setup OK")
    print(json.dumps(response.json().get("data", {}), indent=2)[:800])

    job_description = """
    We are hiring a backend developer to build Python services, Django APIs,
    data workflows, tests, and production integrations. The role requires
    clear communication, product judgment, and collaboration with engineering
    and operations teams.
    """
    response = session.post(
        f"{BASE_URL}/jobs/",
        data={"job_url": "https://example.com/jobs/sample", "job_description": job_description},
        headers=headers,
    )
    if response.status_code != 200:
        raise SystemExit(f"Job match failed: {response.status_code} {response.text}")
    payload = response.json()
    print("Job match OK")
    print(json.dumps(payload.get("data", {}), indent=2))

    response = session.post(f"{BASE_URL}/jobs/generate/", data={"app_id": payload.get("app_id")}, headers=headers)
    if response.status_code != 200:
        raise SystemExit(f"Application kit failed: {response.status_code} {response.text}")
    print("Application kit OK")


if __name__ == "__main__":
    run_test()
