# SERVICES.md

## 1. Service map

### User-facing bots
- Specialist Bot
- User Bot

### Internal services
- Definition Agent
- Compiler Agent
- Patient Controller / Patient Orchestrator
- Runtime Agent (legacy / optional)
- Report Agent
- Evaluation Agent

### Shared support modules
- Together client wrapper
- Input normalizer
- JSON store
- Published graph store
- Graph registry
- Patient graph runtime helpers
- Patient session store

---

## 2. Service catalog

| Component | Type | Primary role |
|---|---|---|
| Specialist Bot | Telegram bot | specialist-side controller and workflow UI |
| User Bot | Telegram bot | patient-side conversational entrypoint |
| Definition Agent | FastAPI | extracts and edits structured assessment draft |
| Compiler Agent | FastAPI | draft -> compiled graph |
| Patient Controller | FastAPI | free conversation, graph discovery, consent, runtime orchestration |
| Report Agent | FastAPI | result summary generation |
| Evaluation Agent | FastAPI | validation / QA layer |
| Published Graph Store | shared module | active graph persistence |
| Graph Registry | shared module | searchable graph library |
| Patient Session Store | shared module | patient conversation/session persistence |
| Patient Graph Runtime | shared module | deterministic graph execution helpers |

---

## 3. Specialist-side services

### 3.1 Specialist Bot
Responsibilities:
- accept specialist messages
- maintain specialist session state
- call definition agent
- inspect draft state
- call compiler
- call publish

### 3.2 Definition Agent
Responsibilities:
- normalize noisy input
- extract structured candidate fields
- merge with current draft
- apply edits

### 3.3 Compiler Agent
Responsibilities:
- validate draft
- compile graph
- generate unique graph id
- preserve enough metadata for runtime and registry

### 3.4 Publish Handoff
Responsibilities:
- persist active graph
- update graph registry
- expose graph to patient-side discovery and execution

---

## 4. Patient-side services

### 4.1 User Bot
Responsibilities:
- receive user messages
- forward them to patient controller
- return the controller’s reply

### 4.2 Patient Controller
Responsibilities:
- analyze the user’s message and current mode
- discover graph candidates
- propose assessments
- wait for consent
- run selected graph
- return results
- move back into free conversation mode

### 4.3 Graph Registry
Responsibilities:
- store graph metadata
- support discovery/search
- keep graph payloads available

### 4.4 Patient Session Store
Responsibilities:
- persist patient conversation mode
- persist selected graph
- persist assessment runtime state
- persist last result

### 4.5 Patient Graph Runtime
Responsibilities:
- execute graph questions deterministically
- normalize answers
- advance graph state
- compute score and result mapping

---

## 5. Supporting services

### 5.1 Report Agent
Used to build result summaries and structured output after completion.

### 5.2 Evaluation Agent
Used for:
- graph checks
- runtime consistency checks
- report QA
- future automated regression checks

---

## 6. Data ownership

### Specialist Bot owns
- specialist chat session
- controller history
- current draft reference
- current compile/publish state

### Definition Agent owns
- extraction logic
- merge logic
- edit application logic

### Compiler Agent owns
- graph compilation and unique graph id generation

### Published Graph Store owns
- active graph persistence

### Graph Registry owns
- collection of published graph entries
- graph discoverability metadata

### Patient Controller owns
- conversation mode transitions
- graph discovery and selection
- consent state
- orchestration of runtime steps

### Patient Session Store owns
- patient session persistence

### Patient Graph Runtime owns
- deterministic execution and answer application

---

## 7. Current service flow

### Specialist flow
Specialist Bot -> Definition Agent -> Compiler Agent -> Publish Store + Graph Registry

### Patient flow
User Bot -> Patient Controller -> Graph Registry / Session Store / Graph Runtime -> Result

---

## 8. MVP operational note

At the current MVP stage:
- some legacy services may still exist in the repository
- the patient side should conceptually rely on **patient controller + graph registry + session store + graph runtime**
- this is the architectural target model even if some old runtime code remains temporarily in the repo

