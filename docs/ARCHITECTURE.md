# Architecture

## Purpose

Hea is designed as a clinical authoring-and-delivery system with two separate but connected agent surfaces:

- `Specialist surface` for authoring clinical artifacts
- `Patient surface` for discovery, intake, runtime execution, and result explanation

The specialist surface intentionally supports both:

- `prompt execution` -> a specialist can submit a full scenario prompt
- `prompt construction assistance` -> the bot can help the specialist create that prompt interactively in chat

The system is intentionally split so that:

- specialists define the logic
- patients consume only published artifacts
- draft authoring is isolated from patient delivery

## Architectural Methodology

The project follows five core principles.

### 1. Typed intermediate representation first

The system does not treat clinical artifacts as plain chat text.

Instead, specialist input is compiled into typed IR using `Pydantic` models:

- `QuestionnaireSpec`
- `QuestionSpec`
- `QuestionOptionSpec`
- `RiskBandSpec`
- `AnamnesisSectionSpec`
- `ClinicalRuleNodeSpec`
- `EditOperation`
- `CriticReview`
- `PendingProposal`
- `PatientSymptomIntake`
- `PatientIntentDecision`

This is the main architectural protection against brittle prompt-only behavior.

### 2. Orchestration and business logic are separated

`LangGraph` is used for routing and state transitions.

Business logic stays outside the graph:

- parsing
- compilation
- validation
- search
- storage
- runtime scoring

This makes the system easier to test and evolve.

### 3. Human approval before publication

Specialist-side authoring is not a direct “LLM writes production graph” path.

The intended flow is:

`message -> analysis -> edit operation -> compile spec -> validate/review -> proposal -> apply -> compile graph -> publish`

This protects the patient-facing registry from half-formed drafts.

This also means the specialist assistant is not just a prompt runner.
It is a prompt-building copilot:

- it can take a complete scenario prompt
- or help the specialist discover and refine the scenario in several turns
- then convert that conversation into a typed artifact proposal

### 4. Shared registry, isolated draft space

There are two different persistence concerns:

- draft/session/version state for specialist and patient workflows
- published graph registry used for patient search

This distinction is critical.

A draft can exist and still be invisible to patients.

Only `publish` makes an artifact searchable by the patient bot.

### 5. Safety by layered constraints

The system does not rely on one model or one prompt for safety.

It uses layers:

- typed schemas
- rule-based validation
- critic pass
- publish gate
- patient triage / red-flag routing
- restricted product boundary

## Libraries and Their Roles

### FastAPI

Used for:

- `specialist_controller`
- `patient_controller`

Role:

- stable HTTP boundary around the LangGraph workflows
- controller lifecycle, startup, and dependency wiring

### LangGraph

Used for:

- specialist authoring graph
- patient orchestration graph
- patient runtime subgraph

Role:

- stateful graph execution
- conditional routing
- explicit state transitions
- subgraph composition

Why LangGraph fits here:

- the system is workflow-heavy, not single-shot
- different states need different policies
- patient runtime is naturally a subgraph
- specialist authoring requires interrupt/apply/review style transitions

What LangGraph is not doing here:

- it is not parsing questionnaires
- it is not validating clinical correctness
- it is not the storage layer

Those concerns live in `src/hea/shared/*`.

### Pydantic

Used for:

- all typed IR and structured contracts
- request DTOs
- validation of model outputs

Role:

- the schema backbone of the system

### aiogram

Used for:

- Telegram bot adapters

Role:

- transport only
- bot layer remains thin and forwards messages to controllers

### httpx

Used for:

- Together API requests
- controller HTTP calls from bot adapters

### sqlite3

Used for:

- published graph registry
- specialist drafts and draft history
- audit events
- specialist sessions
- patient sessions

### Together AI

Used for:

- structured model calls for controller/analyst/compiler/critic roles

The system does not use one universal model for everything.

### Guardrails AI

Current status:

- not installed
- not yet used in runtime

Architectural position:

- valid future addition on top of the current stack
- best suited as an extra validation/re-ask layer after model output, not as the replacement for the current architecture

If added later, Guardrails should sit between:

`model output -> schema/domain validation -> accept / re-ask`

## System Layers

## 1. Specialist Layer

Main graph:

- [`graph.py`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/src/hea/graphs/specialist/graph.py)

Main responsibilities:

- understand specialist intent
- prepare proposals
- apply proposals into draft state
- compile draft into graph
- publish graph to registry

Specialist interaction modes:

- `direct prompt mode`: one large scenario prompt
- `copilot mode`: iterative dialog that helps the specialist formulate the scenario prompt itself

