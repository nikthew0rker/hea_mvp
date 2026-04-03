# Hea MVP

Hea is a two-bot clinical authoring and delivery system:

- a `Specialist Bot` for drafting, reviewing, compiling, and publishing clinical artifacts
- a `User Bot` for patient-facing search, consent, assessment runtime, and result explanation

Live Telegram bots:

- Specialist bot: `@hea_specialist_mvp_bot`
- User bot: `@hea_user_mvp_bot`

Specialist-side authoring supports two modes:

- `single scenario prompt mode` -> a specialist can provide one large prompt that defines the assessment scenario
- `assistant mode` -> the specialist bot can help the specialist iteratively build that prompt and artifact structure in chat

The current system supports three artifact types:

- `questionnaire`
- `anamnesis_flow`
- `clinical_rule_graph`

Canonical assignment demos:

- `Diabetes / FINDRISC-like questionnaire` -> simple scored questionnaire
- `Burnout questionnaire` -> adaptive branching questionnaire

## Core Stack

Runtime libraries actually used in the project:

- `FastAPI` for HTTP controllers
- `LangGraph` for stateful orchestration
- `Pydantic v2` for typed schemas and IR
- `httpx` for model/provider HTTP calls
- `aiogram` for Telegram bots
- `reportlab` for production-style PDF report rendering
- `uvicorn` for ASGI serving
- `uv` for dependency management and execution
- `sqlite3` from the Python standard library for persistence

Model provider:

- `Together AI`

Current model-role split:

- `CONTROLLER_MODEL` -> routing, intent analysis, planning
- `SPECIALIST_COMPILER_MODEL` -> typed authoring compilation
- `EXTRACTION_MODEL` -> extraction helpers
- `SPECIALIST_CRITIC_MODEL` -> review and validation pass
- `FAST_MODEL` -> short conversational replies

Guardrails status:

- `Guardrails AI` is not currently installed or enforced in runtime
- the current validation layer is implemented with `Pydantic` models plus project-specific rule checks
- Guardrails is a valid next-step option for schema validation, corrective re-asks, and output guards, but it is not yet part of the shipped stack

## Architecture

High-level flow:

```text
Specialist Bot
  -> Specialist Controller (FastAPI)
  -> Specialist LangGraph
  -> Draft store / version store / audit store
  -> Compile
  -> Publish
  -> Shared graph registry

User Bot
  -> Patient Controller (FastAPI)
  -> Patient LangGraph
  -> Search in shared graph registry
  -> Consent
  -> Patient runtime LangGraph subgraph
  -> Result / explanation / report
```

Detailed architecture and methodology:

- [`ARCHITECTURE.md`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/docs/ARCHITECTURE.md)
- [`PRODUCTION_ARCHITECTURE_V1.md`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/docs/PRODUCTION_ARCHITECTURE_V1.md)
- [`MLOPS_ROADMAP.md`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/docs/MLOPS_ROADMAP.md)
- [`MODEL_ROLES.md`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/docs/MODEL_ROLES.md)
- [`SCENARIOS.md`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/docs/SCENARIOS.md)
- [`SUBMISSION_PLAN.md`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/docs/SUBMISSION_PLAN.md)
- [`SUBMISSION_RESPONSE.md`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/docs/SUBMISSION_RESPONSE.md)

Full end-to-end demo scripts for both canonical scenarios:

- [`SCENARIOS.md`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/docs/SCENARIOS.md) now includes complete specialist-bot and user-bot scripts for:
  - `Diabetes / FINDRISC-like questionnaire`
  - `Burnout branching questionnaire`

## What LangGraph Does Here

`LangGraph` is the orchestration layer, not the source of business logic.

It is used for:

- stateful turn-by-turn workflows
- explicit routing between graph nodes
- persistence-friendly state transitions
- human-in-the-loop steps like proposal review and apply
- subgraph execution for patient runtime

In this project, LangGraph is intentionally used as a low-level workflow engine:

- specialist graph routes authoring operations
- patient graph routes patient conversation and assessment handoff
- patient runtime graph handles in-assessment answering flow

The clinical logic, validation, parsing, storage, and compilation live outside LangGraph in `src/hea/shared/*`.

## Project Layout

- [`src/hea/graphs/specialist`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/src/hea/graphs/specialist) -> specialist graph
- [`src/hea/graphs/patient`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/src/hea/graphs/patient) -> patient orchestration graph
- [`src/hea/graphs/patient_runtime`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/src/hea/graphs/patient_runtime) -> patient runtime subgraph
- [`src/hea/shared`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/src/hea/shared) -> schemas, storage, search, runtime, model routing, provider client
- [`src/hea/services`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/src/hea/services) -> FastAPI controllers
- [`src/hea/bots`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/src/hea/bots) -> Telegram adapters
- [`config/scaffold_strategies.json`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/config/scaffold_strategies.json) -> starter scaffold catalog

