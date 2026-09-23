import pytest
from io import StringIO

from rich.console import Console
from aidu.support.scoring.knowledge_update import smoke_test

from aidu.support.scoring import (
    KnowledgeEvidenceState,
    TurnAssessment,
    apply_turn_assessment,
    assessment_weight,
    initialize_from_entry_prior,
    independence_factor,
    repeated_evidence_factor,
)


def assessment(**overrides):
    values = {
        "target": "electron-ions",
        "direction": "positive",
        "strength": "moderate",
        "confidence": 0.9,
        "evidence_type": "explanation",
        "response_mode": "deliberate",
        "support_level": "independent",
    }
    values.update(overrides)
    return TurnAssessment(**values)


def test_entry_prior_becomes_low_weight_evidence():
    state = initialize_from_entry_prior(prior=0.63, question_count=1)

    assert state.entry_weight == 0.75
    assert state.positive_evidence == pytest.approx(0.4725)
    assert state.negative_evidence == pytest.approx(0.2775)
    assert state.mastery == pytest.approx(0.63)
    assert state.source_count == 1


def test_reference_dialog_update():
    state = initialize_from_entry_prior(prior=0.54, question_count=1)
    updated, weight = apply_turn_assessment(
        state,
        assessment(),
        turn_index=1,
    )

    assert weight == pytest.approx(0.54)
    assert updated.mastery == pytest.approx(0.945 / 1.29)
    assert updated.turn_assessment_count == 1
    assert updated.last_updated_turn == 1


def test_negative_application_uses_negative_independence_policy():
    item = assessment(
        direction="negative",
        strength="strong",
        confidence=0.8,
        evidence_type="application",
        support_level="guided",
    )

    assert assessment_weight(item) == pytest.approx(0.72)


def test_response_mode_is_descriptive_not_an_extra_multiplier():
    deliberate = assessment(strength="weak", response_mode="deliberate")
    guess = assessment(strength="weak", response_mode="guess")

    assert assessment_weight(deliberate) == assessment_weight(guess)


def test_independence_factor_is_selected_by_direction_and_support():
    assert independence_factor(
        assessment(direction="positive", support_level="guided")
    ) == 0.5
    assert independence_factor(
        assessment(direction="negative", support_level="guided")
    ) == 0.9


def test_positive_answer_revealed_has_zero_weight():
    state = initialize_from_entry_prior(prior=0.5, question_count=1)
    updated, weight = apply_turn_assessment(
        state,
        assessment(support_level="answer_revealed"),
        turn_index=2,
    )

    assert weight == 0
    assert updated.mastery == state.mastery
    assert updated.source_count == state.source_count
    assert updated.turn_assessment_count == 1


def test_repetition_decay_and_turn_cap():
    assert repeated_evidence_factor(2) == pytest.approx(1 / 2.4)
    strong = assessment(
        strength="strong",
        confidence=1.0,
        evidence_type="application",
    )
    state = initialize_from_entry_prior(prior=0.5, question_count=1)

    _, weight = apply_turn_assessment(state, strong, turn_index=1)

    assert weight == 1.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target": ""},
        {"confidence": 1.1},
        {"direction": "unknown"},
        {"strength": "huge"},
        {"evidence_type": "other"},
        {"response_mode": "other"},
        {"support_level": "other"},
    ],
)
def test_invalid_assessment_contract_fails(kwargs):
    with pytest.raises(ValueError):
        assessment(**kwargs)


def test_mastery_without_evidence_is_neutral():
    state = KnowledgeEvidenceState(
        positive_evidence=0,
        negative_evidence=0,
        entry_prior=0.5,
        entry_weight=0,
        source_count=0,
        turn_assessment_count=0,
        last_updated_turn=None,
    )

    assert state.mastery == 0.5


def test_smoke_test_matches_production_shaped_state_transition():
    output = StringIO()
    report = smoke_test(Console(file=output, width=240))

    initial = report["initial_state"]["knowledge"]["proton-identity"]
    final = report["final_state"]["knowledge"]["proton-identity"]
    assert len(report["targets"]) == 3
    assert len(report["assessment"]["evidence"]) == 1
    assert initial["mastery"] == 0.5
    assert final["negative_evidence"] == pytest.approx(0.225)
    assert final["mastery"] == pytest.approx(0.5 / 1.225)
    assert "Learner quote" in output.getvalue()
    assert "Weight calculation" in output.getvalue()
    assert "0.25 × 0.90 × 1.00 × 1.00" in output.getvalue()
