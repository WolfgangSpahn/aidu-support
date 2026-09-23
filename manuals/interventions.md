Yes. I think the clean architecture is:

$$
(Evidence_t) \rightarrow (K_t,B_t,\Delta K_t,\Delta B_t)
\rightarrow \boxed{\text{Intervention policy}}
\rightarrow TutorAct
$$

The important point is that **“ask a question” should not itself be the intervention**. It is a realization mechanism. The intervention should express the pedagogical intention: diagnose, challenge, scaffold, elicit explanation, etc.

### 1. A reasonably small intervention vocabulary

I would start with roughly these 10–12 intervention types:

| Intervention           | Pedagogical purpose                     | Typical trigger                                          |
| ---------------------- | --------------------------------------- | -------------------------------------------------------- |
| **CONTINUE**           | Don't disturb productive work           | learning progressing, engagement adequate                |
| **PROBE**              | Obtain diagnostic evidence              | knowledge/belief uncertainty high                        |
| **RECALL**             | Activate prerequisite knowledge         | relevant prerequisite weak/inactive                      |
| **ELICIT_EXPLANATION** | Force constructive processing           | correct answer but weak explanation evidence             |
| **CHALLENGE**          | Test robustness of understanding        | mastery/confidence high                                  |
| **CONTRAST**           | Expose conceptual distinction           | concepts confused/misconception suspected                |
| **HINT**               | Minimal scaffold                        | learner stuck, but likely able to continue               |
| **DIRECT_ATTENTION**   | Focus on relevant feature               | learner overlooking important evidence                   |
| **EXPLAIN**            | Supply missing conceptual information   | persistent knowledge gap after scaffolding               |
| **MODEL / EXAMPLE**    | Demonstrate strategy                    | repeated failure / insufficient schema                   |
| **TRANSFER**           | Test/generalize knowledge               | concept appears mastered                                 |
| **META_REFLECT**       | Make learner inspect reasoning          | guessing, confidence mismatch, repeated strategy failure |
| **AFFECT_REGULATE**    | Reduce frustration / restore engagement | frustration ↑, engagement ↓                              |
| **ADJUST_DIFFICULTY**  | Change task challenge                   | task too easy/hard relative to learner                   |

There is some overlap, and I would actually try to **keep this ontology deliberately small**. Current ITS literature supports adaptive difficulty, scaffolding, feedback, prompting and self-explanation, but there is no compelling reason to encode dozens of very specific tutor moves at the policy level. ([Nature][1]) Self-explanation is particularly defensible as a distinct intervention; meta-analytic evidence finds meaningful learning benefits, although its effectiveness depends on context. ([ERIC][2])

Then `TutorAct` can realize these interventions through different forms:

```text
ELICIT_EXPLANATION
    -> "Why do you think that?"
    -> "Can you explain what happens to the proton number?"
    -> "What evidence supports your answer?"
```

So intervention and language generation remain separated.

---

## 2. State tells you *where you are*; delta tells you *whether intervention is necessary*

I think this distinction is particularly useful for AIDu.

Suppose:

```text
knowledge = 0.42
confusion = 0.65
engagement = 0.70
```

That alone suggests scaffolding.

But compare:

```text
Δknowledge = +0.10
Δconfusion = -0.12
```

The learner is recovering. The best intervention may simply be:

```text
CONTINUE
```

Whereas:

```text
Δknowledge = -0.02
Δconfusion = +0.15
```

makes `HINT` or `DIRECT_ATTENTION` much more reasonable.

So I would conceptually use:

$$
\boxed{\text{state} \rightarrow \text{which actions are appropriate}}
$$

and

$$
\boxed{\Delta state \rightarrow \text{whether/how strongly to intervene}}
$$

That also protects against an overly reactive tutor.

---

## 3. Some combinations become particularly informative

Your existing belief dimensions give you quite a good decision space.

| Observation                             | Likely intervention                  |
| --------------------------------------- | ------------------------------------ |
| low K + low confidence                  | HINT / RECALL                        |
| low K + high confidence                 | CONTRAST / CHALLENGE                 |
| high K + low confidence                 | ELICIT_EXPLANATION / small CHALLENGE |
| high K + high confidence                | TRANSFER                             |
| confusion ↑, engagement high            | HINT / DIRECT_ATTENTION              |
| confusion ↑, engagement ↓               | simplify / AFFECT_REGULATE           |
| frustration ↑ rapidly                   | reduce difficulty / scaffold         |
| guessing ↑                              | META_REFLECT / ELICIT_EXPLANATION    |
| self-explanation ↓                      | ELICIT_EXPLANATION                   |
| help-seeking ↑ appropriately            | HINT                                 |
| repeated help-seeking + little progress | EXPLAIN / MODEL                      |
| curiosity ↑                             | CHALLENGE / TRANSFER                 |
| K improving                             | CONTINUE                             |
| K stable despite several attempts       | change intervention type             |

One particularly useful case is **knowledge–confidence mismatch**.

$$
K \ll C
$$

suggests overconfidence and calls for challenge, prediction, contradiction or justification.

Whereas

$$
K \gg C
$$

suggests underconfidence and calls for successful retrieval, explanation, or transfer—not more instruction.

That is pedagogically much richer than treating confidence simply as another weight.

---

# 4. How I would select the intervention

I would **not** initially train a direct mapping

