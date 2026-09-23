import pytest
from io import StringIO

from rich.console import Console

from aidu.support.scoring import BeliefEvidenceSignal, project_belief_state
from aidu.support.scoring.belief_update import smoke_test


def neutral_belief():
    return {
        "engagement": 0.5,
        "confidence": 0.5,
        "confusion": 0.5,
        "frustration": 0.5,
        "curiosity": 0.5,
        "self_explanation": 0.5,
        "guessing": 0.5,
        "help_seeking": 0.5,
    }


def test_matrix_projects_speech_act_evidence_to_belief_delta():
    state, delta, evidence = project_belief_state(
        neutral_belief(),
        [BeliefEvidenceSignal(
            speech_act="express_uncertainty",
            strength="strong",
            confidence=1.0,
        )],
    )

    assert evidence["express_uncertainty"] == pytest.approx(0.15)
    assert delta["confidence"] == pytest.approx(-0.15)
    assert delta["confusion"] == pytest.approx(0.075)
    assert state["confidence"] == pytest.approx(0.35)
    assert state["confusion"] == pytest.approx(0.575)


def test_matrix_caps_accumulated_dimension_delta_per_turn():
    state, delta, _ = project_belief_state(
        neutral_belief(),
        [
            BeliefEvidenceSignal("explain", "strong", 1.0),
            BeliefEvidenceSignal("justify", "strong", 1.0),
        ],
    )

    assert delta["self_explanation"] == pytest.approx(0.15)
    assert state["self_explanation"] == pytest.approx(0.65)


def test_state_weakly_increases_expressed_confidence():
    state, delta, _ = project_belief_state(
        neutral_belief(),
        [BeliefEvidenceSignal("state", "strong", 1.0)],
    )

    assert delta["confidence"] == pytest.approx(0.075)
    assert state["confidence"] == pytest.approx(0.575)


def test_smoke_view_explains_evidence_and_belief_contributions():
    output = StringIO()
    state = smoke_test(Console(file=output, width=240))

    rendered = output.getvalue()
    assert "Belief assessment evidence" in rendered
    assert "Strength weight" in rendered
    assert "express_uncertainty: -1.0 × 0.120 = -0.120" in rendered
    assert "explain: +1.0 × 0.090 = +0.090" in rendered
    assert "No contributing evidence" in rendered
    assert state["confidence"] == pytest.approx(0.38)
    assert state["self_explanation"] == pytest.approx(0.59)
