# Knowledge-state update

One learner assessment receives the weight

```text
w = strength × confidence × independence × repetition
```

## Coefficients

| Strength | Weight |
|---|---:|
| `weak` | 0.25 |
| `moderate` | 0.60 |
| `strong` | 1.00 |

`evidence_type` (`recall`, `explanation`, `application`, `correction`) and
`response_mode` (`deliberate`, `uncertain`, `guess`) are descriptive metadata.
They are not additional multipliers; their diagnostic content is represented
by `strength`.

| Support level | Positive independence | Negative independence |
|---|---:|---:|
| `independent` | 1.00 | 1.00 |
| `small_prompt` | 0.80 | 1.00 |
| `guided` | 0.50 | 0.90 |
| `explicit_hint` | 0.25 | 0.70 |
| `answer_revealed` | 0.00 | 0.30 |

Independence estimates how diagnostic the observation is of performance without
tutor help. Negative evidence can remain informative despite support.

Repeated related evidence is reduced by

```text
repetition = 1 / (1 + 0.7 × previous_related_assessments)
```

Applied evidence is capped at `1.0` per target and learner turn.

## Mastery

The applied weight is added to positive or negative accumulated evidence:

```text
mastery = positive_evidence / (positive_evidence + negative_evidence)
```

Without entry-test evidence, a neutral prior of weight `1.0` prevents a small
first observation from making mastery exactly zero or one.

The coefficients are explicit scoring-policy assumptions. They should be
reviewed against annotated learner data rather than treated as fitted facts.

The module's executable assessment view shows the learner quote, assessment
labels, numeric weight factors, and applied weight alongside initial and final
knowledge states. Run it with `python -m aidu.support.scoring.knowledge_update`.
