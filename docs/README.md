# README.md

# Documentation Overview

This folder contains the architecture and technical documentation for the **Hea MVP** — a prompt-driven health assessment engine.

The goal of this documentation is to describe:

- what the system is
- how it is structured
- which services exist
- how data flows through the system
- how to work with the API
- how the MVP can grow into a lightweight product platform

---

## What this project is

The MVP implements a **prompt-driven assessment engine** where:

- a specialist defines assessment logic outside of code
- the definition is compiled into an executable graph
- the runtime executes that graph for end users
- the system generates a final report

The architecture is intentionally lightweight:
- one MVP
- one main end-to-end flow
- clear domain boundaries

---

## Documentation Map

### Core system documents

#### `ARCHITECTURE.md`
Start here if you want the high-level picture.

Explains:
- the overall architecture
- key design principles
- compiler/runtime split
- graph runtime model
- guardrails
- eval-driven approach
- product fit and MVP boundaries

Use this document to understand **why the system is designed this way**.

---

#### `SERVICES.md`
Describes the system as a set of logical services.

Explains:
- which services exist
- what each service is responsible for
- how services interact
- why this is still a lightweight MVP and not enterprise overdesign

Use this document to understand **service boundaries and system decomposition**.

---

#### `DATA_MODEL.md`
Describes the core data model and storage entities.

Explains:
- the main tables/entities
- relationships between definitions, graphs, sessions, reports, and evals
- which artifact is canonical
- how versioning works

Use this document to understand **what data the system stores and why**.

---

#### `API.md`
Describes the MVP API surface.

Explains:
- all main endpoints
- request/response shapes
- error format
- API grouped by service boundaries

Use this document to understand **how clients interact with the system**.

---

## Service documentation

Detailed service descriptions are located in:

```text
docs/services/
```

These files describe each logical service at a service-overview level.

### `services/definition-service.md`
Assessment Definition Service

Use this to understand:
- how specialist-authored definitions are stored
- what belongs to authoring input
- what is in scope and out of scope for this service

---

### `services/compiler-service.md`
Assessment Compiler Service

Use this to understand:
- how definitions are compiled into executable graphs
- what validation happens before runtime
- how compiled graph versions are created

---

### `services/runtime-service.md`
Assessment Runtime Service

Use this to understand:
- how the user assessment flow works
- how session state is handled
- how branching, score, and conversational freedom work at runtime

---

### `services/report-service.md`
Report Generation Service

Use this to understand:
- how final reports are built
- how HTML/PDF output works
- which output guardrails apply

---

### `services/evaluation-service.md`
Evaluation & Safety Service

Use this to understand:
- which checks and evals exist
- how safety rules are validated
- how the MVP remains testable and debuggable

---

## Technical specs

The more implementation-oriented technical specs are also located in:

```text
docs/services/
```

These files go one step deeper than the service overviews and are intended to support actual implementation work.

### `services/techspec-definition-service.md`
Implementation-focused spec for the Definition Service.

Includes:
- API expectations
- storage model
- validation rules
- acceptance criteria

---

### `services/techspec-compiler-service.md`
Implementation-focused spec for the Compiler Service.

Includes:
- compile pipeline
- graph validation rules
- persistence model
- publish rules

---

### `services/techspec-runtime-service.md`
Implementation-focused spec for the Runtime Service.

Includes:
- runtime flow
- session model
- conversation orchestration
- safety constraints
- acceptance criteria

---

### `services/techspec-report-service.md`
Implementation-focused spec for the Report Service.

Includes:
- report generation flow
- output structure
- rendering rules
- report guardrails

---

### `services/techspec-evaluation-service.md`
Implementation-focused spec for the Evaluation & Safety Service.

Includes:
- eval targets
- check types
- result model
- acceptance criteria

---

## Suggested reading order

If you are new to the project, the recommended order is:

1. `ARCHITECTURE.md`
2. `SERVICES.md`
3. `DATA_MODEL.md`
4. `API.md`
5. `services/runtime-service.md`
6. `services/techspec-runtime-service.md`

If you want to understand the project quickly, start with:

1. `ARCHITECTURE.md`
2. `SERVICES.md`
3. `API.md`

If you want to implement the system, read:

1. `ARCHITECTURE.md`
2. `DATA_MODEL.md`
3. `API.md`
4. `services/techspec-*.md`

---

## Canonical architectural idea

The most important idea in this project is:

**specialist-defined input → compiler → canonical compiled graph → runtime execution → final report**

This means:

- raw specialist input is the authoring source
- the **compiled graph** is the canonical executable artifact
- runtime always executes a graph version
- reports and evals are always tied to that graph version

---

## MVP boundaries

This documentation describes an MVP, not a full enterprise platform.

### Included in MVP
- text-based assessment definition
- graph compilation
- runtime assessment flow
- final report generation
- lightweight safety and evals

### Planned for later
- specialist-facing authoring UI
- visual graph editor
- richer evidence integrations
- advanced review workflows
- dashboards and analytics

---

## Notes on structure

This documentation is intentionally separated into:

- **high-level architecture docs**
- **service overviews**
- **technical implementation specs**

This allows the project to be read at different levels:

- product/system level
- service boundary level
- implementation level

---

## Summary

Use this folder as the main source of truth for the MVP design.

If you need:

- **big picture** → read `ARCHITECTURE.md`
- **service boundaries** → read `SERVICES.md`
- **data/storage model** → read `DATA_MODEL.md`
- **API contract** → read `API.md`
- **implementation detail** → read `services/techspec-*.md`