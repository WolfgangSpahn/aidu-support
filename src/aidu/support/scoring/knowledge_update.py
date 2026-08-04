"""Canonical weighted-evidence updates for learner knowledge.

This module owns the mathematics shared by entry tests, dialog assessment, and
deterministic applet evidence.  It has no dependency on the backend, Pydantic,
an LLM provider, or persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal


Direction = Literal["positive", "negative"]
Strength = Literal["weak", "moderate", "strong"]
EvidenceType = Literal[
    "recall",
    "explanation",
    "application",
    "correction",
    "guess",
    "hinted_response",
]
SupportLevel = Literal[
    "independent",
    "small_prompt",
    "guided",
    "explicit_hint",
    "answer_revealed",
]

ENTRY_WEIGHT_PER_QUESTION = 0.75
MAX_TARGET_WEIGHT_PER_TURN = 1.0
REPETITION_DECAY = 0.7
DEFAULT_PRIOR_WEIGHT = 1.0

STRENGTH_WEIGHT = {
    "weak": 0.25,
    "moderate": 0.6,
    "strong": 1.0,
}
EVIDENCE_TYPE_FACTOR = {
    "recall": 0.7,
    "explanation": 1.0,
    "application": 1.2,
    "correction": 0.8,
    "guess": 0.2,
    "hinted_response": 0.35,
}
POSITIVE_SUPPORT_FACTOR = {
    "independent": 1.0,
    "small_prompt": 0.7,
    "guided": 0.45,
    "explicit_hint": 0.25,
    "answer_revealed": 0.0,
}
NEGATIVE_SUPPORT_FACTOR = {
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
        if self.evidence_type not in EVIDENCE_TYPE_FACTOR:
            raise ValueError(f"Invalid evidence_type {self.evidence_type!r}.")
        if self.support_level not in POSITIVE_SUPPORT_FACTOR:
            raise ValueError(f"Invalid support_level {self.support_level!r}.")


def initialize_from_entry_prior(
    *,
    prior: float,
    question_count: int,
) -> KnowledgeEvidenceState:
    """Convert a quiz prior into deliberately low-weight pseudo-evidence."""

    if not 0.0 <= prior <= 1.0:
        raise ValueError("prior must be between 0 and 1.")
    if (
        isinstance(question_count, bool)
        or not isinstance(question_count, int)
        or question_count <= 0
    ):
        raise ValueError("question_count must be a positive integer.")
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
    """Reduce correlated evidence after earlier observations in one episode."""

    if isinstance(previous_related_assessments, bool) or previous_related_assessments < 0:
        raise ValueError("previous_related_assessments must be a non-negative integer.")
    return 1.0 / (1.0 + REPETITION_DECAY * previous_related_assessments)


def assessment_weight(
    assessment: TurnAssessment,
    *,
    previous_related_assessments: int = 0,
) -> float:
    """Calculate the uncapped contribution of one assessment."""

    support_factors = (
        POSITIVE_SUPPORT_FACTOR
        if assessment.direction == "positive"
        else NEGATIVE_SUPPORT_FACTOR
    )
    return (
        STRENGTH_WEIGHT[assessment.strength]
        * assessment.confidence
        * EVIDENCE_TYPE_FACTOR[assessment.evidence_type]
        * support_factors[assessment.support_level]
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
    """Return updated evidence and the applied, per-target-capped weight."""

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
    positive = state.positive_evidence
    negative = state.negative_evidence
    if assessment.direction == "positive":
        positive += weight
    else:
        negative += weight
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
