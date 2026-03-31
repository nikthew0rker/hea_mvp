# SERVICES.md

## 1. Service map

The current MVP contains the following main runtime components:

### User-facing bots
- Specialist Bot
- Patient Bot

### Internal services
- Definition Agent
- Compiler Agent
- Runtime Agent
- Report Agent
- Evaluation Agent

### Shared support modules
- Together client wrapper
- Input normalizer
- Prompt / policy loader
- Published graph store
- Shared schemas

---

## 2. Service catalog

| Component | Type | Main responsibility |
|---|---|---|
| Specialist Bot | Telegram bot | Controller for specialist workflow, draft operations, compile/publish |
| Patient Bot | Telegram bot | Entry point for patient assessment runtime |
| Definition Agent | FastAPI service | Structured extraction and edit application over draft |
| Compiler Agent | FastAPI service | Transform draft into compiled graph |
| Runtime Agent | FastAPI service | Execute active graph for the patient |
| Report Agent | FastAPI service | Generate patient-facing report |
| Evaluation Agent | FastAPI service | Run validation / QA checks |
| Published Graph Store | shared module | Persist and load currently active graph |

---

## 3. Component responsibilities

### 3.1 Specialist Bot
Responsibilities:
- hold specialist session state
- maintain current draft object
- interpret latest message in conversational context
- decide whether to:
  - inspect draft
  - update draft
  - edit draft
  - compile graph
  - publish graph
- generate natural final responses

Dependencies:
- Definition Agent
- Compiler Agent
- Published Graph Store
- Together AI (controller reasoning + final response generation)

### 3.2 Patient Bot
Responsibilities:
- load current published graph
- start patient conversation
- forward patient turns into runtime flow
- trigger report generation after completion

Dependencies:
- Published Graph Store
- Runtime Agent
- Report Agent

### 3.3 Definition Agent
Responsibilities:
- parse noisy medical content
- extract structured candidate fields
- apply edit instructions to existing draft
- keep merge logic stable even with imperfect model output

Dependencies:
- Together AI
- Input normalizer
- Policy files

### 3.4 Compiler Agent
Responsibilities:
- validate required draft structure
- create compiled graph artifact
- assign graph identifier

Dependencies:
- draft payload from specialist workflow

### 3.5 Runtime Agent
Responsibilities:
- drive graph-based patient flow
- interpret patient responses
- update runtime session state
- decide when report generation should start

Dependencies:
- active published graph id / graph payload
- patient bot session data

### 3.6 Report Agent
Responsibilities:
- transform final session state into report output
- produce concise patient-facing summary

Dependencies:
- runtime session state
- graph payload

### 3.7 Evaluation Agent
Responsibilities:
- validate graph integrity
- validate runtime/report outputs
- act as internal QA layer for future automated checks

---

## 4. Ownership of data

### Specialist Bot owns
- in-memory specialist session state
- conversation history
- current draft object reference
- compiled graph id for the current session

### Definition Agent owns
- extraction logic
- edit application logic
- merge/sanitization logic

### Published Graph Store owns
- active graph record
- publish registry

### Patient Bot owns
- patient chat routing
- current active graph lookup

### Runtime Agent owns
- runtime session state for patient interaction

### Report Agent owns
- final response formatting for patient result

---

## 5. Storage model

### Shared published graph storage
File-based MVP storage:
- `data/active_graph.json`
- `data/graph_registry.json`

Purpose:
- real publish handoff
- shared visibility between specialist and patient bot
- simple demo-friendly end-to-end integration

### Why file storage is acceptable here
For MVP:
- low complexity
- transparent behavior
- easy debugging
- enough for one active graph handoff flow

---

## 6. Key runtime dependencies

### Specialist-side path
Specialist Bot -> Definition Agent -> Compiler Agent -> Published Graph Store

### Patient-side path
Patient Bot -> Published Graph Store -> Runtime Agent -> Report Agent

---

## 7. Service contracts summary

### Specialist Bot -> Definition Agent
Operation:
- `update`
- `edit`

Payload:
- latest specialist message
- conversation id
- current draft
- current language

### Specialist Bot -> Compiler Agent
Payload:
- current draft

### Specialist Bot -> Published Graph Store
Payload:
- compiled graph id
- compiled graph payload
- publish metadata

### Patient Bot -> Runtime Agent
Payload:
- patient conversation id
- latest patient message
- active graph id

### Patient Bot -> Report Agent
Payload:
- runtime session state
- active graph payload

---

## 8. Operational behavior

### Specialist Bot failure tolerance
If controller-model reasoning fails:
- specialist bot should fall back to deterministic action inference
- bot must not crash user flow on provider exceptions

### Definition Agent failure tolerance
If model returns malformed JSON:
- sanitize before merge
- keep merge logic stable
- never trust raw model structure directly

### Patient Bot failure tolerance
If no graph is published:
- bot must state clearly that no active graph is available
- no fake runtime should start

---

## 9. MVP extension path

Likely future expansions:
- persistent specialist sessions
- graph version registry
- multiple published graphs
- explicit graph activation/deactivation
- UI for draft inspection and editing
- database-backed publish storage
- dedicated graph runtime registry service
