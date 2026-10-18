"""Read-only, evidence-neutral PDF export checks for an application draft.

This is a *static preflight*, not an ATS compatibility certification, visual
inspection, or a replacement for candidate approval. Report only check codes,
never extracted candidate data. Designed for a later durable quality-gate step.
"""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from typing import Literal

from pypdf import PdfReader

DocumentKind = Literal["resume", "cover_letter"]
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PAGES = {"resume": 2, "cover_letter": 1}
_UNICODE_DATE_RANGE = re.compile(r"\b(?:19|20)\d{2}\s*[\u2013\u2014]\s*(?:19|20)\d{2}\b")


def _fold(value: str) -> str:
    """Normalize text for presence checks without changing the PDF itself."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def audit_application_pdf(
    pdf: bytes,
    *,
    kind: DocumentKind,
    candidate_name: str,
    candidate_email: str,
    required_phrases: tuple[str, ...] = (),
) -> dict:
    """Return deterministic, non-PII quality evidence for a generated PDF.

    Checks are deliberately conservative and fail closed on malformed/encrypted
    output. required_phrases must be derived from the *verified* profile or
    actual job requirements, not invented ATS keywords.
    """
    if kind not in MAX_PAGES:
        raise ValueError("kind must be 'resume' or 'cover_letter'")
    if not isinstance(pdf, bytes):
        raise TypeError("pdf must be bytes")

    checks: list[dict[str, bool | str]] = []

    def record(code: str, passed: bool) -> None:
        checks.append({"code": code, "passed": passed})

    fingerprint = hashlib.sha256(pdf).hexdigest()
    valid_container = bool(pdf.startswith(b"%PDF-") and 0 < len(pdf) <= MAX_PDF_BYTES)
    record("pdf_container", valid_container)
    if not valid_container:
        return {
            "verdict": "NEEDS_REVIEW",
            "document_sha256": fingerprint,
            "kind": kind,
            "page_count": None,
            "extractable_characters": 0,
            "checks": checks,
            "visual_inspection": "NOT_PERFORMED",
        }

    page_count: int | None = None
    extracted = ""
    try:
        reader = PdfReader(io.BytesIO(pdf), strict=True)
        if reader.is_encrypted:
            raise ValueError("encrypted PDF")
        page_count = len(reader.pages)
        extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
        record("pdf_parseable_and_unencrypted", True)
    except Exception:
        record("pdf_parseable_and_unencrypted", False)
        return {
            "verdict": "NEEDS_REVIEW",
            "document_sha256": fingerprint,
            "kind": kind,
            "page_count": page_count,
            "extractable_characters": 0,
            "checks": checks,
            "visual_inspection": "NOT_PERFORMED",
        }

    record("page_limit", 0 < page_count <= MAX_PAGES[kind])
    characters = len("".join(extracted.split()))
    record("text_layer_readable", characters >= 80 and "\ufffd" not in extracted)
    folded = _fold(extracted)
    record("candidate_name_present", bool(_fold(candidate_name)) and _fold(candidate_name) in folded)
    record("candidate_email_present", bool(candidate_email.strip()) and _fold(candidate_email) in folded)
    record("date_ranges_ascii_safe", not bool(_UNICODE_DATE_RANGE.search(extracted)))
    for index, phrase in enumerate(required_phrases):
        record(f"verified_phrase_{index}_present", bool(_fold(phrase)) and _fold(phrase) in folded)

    return {
        "verdict": "PASS" if all(check["passed"] for check in checks) else "NEEDS_REVIEW",
        "document_sha256": fingerprint,
        "kind": kind,
        "page_count": page_count,
        "extractable_characters": characters,
        "checks": checks,
        "visual_inspection": "NOT_PERFORMED",
    }
