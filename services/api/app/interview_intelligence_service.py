from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.career_memory_models import CandidateCareerFact
from app.models import Company, Job, JobRequirement, JobSkill


PHASES = (
    (1, "RECRUITER", "Recruiter screen"),
    (2, "HIRING_MANAGER", "Hiring manager"),
    (3, "TECHNICAL", "Technical / case panel"),
    (4, "EXECUTIVE", "Executive / culture"),
)

STOPWORDS = {
    "and", "the", "with", "for", "that", "this", "from", "your", "you", "our", "will",
    "are", "have", "has", "into", "using", "work", "team", "role", "years", "experience",
    "skills", "about", "their", "they", "job", "who", "but", "not", "can", "all", "more",
}


@dataclass(slots=True)
class PreparationContext:
    job: Job
    company: Company
    skills: list[str]
    requirements: list[str]
    facts: list[CandidateCareerFact]
    sibling_jobs: list[Job]
    sibling_skills: list[str]


def _words(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}", text)]


def _keywords(text: str, limit: int = 12) -> list[str]:
    counts = Counter(word for word in _words(text) if word not in STOPWORDS)
    return [word for word, _ in counts.most_common(limit)]


def load_context(session: Session, user_id: Any, job_id: Any) -> PreparationContext:
    job = session.get(Job, job_id)
    if job is None:
        raise LookupError("JOB_NOT_FOUND")
    company = session.get(Company, job.company_id)
    if company is None:
        raise LookupError("COMPANY_NOT_FOUND")
    skills = list(session.scalars(select(JobSkill.name).where(JobSkill.job_id == job.id)))
    requirements = list(session.scalars(select(JobRequirement.text).where(JobRequirement.job_id == job.id)))
    facts = list(
        session.scalars(
            select(CandidateCareerFact)
            .where(
                CandidateCareerFact.user_id == user_id,
                CandidateCareerFact.archived_at.is_(None),
                CandidateCareerFact.user_verified.is_(True),
            )
            .order_by(CandidateCareerFact.occurred_at.desc().nullslast(), CandidateCareerFact.updated_at.desc())
            .limit(80)
        )
    )
    sibling_jobs = list(
        session.scalars(
            select(Job)
            .where(Job.normalized_title == job.normalized_title, Job.status == "ACTIVE")
            .order_by(Job.posted_at.desc().nullslast())
            .limit(250)
        )
    )
    sibling_ids = [item.id for item in sibling_jobs]
    sibling_skills = list(session.scalars(select(JobSkill.name).where(JobSkill.job_id.in_(sibling_ids)))) if sibling_ids else []
    return PreparationContext(
        job=job,
        company=company,
        skills=skills,
        requirements=requirements,
        facts=facts,
        sibling_jobs=sibling_jobs,
        sibling_skills=sibling_skills,
    )


def build_analysis(ctx: PreparationContext) -> dict[str, Any]:
    role_keywords = list(dict.fromkeys([*ctx.skills, *_keywords("\n".join(ctx.requirements) + "\n" + ctx.job.description)]))[:18]
    fact_text = "\n".join(fact.fact_text for fact in ctx.facts)
    fact_words = set(_words(fact_text))
    covered = [skill for skill in role_keywords if skill.lower() in fact_words or any(skill.lower() in _words(fact.fact_text) for fact in ctx.facts)]
    gaps = [skill for skill in role_keywords if skill not in covered][:8]
    market_counts = Counter(skill for skill in ctx.sibling_skills if skill)
    market_total = max(len(ctx.sibling_jobs), 1)
    market = [
        {
            "skill": skill,
            "job_mentions": count,
            "share_pct": min(100, round(count / market_total * 100)),
            "candidate_evidence": skill.lower() in fact_words,
        }
        for skill, count in market_counts.most_common(15)
    ]
    evidence = [
        {
            "id": str(fact.id),
            "category": fact.category,
            "title": fact.title,
            "text": fact.fact_text,
            "tags": fact.tags,
        }
        for fact in ctx.facts[:18]
    ]
    role_analysis = {
        "title": ctx.job.title,
        "seniority": ctx.job.seniority,
        "required_skills": ctx.skills[:20],
        "requirements": ctx.requirements[:16],
        "keywords": role_keywords,
        "likely_focus": role_keywords[:8],
    }
    company_research = {
        "company_name": ctx.company.canonical_name,
        "website_url": ctx.company.website_url,
        "description": ctx.company.description,
        "evidence_basis": "ApplyAI canonical company profile and current public job corpus",
        "known_openings_for_target_role": len(ctx.sibling_jobs),
        "hiring_signals": market[:8],
        "talking_points": [
            f"Connect your experience to {skill}." for skill in role_keywords[:3]
        ],
        "freshness_note": "This baseline works without an external research provider. Reviewed live-web sources can be added to the preparation as research evidence.",
    }
    resume_analysis = {
        "verified_evidence_count": len(ctx.facts),
        "matched_strengths": covered[:10],
        "gaps_to_prepare": gaps,
        "evidence": evidence,
    }
    market_benchmark = {
        "comparison_job_count": len(ctx.sibling_jobs),
        "role": ctx.job.title,
        "skills": market,
        "basis": "currently active ApplyAI job corpus with the same normalized title",
    }
    return {
        "company_research": company_research,
        "role_analysis": role_analysis,
        "resume_analysis": resume_analysis,
        "market_benchmark": market_benchmark,
    }