$$
(K,B,\Delta K,\Delta B) \rightarrow action.
$$

You don't have enough trustworthy labels, and it becomes difficult to explain why something happened.

Instead, use your existing Supervisor architecture:

```text
KnowledgeState ─┐
BeliefState ────┤
ΔKnowledge ─────┤
ΔBelief ────────┤
Evidence ───────┤
History ────────┘
        ↓
 Candidate interventions
        ↓
 Preconditions / exclusions
        ↓
 Utility evaluation
        ↓
 Intervention
        ↓
 TutorAgent realizes TutorAct
```

This is essentially **constrained action selection**.

For every candidate intervention \(a\), calculate something like:

$$
U(a)=
w_L L(a)
+w_E E(a)
+w_A A(a)
+w_R R(a)
-w_C C(a)
-w_O O(a)
$$

where:

* \(L\): expected learning gain
* \(E\): expected diagnostic/evidence gain
* \(A\): learner autonomy preserved
* \(R\): affective/engagement benefit
* \(C\): cognitive-load cost
* \(O\): risk of over-helping

You don't even need trustworthy numerical weights initially. These could first be ordinal:

```text
ELICIT_EXPLANATION:
    learning_gain:      high
    evidence_gain:      high
    autonomy:           high
    cognitive_load:     medium
    overhelp_risk:      low
```

That is already enough for an LLM or rule-based Supervisor to rank candidates.

---

## 5. Add one particularly important action: `PROBE`

This follows directly from the fact that your belief and knowledge states are **latent estimates**.

Suppose:

```text
Knowledge:
  acid_base: 0.52 ± 0.28
```

The important information isn't `0.52`; it's the large uncertainty.

In that situation you don't know enough to decide between `HINT`, `CHALLENGE`, or `EXPLAIN`.

So:

$$
\text{uncertainty high}
\Rightarrow
\text{PROBE}
$$

The tutor asks a question chosen primarily to reduce uncertainty.

This gives you a very nice distinction:

$$
\text{PROBE} = \text{maximize information gain}
$$

versus

$$
\text{SCAFFOLD} = \text{maximize immediate learning support}.
$$

That starts looking much more like a principled partially observable agent than a collection of tutor heuristics.

---

# 6. There should also be an explicit preference ordering

For AIDu's pedagogical goal of preserving cognitive activity, I would impose something like:

$$
\text{CONTINUE}
<
\text{PROBE}
<
\text{ELICIT}
<
\text{HINT}
<
\text{EXPLAIN}
<
\text{MODEL}
$$

where `<` means **increasing tutor takeover of cognitive work**.

The policy should prefer the lowest intervention sufficient to restore productive learning.

That corresponds well to progressive scaffolding used in tutoring systems—starting with lighter support and escalating only when necessary. ([Springer Nature][3]) Recent meta-analysis of digital prompting likewise suggests that adaptive/action-triggered prompts and mixtures of generic and directed prompts can outperform undifferentiated prompting. ([ScienceDirect][4])

This gives AIDu a very defensible principle:

> **Select the intervention expected to advance the learning goal while transferring as little cognitive work from the learner to the tutor as necessary.**

That is stronger than simply saying "choose the action with the highest predicted learning gain."

---

## 7. And this connects nicely to your evaluator idea

Later, you can learn the intervention policy from expert/LLM assessment.

Instead of asking the evaluator:

> Was this tutor response good?

ask something structurally stronger:

```text
Given:
    evidence
    previous state
    updated knowledge state
    updated belief state
    previous interventions

Was the selected intervention appropriate?
```

Then your learning problem becomes:

$$
(s,\Delta s,a) \rightarrow \text{quality}
$$

and eventually:

$$
\pi(a|s,\Delta s)
$$

The **intervention ontology remains fixed**, while the selection policy improves from data. There is already ITS work explicitly framing assistance selection as a learnable policy problem. ([Springer Nature][3])

For AIDu, I think that is the cleanest architecture:

```text
Evidence
   ↓
Knowledge + Belief update
   ↓
Need detection
   ↓
Candidate interventions
   ↓
Supervisor / policy
   ↓
INTERVENTION
   ↓
TutorAgent
   ↓
concrete question / hint / explanation
```

Crucially, I would make **`CONTINUE` a first-class intervention**. A common failure mode of AI tutors is feeling obliged to teach on every turn. In your architecture, evidence that the learner is making productive progress should actively cause the tutor **not to interfere**.

[1]: https://www.nature.com/articles/s41539-025-00320-7?utm_source=chatgpt.com "A systematic review of AI-driven intelligent tutoring systems (ITS) in K-12 education | npj Science of Learning"
[2]: https://eric.ed.gov/?id=EJ1186664&utm_source=chatgpt.com "ERIC - EJ1186664 - Inducing Self-Explanation: A Meta-Analysis, Educational Psychology Review, 2018-Sep"
[3]: https://link.springer.com/chapter/10.1007/978-3-031-42682-7_26?utm_source=chatgpt.com "Learning to Give Useful Hints: Assistance Action Evaluation and Policy Improvements | Springer Nature Link"
[4]: https://www.sciencedirect.com/science/article/pii/S1747938X25000235?utm_source=chatgpt.com "Scaffolding through prompts in digital learning: A systematic review and meta-analysis of effectiveness on learning achievement - ScienceDirect"
