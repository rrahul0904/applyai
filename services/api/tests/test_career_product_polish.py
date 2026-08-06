from collections import Counter

from app.core.database import SessionLocal
from app.jobs.seed import seed_development_jobs


def seed_jobs() -> None:
    with SessionLocal() as session:
        seed_development_jobs(session)


def candidate_profile() -> dict:
    return {
        "headline": "Senior data engineering leader",
        "current_title": "Senior Data Engineering Manager",
        "summary": (
            "Data platform leader with 12 years of experience building reliable "
            "analytics and machine-learning infrastructure."
        ),
        "years_experience": 12,
        "target_roles": [
            "Data Engineering Manager",
            "Analytics Engineering Manager",
            "Machine Learning Engineering Manager",
        ],
        "location_text": "Boston, MA",
        "work_modes": ["REMOTE", "HYBRID"],
        "minimum_compensation": 90000,
        "experiences": [
            {
                "company_name": "Atlas Health",
                "title": "Senior Data Engineering Manager",
                "start_date": "2021-01-01",
                "end_date": None,
                "description": (
                    "Built and led a 12-person data engineering organization and "
                    "reduced pipeline delivery time by 35% while improving reliability "
                    "across four business units."
                ),
                "provenance": "USER_VERIFIED",
            }
        ],
        "education": [],
        "skills": [
            {"name": "Python", "provenance": "USER_VERIFIED"},
            {"name": "SQL", "provenance": "USER_VERIFIED"},
            {"name": "Analytics", "provenance": "USER_VERIFIED"},
            {"name": "Machine learning", "provenance": "USER_VERIFIED"},
            {"name": "AWS", "provenance": "USER_VERIFIED"},
            {"name": "Snowflake", "provenance": "USER_VERIFIED"},
        ],
    }


def test_beta_shortlist_and_candidate_language_are_polished(client):
    seed_jobs()
    profile_response = client.put("/api/v1/profile", json=candidate_profile())
    assert profile_response.status_code == 200

    matches_response = client.get("/api/v1/career-v1/matches?limit=12")
    assert matches_response.status_code == 200
    matches = matches_response.json()
    assert "Equivalent title-and-company postings are grouped" in matches["shortlist_policy"]
    assert len(matches["items"]) >= 6

    role_company_keys = [
        (item["company_name"].casefold(), item["title"].casefold())
        for item in matches["items"]
    ]
    assert len(role_company_keys) == len(set(role_company_keys))
    company_counts = Counter(item["company_name"] for item in matches["items"])
    assert max(company_counts.values()) <= 2

    selected = next(item for item in matches["items"] if item["match_score"] >= 60)
    job_id = selected["job_id"]

    tailoring_response = client.get(f"/api/v1/career-v1/tailoring/{job_id}")
    assert tailoring_response.status_code == 200
    tailoring = tailoring_response.json()
    suggestions = " ".join(item["text"] for item in tailoring["edits"])
    assert "Position this experience" not in suggestions
    assert "Emphasize the parts" not in suggestions
    assert all(item["text"].rstrip().endswith((".", "!", "?")) for item in tailoring["edits"])
    assert tailoring["edits"][2]["text"] == tailoring["edits"][2]["current"]

    assistant_response = client.get(
        f"/api/v1/career-v1/application-assistant/{job_id}"
    )
    assert assistant_response.status_code == 200
    assistant = assistant_response.json()
    all_answers = " ".join(item["answer"] for item in assistant["questions"])
    assert "Missing required skills:" not in all_answers
    assert "I also want to be transparent" not in all_answers
    assert "expected depth" in all_answers or "first-year expectations" in all_answers
    assert ".." not in assistant["cover_letter"]

    custom_cover = "My candidate-edited cover letter draft."
    custom_answers = [
        {
            "question": item["question"],
            "answer": f"Candidate-edited answer {index + 1}.",
            "user_verified": False,
        }
        for index, item in enumerate(assistant["questions"])
    ]
    save_response = client.put(
        f"/api/v1/career-v1/application-assistant/{job_id}",
        json={
            "cover_letter": custom_cover,
            "cover_letter_verified": False,
            "answers": custom_answers,
        },
    )
    assert save_response.status_code == 200

    reload_response = client.get(
        f"/api/v1/career-v1/application-assistant/{job_id}"
    )
    assert reload_response.status_code == 200
    reloaded = reload_response.json()
    assert reloaded["cover_letter"] == custom_cover
    assert [item["answer"] for item in reloaded["questions"]] == [
        item["answer"] for item in custom_answers
    ]
