import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"
RESUME_PATH = r"C:\Users\arpan\Downloads\Arpan_Majumdar.pdf"

def run_test():
    session = requests.Session()
    
    print("--- 1. Testing Profile Setup ---")
    response = session.get(f"{BASE_URL}/")
    csrf_token = session.cookies.get('csrftoken')
    headers = {"X-CSRFToken": csrf_token, "Referer": f"{BASE_URL}/"}
    
    try:
        with open(RESUME_PATH, "rb") as f:
            files = {"resume": f}
            data = {"linkedin_url": "www.linkedin.com/in/arpan-majumdar-", "github_url": ""}
            print("Sending POST request to upload resume (this may take a few seconds)...")
            response = session.post(f"{BASE_URL}/", files=files, data=data, headers=headers)
            
            if response.status_code == 200:
                print("✅ Profile Setup Success!")
                print("Profile Data:", json.dumps(response.json().get('data', {}), indent=2)[:500] + "...\n")
            else:
                print("❌ Profile Setup Failed:", response.status_code, response.text)
                return
    except FileNotFoundError:
        print(f"❌ Error: Could not find resume at {RESUME_PATH}")
        return

    print("--- 2. Testing Job Discovery & Matching ---")
    
    mock_jd = """
    We are looking for a Software Engineer with experience in Python, Django, HTML, CSS, and Javascript.
    Experience with Machine Learning and AI models like LLMs is a huge plus.
    You will be building responsive web applications and integrating them with AI backends.
    Requires strong communication skills and ability to work in a fast-paced environment.
    """
    
    data = {
        "job_url": "https://example.com/job",
        "job_description": mock_jd
    }
    
    print("Sending POST request to match job...")
    response = session.post(f"{BASE_URL}/jobs/", data=data, headers=headers)
    
    if response.status_code == 200:
        res_json = response.json()
        print("✅ Job Match Success!")
        print(f"Score: {res_json['data']['match_score']}%")
        print(f"Summary: {res_json['data']['summary']}")
        app_id = res_json.get('app_id')
        print(f"Generated App ID: {app_id}\n")
    else:
        print("❌ Job Match Failed:", response.status_code, response.text)
        return
        
    print("--- 3. Testing Application Kit Generation ---")
    data = {"app_id": app_id}
    print("Sending POST to generate Cover Letter & Resume...")
    response = session.post(f"{BASE_URL}/jobs/generate/", data=data, headers=headers)
    
    if response.status_code == 200:
        print("✅ Application Kit Success!")
        kit = response.json()['data']
        print("Tailored Resume Skills:", kit['tailored_resume'].get('skills', []))
        print("\nCover Letter Snippet:", kit['cover_letter'][:200] + "...\n")
    else:
        print("❌ Application Kit Failed:", response.status_code, response.text)
        return
        
    print("--- 4. Testing Mark Submitted ---")
    data = {"app_id": app_id}
    response = session.post(f"{BASE_URL}/jobs/submit/", data=data, headers=headers)
    
    if response.status_code == 200:
        print("✅ Tracked Successfully!")
    else:
        print("❌ Track Failed:", response.status_code, response.text)

if __name__ == "__main__":
    run_test()