def _best_fact(ctx: PreparationContext, index: int = 0) -> str:
    if not ctx.facts:
        return "Use one verified example from your Career Memory and quantify your direct contribution and result."
    fact = ctx.facts[index % len(ctx.facts)]
    return fact.fact_text


def _model_answer(ctx: PreparationContext, question: str, index: int) -> str:
    evidence = _best_fact(ctx, index)
    return (
        f"Anchor the answer in this verified evidence: {evidence} "
        "State the situation briefly, your personal decision/action, the measurable result, and what you learned. "
        f"Tie the closing sentence back to {ctx.job.title} at {ctx.company.canonical_name}."
    )


def phase_content(ctx: PreparationContext, phase_number: int, phase_type: str, title: str) -> dict[str, Any]:
    top = (ctx.skills or _keywords(ctx.job.description, 8) or [ctx.job.title])[:6]
    behavioral = [
        "Tell me about a high-impact project you personally drove.",
        "Describe a difficult trade-off or disagreement and how you resolved it.",
        "Tell me about a failure or incident and what changed because of it.",
        "How do you influence stakeholders when you do not own the decision?",
    ]
    if phase_type == "RECRUITER":
        questions = [
            f"Why {ctx.company.canonical_name} and why this {ctx.job.title} role now?",
            "Walk me through the parts of your background most relevant to this role.",
            "What are you looking for in your next role and team?",
            "What constraints or timing should we know about?",
            *behavioral[:4],
        ]
        focus = ["motivation", "trajectory", "role fit", "communication", "logistics"]
    elif phase_type == "HIRING_MANAGER":
        questions = [
            *behavioral,
            f"How have you applied {top[0]} in production?",
            f"How would your experience with {top[min(1, len(top)-1)]} transfer to our environment?",
            "How do you prioritize when several important initiatives compete for capacity?",
            "What would your first 60 days in this role look like?",
        ]
        focus = ["ownership", "judgment", "execution", "leadership", "evidence"]
    elif phase_type == "TECHNICAL":
        questions = [
            f"Design a production approach for a realistic problem involving {top[0]}.",
            f"What failure modes would you expect around {top[min(1, len(top)-1)]}, and how would you detect them?",
            "Explain a system you designed: requirements, architecture, trade-offs, reliability, security, and cost.",
            "How would you debug a severe production regression with incomplete evidence?",
            "How do you validate data or system correctness before and after a migration?",
            f"Compare two viable approaches for {top[min(2, len(top)-1)]} and defend your choice.",
            "Describe your observability strategy and the signals you would page on.",
            "What would you simplify if you had to deliver half the scope in half the time?",
        ]
        focus = ["technical depth", "trade-offs", "failure modes", "verification", "clarity"]
    else:
        questions = [
            "What is the highest-leverage change you have led across teams?",
            "How do you communicate technical risk to an executive audience?",
            "Tell me about a decision where the technically strongest option was not the right business choice.",
            "How do you raise the performance of people or teams around you?",
            "What would you want this organization to be able to say you changed after one year?",
            *behavioral[:3],
        ]
        focus = ["strategy", "influence", "leadership", "business judgment", "culture"]
    questions = questions[:8]
    quiz = [
        {
            "id": f"{phase_number}-q-{index+1}",
            "question": question,
            "options": [correct, *distractors],
            "correct_index": 0,
            "explanation": explanation,
        }
        for index, (question, correct, distractors, explanation) in enumerate(
            [
                (f"What is the strongest opening for a {title} answer?", "Answer the exact question, then anchor it in relevant evidence.", ["Recite your resume chronologically.", "Start with every caveat you can think of.", "Give a generic industry definition."], "Directness plus evidence makes the answer easier to evaluate."),
                ("Which evidence is safest to use?", "A candidate-verified example from Career Memory.", ["A metric invented for impact.", "An unverified claim generated by AI.", "A competitor rumor."], "ApplyAI keeps interview coaching evidence-locked."),
                ("What makes a STAR answer stronger?", "Specific ownership and a measurable or observable result.", ["More adjectives.", "A longer setup.", "Avoiding the result."], "Interviewers need to distinguish your contribution from the team's."),
                ("When you do not know an answer, what should you do?", "State assumptions, reason visibly, and explain how you would verify.", ["Bluff confidently.", "Change the subject.", "Invent a production example."], "Transparent reasoning is more credible than unsupported certainty."),
                ("How should company research be used?", "Connect verified company signals to thoughtful role-specific questions.", ["Repeat headlines without context.", "Claim confidential knowledge.", "Assume every public signal is company policy."], "Research is useful when its source and inference boundary are clear."),
                ("What is the best way to handle a resume gap?", "Acknowledge it and show adjacent evidence plus a concrete learning plan.", ["Pretend the skill is on your resume.", "Attack the requirement.", "Avoid the topic entirely."], "Credible transferability beats fabricated experience."),
                ("What should the end of most answers accomplish?", "Tie the evidence back to the role or interviewer concern.", ["Introduce an unrelated story.", "Repeat the question verbatim.", "Apologize for the length."], "A short relevance bridge makes the signal explicit."),
                ("What should change after a completed interview round?", "Capture what happened and adapt preparation for the next round.", ["Delete prior prep.", "Restart with generic questions.", "Ignore unexpected questions."], "Round memory is how preparation compounds."),
            ][:8]
        )
    ]
    flashcards = [
        {"front": f"Your strongest {focus[index % len(focus)]} proof", "back": _best_fact(ctx, index)}
        for index in range(4)
    ]
    cheat_sheet = {
        "remember": [
            f"Role: {ctx.job.title}",
            f"Company: {ctx.company.canonical_name}",
            *[f"Strength to prove: {skill}" for skill in top[:3]],
        ],
        "stories": [_best_fact(ctx, index) for index in range(min(3, max(1, len(ctx.facts))))],
        "questions_to_ask": [
            f"What would outstanding performance in this {ctx.job.title} role look like after six months?",
            "Which problem is most urgent for the person joining this team to solve?",
            "What trade-offs or constraints shape the team's decisions today?",
        ],
    }
    return {
        "prep": {"focus": focus, "target_questions": questions, "carry_forward": []},
        "quiz": quiz,
        "flashcards": flashcards,
        "cheat_sheet": cheat_sheet,
        "questions": [
            {
                "mode": phase_type,
                "prompt": question,
                "model_answer": _model_answer(ctx, question, index),
                "rubric": {"relevance": 25, "specificity": 20, "ownership": 20, "result": 20, "clarity": 15},
                "followups": [
                    "What was your direct contribution rather than the team's?",
                    "How did you measure success?",
                    "What trade-off did you make and what would you change now?",
                ],
                "display_order": index + 1,
            }
            for index, question in enumerate(questions)
        ],
    }


