from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceBackedItem(StrictOutputModel):
    evidence_refs: list[str] = Field(min_length=1, max_length=12)


class DeepMatchOutput(StrictOutputModel):
    ai_score: int = Field(ge=0, le=100)
    priority: Literal["PRIORITIZE", "CONSIDER", "STRETCH", "SKIP"]
    summary: str = Field(min_length=1, max_length=1800)
    strengths: list[str] = Field(max_length=8)
    gaps: list[str] = Field(max_length=8)
    interview_risks: list[str] = Field(max_length=8)
    recommended_actions: list[str] = Field(max_length=8)
    evidence_refs: list[str] = Field(min_length=1, max_length=24)


class ResumeEdit(EvidenceBackedItem):
    source_text: str = Field(min_length=1, max_length=5000)
    suggested_text: str = Field(min_length=1, max_length=5000)
    reason: str = Field(min_length=1, max_length=1500)
    risk_flags: list[str] = Field(max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)


class ResumeTailoringOutput(StrictOutputModel):
    strategy_summary: str = Field(min_length=1, max_length=2000)
    edits: list[ResumeEdit] = Field(min_length=1, max_length=20)
    evidence_refs: list[str] = Field(min_length=1, max_length=30)


class ApplicationAnswerDraft(EvidenceBackedItem):
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=5000)


class ApplicationCopilotOutput(StrictOutputModel):
    cover_letter: str = Field(min_length=1, max_length=12000)
    cover_letter_evidence_refs: list[str] = Field(min_length=1, max_length=30)
    questions: list[ApplicationAnswerDraft] = Field(max_length=12)
    recruiter_message: str = Field(min_length=1, max_length=4000)
    recruiter_message_evidence_refs: list[str] = Field(min_length=1, max_length=20)
    strategy_notes: list[str] = Field(max_length=8)
    evidence_refs: list[str] = Field(min_length=1, max_length=40)


class InterviewQuestion(EvidenceBackedItem):
    question: str = Field(min_length=1, max_length=1200)
    why_it_matters: str = Field(min_length=1, max_length=1800)
    answer_outline: str = Field(min_length=1, max_length=5000)


class InterviewPrepOutput(StrictOutputModel):
    strategy_summary: str = Field(min_length=1, max_length=2500)
    likely_questions: list[InterviewQuestion] = Field(min_length=3, max_length=15)
    questions_to_ask: list[str] = Field(min_length=3, max_length=12)
    skill_gap_plan: list[str] = Field(max_length=10)
    evidence_refs: list[str] = Field(min_length=1, max_length=40)


OUTPUT_MODELS = {
    "AI_DEEP_MATCH": DeepMatchOutput,
    "AI_RESUME_TAILOR": ResumeTailoringOutput,
    "AI_APPLICATION_COPILOT": ApplicationCopilotOutput,
    "AI_INTERVIEW_PREP": InterviewPrepOutput,
}
