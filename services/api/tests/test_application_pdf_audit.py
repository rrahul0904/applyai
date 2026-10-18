"""Pure PDF QA unit tests; no database, provider or external network."""

from __future__ import annotations

import io

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.ai.application_pdf_audit import audit_application_pdf


def make_pdf(*, pages: int = 1, name: str = "Jane Example", email: str = "jane@example.com", dates: str = "2019-2024") -> bytes:
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    for _ in range(pages):
        pdf.drawString(50, 750, f"{name}  {email}")
        pdf.drawString(50, 720, f"Verified data engineering experience {dates}; Python SQL Azure Cloud Architecture")
        pdf.drawString(50, 700, "Produced reliable data pipelines and managed auditable evidence-based delivery outcomes.")
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def codes(result: dict) -> dict[str, bool]:
    return {check["code"]: check["passed"] for check in result["checks"]}


def test_valid_resume_passes_static_checks_without_claiming_visual_inspection():
    result = audit_application_pdf(
        make_pdf(pages=2),
        kind="resume", candidate_name="Jane Example", candidate_email="jane@example.com",
        required_phrases=("Python", "Azure"),
    )
    assert result["verdict"] == "PASS"
    assert result["page_count"] == 2
    assert result["visual_inspection"] == "NOT_PERFORMED"
    assert all(codes(result).values())
    assert "Jane Example" not in str(result)
    assert "jane@example.com" not in str(result)


def test_overlong_cover_letter_fails_page_limit():
    result = audit_application_pdf(make_pdf(pages=2), kind="cover_letter", candidate_name="Jane Example", candidate_email="jane@example.com")
    assert result["verdict"] == "NEEDS_REVIEW"
    assert codes(result)["page_limit"] is False


def test_missing_contact_and_requirements_fail_closed():
    result = audit_application_pdf(make_pdf(), kind="resume", candidate_name="Someone Else", candidate_email="missing@example.com", required_phrases=("Snowflake",))
    assert result["verdict"] == "NEEDS_REVIEW"
    assert not codes(result)["candidate_name_present"]
    assert not codes(result)["candidate_email_present"]
    assert not codes(result)["verified_phrase_0_present"]


def test_invalid_pdf_does_not_leak_raw_data_or_raise_parser_detail():
    result = audit_application_pdf(b"%PDF-invalid Jane Example jane@example.com", kind="resume", candidate_name="Jane Example", candidate_email="jane@example.com")
    assert result["verdict"] == "NEEDS_REVIEW"
    assert result["checks"][-1]["code"] == "pdf_parseable_and_unencrypted"
    assert result["checks"][-1]["passed"] is False
    assert "jane@example.com" not in str(result)


def test_oversize_blob_fails_without_parsing():
    result = audit_application_pdf(b"%PDF-" + b"a" * (10 * 1024 * 1024), kind="resume", candidate_name="Jane Example", candidate_email="jane@example.com")
    assert result["verdict"] == "NEEDS_REVIEW"
    assert codes(result)["pdf_container"] is False


def test_invalid_kind_rejected():
    try:
        audit_application_pdf(b"", kind="other", candidate_name="Jane", candidate_email="jane@example.com")
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported document kind was not rejected")
