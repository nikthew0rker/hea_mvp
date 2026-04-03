# ARCHITECTURE.md

## 1. Overview

Hea MVP is a **prompt-driven assessment platform** with two distinct but connected interaction domains:

1. **Specialist-side authoring**
2. **Patient-side orchestration and runtime**

The system is designed to support **graph-agnostic assessment authoring and execution**.

That means the platform should not be limited to:
- diabetes
- sleep
- stress
- cardiometabolic risk
- one fixed questionnaire

Instead, it should support **any published assessment graph** that conforms to the runtime contract.

---

## 2. Main architectural principle

The system separates:

- **authoring**
- **compilation**
- **publication**
- **discovery**
- **execution**
- **result presentation**

This separation is essential because the specialist and the patient solve different problems.

### Specialist problem
“How do I define a safe, structured, executable assessment?”

### Patient problem
“How do I naturally talk to the assistant and, when appropriate, get matched to the right assessment?”

---

## 3. Top-level architecture

```text
                         ┌──────────────────────────────┐
                         │       Specialist Bot         │
                         │   controller-based authoring │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │      Definition Agent        │
                         │  extract / merge / edit draft│
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │       Compiler Agent         │
                         │ draft -> runtime-ready graph │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │ Publish Handoff + Registry   │
                         │ active graph + graph library │
                         └──────────────┬───────────────┘
                                        │
      ┌─────────────────────────────────┴─────────────────────────────────┐
      │                                                                   │
      ▼                                                                   ▼
┌───────────────┐                                            ┌──────────────────────┐
│ Active Graph  │                                            │  Graph Registry      │
│ current active│                                            │ searchable collection│
└───────────────┘                                            └──────────────────────┘
                                                                      │
                                                                      ▼
                                                         ┌──────────────────────────┐
                                                         │   Patient Controller /   │
                                                         │   Patient Orchestrator   │
                                                         └────────────┬─────────────┘
                                                                      │
                                                                      ▼
                                                         ┌──────────────────────────┐
                                                         │ Graph Search + Selector  │
                                                         └────────────┬─────────────┘
                                                                      │
                                                                      ▼
                                                         ┌──────────────────────────┐
                                                         │ Consent + Graph Runtime  │
                                                         └────────────┬─────────────┘
                                                                      │
                                                                      ▼
                                                         ┌──────────────────────────┐
                                                         │ Result Interpreter /     │
                                                         │ Response Renderer         │
                                                         └──────────────────────────┘
```

---

## 4. Specialist-side architecture

The specialist side is built around a **draft-first authoring model**.

### Main objects
- draft
- compiled graph
- published graph

### Main stages
1. source intake
2. structured extraction
3. draft inspection
4. draft editing
5. compilation
6. publication

The specialist bot acts as a **controller-based copilot**, not a rigid form.

---

## 5. Patient-side architecture

The patient side is built around **orchestration over a graph library**.

### It does not assume:
- that one graph is always the right one
- that the user wants to start assessment immediately
- that the conversation starts inside a questionnaire

### It does assume:
- the patient begins in free conversation mode
- the system should discover the right graph
- consent should be collected before runtime starts
- after completion, the assistant should return to free conversation mode

---

## 6. Canonical product loop

The full product loop is:

### Specialist loop
source material -> draft -> compile -> publish

### Patient loop
free conversation -> graph discovery -> offer -> consent -> runtime -> result -> free conversation

This is the most important conceptual model in the system.

---

## 7. Core artifacts

### 7.1 Draft
Mutable specialist-side object.

Contains:
- topic
- target audience
- candidate questions
- scoring rules
- risk bands
- report requirements
- safety requirements
- missing fields

### 7.2 Compiled graph
Executable assessment artifact.

Contains:
- unique graph id
- title/topic
- questions or nodes
- scoring structure
- risk band mapping
- source draft linkage

### 7.3 Active graph
The currently active graph for direct runtime use.

### 7.4 Graph registry entry
Searchable library entry used by patient orchestration.

Contains:
- graph id
- title
- description
- tags
- entry signals
- search text
- runtime payload

---

## 8. Why there are both active graph and graph registry

The system currently supports two related but different concepts:

### Active graph
Used when the system needs one currently active graph.

### Graph registry
Used when the patient assistant needs to search across multiple published graphs.

In the final patient-side design, **graph registry is the more important abstraction**.

---

## 9. Runtime boundaries

### The system may:
- explain assessments
- guide users through them
- compute graph-defined results
- present graph-defined categories and summaries

### The system must not:
- diagnose disease
- prescribe treatment
- recommend medication
- act as a full medical advisor

This boundary exists on both specialist and patient side.

---

## 10. Why this architecture fits MVP

This architecture is suitable for MVP because it:

- demonstrates platform thinking
- supports multiple future graph domains
- avoids hardcoding one questionnaire
- keeps deterministic graph execution separate from conversational reasoning
- remains lightweight enough for fast iteration

---

## 11. Deliberate MVP limitations

Known simplifications:
- file-based storage
- simple graph registry search
- minimal session store
- no web UI
- no persistent DB-backed transaction layer
- no enterprise-grade approval flow

These are acceptable at MVP stage.

