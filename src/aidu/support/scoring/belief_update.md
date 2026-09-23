# Belief-state update

The learner-belief vector is updated from observable speech-act evidence:

```text
b_next = clip_0_1(b_prior + clip_delta(M · e))
```

- `e`: confidence-weighted speech-act evidence vector
- `M`: speech-act-to-belief coefficient matrix
- `b_prior`: belief state before the learner turn
- `b_next`: derived belief state after the learner turn

## Coefficient matrix

Empty cells are `0.0`.

| Speech act | Allowed utterance role | engagement | confidence | confusion | frustration | curiosity | self_explanation | guessing | help_seeking |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `state` | student/tutor | | 0.5 | | | | | | |
| `hypothesize` | student/tutor | 1.0 | | | | | | | |
| `explain` | student/tutor | 0.5 | | | | | 1.0 | | |
| `infer` | student/tutor | 1.0 | | | | | | | |
| `predict` | student/tutor | 0.5 | | | | 1.0 | | | |
| `compare` | student/tutor | 1.0 | | | | | | | |
| `justify` | student/tutor | 0.5 | | | | | 1.0 | | |
| `report_action` | student | 0.5 | | | | | | | |
| `propose_action` | student | 1.0 | | | | | | | |
| `commit_action` | student | 1.0 | | | | | | | |
| `request_continue` | student | 1.0 | | | | | | | |
| `request_stop` | student | -1.0 | | | | | | | |
| `off_topic` | student | -1.0 | | | | | | | |
| `ask_for_confirmation` | student | | -0.5 | | | | | | 1.0 |
| `express_uncertainty` | student | | -1.0 | 0.5 | | | | | |
| `express_understanding` | student | | 1.0 | -1.0 | | | | | |
| `express_nonunderstanding` | student | | | 1.0 | | | | | |
| `ask` | student/tutor | | | | | | | | 0.5 |
| `ask_for_explanation` | student/tutor | | | | | | | | 1.0 |
| `ask_for_hint` | student | | | | | | | | 1.0 |

The coefficients are conservative policy assumptions:

- `1.0`: direct relationship
- `0.5`: indirect relationship
- Negative values decrease a belief dimension
- `0.0`: the speech act alone does not justify an update

`state → confidence = 0.5` represents commitment to a proposition as true. It
does not imply that the proposition is correct or known.

`frustration` and `guessing` currently have zero columns because a speech-act
label alone is insufficient evidence for either state.

The role column describes ontology admissibility. This update always uses a
student utterance; tutor utterances may clarify context but never enter `e`.

Each evidence item contributes:

```text
e[act] += strength_weight × assessor_confidence
```

where `weak = 0.05`, `moderate = 0.10`, and `strong = 0.15`. The resulting
change is capped to `±0.15` per belief dimension and learner turn.

Run `python -m aidu.support.scoring.belief_update` to view individual speech-act
assessments, their strength and confidence weights, the evidence vector and
matrix, and each belief dimension's contributing terms before clipping.
