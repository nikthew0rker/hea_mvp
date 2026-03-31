# ARCHITECTURE.md

## 1. Overview

This MVP implements a **prompt-driven health-assessment platform** with two user-facing entry points:

1. **Specialist Bot**
   - used by a medical or product specialist
   - collects source material
   - builds and edits a structured draft
   - compiles the draft into a graph
   - publishes the graph

2. **Patient Bot**
   - used by an end user / patient
   - loads the currently published active graph
   - executes the assessment flow
   - generates a report at the end

The architecture is intentionally lightweight. It is designed to demonstrate a platform mindset without turning the MVP into heavy enterprise infrastructure.

---

## 2. Core architectural principles

### 2.1 Spec-driven
The specialist can define the assessment in natural language and through pasted materials such as:
- scales
- questionnaires
- tables
- guideline fragments
- noisy webpage text

The system converts this into a structured draft and eventually a graph.

### 2.2 Controller-based specialist workflow
The specialist side is no longer a rigid scripted state machine.  
Instead, the specialist bot uses a **controller loop**:

1. understand the latest message in context
2. decide which workflow action is needed
3. operate on the draft
4. answer naturally
5. remain inside graph-building boundaries

### 2.3 Draft as the primary working object
The system centers specialist interaction around a live **draft object**, not around one-shot prompts.

The draft contains:
- topic
- target audience
- candidate questions
- scoring rules
- risk bands
- report requirements
- safety requirements
- missing fields

### 2.4 Separation of concerns
The system separates:
- specialist-side control
- structured extraction / editing
- graph compilation
- patient runtime
- report generation
- evaluation
- publish handoff

### 2.5 Publish handoff
Compiled graphs are not useful until they become active for patient runtime.  
The MVP therefore includes a real publish step:
- publish writes the active graph into shared storage
- patient assistant loads the active graph from storage

---

## 3. High-level component model

```text
┌──────────────────────────────────────────────────────────┐
│                    Specialist Bot                        │
│                                                          │
│  Controller reasoning + natural reply generation         │
│  Works on a live draft object                            │
└───────────────┬──────────────────────────────────────────┘
                │
                │ update/edit/compile/publish
                ▼
┌──────────────────────────────────────────────────────────┐
│                  Definition Agent                        │
│                                                          │
│  update mode: extract structure from source material     │
│  edit mode: apply natural-language edits to the draft    │
└───────────────┬──────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────┐
│                   Compiler Agent                         │
│                                                          │
│  draft -> compiled graph                                 │
└───────────────┬──────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────┐
│              Published Graph Storage                     │
│                                                          │
│  data/active_graph.json                                  │
│  data/graph_registry.json                                │
└───────────────┬──────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────┐
│                     Patient Bot                          │
│                                                          │
│  loads active graph -> Runtime Agent -> Report Agent     │
└──────────────────────────────────────────────────────────┘
```

---

## 4. Runtime layers

### 4.1 Specialist-side layer
Main responsibilities:
- accept source material
- preserve session context
- inspect draft state
- apply edits
- trigger compile
- trigger publish
- keep natural conversational UX

### 4.2 Definition layer
Main responsibilities:
- normalize noisy medical source text
- extract structured candidate fields
- merge extracted information into the current draft
- apply natural-language edit instructions safely

### 4.3 Compilation layer
Main responsibilities:
- validate required draft pieces
- transform draft into graph artifact
- assign graph id / graph version

### 4.4 Publication layer
Main responsibilities:
- mark one graph as active
- persist active graph artifact
- expose current graph to patient runtime

### 4.5 Patient runtime layer
Main responsibilities:
- load active graph
- run conversational assessment
- preserve session state
- hand final state to reporting

### 4.6 Reporting layer
Main responsibilities:
- transform runtime session state into a user-facing summary / report
- preserve non-diagnostic product boundaries

---

## 5. End-to-end workflows

### 5.1 Specialist workflow

#### Step 1 — source intake
The specialist sends:
- free-text description
- article fragment
- scale
- guideline
- noisy copied webpage

#### Step 2 — draft update
The specialist bot sends the input to the Definition Agent in `update` mode.

Definition Agent:
- normalizes source text
- extracts candidate structure
- merges result into the draft

#### Step 3 — draft inspection
The specialist can ask:
- what did you understand
- show questions
- show scoring
- show risk bands
- show report rules
- show safety rules

#### Step 4 — draft editing
The specialist can send edit instructions:
- change question 3
- remove a risk band
- rewrite scoring logic
- update wording
- add safety escalation

Definition Agent runs in `edit` mode and updates the draft.

#### Step 5 — compile
The specialist requests compilation.

Compiler Agent:
- validates the draft
- returns compiled graph + graph id

#### Step 6 — publish
The specialist requests publication.

Publish flow:
- active graph is written to `data/active_graph.json`
- publish event is appended to `data/graph_registry.json`

---

### 5.2 Patient workflow

#### Step 1 — patient bot start
Patient bot loads the active graph record.

#### Step 2 — runtime execution
Patient message -> Runtime Agent.

Runtime Agent:
- advances graph state
- asks next question
- updates session state

#### Step 3 — report generation
When the runtime decides the assessment is complete:
- Runtime Agent marks completion
- Report Agent generates summary / report using:
  - session state
  - active graph payload

---

## 6. Data model

### 6.1 Draft
A mutable specialist-side object.

Main fields:
- `understood`
- `candidate_questions`
- `candidate_scoring_rules`
- `candidate_risk_bands`
- `candidate_report_requirements`
- `candidate_safety_requirements`
- `missing_fields`

### 6.2 Compiled graph
A runtime-ready assessment artifact.

Main fields:
- `graph_version_id`
- graph nodes / edges / runtime metadata
- source draft linkage

### 6.3 Published active graph record
Stored in `data/active_graph.json`.

Main fields:
- `graph_id`
- `status=published`
- `is_active=true`
- `published_at`
- `metadata`
- `graph`

---

## 7. Models and reasoning roles

### 7.1 Specialist controller model
Used inside the specialist bot for:
- understanding user intent in context
- deciding which workflow action is needed
- writing the final natural reply

### 7.2 Definition model
Used by Definition Agent for:
- structured extraction
- edit application
- schema-aligned update suggestions

### 7.3 Runtime model
Used by Runtime Agent for:
- patient-side interaction
- graph-driven progression

### 7.4 Report model
Used by Report Agent for:
- patient-facing summary/report generation

---

## 8. Guardrails and boundaries

The specialist and patient layers must remain inside product boundaries.

Hard constraints:
- no diagnosis
- no treatment plan
- no medication recommendation
- no uncontrolled medical advice
- specialist flow stays inside graph-building workflow

This is implemented through:
- system prompts
- action boundaries
- restricted publish/runtime contracts
- deterministic storage handoff

---

## 9. Why this architecture fits the MVP

This design is appropriate for MVP because it:
- demonstrates platform thinking
- supports flexible natural-language authoring
- avoids hardcoded questionnaire logic
- shows real end-to-end handoff
- remains lightweight and understandable
- does not overbuild infrastructure too early

---

## 10. Deliberate MVP limitations

Known simplifications:
- publish storage is file-based, not database-backed
- one active graph at a time
- no multi-user specialist isolation beyond in-memory session state
- no versioned graph management UI
- no separate audit trail service
- limited persistence outside active graph storage

These are acceptable for MVP and good candidates for future expansion.
