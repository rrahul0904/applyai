from app.jobs.ats_detector import detect_ats
from app.jobs.contracts import JobSourceType


def test_neogov_governmentjobs_detection_extracts_employer_identity():
    result = detect_ats("https://www.governmentjobs.com/careers/examplecity")
    assert result.provider == JobSourceType.NEOGOV
    assert result.source_identity == "examplecity"
    assert result.confidence >= 0.8


def test_pageup_reference_is_detected_from_employer_page_html():
    html = '<a href="https://careers.pageuppeople.com/123/cw/en/listing/">Jobs</a>'
    result = detect_ats("https://example.edu/careers", html)
    assert result.provider == JobSourceType.PAGEUP
    assert "matched:careers.pageuppeople.com" in result.evidence
