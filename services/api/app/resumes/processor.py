import io
import re
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

from docx import Document
from pypdf import PdfReader
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.storage import ObjectStorageProvider
from app.durability_models import ResumeProcessingAttempt
from app.models import ResumeExtraction, ResumeVersion


PARSER_VERSION = "deterministic-v1"


class OcrProvider(ABC):
    @abstractmethod
    def extract(self, content: bytes, content_type: str) -> str:
        raise NotImplementedError


def extract_document_text(content: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if (
        content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ):
        document = Document(io.BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    raise ValueError("UNSUPPORTED_DOCUMENT_TYPE")


def parse_month(value: str) -> str | None:
    value = value.strip()
    for fmt in ("%Y-%m", "%Y", "%b %Y", "%B %Y"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.date().replace(day=1).isoformat()
        except ValueError:
            continue
    return None


def split_date_range(value: str) -> tuple[str | None, str | None]:
    parts = re.split(r"\s+(?:-|–|—|to)\s+", value.strip(), maxsplit=1)
    start = parse_month(parts[0]) if parts else None
    end = None
    if len(parts) > 1 and parts[1].lower() not in {"present", "current"}:
        end = parse_month(parts[1])
    return start, end


def structure_resume(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    section = "basic"
    sections: dict[str, list[str]] = {
        "basic": [],
        "experience": [],
        "education": [],
        "skills": [],
        "certifications": [],
    }
    headings = {
        "experience": "experience",
        "professional experience": "experience",
        "work experience": "experience",
        "education": "education",
        "skills": "skills",
        "technical skills": "skills",
        "certifications": "certifications",
    }
    for line in lines:
        normalized = line.lower().rstrip(":")
        if normalized in headings:
            section = headings[normalized]
            continue
        sections[section].append(line)

    email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    name = next(
        (
            line
            for line in sections["basic"]
            if "@" not in line and not re.search(r"\d{3}[-.)\s]\d{3}", line)
        ),
        None,
    )
    current_title = sections["basic"][1] if len(sections["basic"]) > 1 else None

    experiences: list[dict] = []
    achievements: list[str] = []
    for line in sections["experience"]:
        if line.startswith(("•", "-", "*")):
            bullet = line.lstrip("•-* ").strip()
            if bullet:
                achievements.append(bullet)
                if experiences:
                    existing = experiences[-1].get("description") or ""
                    experiences[-1]["description"] = "\n".join(
                        item for item in [existing, bullet] if item
                    )
            continue
        parts = [part.strip() for part in re.split(r"\s*\|\s*", line)]
        if len(parts) >= 2:
            start_date, end_date = split_date_range(parts[2]) if len(parts) >= 3 else (None, None)
            experiences.append(
                {
                    "title": parts[0],
                    "company_name": parts[1],
                    "start_date": start_date,
                    "end_date": end_date,
                    "description": None,
                    "provenance": "DOCUMENT_EXTRACTED",
                }
            )

    education: list[dict] = []
    for line in sections["education"]:
        parts = [part.strip() for part in re.split(r"\s*\|\s*", line)]
        if not parts:
            continue
        degree_parts = [part.strip() for part in parts[0].split(",", maxsplit=1)]
        education.append(
            {
                "degree": degree_parts[0] or None,
                "field_of_study": degree_parts[1] if len(degree_parts) > 1 else None,
                "institution": parts[1] if len(parts) > 1 else "Not specified",
                "start_date": None,
                "end_date": parse_month(parts[2]) if len(parts) > 2 else None,
                "provenance": "DOCUMENT_EXTRACTED",
            }
        )

    skill_text = ", ".join(sections["skills"])
    skills = [
        {"name": skill.strip(), "provenance": "DOCUMENT_EXTRACTED"}
        for skill in re.split(r"[,;•]", skill_text)
        if skill.strip()
    ]
    certifications = [
        item.lstrip("•-* ").strip()
        for item in sections["certifications"]
        if item.lstrip("•-* ").strip()
    ]

    return {
        "basic_profile": {
            "name": name,
            "email": email_match.group(0) if email_match else None,
            "current_title": current_title,
            "provenance": "DOCUMENT_EXTRACTED",
        },
        "experiences": experiences,
        "education": education,
        "skills": skills,
        "certifications": certifications,
        "achievements": achievements,
    }


def process_resume_version(
    resume_version_id: uuid.UUID,
    storage: ObjectStorageProvider,
) -> None:
    settings = get_settings()
    with SessionLocal() as session:
        version = session.scalar(
            select(ResumeVersion)
            .where(ResumeVersion.id == resume_version_id)
            .with_for_update()
        )
        if version is None or version.processing_status in {"NEEDS_REVIEW", "COMPLETED"}:
            return
        if version.upload_status != "UPLOADED":
            return

        extraction = session.scalar(
            select(ResumeExtraction).where(
                ResumeExtraction.resume_version_id == version.id,
                ResumeExtraction.parser_version == PARSER_VERSION,
            )
        )
        if extraction is not None and extraction.status in {"NEEDS_REVIEW", "COMPLETED"}:
            version.processing_status = extraction.status
            session.commit()
            return

        latest_attempt = session.scalar(
            select(ResumeProcessingAttempt)
            .where(
                ResumeProcessingAttempt.resume_version_id == version.id,
                ResumeProcessingAttempt.parser_version == PARSER_VERSION,
            )
            .order_by(ResumeProcessingAttempt.attempt_number.desc())
            .limit(1)
        )
        if latest_attempt is not None and latest_attempt.status == "PROCESSING":
            lease_until = latest_attempt.started_at + timedelta(
                seconds=settings.sqs_visibility_timeout_seconds * 2
            )
            if lease_until > datetime.now(timezone.utc):
                # Another delivery is actively processing this version. The durable
                # extraction/attempt rows make it safe to acknowledge this duplicate.
                return
            latest_attempt.status = "ABANDONED"
            latest_attempt.completed_at = datetime.now(timezone.utc)

        next_attempt = (
            session.scalar(
                select(func.coalesce(func.max(ResumeProcessingAttempt.attempt_number), 0)).where(
                    ResumeProcessingAttempt.resume_version_id == version.id,
                    ResumeProcessingAttempt.parser_version == PARSER_VERSION,
                )
            )
            or 0
        ) + 1
        attempt = ResumeProcessingAttempt(
            resume_version_id=version.id,
            parser_version=PARSER_VERSION,
            attempt_number=next_attempt,
            status="PROCESSING",
        )
        session.add(attempt)

        if extraction is None:
            extraction = ResumeExtraction(
                resume_version_id=version.id,
                parser_version=PARSER_VERSION,
                status="PROCESSING",
            )
            session.add(extraction)
        else:
            extraction.status = "PROCESSING"
            extraction.error_code = None
        version.processing_status = "PROCESSING"
        session.commit()

        try:
            content = storage.get(key=version.storage_key)
            text = extract_document_text(content, version.content_type).strip()
            extraction.extracted_text = text or None
            if len(text) < 120 or len(text.split()) < 20:
                extraction.structured_data = None
                extraction.status = "NEEDS_REVIEW"
                extraction.error_code = "INSUFFICIENT_TEXT"
            else:
                extraction.structured_data = structure_resume(text)
                extraction.status = "NEEDS_REVIEW"
                extraction.error_code = None
            version.processing_status = "NEEDS_REVIEW"
            attempt.status = "COMPLETED"
            attempt.completed_at = datetime.now(timezone.utc)
            session.commit()
        except Exception as exc:
            error_code = (
                str(exc) if str(exc) in {"UNSUPPORTED_DOCUMENT_TYPE"} else "EXTRACTION_FAILED"
            )
            extraction.status = "FAILED"
            extraction.error_code = error_code
            version.processing_status = "FAILED"
            attempt.status = "FAILED"
            attempt.error_code = error_code
            attempt.completed_at = datetime.now(timezone.utc)
            session.commit()