def podcast_episodes(ctx: PreparationContext, analysis: dict[str, Any]) -> list[dict[str, Any]]:
    role = ctx.job.title
    company = ctx.company.canonical_name
    strengths = analysis["resume_analysis"].get("matched_strengths") or ctx.skills[:3]
    gaps = analysis["resume_analysis"].get("gaps_to_prepare") or []
    snippets = [
        (1, "The Briefing", 15, [
            ("Host A", f"Today we are preparing for {role} at {company}."),
            ("Host B", f"Start with the company signal: ApplyAI currently knows {analysis['company_research']['known_openings_for_target_role']} active openings for this role family."),
            ("Host A", "What should the candidate connect to the role?"),
            ("Host B", f"The strongest role signals are {', '.join(analysis['role_analysis']['likely_focus'][:6]) or 'the stated responsibilities'}. Use these as evidence-backed talking points."),
        ]),
        (2, "Role Deep Dive", 15, [
            ("Host A", "Where does the candidate already have strong evidence?"),
            ("Host B", f"Verified strengths include {', '.join(strengths[:6]) or 'the experiences stored in Career Memory'}."),
            ("Host A", "And where should preparation be more deliberate?"),
            ("Host B", f"Prepare honest transferability stories for {', '.join(gaps[:5]) or 'requirements without direct verified evidence'}. Never invent missing experience."),
        ]),
        (3, "Hard Questions", 15, [
            ("Host A", "Expect the panel to push beyond definitions."),
            ("Host B", "Answer in terms of requirements, trade-offs, failure modes, security, observability, cost, and verification."),
            ("Host A", "What if the candidate does not know?"),
            ("Host B", "State assumptions, reason visibly, and explain exactly how you would validate the answer in a real system."),
        ]),
        (4, "Mock Interview", 20, [
            ("Host A", "We will ask a question. Pause the episode and answer out loud before continuing."),
            ("Host B", "After each answer, compare your response with the evidence-locked model-answer structure in ApplyAI Practice."),
            ("Host A", f"First question: Why {company}, and why this {role} role now?"),
            ("Host B", "Pause now. Then check that your answer connects motivation, verified experience, and the problems this role needs to solve."),
        ]),
        (5, "Final Brief", 8, [
            ("Host A", "This is the interview-day reset."),
            ("Host B", f"Remember the role is {role}. Lead with your strongest evidence, keep answers specific, and close by tying them back to {company}."),
            ("Host A", "What should you ask them?"),
            ("Host B", "Ask what excellent performance looks like, which problem is most urgent, and which constraints shape the team's decisions."),
        ]),
    ]
    return [
        {
            "episode_number": number,
            "title": title,
            "duration_estimate_minutes": minutes,
            "summary": " ".join(text for _, text in script),
            "script": [{"speaker": speaker, "text": text} for speaker, text in script],
        }
        for number, title, minutes, script in snippets
    ]


