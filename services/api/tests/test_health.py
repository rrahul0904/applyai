def test_health_and_readiness(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    ready = client.get("/ready")
    readiness = ready.json()
    assert ready.status_code in {200, 503}
    assert (ready.status_code == 200) is (readiness["status"] == "ready")
    assert {
        "database_reachable",
        "database_migrations_current",
        "storage_configured",
        "storage_reachable",
        "auth_provider",
        "auth_configured",
        "auth_instance_match",
        "operator_auth_configured",
        "operator_auth_location",
        "task_queue_configured",
        "background_worker_configured",
        "background_worker_healthy",
        "deployment_sha",
    } <= readiness.keys()
