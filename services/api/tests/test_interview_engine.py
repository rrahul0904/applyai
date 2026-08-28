from app.interview_engine import (
    DeterministicInterviewEngine,
    InterviewEvidence,
    InterviewMode,
    InterviewRequest,
    RigorInterviewEngine,
    RigorProviderConfig,
    choose_interview_engine,
)


def request(mode=InterviewMode.TECHNICAL):
    return InterviewRequest(
        candidate_id="candidate-1",
        job_id="job-1",
        mode=mode,
        target_role="Senior Data Engineer",
        verified_skills=("Python", "SQL", "Snowflake"),
        evidence=(InterviewEvidence(kind="resume", reference="exp:1", summary="Verified role"),),
    )


def test_deterministic_engine_is_evidence_locked():
    session = DeterministicInterviewEngine().create_session(request())
    assert session.provider == "applyai-deterministic"
    assert len(session.questions) == 3
    assert session.metadata["evidence_locked"] is True
    assert session.questions[0].evidence_refs == ("exp:1",)


def test_coding_and_sql_are_marked_for_external_execution():
    session = DeterministicInterviewEngine().create_session(request(InterviewMode.SQL))
    assert all(question.execution_required for question in session.questions)
    assert session.metadata["external_execution"] is False


def test_rigor_is_fail_closed_until_reviewed_contract_is_enabled():
    rigor = RigorInterviewEngine(RigorProviderConfig(base_url="https://rigor.invalid"))
    engine = choose_interview_engine(prefer_rigor=True, rigor=rigor)
    assert isinstance(engine, DeterministicInterviewEngine)


def test_enabled_rigor_placeholder_still_refuses_unconfigured_remote_calls():
    rigor = RigorInterviewEngine(RigorProviderConfig(base_url="https://rigor.invalid", enabled=True))
    try:
        rigor.create_session(request())
    except RuntimeError as exc:
        assert str(exc) == "RIGOR_REMOTE_CONTRACT_NOT_CONFIGURED"
    else:
        raise AssertionError("Rigor integration must fail closed before a reviewed API contract exists")
