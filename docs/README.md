# Hea MVP v2 — Technical Documentation

This folder contains the current technical documentation for the **controller-based specialist workflow** and the **published-graph handoff** to the patient assistant.

## Documentation map

### Product and system-level documents
- `ARCHITECTURE.md` — end-to-end system architecture, main workflows, runtime boundaries, deployment shape
- `SERVICES.md` — service catalog, responsibilities, dependencies, data ownership, runtime interactions

### Service specifications
- `definition-service.md` — structured extraction and edit application for assessment drafts
- `compiler-service.md` — conversion from structured draft to executable graph artifact
- `runtime-service.md` — patient-side graph execution and conversational runtime
- `report-service.md` — patient-facing report generation
- `evaluation-service.md` — validation and quality checks for graph artifacts and outputs
- `specialist-controller.md` — specialist-side controller behavior, reasoning flow, tool selection, dialogue boundaries
- `publish-handoff.md` — publish flow, active graph storage, patient assistant handoff contract

## Current system state

The documentation reflects the **current implementation direction**:

- the old planner-agent-based specialist orchestration is removed
- the specialist bot now acts as a **controller-based copilot**
- the specialist side works around a live **draft object**
- the system supports:
  - draft extraction from noisy medical content
  - draft editing
  - graph compilation
  - graph publication
  - patient assistant handoff through shared published-graph storage

## Main architectural idea

The specialist experience is no longer a rigid scripted state machine.

Instead, the specialist bot performs a repeated loop:

1. understand the latest user message in context
2. decide what operation is needed on the current draft
3. execute one safe workflow action
4. answer naturally in the user's language
5. preserve system boundaries:
   - no diagnosis
   - no treatment plan
   - no medication recommendation
   - stay inside graph-building workflow

## Canonical artifacts

The core product artifacts in this MVP are:

1. **Structured draft**
   - topic
   - target audience
   - candidate questions
   - scoring rules
   - risk bands
   - report requirements
   - safety requirements

2. **Compiled graph**
   - executable assessment graph
   - graph identifier
   - graph metadata

3. **Published active graph**
   - the graph currently exposed to the patient assistant
   - stored in shared storage for runtime handoff

## What changed compared to older docs

This documentation supersedes older assumptions such as:

- separate planner agent as the main specialist orchestrator
- hardcoded demo graph ids for patient runtime
- publish as a placeholder only
- specialist flow centered on fixed scripted templates

The current docs describe a **controller-driven specialist workflow** with a **real publish handoff**.

## Suggested reading order

If you are new to the project, read in this order:

1. `ARCHITECTURE.md`
2. `SERVICES.md`
3. `specialist-controller.md`
4. `definition-service.md`
5. `publish-handoff.md`
6. `runtime-service.md`
