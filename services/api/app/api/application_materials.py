from __future__ import annotations

import textwrap
import unicodedata
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.candidate_workspace import candidate_context, get_owned_job
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import CandidateEducation, Company, JobSkill, User
from app.platform_models import ResumeStudioDocument

router = APIRouter(prefix="/career-v2", tags=["career preparation"])
KIT_KIND = "JOB_APPLICATION_KIT"


def _ascii(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "replace").decode("ascii")
    return " ".join(text.replace("\u0000", "").split())


def _date_label(value: date | None) -> str:
    return value.strftime("%b %Y") if value else ""


def _latest_kit(session: Session, user: User, job_id: uuid.UUID) -> ResumeStudioDocument | None:
    rows = list(
        session.scalars(
            select(ResumeStudioDocument)
            .where(ResumeStudioDocument.user_id == user.id, ResumeStudioDocument.job_id == job_id)
            .order_by(ResumeStudioDocument.updated_at.desc())
        )
    )
    return next((row for row in rows if isinstance(row.content, dict) and row.content.get("kind") == KIT_KIND), None)


def _skill_sets(session: Session, job_id: uuid.UUID, verified: set[str]) -> tuple[list[str], list[str], list[str]]:
    skills = list(
        session.scalars(
            select(JobSkill)
            .where(JobSkill.job_id == job_id)
            .order_by(JobSkill.required.desc(), JobSkill.name)
        )
    )
    matched = [skill.name for skill in skills if skill.normalized_name in verified]
    missing_required = [skill.name for skill in skills if skill.required and skill.normalized_name not in verified]
    preferred = [skill.name for skill in skills if not skill.required]
    return matched, missing_required, preferred


def _ats_score(session: Session, job_id: uuid.UUID, verified: set[str]) -> int:
    skills = list(session.scalars(select(JobSkill).where(JobSkill.job_id == job_id)))
    if not skills:
        return 70
    required = [skill for skill in skills if skill.required]
    preferred = [skill for skill in skills if not skill.required]
    required_ratio = sum(skill.normalized_name in verified for skill in required) / max(1, len(required))
    preferred_ratio = sum(skill.normalized_name in verified for skill in preferred) / max(1, len(preferred)) if preferred else 1.0
    return max(35, min(98, round(35 + required_ratio * 50 + preferred_ratio * 13)))


