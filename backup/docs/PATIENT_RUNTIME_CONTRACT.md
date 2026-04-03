# PATIENT_RUNTIME_CONTRACT.md

## 1. Purpose

This document defines the minimum graph shape required for patient-side runtime.

The runtime must be **graph-agnostic**.  
Therefore, any graph used by the patient assistant should follow a predictable contract.

---

## 2. Minimum graph-level fields

```json
{
  "graph_id": "string",
  "title": "string",
  "topic": "string",
  "questions": [],
  "risk_bands": [],
  "scoring": {}
}
```

Or, in a more explicit node-based model:

```json id="mja0zj"
{
  "graph_id": "string",
  "title": "string",
  "topic": "string",
  "entry_node_id": "string",
  "nodes": [],
  "risk_bands": [],
  "scoring": {}
}
```

---

## 3. Question fields

Each question should ideally support:

- id
- text
- question_type
- options
- help_text
- why_it_matters
- normalization_rule
- validation_rule
- scoring_rule
- next

---

## 4. Why this matters

Without a stable runtime contract:
- the assistant cannot normalize answers properly
- graph execution becomes brittle
- patient-side orchestration cannot stay graph-agnostic

---

## 5. Practical note

At MVP stage, the compiler may still output a simpler question list.  
The patient-side runtime can then adapt it into a sequential node graph.

This is acceptable as an intermediate step.

