# README.md

# Documentation Overview

This folder contains the design and technical documentation for the **Hea MVP v2**.

The system is now built as an **agentic architecture with two Telegram bots**:

- **Specialist Bot** — collects assessment definitions from a specialist in free-form text
- **User Bot** — runs the assessment with the end user in Telegram

Both bots use a shared model layer through **Together AI API**.

The system does **not** execute raw chat history directly.  
The canonical executable artifact remains the:

**Compiled Assessment Graph**

This graph is produced from specialist input and is later executed by the runtime agent.

---

## Core Idea

The core flow is:

**specialist Telegram chat → structured definition draft → compiled graph → user Telegram assessment → final report**

This preserves:

- flexibility at authoring time
- deterministic execution at runtime
- versioning and safety
- reproducibility and evaluation

---

## Documentation Map

### High-level docs

#### `ARCHITECTURE.md`
Read this first.

Explains:
- the overall system structure
- the two-bot model
- the agent roles
- shared Together AI layer
- canonical compiled graph
- runtime and reporting flow

#### `SERVICES.md`
Explains:
- what logical services/agents exist
- what each service owns
- how the bots and agents interact
- which boundaries are preserved in MVP

#### `DATA_MODEL.md`
Explains:
- which entities are stored
- how specialist chats, drafts, graphs, sessions, reports, and evals relate
- how canonical graph versioning works

#### `API.md`
Explains:
- internal/admin API surface
- orchestration endpoints
- service-to-service contract examples

#### `ideas.md`
Contains:
- roadmap ideas
- future product extensions
- optional features intentionally left out of MVP

---

## Service Documentation

Detailed service documents are under:

```text
docs/services/
```

These files preserve the original naming convention, but their content reflects the **new agentic architecture**.

### `services/definition-service.md`
Now describes the **Specialist Intake + Definition Agent** boundary.

### `services/compiler-service.md`
Now describes the **Compiler Agent**.

### `services/runtime-service.md`
Now describes the **User Bot + Runtime Agent** boundary.

### `services/report-service.md`
Now describes the **Report Agent**.

### `services/evaluation-service.md`
Now describes the **Evaluation & Safety Agent**.

---

## Technical Specs

The `techspec-*` documents are implementation-facing versions of the service docs.

They focus on:
- responsibilities
- inputs/outputs
- state
- internal contracts
- edge cases
- acceptance criteria

---

## Suggested Reading Order

### To understand the system quickly
1. `ARCHITECTURE.md`
2. `SERVICES.md`
3. `DATA_MODEL.md`

### To understand implementation boundaries
1. `SERVICES.md`
2. `services/*.md`
3. `services/techspec-*.md`

### To implement or review internal contracts
1. `API.md`
2. `DATA_MODEL.md`
3. `services/techspec-*.md`

---

## MVP Boundaries

### Included in MVP
- two Telegram bots
- Together AI integration
- specialist-driven definition collection
- compiled graph generation
- graph-driven user assessment
- final user report
- lightweight evaluation and safety checks

### Not included in MVP
- specialist web UI
- visual graph editor
- advanced evidence integrations
- dashboards
- multi-tenant administration

---

## Canonical Artifact

The system has one canonical executable artifact:

**Compiled Assessment Graph**

This means:
- specialist Telegram messages are not executed directly
- drafts are not executed directly
- runtime always uses a compiled graph version
- reports and evals are always tied to a graph version

---

## Summary

This documentation describes a **lightweight agentic platform** for prompt-driven health assessments.

The system uses:
- Telegram as the external interface
- Together AI as the shared model layer
- agents for structuring, compiling, executing, reporting, and evaluating
- compiled graph as the stable execution truth