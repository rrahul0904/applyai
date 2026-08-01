def test_profile_write_read_and_user_isolation(client, switch_user):
    response = client.put(
        "/api/v1/profile",
        json={
            "headline": "Senior product leader",
            "years_experience": 9,
            "target_roles": ["Director of Product"],
            "location_text": "New York, NY",
            "work_modes": ["remote", "hybrid"],
            "minimum_compensation": 180000,
        },
    )
    assert response.status_code == 200
    assert response.json()["target_roles"] == ["Director of Product"]

    switch_user("clerk_user_b", "b@example.com")
    isolated = client.get("/api/v1/profile")
    assert isolated.status_code == 200
    assert isolated.json() is None


def test_profile_rejects_invalid_input(client):
    response = client.put("/api/v1/profile", json={"years_experience": -3})
    assert response.status_code == 422
