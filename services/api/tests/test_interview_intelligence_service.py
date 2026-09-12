from app.interview_intelligence_service import evaluate_answer, readiness_from_scores


def test_evaluate_answer_rewards_specific_owned_measurable_results() -> None:
    vague_score, vague = evaluate_answer(
        "We worked on a migration and it went well.",
        "Use verified evidence.",
        ["What was your direct contribution?"],
    )
    strong_score, strong = evaluate_answer(
        "Situation: our migration window was at risk. I owned the cutover plan and changed the validation sequence. "
        "Action: I added parity checks, rollback criteria, and daily stakeholder reviews. Result: we reduced the "
        "planned outage by 35% and delivered the cutover without a rollback.",
        "Use verified evidence.",
        ["How did you measure success?"],
    )

    assert strong_score > vague_score
    assert strong["dimensions"]["ownership"] == 100
    assert strong["dimensions"]["quantification"] == 100
    assert strong["next_followup"] == "How did you measure success?"
    assert vague["dimensions"]["quantification"] < 100


def test_readiness_combines_practice_with_round_learning() -> None:
    baseline = readiness_from_scores([], completed_reflections=0, completed_notes=0, phase_count=4)
    prepared = readiness_from_scores([80, 90, 100], completed_reflections=3, completed_notes=4, phase_count=4)

    assert baseline["overall"] < prepared["overall"]
    assert prepared["practice"] == 90
    assert prepared["round_learning"] == 75
    assert prepared["notes"] == 100
    assert prepared["attempt_count"] == 3


def test_empty_readiness_is_stable_and_bounded() -> None:
    readiness = readiness_from_scores([], completed_reflections=0, completed_notes=0, phase_count=0)

    assert readiness == {
        "overall": 32,
        "practice": 45,
        "round_learning": 0,
        "notes": 0,
        "attempt_count": 0,
    }
