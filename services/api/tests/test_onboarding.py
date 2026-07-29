def advance(client, stage: str):
    return client.put("/api/v1/onboarding", json={"stage": stage})


def test_onboarding_persists_stage_and_blocks_skips(client):
    initial = client.get("/api/v1/onboarding")
    assert initial.status_code == 200
    assert initial.json() == {
        "onboarding_stage": "ACCOUNT_CREATED",
        "onboarding_completed": False,
    }

    skipped = advance(client, "TARGET_ROLES")
    assert skipped.status_code == 409
    assert skipped.json()["error"]["code"] == "ONBOARDING_STAGE_OUT_OF_ORDER"

    assert advance(client, "RESUME").status_code == 200
    assert advance(client, "PROFILE_REVIEW").status_code == 200

    persisted = client.get("/api/v1/onboarding")
    assert persisted.json()["onboarding_stage"] == "PROFILE_REVIEW"


def test_onboarding_completion_requires_candidate_minimums(client):
    for stage in [
        "RESUME",
        "PROFILE_REVIEW",
        "TARGET_ROLES",
        "LOCATION",
        "WORK_PREFERENCES",
        "COMPENSATION",
        "REVIEW",
    ]:
        response = advance(client, stage)
        assert response.status_code == 200

    incomplete = advance(client, "COMPLETE")
    assert incomplete.status_code == 409
    assert incomplete.json()["error"]["code"] == "ONBOARDING_INCOMPLETE"

    profile = client.put(
        "/api/v1/profile",
        json={
            "current_title": "Senior Data Engineer",
            "target_roles": ["Staff Data Engineer"],
            "work_modes": ["remote"],
            "location_text": "Boston, MA",
        },
    )
    assert profile.status_code == 200

    completed = advance(client, "COMPLETE")
    assert completed.status_code == 200
    assert completed.json() == {
        "onboarding_stage": "COMPLETE",
        "onboarding_completed": True,
    }


def test_onboarding_resume_processing_is_optional(client):
    assert advance(client, "RESUME").status_code == 200
    assert advance(client, "RESUME_PROCESSING").status_code == 200
    assert advance(client, "PROFILE_REVIEW").status_code == 200

    # Returning to an earlier step is allowed so candidates can correct persisted data.
    back = advance(client, "RESUME")
    assert back.status_code == 200
    assert back.json()["onboarding_stage"] == "RESUME"