def evaluate_answer(answer: str, model_answer: str, followups: list[str]) -> tuple[int, dict[str, Any]]:
    text = answer.strip()
    words = _words(text)
    word_count = len(words)
    numbers = bool(re.search(r"\b\d+(?:\.\d+)?%?\b", text))
    ownership = any(token in {"i", "my", "me"} for token in words)
    result_signal = any(token in words for token in ("result", "reduced", "increased", "improved", "saved", "delivered", "grew", "cut", "avoided"))
    structure = any(token in words for token in ("situation", "task", "action", "result"))
    concise = 45 <= word_count <= 260
    score = 25
    score += 15 if word_count >= 35 else max(0, word_count // 3)
    score += 15 if ownership else 0
    score += 15 if result_signal else 0
    score += 10 if numbers else 0
    score += 10 if structure else 0
    score += 10 if concise else 0
    score = min(100, score)
    strengths = []
    improvements = []
    (strengths if ownership else improvements).append("Make your personal ownership explicit." if not ownership else "Personal ownership is clear.")
    (strengths if result_signal else improvements).append("The answer includes an outcome." if result_signal else "Add a concrete outcome or observable result.")
    (strengths if numbers else improvements).append("You used a measurable detail." if numbers else "Add a metric when you have a verified one; do not invent it.")
    if not concise:
        improvements.append("Aim for roughly 45–260 words so the answer is complete without becoming a monologue.")
    feedback = {
        "word_count": word_count,
        "strengths": strengths,
        "improvements": improvements,
        "model_answer": model_answer,
        "next_followup": followups[0] if followups else "What would you change if you handled this again?",
        "dimensions": {
            "ownership": 100 if ownership else 35,
            "result": 100 if result_signal else 35,
            "quantification": 100 if numbers else 40,
            "structure": 100 if structure else 60,
            "clarity": 90 if concise else 60,
        },
        "scoring_note": "Deterministic coaching baseline. It rewards observable answer characteristics and never fabricates candidate evidence.",
    }
    return score, feedback


def readiness_from_scores(scores: list[int], completed_reflections: int, completed_notes: int, phase_count: int) -> dict[str, Any]:
    practice = round(sum(scores) / len(scores)) if scores else 45
    reflection = round(min(100, completed_reflections / max(phase_count, 1) * 100))
    notes = round(min(100, completed_notes / max(phase_count, 1) * 100))
    overall = round(practice * 0.7 + reflection * 0.2 + notes * 0.1)
    return {
        "overall": overall,
        "practice": practice,
        "round_learning": reflection,
        "notes": notes,
        "attempt_count": len(scores),
    }
