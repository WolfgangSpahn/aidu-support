"""Canonical weighted-evidence updates for learner knowledge.

For one assessment, the evidence weight is::

    w = strength × confidence × independence × repetition

The weight is added to positive or negative evidence. Mastery is their weighted
ratio. These coefficients are conservative scoring policy, not fitted learner
parameters.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
from typing import Any, Literal

from rich.console import Console
from rich.table import Table


Direction = Literal["positive", "negative"]
Strength = Literal["weak", "moderate", "strong"]
EvidenceType = Literal[
    "recall",
    "explanation",
    "application",
    "correction",
]
ResponseMode = Literal["deliberate", "uncertain", "guess"]
SupportLevel = Literal[
    "independent",
    "small_prompt",
    "guided",
    "explicit_hint",
    "answer_revealed",
]

# Entry evidence has limited weight so dialog evidence can revise it.
ENTRY_WEIGHT_PER_QUESTION = 0.75
MAX_TARGET_WEIGHT_PER_TURN = 1.0
REPETITION_DECAY = 0.7
DEFAULT_PRIOR_WEIGHT = 1.0

# Numeric model parameters. Evidence type and response mode remain descriptive.
STRENGTH_WEIGHT = {
    "weak": 0.25,
    "moderate": 0.6,
    "strong": 1.0,
}
EVIDENCE_TYPES = {"recall", "explanation", "application", "correction"}
RESPONSE_MODES = {"deliberate", "uncertain", "guess"}
SUPPORT_LEVELS = {
    "independent", "small_prompt", "guided", "explicit_hint", "answer_revealed",
}
POSITIVE_INDEPENDENCE_FACTOR = {
    "independent": 1.0,
    "small_prompt": 0.8,
    "guided": 0.5,
    "explicit_hint": 0.25,
    "answer_revealed": 0.0,
}
NEGATIVE_INDEPENDENCE_FACTOR = {
    "independent": 1.0,
    "small_prompt": 1.0,
    "guided": 0.9,
    "explicit_hint": 0.7,
    "answer_revealed": 0.3,
}


@dataclass(frozen=True)
class KnowledgeEvidenceState:
    """Authoritative accumulated evidence for one learning target."""

    positive_evidence: float
    negative_evidence: float
    entry_prior: float
    entry_weight: float
    source_count: int
    turn_assessment_count: int
    last_updated_turn: int | None
    evidence_fingerprints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("positive_evidence", "negative_evidence", "entry_weight"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative.")
        if not 0.0 <= self.entry_prior <= 1.0:
            raise ValueError("entry_prior must be between 0 and 1.")
        if self.source_count < 0 or self.turn_assessment_count < 0:
            raise ValueError("Evidence counts must be non-negative.")
        if self.last_updated_turn is not None and self.last_updated_turn < 0:
            raise ValueError("last_updated_turn must be non-negative.")

    @property
    def evidence_weight(self) -> float:
        return self.positive_evidence + self.negative_evidence

    @property
    def mastery(self) -> float:
        """Return positive evidence divided by total weighted evidence."""
        # Targets without an entry test still need a small neutral prior.
        # Otherwise one tiny observation makes mastery exactly 0 or 1.
        fallback_weight = DEFAULT_PRIOR_WEIGHT if self.entry_weight == 0 else 0.0
        total_weight = self.evidence_weight + fallback_weight
        if total_weight == 0:
            return self.entry_prior
        return (
            self.positive_evidence + self.entry_prior * fallback_weight
        ) / total_weight


@dataclass(frozen=True)
class TurnAssessment:
    """One validated target-specific observation from a learner turn."""

    target: str
    direction: Direction
    strength: Strength
    confidence: float
    evidence_type: EvidenceType
    response_mode: ResponseMode
    support_level: SupportLevel

    def __post_init__(self) -> None:
        if not self.target.strip():
            raise ValueError("target must be a non-empty string.")
        if self.direction not in {"positive", "negative"}:
            raise ValueError(f"Invalid direction {self.direction!r}.")
        if self.strength not in STRENGTH_WEIGHT:
            raise ValueError(f"Invalid strength {self.strength!r}.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1.")
        if self.evidence_type not in EVIDENCE_TYPES:
            raise ValueError(f"Invalid evidence_type {self.evidence_type!r}.")
        if self.response_mode not in RESPONSE_MODES:
            raise ValueError(f"Invalid response_mode {self.response_mode!r}.")
        if self.support_level not in SUPPORT_LEVELS:
            raise ValueError(f"Invalid support_level {self.support_level!r}.")


def initialize_from_entry_prior(
    *,
    prior: float,
    question_count: int,
) -> KnowledgeEvidenceState:
    """Convert a quiz prior into low-weight positive and negative evidence."""

    # Phase 1: Validate the entry-test result and its evidence count.
    if not 0.0 <= prior <= 1.0:
        raise ValueError("prior must be between 0 and 1.")
    if (
        isinstance(question_count, bool)
        or not isinstance(question_count, int)
        or question_count <= 0
    ):
        raise ValueError("question_count must be a positive integer.")
    # Phase 2: Split the entry weight according to the observed prior score.
    entry_weight = question_count * ENTRY_WEIGHT_PER_QUESTION
    return KnowledgeEvidenceState(
        positive_evidence=prior * entry_weight,
        negative_evidence=(1.0 - prior) * entry_weight,
        entry_prior=prior,
        entry_weight=entry_weight,
        source_count=1,
        turn_assessment_count=0,
        last_updated_turn=None,
    )


def repeated_evidence_factor(previous_related_assessments: int) -> float:
    """Return ``1 / (1 + decay × previous evidence count)``."""

    if isinstance(previous_related_assessments, bool) or previous_related_assessments < 0:
        raise ValueError("previous_related_assessments must be a non-negative integer.")
    return 1.0 / (1.0 + REPETITION_DECAY * previous_related_assessments)


def independence_factor(assessment: TurnAssessment) -> float:
    """Return how diagnostic the observation is of independent mastery."""
    factors = (
        POSITIVE_INDEPENDENCE_FACTOR
        if assessment.direction == "positive"
        else NEGATIVE_INDEPENDENCE_FACTOR
    )
    return factors[assessment.support_level]


def assessment_weight(
    assessment: TurnAssessment,
    *,
    previous_related_assessments: int = 0,
) -> float:
    """Calculate ``strength × confidence × independence × repetition``."""

    # Positive evidence is discounted more strongly when help was provided;
    # negative evidence remains informative even after learner support.
    return (
        STRENGTH_WEIGHT[assessment.strength]
        * assessment.confidence
        * independence_factor(assessment)
        * repeated_evidence_factor(previous_related_assessments)
    )


def apply_turn_assessment(
    state: KnowledgeEvidenceState,
    assessment: TurnAssessment,
    *,
    turn_index: int,
    previous_related_assessments: int = 0,
    remaining_target_weight: float = MAX_TARGET_WEIGHT_PER_TURN,
) -> tuple[KnowledgeEvidenceState, float]:
    """Add one capped assessment weight to the accumulated evidence state."""

    # Phase 1: Validate turn metadata and calculate the capped weight.
    if turn_index < 0:
        raise ValueError("turn_index must be non-negative.")
    if remaining_target_weight < 0:
        raise ValueError("remaining_target_weight must be non-negative.")
    weight = min(
        assessment_weight(
            assessment,
            previous_related_assessments=previous_related_assessments,
        ),
        remaining_target_weight,
    )
    # Phase 2: Add the weight to the direction selected by the assessor.
    positive = state.positive_evidence
    negative = state.negative_evidence
    if assessment.direction == "positive":
        positive += weight
    else:
        negative += weight
    # Phase 3: Return an immutable replacement with updated provenance.
    return (
        replace(
            state,
            positive_evidence=positive,
            negative_evidence=negative,
            source_count=state.source_count + (1 if weight > 0 else 0),
            turn_assessment_count=state.turn_assessment_count + 1,
            last_updated_turn=turn_index,
        ),
        weight,
    )


def smoke_test(console: Console | None = None) -> dict[str, Any]:
    """Run production-shaped evidence over a target list and show both states."""
    console = console or Console(width=150)
    targets = [
        {"id": "neutron-identity", "text": "Identify neutrons in an atom."},
        {"id": "proton-identity", "text": "Identify an element from its proton count."},
        {"id": "electron-ions", "text": "Explain how electrons create ions."},
    ]
    assessment = {
        "evidence": [{
            "target": "proton-identity",
            "direction": "negative",
            "strength": "weak",
            "confidence": 0.9,
            "evidence_type": "recall",
            "response_mode": "guess",
            "support_level": "independent",
            "quote": "Nitrogen I guess",
        }],
        "review": False,
    }

    # Initialize every configured target exactly as a session without an entry
    # test: neutral prior, no accumulated evidence, and no provenance.
    states = {
        target["id"]: KnowledgeEvidenceState(
            positive_evidence=0.0,
            negative_evidence=0.0,
            entry_prior=0.5,
            entry_weight=0.0,
            source_count=0,
            turn_assessment_count=0,
            last_updated_turn=None,
        )
        for target in targets
    }

    def serialize_state(state: KnowledgeEvidenceState) -> dict[str, Any]:
        return {"mastery": state.mastery, **asdict(state)}

    initial_state = {
        target: serialize_state(state) for target, state in states.items()
    }

    # Apply the same TurnAssessment contract and fingerprint provenance used by
    # the director integration. Omitted targets remain unchanged.
    applied_weights: dict[str, float] = {}
    for item in assessment["evidence"]:
        turn_assessment = TurnAssessment(**{
            key: item[key]
            for key in (
                "target", "direction", "strength", "confidence",
                "evidence_type", "response_mode", "support_level",
            )
        })
        updated, weight = apply_turn_assessment(
            states[item["target"]],
            turn_assessment,
            turn_index=2,
        )
        fingerprint = hashlib.sha256(
            f"2\0{item['target']}\0{item['quote'].casefold()}".encode("utf-8")
        ).hexdigest()
        states[item["target"]] = replace(
            updated,
            evidence_fingerprints=(*updated.evidence_fingerprints, fingerprint),
        )
        applied_weights[item["target"]] = weight

    final_state = {
        target: serialize_state(state) for target, state in states.items()
    }
    report = {
        "targets": targets,
        "assessment": assessment,
        "initial_state": {"knowledge": initial_state},
        "final_state": {"knowledge": final_state},
    }

    # View the configured targets and the one-or-two evidence items selected by
    # the production assessment contract.
    evidence_table = Table(title="Knowledge assessment evidence")
    evidence_table.add_column("Target")
    evidence_table.add_column("Learner quote")
    evidence_table.add_column("Direction")
    evidence_table.add_column("Strength")
    evidence_table.add_column("Confidence", justify="right")
    evidence_table.add_column("Type")
    evidence_table.add_column("Response mode")
    evidence_table.add_column("Support")
    evidence_table.add_column("Weight calculation")
    evidence_table.add_column("Applied weight", justify="right")
    for item in assessment["evidence"]:
        observation = TurnAssessment(**{
            key: item[key]
            for key in (
                "target", "direction", "strength", "confidence",
                "evidence_type", "response_mode", "support_level",
            )
        })
        evidence_table.add_row(
            item["target"], item["quote"], item["direction"], item["strength"],
            f"{item['confidence']:.2f}", item["evidence_type"],
            item["response_mode"], item["support_level"],
            f"{STRENGTH_WEIGHT[observation.strength]:.2f} × "
            f"{observation.confidence:.2f} × "
            f"{independence_factor(observation):.2f} × "
            f"{repeated_evidence_factor(0):.2f}",
            f"{applied_weights[item['target']]:.3f}",
        )
    console.print(evidence_table)
    console.print("Weight = strength × confidence × independence × repetition; "
                  f"capped at {MAX_TARGET_WEIGHT_PER_TURN:.2f} per target and turn.")

    # Show the initial-to-final transition for every target, including those
    # for which the assessor returned no evidence.
    state_table = Table(title="Knowledge state: initial → final")
    state_table.add_column("Target")
    state_table.add_column("Initial mastery", justify="right")
    state_table.add_column("Final mastery", justify="right")
    state_table.add_column("Positive", justify="right")
    state_table.add_column("Negative", justify="right")
    state_table.add_column("Sources", justify="right")
    for target in targets:
        target_id = target["id"]
        state_table.add_row(
            target_id,
            f"{initial_state[target_id]['mastery']:.6f}",
            f"{final_state[target_id]['mastery']:.6f}",
            f"{final_state[target_id]['positive_evidence']:.3f}",
            f"{final_state[target_id]['negative_evidence']:.3f}",
            str(final_state[target_id]["source_count"]),
        )
    console.print(state_table)
    console.print_json(data=report)
    return report


if __name__ == "__main__":
    smoke_test()
