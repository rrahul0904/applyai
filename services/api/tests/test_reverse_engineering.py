from app.reverse_engineering import (
    ApplyAIFit,
    FitScope,
    JourneyStage,
    classify_topic,
    taxonomy_payload,
)


def classify(title: str, summary: str) -> dict:
    return classify_topic(title=title, summary=summary)


def test_terum_evaluation_is_partial_infrastructure() -> None:
    result = classify(
        "Terum Skills / Claude Skills Evaluation",
        (
            "Agent evaluation with A/B evaluation, baseline arm, candidate arm, regression detection, "
            "immutable evaluation receipts, provenance, trigger precision and cost measurement."
        ),
    )
    assert result["applyai_fit"] == ApplyAIFit.INFRASTRUCTURE.value
    assert result["fit_scope"] == FitScope.PARTIAL.value
    assert result["destination"] == "platform-infrastructure"
    assert JourneyStage.MEASURE_READINESS.value in result["candidate_journey_stages"]


def test_candidate_job_resume_and_application_workflows_are_core() -> None:
    result = classify(
        "Candidate command center",
        "Job discovery, job matching, resume tailoring, application tracking, and recruiter lens.",
    )
    assert result["applyai_fit"] == ApplyAIFit.CORE.value
    assert result["fit_scope"] == FitScope.FULL.value
    assert JourneyStage.DISCOVER_JOBS.value in result["candidate_journey_stages"]
    assert JourneyStage.IMPROVE_RESUME_PROFILE.value in result["candidate_journey_stages"]


def test_interview_tutor_and_mock_practice_are_prepare() -> None:
    result = classify(
        "Interview coach",
        "AI tutor with interview prep, mock interview, question bank, coding practice, and skill gap learning.",
    )
    assert result["applyai_fit"] == ApplyAIFit.PREPARE.value
    assert result["destination"] == "prepare"
    assert JourneyStage.PRACTICE_MOCKS.value in result["candidate_journey_stages"]


def test_salary_and_career_navigation_are_intelligence() -> None:
    result = classify(
        "Career radar",
        "Salary intelligence, market intelligence, company intelligence, and career navigation.",
    )
    assert result["applyai_fit"] == ApplyAIFit.INTELLIGENCE.value
    assert result["destination"] == "career-intelligence"


def test_mcp_specialist_execution_is_integration() -> None:
    result = classify(
        "External coding engine",
        "MCP interoperability with a sandbox execution engine and external assessment API integration.",
    )
    assert result["applyai_fit"] == ApplyAIFit.INTEGRATION.value
    assert result["fit_scope"] == FitScope.PARTIAL.value


def test_unrelated_product_is_not_applyai() -> None:
    result = classify(
        "Growth toolkit",
        "SEO automation for ecommerce video generation and crypto trading.",
    )
    assert result["applyai_fit"] == ApplyAIFit.NOT_APPLYAI.value
    assert result["fit_scope"] == FitScope.NONE.value
    assert result["destination"] == "separate-product"


def test_unknown_topic_fails_closed_to_not_applyai() -> None:
    result = classify("Unclassified utility", "A generic utility with no career context.")
    assert result["applyai_fit"] == ApplyAIFit.NOT_APPLYAI.value


def test_taxonomy_exposes_required_reverse_engineering_summary_contract() -> None:
    payload = taxonomy_payload()
    assert payload["classifier_version"]
    assert [item["fit"] for item in payload["classifications"]] == [
        "CORE",
        "PREPARE",
        "INTELLIGENCE",
        "INFRASTRUCTURE",
        "INTEGRATION",
        "NOT_APPLYAI",
    ]
    assert payload["summary_contract"][0] == "ApplyAI Fit"
    assert "Capabilities to keep separate" in payload["summary_contract"]
