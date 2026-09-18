from __future__ import annotations

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
