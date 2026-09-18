from __future__ import annotations

from app.core.operator_auth import require_operator_or_internal
from app.main import app


def test_referral_code_claim_and_owner_visibility(client, switch_user) -> None:
    assert client.get("/api/v1/me").status_code == 200

    first = client.get("/api/v1/referrals/me")
    assert first.status_code == 200, first.text
    first_payload = first.json()
    assert first_payload["code"]
    assert first_payload["referrals"] == []
    assert first_payload["available_credit_cents"] == 0

    switch_user("clerk_user_b", "b@example.com")
    assert client.get("/api/v1/me").status_code == 200

    claimed = client.post(
        "/api/v1/referrals/claim",
        json={"code": first_payload["code"]},
    )
    assert claimed.status_code == 201, claimed.text
    assert claimed.json()["status"] == "PENDING"
    assert claimed.json()["already_claimed"] is False

    duplicate = client.post(
        "/api/v1/referrals/claim",
        json={"code": first_payload["code"]},
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["already_claimed"] is True

    switch_user("clerk_user_a", "a@example.com")
    owner = client.get("/api/v1/referrals/me")
    assert owner.status_code == 200
    assert len(owner.json()["referrals"]) == 1
    assert owner.json()["referrals"][0]["status"] == "PENDING"


def test_self_referral_is_blocked(client) -> None:
    assert client.get("/api/v1/me").status_code == 200
    code = client.get("/api/v1/referrals/me").json()["code"]

    response = client.post("/api/v1/referrals/claim", json={"code": code})
    assert response.status_code == 409



def test_referral_operator_queue_and_qualification(client, switch_user) -> None:
    assert client.get("/api/v1/me").status_code == 200
    code = client.get("/api/v1/referrals/me").json()["code"]

    switch_user("clerk_user_b", "b@example.com")
    assert client.get("/api/v1/me").status_code == 200
    claimed = client.post("/api/v1/referrals/claim", json={"code": code})
    assert claimed.status_code == 201
    event_id = claimed.json()["id"]

    app.dependency_overrides[require_operator_or_internal] = lambda: None
    try:
        events = client.get("/api/v1/internal/referrals/events?status=PENDING")
        assert events.status_code == 200, events.text
        assert len(events.json()) == 1
        assert events.json()[0]["id"] == event_id
        assert events.json()[0]["referrer_email"] == "a@example.com"
        assert events.json()[0]["referred_email"] == "b@example.com"

        qualified = client.post(
            f"/api/v1/internal/referrals/{event_id}/qualify",
            json={"referrer_credit_cents": 1000, "referred_credit_cents": 250},
        )
        assert qualified.status_code == 200, qualified.text
        assert qualified.json()["status"] == "CREDITED"

        repeated = client.post(
            f"/api/v1/internal/referrals/{event_id}/qualify",
            json={"referrer_credit_cents": 1000, "referred_credit_cents": 250},
        )
        assert repeated.status_code == 200, repeated.text

        metrics = client.get("/api/v1/internal/referrals/metrics")
        assert metrics.status_code == 200
        assert metrics.json()["events"] == 1
        assert metrics.json()["qualified"] == 1
        assert metrics.json()["available_credit_cents"] == 1250
    finally:
        app.dependency_overrides.pop(require_operator_or_internal, None)

    switch_user("clerk_user_a", "a@example.com")
    owner = client.get("/api/v1/referrals/me")
    assert owner.status_code == 200
    assert owner.json()["available_credit_cents"] == 1000
    assert len(owner.json()["ledger"]) == 1

    switch_user("clerk_user_b", "b@example.com")
    referred = client.get("/api/v1/referrals/me")
    assert referred.status_code == 200
    assert referred.json()["available_credit_cents"] == 250
    assert len(referred.json()["ledger"]) == 1
