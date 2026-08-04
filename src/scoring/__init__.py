"""Standalone public entry point for AIDu's entry-test scoring.

The implementation remains canonical under ``aidu.support.scoring``.  This
package provides the shorter import path intended for independent review.
"""

from aidu.support.scoring import (
    MISSED_CORRECT,
    REJECTED_WRONG,
    SELECTED_CORRECT,
    SELECTED_WRONG,
    EntryTestScore,
    KnowledgeEvidenceState,
    KnowledgePrior,
    ScoringOption,
    ScoringQuestion,
    TargetEvidence,
    TurnAssessment,
    apply_turn_assessment,
    assessment_weight,
    calculate_option_evidence,
    initialize_from_entry_prior,
    parse_questions,
    poll_responses_to_indices,
    raw_score_to_prior,
    score_entry_test,
    score_poll_test,
)

__all__ = [
    "MISSED_CORRECT",
    "REJECTED_WRONG",
    "SELECTED_CORRECT",
    "SELECTED_WRONG",
    "EntryTestScore",
    "KnowledgeEvidenceState",
    "KnowledgePrior",
    "ScoringOption",
    "ScoringQuestion",
    "TargetEvidence",
    "TurnAssessment",
    "apply_turn_assessment",
    "assessment_weight",
    "calculate_option_evidence",
    "initialize_from_entry_prior",
    "parse_questions",
    "poll_responses_to_indices",
    "raw_score_to_prior",
    "score_entry_test",
    "score_poll_test",
]
