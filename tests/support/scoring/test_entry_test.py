import pytest

from aidu.support.scoring import (
    MISSED_CORRECT,
    REJECTED_WRONG,
    SELECTED_CORRECT,
    SELECTED_WRONG,
    calculate_option_evidence,
    parse_questions,
    poll_responses_to_indices,
    raw_score_to_prior,
    score_entry_test,
    score_poll_test,
)


QUESTIONS = [
    {
        "id": "q01",
        "options": [
            {"text": "A", "targets": ["alpha", "shared"]},
            {"text": "B", "targets": ["beta"]},
            {"text": "C", "targets": ["alpha"]},
            {"text": "D", "targets": ["shared"]},
            {"text": "E", "targets": ["beta"]},
        ],
        "solution": [0, 2, 3],
    }
]


@pytest.mark.parametrize(
    ("option", "selected", "solution", "expected"),
    [
        (0, {0}, {0}, SELECTED_CORRECT),
        (0, {0}, set(), SELECTED_WRONG),
        (0, set(), {0}, MISSED_CORRECT),
        (0, set(), set(), REJECTED_WRONG),
    ],
)
def test_all_option_evidence_states(option, selected, solution, expected):
    assert calculate_option_evidence(option, selected, solution) == expected


def test_reference_example_and_multi_target_distribution():
    questions = parse_questions(QUESTIONS)
    score = score_entry_test(questions, {"q01": [0, 1, 3]})

    assert score.evidence["alpha"].values == (1.0, -0.4)
    assert score.evidence["shared"].values == (1.0, 1.0)
    assert score.evidence["beta"].values == (-1.0, 0.0)
    assert score.priors["alpha"].raw_score == pytest.approx(0.3)
    assert score.priors["alpha"].prior == pytest.approx(0.62)
    assert score.priors["alpha"].evidence_count == 2
    assert score.priors["alpha"].question_count == 1


def test_target_aggregates_across_distinct_questions():
    raw = QUESTIONS + [
        {
            "id": "q02",
            "options": [{"text": "F", "targets": ["alpha"]}],
            "solution": [0],
        }
    ]
    score = score_entry_test(parse_questions(raw), {"q01": [0, 2, 3], "q02": [0]})

    assert score.priors["alpha"].raw_score == 1.0
    assert score.priors["alpha"].evidence_count == 3
    assert score.priors["alpha"].question_count == 2


@pytest.mark.parametrize(
    ("raw", "prior"),
    [(-1.0, 0.1), (-0.5, 0.3), (0.0, 0.5), (0.5, 0.7), (1.0, 0.9)],
)
def test_prior_mapping(raw, prior):
    assert raw_score_to_prior(raw) == pytest.approx(prior)


def test_skipped_question_has_no_evidence_but_empty_submission_does():
    questions = parse_questions(QUESTIONS)

    assert score_entry_test(questions, {}).priors == {}
    empty = score_entry_test(questions, {"q01": []})
    assert empty.evidence["alpha"].values == (-0.4, -0.4)


def test_poll_payload_is_translated_by_option_text_and_skip_is_omitted():
    questions = parse_questions(QUESTIONS)

    assert poll_responses_to_indices(
        questions, {"q01": {"options": ["D", "A"], "skip": False}}
    ) == {"q01": (3, 0)}
    assert poll_responses_to_indices(
        questions, {"q01": {"options": [], "skip": True}}
    ) == {}


def test_high_level_poll_scoring_entry_point():
    score = score_poll_test(
        QUESTIONS,
        {"q01": {"options": ["A", "B", "D"], "skip": False}},
    )
    assert score.priors["shared"].prior == 0.9


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda q: q["options"][0].pop("text"), "non-empty string"),
        (lambda q: q["options"][0].update(targets=[]), "must contain targets"),
        (lambda q: q["options"][0].update(targets=[""]), "non-empty string"),
        (lambda q: q.update(solution=[99]), "invalid solution"),
        (lambda q: q.update(solution=[0, 0]), "duplicate indices"),
        (lambda q: q["options"].append({"text": "A", "targets": ["x"]}), "duplicate option text"),
    ],
)
def test_invalid_authored_test_is_rejected(mutation, message):
    question = {
        "id": "q",
        "options": [{"text": "A", "targets": ["x"]}],
        "solution": [0],
    }
    mutation(question)
    with pytest.raises(ValueError, match=message):
        parse_questions([question])


def test_invalid_response_indices_and_duplicates_are_rejected():
    questions = parse_questions(QUESTIONS)
    with pytest.raises(ValueError, match="invalid response"):
        score_entry_test(questions, {"q01": [8]})
    with pytest.raises(ValueError, match="duplicate indices"):
        score_entry_test(questions, {"q01": [0, 0]})


def test_unknown_poll_question_and_option_are_rejected():
    questions = parse_questions(QUESTIONS)
    with pytest.raises(ValueError, match="unknown question"):
        poll_responses_to_indices(questions, {"q99": {"options": []}})
    with pytest.raises(ValueError, match="unknown options"):
        poll_responses_to_indices(
            questions, {"q01": {"options": ["not authored"], "skip": False}}
        )
