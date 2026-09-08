def test_health_and_readiness(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "database_reachable": True,
        "auth_provider": "clerk",
        "operator_auth_configured": False,
        "operator_auth_location": "api",
        "storage_configured": True,
        "internal_auth_configured": False,
        "supabase_project_fingerprint": "",
        "clerk_instance_fingerprint": "",
    }
