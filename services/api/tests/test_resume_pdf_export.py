import base64
import io
import re

import pytest
from pypdf import PdfReader

from app.resumes.pdf_export import UnsupportedPdfText, export_resume_pdf


def extracted_pdf(content):
    reader = PdfReader(io.BytesIO(content))
    return reader, "\n".join(page.extract_text() for page in reader.pages)


def compact(text):
    return re.sub(r"\s+", "", text)


def test_pdf_is_one_page_extractable_text_with_literal_punctuation():
    source = "Alex Rivera\nalex@example.com\nEXPERIENCE\nBuilt Python (SQL) pipelines; saved $1,200 and 30%.\nEDUCATION\nExample University, 2020-2024"
    pdf = export_resume_pdf(source)
    reader, text = extracted_pdf(pdf.content)
    assert pdf.page_count == len(reader.pages) == 1
    assert compact(source) == compact(text)
    assert reader.pages[0].get("/Annots") is None


def test_pdf_paginates_instead_of_truncating_long_lines_or_chronology():
    source = "FIRST IDENTITY\n" + "\n".join(
        f"Experience {index:03d}: " + "Supported verified candidate experience. " * 5
        for index in range(100)
    ) + "\nFINAL CHRONOLOGY 1999-2026\n" + "unbroken" * 80
    pdf = export_resume_pdf(source)
    reader, text = extracted_pdf(pdf.content)
    assert pdf.page_count == len(reader.pages) > 1
    assert compact(source) == compact(text)
    assert "FIRST IDENTITY" in reader.pages[0].extract_text()
    assert "FINAL CHRONOLOGY" in text


@pytest.mark.parametrize("text", ["李明", "Hidden\x00text", "Hidden\u200btext"])
def test_pdf_explicitly_rejects_unrenderable_text_without_loss(text):
    with pytest.raises(UnsupportedPdfText):
        export_resume_pdf(text)


def test_pdf_preserves_supported_international_names_and_currency():
    source = "Zoë García\nSaved €1,000 and £500; achieved 20% improvement."
    _, text = extracted_pdf(export_resume_pdf(source).content)
    assert compact(source) == compact(text)


@pytest.mark.parametrize("long", [False, True])
def test_resume_studio_pdf_reports_actual_page_count_and_preserves_saved_state(client, long):
    summary = "Verified Python engineer with 4 years of experience."
    lines = [f"Verified achievement {index}: improved latency by 30%." for index in range(140 if long else 3)]
    created = client.post("/api/v1/resume-studio", json={
        "title": "Engineering resume", "status": "REVIEWED",
        "content": {"summary": summary, "sections": [{"heading": "Experience", "body": lines}]},
    })
    assert created.status_code == 201, created.text
    before = created.json()
    exported = client.get(f"/api/v1/resume-studio/{before['id']}/export?format=pdf")
    assert exported.status_code == 200, exported.text
    file = exported.json()
    assert file["filename"] == "Engineering-resume.pdf"
    assert file["content_type"] == "application/pdf"
    assert file["content_encoding"] == "base64"
    reader, text = extracted_pdf(base64.b64decode(file["content"], validate=True))
    assert "a@example.com" in text
    assert summary in text
    assert "EXPERIENCE" in text
    for line in lines:
        assert line in text
    assert len(reader.pages) == file["composition"]["page_count"]
    assert (len(reader.pages) > 1) is long
    assert file["composition"]["page_status"] == ("OVERFLOW_REQUIRES_REVIEW" if long else "WITHIN_ONE_PAGE_TARGET")
    assert file["composition"]["extractable_text"] is True
    assert file["composition"]["universal_ats_compatibility"] == "NOT_CLAIMED"
    after = client.get(f"/api/v1/resume-studio/{before['id']}").json()
    assert after["status"] == before["status"] == "REVIEWED"
    assert after["version"] == before["version"]
    assert after["content"] == before["content"]


def test_pdf_export_is_candidate_owned(client, switch_user):
    created = client.post("/api/v1/resume-studio", json={"title": "Private resume", "content": {"summary": "Candidate A only"}}).json()
    switch_user("candidate_b", "b@example.com")
    denied = client.get(f"/api/v1/resume-studio/{created['id']}/export?format=pdf")
    assert denied.status_code == 404
    assert "Candidate A only" not in denied.text


def test_pdf_unsupported_characters_leave_text_export_available(client):
    created = client.post("/api/v1/resume-studio", json={"title": "Resume", "content": {"summary": "李明"}}).json()
    rejected = client.get(f"/api/v1/resume-studio/{created['id']}/export?format=pdf")
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "PDF_TEXT_UNSUPPORTED"
    text_export = client.get(f"/api/v1/resume-studio/{created['id']}/export?format=txt")
    assert text_export.status_code == 200
    assert text_export.json()["content"] == "李明"
