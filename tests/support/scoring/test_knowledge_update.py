import pytest

from aidu.support.scoring import (
    KnowledgeEvidenceState,
    TurnAssessment,
    apply_turn_assessment,
    assessment_weight,
    initialize_from_entry_prior,
    repeated_evidence_factor,
)


def assessment(**overrides):
    values = {
        "target": "electron-ions",
        "direction": "positive",
        "strength": "moderate",
        "confidence": 0.9,
        "evidence_type": "explanation",
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


def test_negative_application_uses_negative_support_policy():
    item = assessment(
        direction="negative",
        strength="strong",
        confidence=0.8,
        evidence_type="application",
        support_level="guided",
    )

    assert assessment_weight(item) == pytest.approx(0.864)


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
