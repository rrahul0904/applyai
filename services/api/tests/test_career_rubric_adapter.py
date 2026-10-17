from app.career_rubric import assess_career_rubric
from app.career_rubric_adapter import build_rubric_inputs_from_career_context


def _context():
    return {
        "candidate": {
            "profile_id": "profile-1",
            "current_title": "Senior Data Engineer",
            "skills": [
                {
                    "id": "skill-python",
                    "name": "Python",
                    "provenance": "USER_VERIFIED",
                },
                {
                    "id": "skill-kafka",
                    "name": "Kafka",
                    "provenance": "IMPORTED_UNVERIFIED",
                },
            ],
            "experiences": [
                {
                    "id": "exp-1",
                    "company_name": "Example Co",
                    "title": "Senior Data Engineer",
                    "description": "Owned architecture decisions for a shared data platform.",
                    "provenance": "USER_VERIFIED",
                }
            ],
            "career_memory": [
                {
                    "id": "fact-1",
                    "category": "impact",
                    "title": "Cost control",
                    "fact_text": "Reduced platform spend through storage lifecycle controls.",
                    "provenance": "USER_VERIFIED",
                }
            ],
        },
        "job": {
            "id": "job-1",
            "title": "Senior Data Architect",
            "seniority": "SENIOR",
            "skills": [
                {"id": "job-skill-python", "name": "Python", "required": True},
                {"id": "job-skill-kafka", "name": "Kafka", "required": True},
            ],
            "requirements": [
                {
                    "id": "req-autonomy",
                    "category": "GENERAL",
                    "text": "Own architecture decisions independently.",
                    "required": True,
                },
                {
                    "id": "req-impact",
                    "category": "GENERAL",
                    "text": "Own platform reliability and cost outcomes.",
                    "required": True,
                },
            ],
        },
    }


def _results(assessment):
    return {row.dimension_id: row for row in assessment.results}


def test_adapter_auto_links_only_exact_verified_structured_skills():
    bundle = build_rubric_inputs_from_career_context(_context())
    assessment = assess_career_rubric(
        candidate_revision=bundle.candidate_revision,
        job_revision=bundle.job_revision,
        requirements=bundle.requirements,
        evidence=bundle.evidence,
    )

    result = _results(assessment)["functional_knowledge"]
    assert result.coverage == "partial"
    assert result.fit_state == "unknown"
    assert result.supported_requirement_ids == ("job.skill.job-skill-python",)
    assert result.unsupported_requirement_ids == ("job.skill.job-skill-kafka",)


def test_free_text_requirements_and_evidence_require_explicit_links():
    context = _context()
    without_links = build_rubric_inputs_from_career_context(
        context,
        requirement_dimensions={
            "job.requirement.req-autonomy": "decision_scope",
            "job.requirement.req-impact": "business_accountability",
        },
    )
    baseline = assess_career_rubric(
        candidate_revision=without_links.candidate_revision,
        job_revision=without_links.job_revision,
        requirements=without_links.requirements,
        evidence=without_links.evidence,
    )
    baseline_results = _results(baseline)
    assert baseline_results["decision_scope"].coverage == "absent"
    assert baseline_results["business_accountability"].coverage == "absent"

    with_links = build_rubric_inputs_from_career_context(
        context,
        requirement_dimensions={
            "job.requirement.req-autonomy": "decision_scope",
            "job.requirement.req-impact": "business_accountability",
        },
        evidence_links={
            "candidate.experience.exp-1": ("job.requirement.req-autonomy",),
            "candidate.career_fact.fact-1": ("job.requirement.req-impact",),
        },
    )
    linked = assess_career_rubric(
        candidate_revision=with_links.candidate_revision,
        job_revision=with_links.job_revision,
        requirements=with_links.requirements,
        evidence=with_links.evidence,
    )
    linked_results = _results(linked)
    assert linked_results["decision_scope"].coverage == "strong"
    assert linked_results["business_accountability"].coverage == "strong"


def test_job_title_does_not_create_role_level_or_leadership_support():
    bundle = build_rubric_inputs_from_career_context(_context())
    assessment = assess_career_rubric(
        candidate_revision=bundle.candidate_revision,
        job_revision=bundle.job_revision,
        requirements=bundle.requirements,
        evidence=bundle.evidence,
    )
    results = _results(assessment)

    assert results["role_level_consistency"].coverage == "unknown"
    assert results["leadership_influence"].coverage == "unknown"


def test_context_revisions_change_when_candidate_or_job_changes():
    first = build_rubric_inputs_from_career_context(_context())
    second_context = _context()
    second_context["candidate"]["skills"][0]["name"] = "Python 3"
    second = build_rubric_inputs_from_career_context(second_context)

    assert first.candidate_revision != second.candidate_revision
    assert first.job_revision == second.job_revision