def _build_content(session: Session, user: User, job_id: uuid.UUID) -> dict:
    job = get_owned_job(job_id, session)
    company = session.get(Company, job.company_id)
    context = candidate_context(session, user)
    profile = context["profile"]
    verified_skills = {skill.normalized_name for skill in context["skills"]}
    matched, missing_required, preferred = _skill_sets(session, job.id, verified_skills)
    score = _ats_score(session, job.id, verified_skills)

    education = []
    if profile is not None:
        education = list(
            session.scalars(
                select(CandidateEducation)
                .where(CandidateEducation.profile_id == profile.id)
                .order_by(CandidateEducation.end_date.desc().nullslast())
            )
        )

    candidate_name = " ".join(part for part in (user.first_name, user.last_name) if part).strip() or user.email
    current_title = profile.current_title if profile and profile.current_title else "Candidate"
    years = profile.years_experience if profile else None
    company_name = company.canonical_name if company else "the hiring team"

    summary_parts = [f"{current_title} targeting {job.title} at {company_name}."]
    if years is not None:
        summary_parts.append(f"{years}+ years of verified professional experience.")
    if matched:
        summary_parts.append(f"Verified role-aligned strengths include {', '.join(matched[:6])}.")
    if profile and profile.summary:
        summary_parts.append(profile.summary.strip())
    tailored_summary = " ".join(summary_parts)

    experience_rows = []
    for item in context["experiences"][:8]:
        experience_rows.append(
            {
                "company": item.company_name,
                "title": item.title,
                "start": _date_label(item.start_date),
                "end": _date_label(item.end_date) or "Present",
                "description": item.description or "",
                "provenance": item.provenance,
            }
        )

    education_rows = [
        {
            "institution": item.institution,
            "degree": item.degree or "",
            "field": item.field_of_study or "",
            "start": _date_label(item.start_date),
            "end": _date_label(item.end_date),
            "provenance": item.provenance,
        }
        for item in education[:6]
    ]

    all_verified_skills = [skill.name for skill in context["skills"]]
    ordered_skills = matched + [skill for skill in all_verified_skills if skill not in matched]

    evidence_sentence = (
        f"My verified background aligns with this role through {', '.join(matched[:5])}."
        if matched
        else "My background is adjacent to this role, and I would welcome the chance to discuss the transferable experience I can substantiate."
    )
    experience_sentence = ""
    if context["experiences"]:
        lead = context["experiences"][0]
        experience_sentence = f" Most recently, I worked as {lead.title} at {lead.company_name}."

    cover_letter = (
        f"Dear {company_name} Hiring Team,\n\n"
        f"I am applying for the {job.title} opportunity. {evidence_sentence}{experience_sentence}\n\n"
        f"I am especially interested in the role because its requirements connect directly to the verified strengths listed in my ApplyAI profile. "
        f"I have intentionally left unsupported requirements out of this letter rather than presenting learning goals as professional experience."
        f"{' The main requirements I would be prepared to discuss as learning or development areas are ' + ', '.join(missing_required[:4]) + '.' if missing_required else ''}\n\n"
        f"I would value the opportunity to discuss how my experience and evidence-backed skills can contribute to {company_name}.\n\n"
        f"Sincerely,\n{candidate_name}"
    )

    return {
        "kind": KIT_KIND,
        "job": {"id": str(job.id), "title": job.title, "company": company_name},
        "candidate": {"name": candidate_name, "email": user.email, "current_title": current_title},
        "resume": {
            "headline": f"{current_title} | {job.title}",
            "summary": tailored_summary,
            "skills": ordered_skills[:18],
            "experience": experience_rows,
            "education": education_rows,
        },
        "cover_letter": cover_letter,
        "ats": {
            "score": score,
            "matched_skills": matched,
            "missing_required_skills": missing_required,
            "preferred_skills": preferred,
            "policy": "Only user-verified profile evidence is presented as candidate experience. Missing skills remain explicit gaps.",
        },
        "evidence_refs": [f"candidate:{user.id}", f"job:{job.id}"],
    }


def _payload(row: ResumeStudioDocument) -> dict:
    return {
        "id": row.id,
        "job_id": row.job_id,
        "title": row.title,
        "status": row.status,
        "version": row.version,
        "content": row.content,
        "downloads": {
            "resume_pdf": f"/api/v1/career-v2/application-kits/{row.id}/resume.pdf",
            "cover_letter_pdf": f"/api/v1/career-v2/application-kits/{row.id}/cover-letter.pdf",
        },
    }


