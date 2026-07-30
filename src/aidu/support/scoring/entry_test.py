"""Option-level entry-test scoring.

The formulas in this module implement
``aidu-backend-components/Manuals/test_scoring.md``.  The implementation is
deliberately independent of the backend, database, Pydantic, and AI runtime so
assessment specialists can execute and review it in isolation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from rich.console import Console
from rich.table import Table

from .models import (
    EntryTestScore,
    KnowledgePrior,
    ScoringOption,
    ScoringQuestion,
    TargetEvidence,
)


# These asymmetric weights are assessment policy, not tuning parameters hidden
# in application code.  In particular, missing a correct option is weaker
# negative evidence than actively selecting an incorrect statement.
SELECTED_CORRECT = 1.0
SELECTED_WRONG = -1.0
MISSED_CORRECT = -0.4
REJECTED_WRONG = 0.0


def parse_questions(raw_questions: Iterable[Mapping[str, Any]]) -> tuple[ScoringQuestion, ...]:
    """Validate test configuration and return its canonical scoring form.

    Invalid configuration is rejected here rather than ignored during scoring.
    This keeps authored targets, option positions, and solution indices
    authoritative.
    """

    questions: list[ScoringQuestion] = []
    seen_question_ids: set[str] = set()

    for raw_question in raw_questions:
        question_id = _required_text(raw_question.get("id"), "Question id")
        if question_id in seen_question_ids:
            raise ValueError(f"Duplicate question id {question_id!r}.")
        seen_question_ids.add(question_id)

        raw_options = raw_question.get("options")
        if not isinstance(raw_options, list) or not raw_options:
            raise ValueError(f"Question {question_id!r} must contain options.")

        options: list[ScoringOption] = []
        option_texts: set[str] = set()
        for option_index, raw_option in enumerate(raw_options):
            if not isinstance(raw_option, Mapping):
                raise ValueError(
                    f"Question {question_id!r}, option {option_index} must be a mapping."
                )
            text = _required_text(
                raw_option.get("text"),
                f"Question {question_id!r}, option {option_index} text",
            )
            if text in option_texts:
                raise ValueError(
                    f"Question {question_id!r} contains duplicate option text {text!r}."
                )
            option_texts.add(text)

            raw_targets = raw_option.get("targets")
            if not isinstance(raw_targets, list) or not raw_targets:
                raise ValueError(
                    f"Question {question_id!r}, option {option_index} must contain targets."
                )
            targets = tuple(
                _required_text(
                    target,
                    f"Question {question_id!r}, option {option_index} target",
                )
                for target in raw_targets
            )
            if len(set(targets)) != len(targets):
                raise ValueError(
                    f"Question {question_id!r}, option {option_index} contains duplicate targets."
                )
            options.append(ScoringOption(text=text, targets=targets))

        raw_solution = raw_question.get("solution")
        if not isinstance(raw_solution, list):
            raise ValueError(f"Question {question_id!r} solution must be a list.")
        solution = _unique_indices(
            raw_solution,
            label=f"Question {question_id!r} solution",
        )
        _validate_indices(question_id, solution, len(options), "solution")

        questions.append(
            ScoringQuestion(
                id=question_id,
                options=tuple(options),
                solution=frozenset(solution),
            )
        )

    return tuple(questions)


def poll_responses_to_indices(
    questions: Sequence[ScoringQuestion],
    poll_responses: Mapping[str, Any],
) -> dict[str, tuple[int, ...]]:
    """Translate the current poll response payload to canonical option indices.

    Polls persist selected option text.  The scoring formula intentionally uses
    indices because ``solution`` is index-based.  This boundary performs the
    one explicit translation and rejects text that is not in the corresponding
    authored question.

    A response with ``skip: true`` is omitted, preserving the specification's
    distinction between a skipped question and a submitted empty selection.
    """

    questions_by_id = {question.id: question for question in questions}
    unknown_question_ids = set(poll_responses).difference(questions_by_id)
    if unknown_question_ids:
        raise ValueError(
            f"Responses contain unknown question ids: {sorted(unknown_question_ids)}."
        )

    normalized: dict[str, tuple[int, ...]] = {}
    for question_id, raw_response in poll_responses.items():
        question = questions_by_id[question_id]
        if not isinstance(raw_response, Mapping):
            raise ValueError(f"Response for question {question_id!r} must be a mapping.")
        if raw_response.get("skip") is True:
            continue
        if raw_response.get("skip") not in {None, False}:
            raise ValueError(f"Response for question {question_id!r} has an invalid skip value.")

        selected_texts = raw_response.get("options")
        if not isinstance(selected_texts, list):
            raise ValueError(f"Response for question {question_id!r} options must be a list.")
        if not all(isinstance(text, str) for text in selected_texts):
            raise ValueError(f"Response for question {question_id!r} options must be strings.")
        if len(set(selected_texts)) != len(selected_texts):
            raise ValueError(f"Response for question {question_id!r} contains duplicate options.")

        option_index = {
            option.text: index
            for index, option in enumerate(question.options)
        }
        unknown_options = set(selected_texts).difference(option_index)
        if unknown_options:
            raise ValueError(
                f"Response for question {question_id!r} contains unknown options: "
                f"{sorted(unknown_options)}."
            )
        normalized[question_id] = tuple(option_index[text] for text in selected_texts)

    return normalized


def calculate_option_evidence(
    option_index: int,
    selected: set[int] | frozenset[int],
    solution: set[int] | frozenset[int],
) -> float:
    """Return the policy weight for one option-level learner decision."""

    is_selected = option_index in selected
    is_correct = option_index in solution
    if is_selected and is_correct:
        return SELECTED_CORRECT
    if is_selected and not is_correct:
        return SELECTED_WRONG
    if not is_selected and is_correct:
        return MISSED_CORRECT
    return REJECTED_WRONG


def raw_score_to_prior(raw_score: float) -> float:
    """Map normalized evidence to a bounded, non-absolute prior."""

    if not -1.0 <= raw_score <= 1.0:
        raise ValueError("Raw score must be between -1.0 and 1.0.")
    return max(0.1, min(0.9, 0.5 + 0.4 * raw_score))


def score_entry_test(
    questions: Sequence[ScoringQuestion],
    responses: Mapping[str, Sequence[int]],
) -> EntryTestScore:
    """Aggregate submitted option decisions into target-level priors.

    Missing response ids produce no evidence.  A present empty sequence means
    the question was seen and submitted without a selection, so missed correct
    options still contribute ``-0.4``.
    """

    questions_by_id = {question.id: question for question in questions}
    unknown_question_ids = set(responses).difference(questions_by_id)
    if unknown_question_ids:
        raise ValueError(
            f"Responses contain unknown question ids: {sorted(unknown_question_ids)}."
        )

    evidence_values: dict[str, list[float]] = defaultdict(list)
    evidence_questions: dict[str, set[str]] = defaultdict(set)

    for question in questions:
        if question.id not in responses:
            continue
        selected = _unique_indices(
            responses[question.id],
            label=f"Response for question {question.id!r}",
        )
        _validate_indices(question.id, selected, len(question.options), "response")

        for option_index, option in enumerate(question.options):
            evidence = calculate_option_evidence(
                option_index,
                selected,
                question.solution,
            )
            # The evidence is intentionally copied to every target. Dividing by
            # the number of annotations would make a learner's score depend on
            # how finely an expert annotated the option.
            for target in option.targets:
                evidence_values[target].append(evidence)
                evidence_questions[target].add(question.id)

    evidence = {
        target: TargetEvidence(
            values=tuple(values),
            question_ids=frozenset(evidence_questions[target]),
        )
        for target, values in evidence_values.items()
    }
    priors = {
        target: KnowledgePrior(
            prior=raw_score_to_prior(sum(target_evidence.values) / len(target_evidence.values)),
            raw_score=sum(target_evidence.values) / len(target_evidence.values),
            evidence_count=len(target_evidence.values),
            question_count=len(target_evidence.question_ids),
        )
        for target, target_evidence in evidence.items()
    }
    return EntryTestScore(priors=priors, evidence=evidence)


def score_poll_test(
    raw_questions: Iterable[Mapping[str, Any]],
    poll_responses: Mapping[str, Any],
) -> EntryTestScore:
    """Convenience entry point for an authored test and persisted poll result."""

    questions = parse_questions(raw_questions)
    responses = poll_responses_to_indices(questions, poll_responses)
    return score_entry_test(questions, responses)


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string.")
    return value.strip()


def _unique_indices(values: Iterable[Any], *, label: str) -> frozenset[int]:
    materialized = list(values)
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in materialized):
        raise ValueError(f"{label} must contain integer indices.")
    if len(set(materialized)) != len(materialized):
        raise ValueError(f"{label} contains duplicate indices.")
    return frozenset(materialized)


def _validate_indices(
    question_id: str,
    indices: set[int] | frozenset[int],
    option_count: int,
    kind: str,
) -> None:
    invalid = sorted(index for index in indices if index < 0 or index >= option_count)
    if invalid:
        raise ValueError(
            f"Question {question_id!r} contains invalid {kind} option indices: {invalid}."
        )


def _smoke_test() -> None:
    """Run one reviewable scoring example without the rest of AIDu.

    A scoring expert can execute it from the ``aidu-support`` directory:

        python -c "from aidu.support.scoring.entry_test import _smoke_test; _smoke_test()"

    The learner selects one correct statement, selects one distractor, and
    misses another correct statement. The assertions document the expected
    option evidence and resulting target priors.
    """

    # Adapted from aidu-data/store/rene_myclass_entry_test.yaml. Keeping the
    # target annotations here makes this example standalone and lets reviewers
    # trace every resulting number back to a concrete chemistry statement.
    questions = [
        {
            "id": "q01",
            "type": "multiple_choice_quiz",
            "prompt": (
                "Which statements about the fluoride ion "
                "${}^{19}_{9}\\mathrm{F}^-$ and its particles are correct?"
            ),
            "options": [
                {
                    "text": "It has 9 protons, 10 neutrons, and 10 electrons.",
                    "targets": [
                        "neutron-identity",
                        "proton-identity",
                        "electron-ions",
                    ],
                },
                {
                    "text": "Its atomic number is 9 and its mass number is 19.",
                    "targets": [
                        "atomic-number-mass-isotopes",
                        "isotope-notation",
                        "neutron-identity",
                    ],
                },
                {
                    "text": (
                        "Compared with a neutral fluorine atom, it has gained "
                        "one electron."
                    ),
                    "targets": ["electron-ions", "cations-anions"],
                },
                {
                    "text": (
                        "Fluorine-18 and fluorine-19 are isotopes because they "
                        "have different numbers of protons."
                    ),
                    "targets": [
                        "proton-identity",
                        "neutron-identity",
                        "neutron-isotopes",
                    ],
                },
                {
                    "text": "Adding one proton would leave it as the same element.",
                    "targets": [
                        "proton-identity",
                        "atomic-number-mass-isotopes",
                    ],
                },
            ],
            "solution": [0, 1, 2],
        }
    ]
    poll_result = {
        "q01": {
            "options": [
                "It has 9 protons, 10 neutrons, and 10 electrons.",
                (
                    "Fluorine-18 and fluorine-19 are isotopes because they "
                    "have different numbers of protons."
                ),
            ],
            "skip": False,
        }
    }

    result = score_poll_test(questions, poll_result)
    parsed_question = parse_questions(questions)[0]
    selected_indices = set(
        poll_responses_to_indices((parsed_question,), poll_result)["q01"]
    )

    # The learner selected correct option 0 (+1.0), missed correct options 1
    # and 2 (-0.4 each), selected distractor 3 (-1.0), and rejected distractor
    # 4 (0.0). Evidence is then copied to each option's annotated targets.
    assert result.evidence["electron-ions"].values == (1.0, -0.4)
    assert result.evidence["proton-identity"].values == (1.0, -1.0, 0.0)
    assert result.evidence["neutron-identity"].values == (1.0, -0.4, -1.0)
    assert result.priors["electron-ions"].raw_score == 0.3
    assert result.priors["electron-ions"].prior == 0.62
    assert result.priors["proton-identity"].prior == 0.5
    assert result.priors["neutron-isotopes"].prior == 0.1
    assert round(result.priors["neutron-identity"].prior, 4) == 0.4467

    # A mean prior summarizes the diagnostic model, but is not a test grade:
    # 0.5 represents uncertainty in that model rather than 50% achievement.
    mean_mastery = sum(
        target_prior.prior for target_prior in result.priors.values()
    ) / len(result.priors)
    mean_prior_percent = max(0, min(100, int(mean_mastery * 100 + 0.5)))
    assert mean_prior_percent == 40

    # Teacher-facing achievement awards one point for a selected correct
    # statement and subtracts one for a selected distractor. Missed correct
    # statements earn no point. The result is bounded at zero and normalized
    # by the number of available correct statements.
    correct_selected = len(selected_indices & parsed_question.solution)
    wrong_selected = len(selected_indices - parsed_question.solution)
    earned_points = max(0, correct_selected - wrong_selected)
    available_points = len(parsed_question.solution)
    achievement = int(earned_points / available_points * 100 + 0.5)
    assert correct_selected == 1
    assert wrong_selected == 1
    assert achievement == 0

    console = Console()
    console.rule("[bold blue]Entry-test scoring smoke test")
    console.print(f"[bold]Question:[/bold] {questions[0]['prompt']}")
    console.print("[bold]Selected statements:[/bold]")
    for selected_text in poll_result["q01"]["options"]:
        console.print(f"  [cyan]•[/cyan] {selected_text}")

    option_table = Table(title="Option-level scoring")
    option_table.add_column("#", justify="right")
    option_table.add_column("Selected", justify="center")
    option_table.add_column("Correct", justify="center")
    option_table.add_column("Evidence", justify="right")
    option_table.add_column("Statement")
    option_table.add_column("Targets", style="cyan")
    for option_index, option in enumerate(parsed_question.options):
        evidence = calculate_option_evidence(
            option_index,
            selected_indices,
            parsed_question.solution,
        )
        option_table.add_row(
            str(option_index),
            "✓" if option_index in selected_indices else "—",
            "✓" if option_index in parsed_question.solution else "—",
            f"{evidence:+.1f}",
            option.text,
            ", ".join(option.targets),
        )
    console.print(option_table)

    table = Table(
        title="Knowledge-state priors",
        caption=(
            "The frontend slider uses mastery only; its valid range is 0.00–1.00."
        ),
    )
    table.add_column("Target", style="cyan")
    table.add_column("Evidence", justify="right")
    table.add_column("Raw score", justify="right")
    table.add_column("Mastery / slider", justify="right", style="bold green")
    table.add_column("Questions", justify="right")

    for target, prior in result.priors.items():
        values = result.evidence[target].values
        table.add_row(
            target,
            str(values),
            f"{prior.raw_score:.2f}",
            f"{prior.prior:.2f}",
            str(prior.question_count),
        )
    console.print(table)
    console.print(
        f"[bold]Mean knowledge prior:[/bold] {mean_prior_percent}% "
        f"(mean mastery {mean_mastery:.2f} across {len(result.priors)} targets)"
    )
    console.print(
        f"[bold]Final achievement:[/bold] [bold magenta]{achievement}%[/bold magenta] "
        f"({correct_selected} correct selection − {wrong_selected} wrong selection "
        f"= {earned_points}/{available_points} points)"
    )
    console.print("[bold green]✓ Smoke test passed.[/bold green]")


if __name__ == "__main__":
    _smoke_test()
