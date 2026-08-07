from app.main import app


def test_platform_completion_public_openapi_surface():
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/saved-searches",
        "/api/v1/notifications",
        "/api/v1/analytics/summary",
        "/api/v1/contacts",
        "/api/v1/resume-studio",
        "/api/v1/interview-practice",
        "/api/v1/submissions",
        "/api/v1/semantic-matches",
        "/api/v1/company-intelligence/jobs/{job_id}",
        "/api/v1/employer/organizations",
        "/api/v1/billing/subscription",
        "/api/v1/account/export",
        "/api/v1/account",
    }
    assert expected.issubset(paths.keys())
