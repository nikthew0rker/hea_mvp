# Hea MVP — Final Technical Documentation

This folder contains the final project documentation for the current Hea MVP architecture.

## What this documentation reflects

This documentation reflects the **current system direction** after the latest changes:

- specialist-side **controller-based authoring**
- definition → compile → publish workflow
- persistent local JSON-backed storage for MVP
- graph library and graph registry
- patient-side **orchestration over a graph collection**
- consent before assessment execution
- graph-agnostic patient runtime
- return from assessment flow back to free conversation

This is no longer documented as a single hardcoded diabetes questionnaire flow.  
Instead, the architecture is described as a reusable framework for **any published assessment graph**.

---

## Reading order

If you are new to the system, read in this order:

1. `ARCHITECTURE.md`
2. `SERVICES.md`
3. `SPECIALIST_ARCHITECTURE.md`
4. `PATIENT_ORCHESTRATION_ARCHITECTURE.md`
5. `PATIENT_RUNTIME_CONTRACT.md`
6. `definition-service.md`
7. `compiler-service.md`
8. `publish-handoff.md`
9. `graph-registry.md`
10. `graph-search.md`

---

## Main documents

### Core architecture
- `ARCHITECTURE.md`
- `SERVICES.md`

### Specialist-side authoring
- `SPECIALIST_ARCHITECTURE.md`
- `specialist-controller.md`
- `definition-service.md`
- `compiler-service.md`
- `publish-handoff.md`

### Patient-side orchestration
- `PATIENT_ORCHESTRATION_ARCHITECTURE.md`
- `patient-orchestrator.md`
- `graph-registry.md`
- `graph-search.md`
- `PATIENT_RUNTIME_CONTRACT.md`

### Supporting system behavior
- `report-service.md`
- `evaluation-service.md`
- `DATA_AND_STORAGE.md`

---

## Canonical system idea

The platform has two major sides:

### 1. Specialist side
A specialist works with the system to:
- provide source material
- extract a structured draft
- edit that draft
- compile it into a runtime-ready graph
- publish it into the graph library

### 2. Patient side
A patient interacts with a conversational assistant that:
- starts in free conversation mode
- analyzes the user’s intent, goals, or problems
- searches the graph collection
- proposes a suitable assessment
- waits for consent
- executes the chosen graph
- returns the result
- goes back to free conversation mode

---

## Why this architecture matters

This architecture avoids two common failure modes:

### Failure mode 1 — rigid specialist workflow
A scripted specialist bot cannot properly support real authoring.  
The specialist side therefore uses a **controller + draft + compile/publish** architecture.

### Failure mode 2 — rigid questionnaire patient bot
A questionnaire bot hardwired to one graph cannot behave like a real assistant.  
The patient side therefore uses **orchestration over a graph library**, not a single active graph only.

---

## Current MVP limitations

This is still an MVP. The system deliberately stays lightweight.

Known limitations:
- file-based storage instead of a database
- lightweight graph registry
- simplified graph search ranking
- no UI for authoring or graph browsing
- limited session persistence semantics
- no enterprise-grade auth, audit, or approvals

These are acceptable for MVP and preserve the platform’s simplicity.

---

## Guiding product boundary

The system is an **assessment platform**, not a full medical advisor.

It may:
- explain an assessment
- guide the user through it
- present graph-defined results

It must not:
- diagnose
- prescribe treatment
- recommend medication
- drift into unrestricted medical consultation

