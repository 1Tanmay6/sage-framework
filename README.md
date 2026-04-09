# SAGE: Sufficiency-Aware Grounded Evidence Framework

## Overview

SAGE is a context decision framework designed to improve the reliability of large language model (LLM) systems by transforming context handling from a retrieval problem into a decision-making problem.

Instead of simply retrieving relevant information, SAGE selects the minimal set of context required to answer a query under a given objective, evaluates whether the selected context is sufficient, and ensures that all generated outputs are grounded in the provided evidence.

---

## Motivation

Modern LLM systems suffer from three core limitations:

- **Context Overload**: Adding more context initially improves performance but eventually degrades it due to noise and attention dilution.
- **Lack of Sufficiency Awareness**: Models do not know when the available context is insufficient and often hallucinate instead of abstaining.
- **Weak Grounding**: Generated responses are not always supported by the provided context.

SAGE addresses these issues by introducing a structured pipeline for context selection, sufficiency evaluation, and grounding verification.

---

## Problem Definition

Given:

- A conversation trace
  T = { (id_k, c_k) } for k = 1 to N

- An objective
  O

- A query
  Q

SAGE computes:

(R, S, M) = f(O, Q, T)

Where:

- R: Selected subset of context
- S: Sufficiency status ∈ {SUFFICIENT, PARTIAL, INSUFFICIENT, CONTRADICTORY}
- M: Missing or conflicting information

---

## System Architecture

T → Retriever → C
C → Selector → R
R → Generator → Answer + Citations
(R, Answer) → Verifier → Grounded / Not Grounded
(R, Q, O) → Evaluator → S, M

If the context is insufficient or the answer is not grounded, the system refines retrieval and repeats the process.

---

## Components

### 1. Retriever (High Recall Layer)

- Retrieves candidate context C from T
- Optimized for recall, not precision
- Typically uses embeddings or hybrid search

---

### 2. Selector (Context Filtering Layer)

- Scores and selects relevant context
- Learns objective-aware relevance
- Outputs a minimal subset R

---

### 3. Generator (Answering Layer)

- Produces answers using only R
- Outputs structured responses with citations

Example:
{
"answer": "...",
"citations": [
{"claim": "...", "span": "..."}
]
}

---

### 4. Verifier (Grounding Layer)

- Checks whether the answer is fully supported by R
- Detects unsupported or hallucinated claims

Output:
{
"grounded": true/false,
"unsupported_claims": [...]
}

---

### 5. Evaluator (Sufficiency Layer)

- Determines whether R is sufficient to answer Q under O
- Identifies missing or conflicting information

Output:
{
"status": "SUFFICIENT | PARTIAL | INSUFFICIENT | CONTRADICTORY",
"missing_info": "...",
"confidence": 0.0-1.0
}

---

### 6. Controller (Optional)

- Decides whether to:
  - retrieve more context
  - refine selection
  - or finalize the answer

---

## Key Concepts

### Sufficiency

A context set R is sufficient if:

- The answer can be derived from R
- All claims are grounded in R

---

### Minimality

R should contain:

- only necessary information
- no redundant or irrelevant context

---

### Grounding

Every claim in the generated answer must be:

- traceable to R
- supported by explicit evidence

---

## Training Strategy

SAGE uses task-specific fine-tuning across components:

- **Selector**: learns relevance and contribution of context
- **Evaluator**: learns sufficiency classification
- **Verifier**: learns grounding and hallucination detection

Training data includes:

- sufficient and insufficient context cases
- adversarial and contradictory examples
- annotated supporting spans

---

## Evaluation Metrics

SAGE is evaluated using:

- Answer accuracy under constrained context
- Context size vs performance tradeoff
- Hallucination rate reduction
- Sufficiency classification accuracy
- Robustness to noisy or irrelevant context

---

## Goals

- Reduce unnecessary context usage
- Improve answer reliability
- Enable abstention when context is insufficient
- Ensure strict grounding in evidence
- Introduce a decision layer between retrieval and reasoning

---

## Roadmap

- Build baseline retrieval + generation pipeline
- Develop dataset with sufficiency annotations
- Train selector and evaluator models
- Add grounding verification
- Implement iterative refinement loop

---

## Summary

SAGE reframes context handling in LLM systems as a decision problem rather than a retrieval problem. By jointly optimizing context selection, sufficiency evaluation, and grounding, it enables more reliable, efficient, and controllable language model behavior.
