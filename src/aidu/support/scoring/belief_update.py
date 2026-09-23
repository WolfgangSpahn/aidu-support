"""Project observable learner speech acts onto a student-belief vector.

The language model does not set belief-state values directly. It identifies
observable learner speech acts such as ``explain`` or ``ask_for_hint``. This
module then performs a deterministic state transition::

    b_next = clip_0_1(b_prior + clip_delta(M @ e))

``e`` is speech-act evidence, ``M`` is the coefficient matrix, and ``b`` is the
belief vector. Coefficients are conservative policy assumptions, not fitted
psychological parameters: magnitude ``1.0`` means a direct relationship,
``0.5`` an indirect one, and the sign gives the direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

from rich.console import Console
from rich.table import Table


# Dimensions which represent student beliefs.
BELIEF_DIMENSIONS = (
    "engagement", "confidence", "confusion", "frustration", "curiosity",
    "self_explanation", "guessing", "help_seeking",
)
# Evidence dimensions, directly derived from student or tutors utterances
SPEECH_ACT_DIMENSIONS = (
    "state", "hypothesize", "explain", "report_observation", "ask",
    "ask_for_explanation", "ask_for_hint", "ask_for_confirmation", "infer",
    "predict", "compare", "justify", "confirm", "reject", "identify_error",
    "express_uncertainty", "report_action", "propose_action", "commit_action",
    "acknowledge", "express_understanding", "express_nonunderstanding",
    "request_continue", "request_topic_change", "request_stop", "off_topic",
)

# Speech-act ontology admissibility. Every matrix column is valid for a student
# utterance; shared acts may also occur in tutor utterances, but tutor utterances
# are never inserted into the student-belief evidence vector.
_SHARED_SPEECH_ACTS = {
    "state", "hypothesize", "explain", "report_observation", "ask",
    "ask_for_explanation", "infer", "predict", "compare", "justify",
    "confirm", "reject", "identify_error", "acknowledge",
}
SPEECH_ACT_UTTERANCE_ROLES = {
    speech_act: "student/tutor" if speech_act in _SHARED_SPEECH_ACTS else "student"
    for speech_act in SPEECH_ACT_DIMENSIONS
}
# Define evidence scale and the per-turn safety cap.
# An item contributes strength * confidence, for example 0.10 * 0.8 = 0.08.
BELIEF_STRENGTH = {"weak": 0.05, "moderate": 0.10, "strong": 0.15}

MAX_BELIEF_DELTA_PER_TURN = 0.15

# Define the sparse transformation matrix.
# Outer keys are belief rows; inner keys are speech-act columns. Missing pairs
# are zero. Direct evidence uses magnitude 1.0; indirect evidence uses 0.5.
#
# These are reviewable hypotheses: stating a proposition weakly indicates
# confidence because it commits to truth; explicit uncertainty directly lowers
# confidence; explaining directly shows self-explanation. Frustration and
# guessing remain zero because a speech-act label alone does not establish them.
_COEFFICIENTS: dict[str, dict[str, float]] = {
    "engagement": {
        "hypothesize": 1.0, "explain": 0.5, "infer": 1.0, "predict": 0.5,
        "compare": 1.0, "justify": 0.5, "report_action": 0.5,
        "propose_action": 1.0, "commit_action": 1.0, "request_continue": 1.0,
        "request_stop": -1.0, "off_topic": -1.0,
    },
    "confidence": {
        "state": 0.5, "ask_for_confirmation": -0.5,
        "express_uncertainty": -1.0,
        "express_understanding": 1.0,
    },
    "confusion": {
        "express_uncertainty": 0.5, "express_understanding": -1.0,
        "express_nonunderstanding": 1.0,
    },
    "curiosity": {"predict": 1.0},
    "self_explanation": {"explain": 1.0, "justify": 1.0},
    "help_seeking": {
        "ask": 0.5, "ask_for_explanation": 1.0, "ask_for_hint": 1.0,
        "ask_for_confirmation": 1.0,
    },
}

# Expand the sparse coefficients into immutable matrix M.
SPEECH_ACT_TO_BELIEF_MATRIX = tuple(
    tuple(_COEFFICIENTS.get(belief, {}).get(act, 0.0) for act in SPEECH_ACT_DIMENSIONS)
    for belief in BELIEF_DIMENSIONS
)


@dataclass(frozen=True)
class BeliefEvidenceSignal:
    """One speech act with qualitative strength and assessor confidence."""

    speech_act: str
    strength: Literal["weak", "moderate", "strong"]
    confidence: float


def project_belief_state(
    prior: Mapping[str, float],
    evidence: Sequence[BeliefEvidenceSignal],
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """Return state, delta, and evidence vectors using ``state = prior + M·e``.

    Args:
        prior: Current belief values keyed by every ``BELIEF_DIMENSIONS`` name.
        evidence: Validated learner speech-act observations for one turn.

    Returns:
        Next state, capped belief delta, and aggregated evidence vector.

    Raises:
        KeyError: If a required prior dimension or strength label is missing.
        ValueError: If an evidence item contains an unknown speech act.

    Coefficient matrix (omitted cells are zero)::

        Speech act                engage  confidence  confusion  curiosity  self-explain  help-seek
        -------------------------|-------|-----------|----------|----------|-------------|---------
        hypothesize                 1.0
        explain                     0.5                                          1.0
        infer                       1.0
        predict                     0.5                               1.0
        compare                     1.0
        justify                     0.5                                          1.0
        report_action               0.5
        propose_action              1.0
        commit_action               1.0
        request_continue            1.0
        request_stop               -1.0
        off_topic                  -1.0
        ask_for_confirmation                   -0.5                                          1.0
        express_uncertainty                    -1.0        0.5
        express_understanding                   1.0       -1.0
        express_nonunderstanding                           1.0
        ask                                                                                  0.5
        ask_for_explanation                                                                  1.0
        ask_for_hint                                                                         1.0

    Coefficients express relationships, while strength and confidence are
    encoded in ``e[act] = strength_weight * confidence``.
    """

    # Map speech-act names to evidence-vector positions.
    act_index = {name: index for index, name in enumerate(SPEECH_ACT_DIMENSIONS)}

    # Build e by accumulating strength * confidence per speech act.
    evidence_vector = [0.0] * len(SPEECH_ACT_DIMENSIONS)
    for item in evidence:
        if item.speech_act not in act_index:
            raise ValueError(f"Unknown speech act {item.speech_act!r}.")
        evidence_vector[act_index[item.speech_act]] += (
            BELIEF_STRENGTH[item.strength] * item.confidence
        )

    # Compute M @ e, one dot product per belief dimension.
    raw_delta = [
        sum(coefficient * signal for coefficient, signal in zip(row, evidence_vector))
        for row in SPEECH_ACT_TO_BELIEF_MATRIX
    ]
    # Cap each dimension's total change for this turn.
    delta_vector = [
        max(-MAX_BELIEF_DELTA_PER_TURN, min(MAX_BELIEF_DELTA_PER_TURN, value))
        for value in raw_delta
    ]

    # Phase 5: Add the delta to the prior and keep values within [0, 1].
    state = {
        dimension: max(0.0, min(1.0, prior[dimension] + delta))
        for dimension, delta in zip(BELIEF_DIMENSIONS, delta_vector)
    }
    # Phase 6: Restore semantic names for callers and diagnostics.
    return (
        state,
        dict(zip(BELIEF_DIMENSIONS, delta_vector)),
        dict(zip(SPEECH_ACT_DIMENSIONS, evidence_vector)),
    )


def smoke_test(console: Console | None = None) -> dict[str, float]:
    """Run one visible matrix projection and return the derived belief state."""
    console = console or Console(width=200)
    prior = {dimension: 0.5 for dimension in BELIEF_DIMENSIONS}
    evidence = [
        BeliefEvidenceSignal("express_uncertainty", "strong", 0.8),
        BeliefEvidenceSignal("explain", "moderate", 0.9),
    ]
    state, delta, evidence_vector = project_belief_state(prior, evidence)

    # Retain the individual observations before aggregation into e.
    assessment_table = Table(title="Belief assessment evidence")
    assessment_table.add_column("Speech act")
    assessment_table.add_column("Strength")
    assessment_table.add_column("Strength weight", justify="right")
    assessment_table.add_column("Confidence", justify="right")
    assessment_table.add_column("Evidence weight", justify="right")
    for item in evidence:
        assessment_table.add_row(
            item.speech_act, item.strength,
            f"{BELIEF_STRENGTH[item.strength]:.3f}",
            f"{item.confidence:.2f}",
            f"{BELIEF_STRENGTH[item.strength] * item.confidence:.3f}",
        )
    console.print(assessment_table)

    # View 1: show the complete evidence vector e, including zero entries.
    evidence_table = Table(title="Evidence vector e (26 × 1)")
    evidence_table.add_column("Speech act")
    evidence_table.add_column("e(act)", justify="right")
    for speech_act in SPEECH_ACT_DIMENSIONS:
        evidence_table.add_row(
            speech_act,
            f"{evidence_vector[speech_act]:.3f}",
        )
    console.print(evidence_table)

    # View 2: show every coefficient. M is transposed only for display so that
    # speech-act names form readable rows instead of 26 terminal columns.
    matrix_table = Table(title="Full matrix M (8 × 26, transposed for display)")
    matrix_table.add_column("Speech act")
    matrix_table.add_column("Allowed utterance role")
    for dimension in BELIEF_DIMENSIONS:
        matrix_table.add_column(dimension, justify="right")
    for column, speech_act in enumerate(SPEECH_ACT_DIMENSIONS):
        matrix_table.add_row(
            speech_act,
            SPEECH_ACT_UTTERANCE_ROLES[speech_act],
            *(
                f"{row[column]:.1f}" if row[column] else ""
                for row in SPEECH_ACT_TO_BELIEF_MATRIX
            ),
        )
    console.print(matrix_table)

    # View 3: show the multiplication result and both clipping operations.
    raw_delta = {
        dimension: sum(
            coefficient * evidence_vector[speech_act]
            for coefficient, speech_act in zip(row, SPEECH_ACT_DIMENSIONS)
        )
        for dimension, row in zip(BELIEF_DIMENSIONS, SPEECH_ACT_TO_BELIEF_MATRIX)
    }
    state_table = Table(title="b_next = clip_0_1(b_prior + clip_delta(M · e))")
    state_table.add_column("Dimension")
    state_table.add_column("Prior", justify="right")
    state_table.add_column("Scoring evidence (coefficient × e)")
    state_table.add_column("M · e", justify="right")
    state_table.add_column("Capped delta", justify="right")
    state_table.add_column("Next", justify="right")
    for dimension, row in zip(BELIEF_DIMENSIONS, SPEECH_ACT_TO_BELIEF_MATRIX):
        contributions = "; ".join(
            f"{speech_act}: {coefficient:+.1f} × "
            f"{evidence_vector[speech_act]:.3f} = "
            f"{coefficient * evidence_vector[speech_act]:+.3f}"
            for coefficient, speech_act in zip(row, SPEECH_ACT_DIMENSIONS)
            if coefficient and evidence_vector[speech_act]
        )
        state_table.add_row(
            dimension,
            f"{prior[dimension]:.3f}",
            contributions or "No contributing evidence",
            f"{raw_delta[dimension]:+.3f}",
            f"{delta[dimension]:+.3f}",
            f"{state[dimension]:.3f}",
        )
    console.print(state_table)
    return state


if __name__ == "__main__":
    smoke_test()