def _pdf_escape(value: str) -> str:
    return _ascii(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_bytes(title: str, sections: list[tuple[str, list[str]]]) -> bytes:
    lines: list[tuple[str, bool, int]] = [(title, True, 16), ("", False, 10)]
    for heading, values in sections:
        lines.append((heading.upper(), True, 11))
        for value in values:
            clean = _ascii(value)
            if not clean:
                continue
            wrapped = textwrap.wrap(clean, width=86, break_long_words=False, replace_whitespace=True) or [""]
            lines.extend((part, False, 9) for part in wrapped)
        lines.append(("", False, 9))

    page_lines = [lines[index : index + 48] for index in range(0, len(lines), 48)] or [[("", False, 10)]]
    page_ids = [5 + index * 2 for index in range(len(page_lines))]
    content_ids = [page_id + 1 for page_id in page_ids]
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode(),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    }

    for page_id, content_id, page in zip(page_ids, content_ids, page_lines, strict=True):
        stream_parts = ["BT", "50 750 Td", "13 TL"]
        current_font = None
        for text, bold, size in page:
            font = "F2" if bold else "F1"
            key = (font, size)
            if key != current_font:
                stream_parts.append(f"/{font} {size} Tf")
                current_font = key
            stream_parts.append(f"({_pdf_escape(text)}) Tj")
            stream_parts.append("T*")
        stream_parts.append("ET")
        stream = "\n".join(stream_parts).encode("latin-1", "replace")
        objects[content_id] = f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode()

    maximum = max(objects)
    output = bytearray(b"%PDF-1.4\n%ApplyAI\n")
    offsets = [0] * (maximum + 1)
    for object_id in range(1, maximum + 1):
        offsets[object_id] = len(output)
        output.extend(f"{object_id} 0 obj\n".encode())
        output.extend(objects[object_id])
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {maximum + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for object_id in range(1, maximum + 1):
        output.extend(f"{offsets[object_id]:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {maximum + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def _resume_pdf(content: dict) -> bytes:
    resume = content.get("resume", {})
    candidate = content.get("candidate", {})
    sections: list[tuple[str, list[str]]] = [
        ("Contact", [f"{candidate.get('name', '')} | {candidate.get('email', '')}", resume.get("headline", "")]),
        ("Summary", [resume.get("summary", "")]),
        ("Verified skills", [", ".join(resume.get("skills", []))]),
    ]
    experience_lines = []
    for item in resume.get("experience", []):
        experience_lines.extend([
            f"{item.get('title', '')} — {item.get('company', '')} ({item.get('start', '')}–{item.get('end', '')})",
            item.get("description", ""),
        ])
    sections.append(("Experience", experience_lines))
    education_lines = []
    for item in resume.get("education", []):
        degree = " ".join(part for part in (item.get("degree"), item.get("field")) if part)
        education_lines.append(f"{degree} — {item.get('institution', '')} {item.get('end', '')}".strip())
    if education_lines:
        sections.append(("Education", education_lines))
    return _pdf_bytes(f"{candidate.get('name', 'Candidate')} — Tailored Resume", sections)


def _cover_letter_pdf(content: dict) -> bytes:
    candidate = content.get("candidate", {})
    letter = str(content.get("cover_letter", ""))
    return _pdf_bytes(
        f"{candidate.get('name', 'Candidate')} — Cover Letter",
        [("Letter", [paragraph for paragraph in letter.split("\n") if paragraph.strip()])],
    )


@router.post("/jobs/{job_id}/application-kit")
def create_application_kit(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    job = get_owned_job(job_id, session)
    content = _build_content(session, user, job.id)
    existing = _latest_kit(session, user, job.id)
    company_name = content["job"]["company"]
    title = f"{company_name} — {job.title} application kit"
    if existing is None:
        existing = ResumeStudioDocument(user_id=user.id, job_id=job.id, title=title, content=content, status="REVIEWED", version=1)
        session.add(existing)
    else:
        existing.title = title
        existing.content = content
        existing.status = "REVIEWED"
        existing.version += 1
    session.commit()
    session.refresh(existing)
    return _payload(existing)


@router.get("/jobs/{job_id}/application-kit")
def get_application_kit(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    get_owned_job(job_id, session)
    row = _latest_kit(session, user, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Application kit not generated")
    return _payload(row)


def _owned_kit(kit_id: uuid.UUID, user: User, session: Session) -> ResumeStudioDocument:
    row = session.scalar(select(ResumeStudioDocument).where(ResumeStudioDocument.id == kit_id, ResumeStudioDocument.user_id == user.id))
    if row is None or not isinstance(row.content, dict) or row.content.get("kind") != KIT_KIND:
        raise HTTPException(status_code=404, detail="Application kit not found")
    return row


@router.get("/application-kits/{kit_id}/resume.pdf")
def download_resume_pdf(kit_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> Response:
    row = _owned_kit(kit_id, user, session)
    filename = f"applyai-resume-{row.job_id}.pdf"
    return Response(_resume_pdf(row.content), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store"})


@router.get("/application-kits/{kit_id}/cover-letter.pdf")
def download_cover_letter_pdf(kit_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> Response:
    row = _owned_kit(kit_id, user, session)
    filename = f"applyai-cover-letter-{row.job_id}.pdf"
    return Response(_cover_letter_pdf(row.content), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store"})
