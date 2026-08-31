from __future__ import annotations

import io
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from docx import Document
from pypdf import PdfWriter

from app.resumes import processor

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_TYPE = "application/pdf"


def docx_bytes(*paragraphs: str) -> bytes:
    buffer = io.BytesIO()
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    document.save(buffer)
    return buffer.getvalue()


def pdf_bytes(*, pages: int = 1, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    if encrypted:
        writer.encrypt("candidate-secret")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_valid_docx_remains_extractable() -> None:
    content = docx_bytes(
        "Candidate Name",
        "Senior Data Engineer",
        "Experience",
        "Built reliable data platforms with Python, SQL, AWS, and PostgreSQL.",
    )

    extracted = processor.extract_document_text(content, DOCX_TYPE)

    assert "Candidate Name" in extracted
    assert "Python" in extracted


def test_docx_requires_an_office_archive_signature() -> None:
    with pytest.raises(ValueError, match="INVALID_DOCX_SIGNATURE"):
        processor.extract_document_text(b"not-a-docx", DOCX_TYPE)


def test_docx_requires_core_office_members() -> None:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("random.txt", "not a document")

    with pytest.raises(ValueError, match="INVALID_DOCX_ARCHIVE"):
        processor.extract_document_text(buffer.getvalue(), DOCX_TYPE)


def test_docx_uncompressed_expansion_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(processor, "MAX_DOCX_UNCOMPRESSED_BYTES", 64)
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "x" * 80)

    with pytest.raises(ValueError, match="DOCX_EXPANSION_LIMIT_EXCEEDED"):
        processor.extract_document_text(buffer.getvalue(), DOCX_TYPE)


def test_docx_compression_ratio_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(processor, "MAX_DOCX_COMPRESSION_RATIO", 2)
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "a" * 2_000)

    with pytest.raises(ValueError, match="DOCX_COMPRESSION_RATIO_EXCEEDED"):
        processor.extract_document_text(buffer.getvalue(), DOCX_TYPE)


def test_pdf_requires_pdf_signature() -> None:
    with pytest.raises(ValueError, match="INVALID_PDF_SIGNATURE"):
        processor.extract_document_text(b"not-a-pdf", PDF_TYPE)


def test_encrypted_pdf_is_rejected() -> None:
    with pytest.raises(ValueError, match="ENCRYPTED_PDF"):
        processor.extract_document_text(pdf_bytes(encrypted=True), PDF_TYPE)


def test_pdf_page_count_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(processor, "MAX_PDF_PAGES", 1)

    with pytest.raises(ValueError, match="PDF_PAGE_LIMIT_EXCEEDED"):
        processor.extract_document_text(pdf_bytes(pages=2), PDF_TYPE)


def test_extracted_text_length_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(processor, "MAX_EXTRACTED_CHARACTERS", 20)
    content = docx_bytes("This paragraph exceeds the configured extraction character limit.")

    with pytest.raises(ValueError, match="EXTRACTED_TEXT_TOO_LARGE"):
        processor.extract_document_text(content, DOCX_TYPE)
