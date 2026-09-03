from app.core.pulseatlas import event_for_request


def test_pulseatlas_api_events_are_body_blind():
    assert event_for_request("GET", "/health", 200) == ("health_check", "health", {"component": "applyai-api", "status": "ok"})
    assert event_for_request("POST", "/api/v1/applications", 201) == ("application_created", "product", {})
    assert event_for_request("PATCH", "/api/v1/applications/9d1c3d9a-20cc-4f5d-9ed6-9dcedbdf1afb/status", 200) == ("application_status_changed", "product", {})
    assert event_for_request("POST", "/api/v1/resumes", 201) is None
    assert event_for_request("POST", "/api/v1/applications", 422) is None