## Quick Start

### 1. Configure environment

For local development:

```bash
cp .env.example .env
```

Fill in:

- `TOGETHER_API_KEY`
- `SPECIALIST_BOT_TOKEN`
- `USER_BOT_TOKEN`
- optionally tune `PROVIDER_TIMEOUT_SECONDS` and `CONTROLLER_REQUEST_TIMEOUT_SECONDS` for long single-prompt authoring requests

Recommended model set:

- `CONTROLLER_MODEL=MiniMaxAI/MiniMax-M2.5`
- `SPECIALIST_COMPILER_MODEL=zai-org/GLM-5`
- `EXTRACTION_MODEL=zai-org/GLM-5`
- `SPECIALIST_CRITIC_MODEL=MiniMaxAI/MiniMax-M2.5`
- `FAST_MODEL=MiniMaxAI/MiniMax-M2.5`

### 2. Install

```bash
uv sync
```

### 3. Run locally

Controllers:

```bash
uv run uvicorn hea.services.specialist_controller.app:app --reload --port 8107
uv run uvicorn hea.services.patient_controller.app:app --reload --port 8106
```

Bots:

```bash
uv run python -m hea.bots.specialist_bot.bot
uv run python -m hea.bots.user_bot.bot
```

### 4. Run with Docker

```bash
docker compose up -d --build
```

## Storage

SQLite path is configured by:

- `HEA_DB_PATH`

Main tables:

- `graphs`
- `specialist_drafts`
- `specialist_draft_versions`
- `specialist_audit_events`
- `specialist_sessions`
- `patient_sessions`

Docker note:

- Docker services use the SQLite file inside the named volume `hea_data`
- the host file [`data/hea.sqlite`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/data/hea.sqlite) is not automatically the same database as the live Docker bots use

## Specialist Workflow

Canonical flow:

1. `/start`
2. send free-form goal or source material
3. review the proposal
4. `примени предложение`
5. `compile`
6. `publish`

Important publication rule:

- `apply proposal` updates only the specialist draft
- `compile` builds only a compiled candidate graph
- only `publish` writes the graph into the shared registry used by the patient bot

If you do not run `publish`, the patient bot will not see the artifact.

Patient report outputs:

- HTML report: `/report/{conversation_id}`
- PDF report: `/report/{conversation_id}.pdf`
- in Telegram, `@hea_user_mvp_bot` can also send the PDF directly into the chat as a file when the user asks for `pdf` / `пдф`

PDF notes:

- the primary renderer uses `reportlab`
- if `reportlab` is temporarily unavailable, the app falls back to the built-in minimal PDF renderer instead of failing
- the patient bot can fetch the generated PDF from the controller and upload it into Telegram as a document

Specialist-side prompt authoring modes:

1. `single prompt mode`
- the specialist sends one scenario-defining prompt
- the system compiles it into a typed artifact proposal

2. `assistant mode`
- the specialist does not need a perfect prompt upfront
- the bot can help refine the topic, questions, scoring, risk bands, branching, and report structure step by step
- this is intentionally part of the product value: the system helps create the assessment prompt, not only execute it

### Example: publish FINDRISC

Specialist bot:

1. `/start`
2. `я хочу собрать FINDRISC для диабета`
3. send the questions and scores
4. `примени предложение`
5. send the risk interpretation block
6. `примени предложение`
7. `compile`
8. `publish`

Patient bot:

1. `/start`
2. `меня беспокоит уровень сахара в крови`
3. `подбери`

Expected result:

- the patient bot should offer the published diabetes assessment

## Patient Workflow

1. `/start`
2. patient describes a concern
3. patient graph performs intake, triage, and search
4. if needed, patient chooses from several candidates
5. system asks consent
6. runtime subgraph runs the assessment
7. system returns result / explanation / detailed report

Optional web-format report:

- `GET /report/{conversation_id}` on the patient controller returns an HTML report for the latest available result in that conversation
- `GET /report/{conversation_id}.pdf` on the patient controller returns a PDF version of the latest available result

## Safety Boundary

This project is a clinical workflow scaffold, not a medical diagnosis engine.

It may:

- collect information
- run graph-defined questionnaires and flows
- calculate graph-defined scores
- explain graph-defined outputs

It must not:

- silently invent clinical logic
- prescribe treatment
- claim confirmed diagnosis by default
- replace urgent medical evaluation

## Current Status

The system is already beyond a toy MVP:

- typed specialist authoring pipeline
- typed patient intake and routing
- artifact-aware compilation
- selective apply, versioning, rollback
- patient red-flag routing and disambiguation
- Together model-role split

But it is still an engineering scaffold, not a production clinical platform.

The next likely maturity steps are:

- stronger domain validators
- richer conditional rule AST
- selective diff approval UI
- optional Guardrails integration
- stronger end-to-end clinical evaluation
