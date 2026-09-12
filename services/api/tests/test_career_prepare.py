from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import CandidateProfile, CandidateSkill, JobSkill, User
from tests.helpers import create_job


def _seed_candidate_and_job(database_url: str, client):
    assert client.get("/api/v1/me").status_code == 200
    engine = create_engine(database_url)
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == "a@example.com"))
        assert user is not None
        profile = CandidateProfile(
            user_id=user.id,
            headline="Senior operations leader",
            current_title="Product Operations Manager",
            summary="Led production operations systems and workflow improvements.",
            years_experience=9,
        )
        session.add(profile)
        session.flush()
        session.add(
            CandidateSkill(
                profile_id=profile.id,
                name="Operations",
                normalized_name="operations",
                proficiency="STRONG",
                provenance="USER_VERIFIED",
            )
        )
        job = create_job(session)
        session.add_all(
            [
                JobSkill(
                    job_id=job.id,
                    name="Operations",
                    normalized_name="operations",
                    required=True,
                ),
                JobSkill(
                    job_id=job.id,
                    name="Kubernetes",
                    normalized_name="kubernetes",
                    required=True,
                ),
            ]
        )
        session.commit()
        job_id = str(job.id)
    engine.dispose()
    return job_id


def test_prepare_end_to_end_learning_interview_and_readiness(client, database_url):
    job_id = _seed_candidate_and_job(database_url, client)

    gaps = client.post(f"/api/v1/career-v2/jobs/{job_id}/skill-analysis")
    assert gaps.status_code == 200, gaps.text
    by_skill = {item["normalized_skill"]: item for item in gaps.json()["items"]}
    assert by_skill["operations"]["status"] == "CLOSED"
    assert by_skill["kubernetes"]["status"] == "OPEN"
    assert by_skill["kubernetes"]["severity"] == "HIGH"

    path_response = client.post(f"/api/v1/career-v2/jobs/{job_id}/learning-path")
    assert path_response.status_code == 200, path_response.text
    path = path_response.json()
    assert path["courses"]
    assert path["courses"][0]["skill"] == "Kubernetes"

    course_id = path["courses"][0]["id"]
    course_response = client.get(f"/api/v1/career-v2/courses/{course_id}")
    assert course_response.status_code == 200, course_response.text
    course = course_response.json()
    assert len(course["modules"]) == 3
    lesson = course["modules"][0]["lessons"][0]
    assert lesson["estimated_minutes"] == 3
    assert lesson["exercises"]

    tutor = client.post(
        f"/api/v1/career-v2/lessons/{lesson['id']}/chat",
        json={"message": "How should I explain Kubernetes trade-offs?"},
    )
    assert tutor.status_code == 200, tutor.text
    assert "trade-off" in tutor.json()["answer"].lower()

    exercise = client.post(
        f"/api/v1/career-v2/exercises/{lesson['exercises'][0]['id']}/attempts",
        json={
            "response": (
                "I would start with scale and availability requirements, choose Kubernetes only if "
                "orchestration complexity is justified, discuss the trade-off between control and "
                "operational overhead, test failure recovery, monitor workload metrics and verify "
                "the design with observability and load tests."
            )
        },
    )
    assert exercise.status_code == 200, exercise.text
    assert exercise.json()["score"] >= 70

    progress = client.put(
        f"/api/v1/career-v2/lessons/{lesson['id']}/progress",
        json={"completed": True, "mastery_score": exercise.json()["score"]},
    )
    assert progress.status_code == 200

    pack_response = client.post(f"/api/v1/career-v2/jobs/{job_id}/interview-pack")
    assert pack_response.status_code == 200, pack_response.text
    pack = pack_response.json()
    section_types = {section["type"] for section in pack["sections"]}
    assert {
        "TECHNICAL_CHEATSHEET",
        "TECHNICAL_QA",
        "PRACTICAL_TASKS",
        "BEHAVIORAL",
        "RESUME_DEEP_DIVE",
        "QUESTIONS_TO_ASK",
    }.issubset(section_types)

    mock_response = client.post(
        f"/api/v1/career-v2/jobs/{job_id}/mock-interviews",
        json={"mode": "technical", "channel": "WRITTEN", "difficulty": "adaptive"},
    )
    assert mock_response.status_code == 200, mock_response.text
    mock = mock_response.json()
    assert mock["current_question"] is not None

    for _ in range(8):
        if mock["current_question"] is None:
            break
        answer = client.post(
            f"/api/v1/career-v2/interviews/{mock['id']}/answers",
            json={
                "answer": (
                    "I would clarify requirements and constraints first. I would compare alternatives, "
                    "make the trade-off explicit, define a failure mode, test the design, monitor metrics "
                    "and verify the outcome with observability. In production I would validate assumptions "
                    "before rollout and use staged delivery rather than claiming experience I do not have."
                )
            },
        )
        assert answer.status_code == 200, answer.text
        mock = answer.json()

    completed = client.post(f"/api/v1/career-v2/interviews/{mock['id']}/complete")
    assert completed.status_code == 200, completed.text
    report = completed.json()
    assert report["status"] == "COMPLETED"
    assert report["overall_score"] is not None
    assert report["feedback"]["recommended_next_action"]

    readiness = client.get(f"/api/v1/career-v2/jobs/{job_id}/readiness")
    assert readiness.status_code == 200, readiness.text
    readiness_body = readiness.json()
    assert 0 <= readiness_body["overall_score"] <= 100
    assert set(readiness_body["breakdown"]) == {"match", "application", "learning", "interview"}

    history = client.get(f"/api/v1/career-v2/jobs/{job_id}/progress")
    assert history.status_code == 200
    assert history.json()["snapshots"]


def test_interview_recording_proxy_storage_is_private_and_replayable(client, database_url):
    job_id = _seed_candidate_and_job(database_url, client)
    started = client.post(
        f"/api/v1/career-v2/jobs/{job_id}/mock-interviews",
        json={"mode": "behavioral", "channel": "VOICE", "difficulty": "adaptive"},
    )
    assert started.status_code == 200, started.text
    session_id = started.json()["id"]

    intent = client.post(
        f"/api/v1/career-v2/interviews/{session_id}/recording-upload-intents",
        json={"filename": "answer.webm", "content_type": "audio/webm", "file_size": 18, "media_type": "AUDIO"},
    )
    assert intent.status_code == 200, intent.text
    body = intent.json()
    assert body["upload_mode"] == "PROXY"
    assert body["storage_key"].startswith("interviews/")

    uploaded = client.post(
        f"/api/v1/career-v2/interviews/{session_id}/recordings/proxy",
        params={"storage_key": body["storage_key"]},
        files={"file": ("answer.webm", b"mock-audio-content", "audio/webm")},
    )
    assert uploaded.status_code == 200, uploaded.text

    completed = client.post(
        f"/api/v1/career-v2/interviews/{session_id}/recording-upload-complete",
        json={
            "storage_key": body["storage_key"],
            "media_type": "AUDIO",
            "transcript_text": "I led the change, measured the result, and learned from the rollout.",
            "duration_seconds": 42,
            "provider": "browser-media-recorder",
        },
    )
    assert completed.status_code == 200, completed.text
    recording_id = completed.json()["recording_id"]

    replay = client.get(f"/api/v1/career-v2/interviews/{session_id}/recordings/{recording_id}")
    assert replay.status_code == 200
    assert replay.content == b"mock-audio-content"
    assert replay.headers["cache-control"] == "private, no-store"