Specialist architecture:

```text
Specialist message
  -> route_specialist_message
  -> discuss / update / show / apply / compile / publish
  -> authoring pipeline
  -> draft store / version store / audit store
```

Important specialist concept:

- the graph does not directly store free-form text as production logic
- it first generates a `PendingProposal`
- that proposal is reviewed before apply

### Specialist authoring pipeline

Key module:

- [`authoring_pipeline.py`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/src/hea/shared/authoring_pipeline.py)

Responsibilities:

- plan `EditOperation`
- compile specialist input into typed spec
- preserve scored options and question structure
- build anamnesis sections
- build clinical rule nodes
- run local validation
- merge critic review
- produce diff/proposal summaries

### Specialist persistence

Stored data:

- current draft
- draft versions
- audit events
- graph publication result

This gives the system:

- rollback
- version inspection
- safer iterative authoring

## 2. Patient Layer

Main graph:

- [`graph.py`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/src/hea/graphs/patient/graph.py)

Main responsibilities:

- understand patient request
- perform symptom intake
- detect red flags
- search published graphs
- disambiguate between candidates
- ask consent
- hand off to runtime graph
- explain result

Patient architecture:

```text
Patient message
  -> route_user_message
  -> patient analyst decision
  -> triage / search / selection / consent / runtime / result
```

### Patient intake methodology

The patient side does not rely only on the last utterance.

It accumulates a typed `PatientSymptomIntake`:

- summary
- symptoms
- suspected topics
- duration
- severity
- free_text

This is later used by search and recommendation logic.

### Patient safety methodology

Patient routing includes:

- red-flag detection
- non-emergency vs emergency guidance
- explicit consent before assessment
- preservation of context in paused and post-assessment states

## 3. Patient Runtime Layer

Runtime subgraph:

- [`graph.py`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/src/hea/graphs/patient_runtime/graph.py)

Role:

- run the selected artifact
- ask the next question
- accept answers
- repeat/help/explain
- finish with result/report

The runtime layer is artifact-aware:

- questionnaire scoring
- questionnaire branching through option-level `next_question_id`
- rule-graph synthetic diagnostic inputs
- rule matching via `conditions_ast`
- HTML report rendering through the patient controller report endpoint

## Artifact Model

The system supports three artifact families.

### Questionnaire

Use case:

- scored screening scales like FINDRISC

Core structure:

- questions
- options
- optional answer-driven branching via `next_question_id`
- scores
- scoring method
- risk bands

### Anamnesis Flow

Use case:

- structured history-taking flows

Core structure:

- sections
- section goals
- section questions
- branching cues

### Clinical Rule Graph

Use case:

- early triage / diagnostic support logic

Core structure:

- diagnostic inputs
- rule nodes
- condition AST
- outcomes

## Publication Model

There are three different states that must not be confused.

### Draft

Exists only in specialist draft storage.

Visible to patient:

- no

### Compiled graph

A graph candidate produced from a draft.

Visible to patient:

- no

### Published graph

Written into the shared `graphs` registry.

Visible to patient:

- yes

This is one of the most important operational rules in the system.

## Search Architecture

Current patient search is `intake-aware metadata matching`.

Inputs:

- raw user query
- intake summary
- suspected topics
- symptoms
- severity

Graph-side signals:

- title
- topic
- description
- tags
- entry_signals
- artifact_type

This is stronger than plain token overlap, but still not a final semantic retrieval system.

## Validation Architecture

Current validation stack:

1. `Pydantic` schema validation
2. project-specific local validation
3. critic model pass
4. publish gate

Examples of what is checked:

- missing questions
- missing risk bands for scored questionnaires
- malformed single-choice questions
- missing anamnesis sections
- missing rule nodes
- editor commands leaking into description
- unsafe diagnosis/treatment language

## Why This Architecture Is Better Than a Single Chat Agent

Without this architecture, one model would have to do all of the following in one step:

- understand intent
- edit structure
- preserve scores
- validate clinical logic
- decide publication safety

That is fragile.

The current system reduces that fragility by splitting concerns into explicit stages with typed contracts.

## Known Limits

The system is much stronger than the initial MVP, but it still has limits.

Current limits include:

- no real Guardrails integration yet
- no vector retrieval or full semantic search
- partial condition AST only
- no specialist UI beyond chat and controller responses
- limited domain validators compared with a production clinical platform

## Recommended Next Steps

Highest-value next steps:

1. add richer clinical validators
2. extend rule AST with nested `and/or`
3. improve graph metadata and retrieval semantics
4. add selective diff approval UI
5. optionally add Guardrails as a post-generation validation layer
