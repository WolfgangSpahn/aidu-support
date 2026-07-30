"""Dependency-free contracts for entry-test knowledge-prior scoring."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringOption:
    """One independently scored statement and its conceptual interpretations."""

    text: str
    targets: tuple[str, ...]


@dataclass(frozen=True)
class ScoringQuestion:
    """Canonical multiple-choice question used by the scoring calculation."""

    id: str
    options: tuple[ScoringOption, ...]
    solution: frozenset[int]


@dataclass(frozen=True)
class KnowledgePrior:
    """Initial target estimate plus the breadth of evidence behind it."""

    prior: float
    raw_score: float
    evidence_count: int
    question_count: int


@dataclass(frozen=True)
class TargetEvidence:
    """Reviewable intermediate evidence retained for scoring diagnostics."""

    values: tuple[float, ...]
    question_ids: frozenset[str]


@dataclass(frozen=True)
class EntryTestScore:
    """Complete standalone scoring result."""

    priors: dict[str, KnowledgePrior]
    evidence: dict[str, TargetEvidence]
