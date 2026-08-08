import pytest

from app.jobs.ats_detector import detect_ats
from app.jobs.contracts import JobSourceType


@pytest.mark.parametrize(
    ("url", "provider"),
    [
        ("https://company.wd1.myworkdaysite.com/en-US/careers", JobSourceType.WORKDAY),
        ("https://careers.smartrecruiters.com/example", JobSourceType.SMARTRECRUITERS),
        ("https://jobs.jobvite.com/example", JobSourceType.JOBVITE),
        ("https://example.bamboohr.com/careers", JobSourceType.BAMBOOHR),
        ("https://example.applytojob.com/apply/abc", JobSourceType.JAZZHR),
        ("https://example.recruiting.paylocity.com/recruiting/jobs", JobSourceType.PAYLOCITY),
        ("https://example.csod.com/ux/ats/careersite/1/home", JobSourceType.CORNERSTONE),
        ("https://example.pageuppeople.com/cw/en/listing", JobSourceType.PAGEUP),
    ],
)
def test_detects_extended_ats_families(url, provider):
    result = detect_ats(url)
    assert result.provider == provider
    assert result.confidence >= 0.82
    assert result.source_identity
