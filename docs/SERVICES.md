# SERVICES.md

# Service Map — Agentic Architecture

## 1. Overview

This system is organized around **two Telegram bot interfaces** and a set of **internal agent services**.

The service map is logical, not necessarily infrastructural.  
In the MVP, all services may still live inside a single backend deployment.

---

## 2. External Interface Services

### 2.1 Specialist Bot Service
Telegram adapter for specialist-side interaction.

Responsibilities:
- receive messages from specialists
- manage specialist conversation state
- hand off raw content to the Definition Agent
- present compile/publish feedback

### 2.2 User Bot Service
Telegram adapter for end-user interaction.

Responsibilities:
- receive user messages
- maintain active assessment session linkage
- hand off user input to the Runtime Agent
- deliver final summary/report

---

## 3. Core Agent Services

### 3.1 Definition Agent Service
Responsible for turning specialist chat history into a structured assessment draft.

### 3.2 Compiler Agent Service
Responsible for turning a structured draft into a compiled graph.

### 3.3 Runtime Agent Service
Responsible for executing a published graph with an end user.

### 3.4 Report Agent Service
Responsible for producing the final user-facing result.

### 3.5 Evaluation & Safety Agent Service
Responsible for quality checks and safety validation.

---

## 4. Shared Infrastructure Services

### 4.1 Together AI Client
A shared internal client used by all agent services that require LLM reasoning or generation.

### 4.2 Shared Storage Layer
A shared DB used to store:
- specialist conversation state
- definition drafts
- compiled graphs
- runtime sessions
- reports
- eval runs

---

## 5. Canonical Artifact

The system has one canonical executable artifact:

**Compiled Assessment Graph**

This is what runtime executes.

Everything else is either:
- raw input
- intermediate state
- output
- evaluation data

---

## 6. Service Interaction Map

```text
Specialist Bot Service
    -> Definition Agent Service
    -> Compiler Agent Service
    -> Shared Storage

User Bot Service
    -> Runtime Agent Service
    -> Report Agent Service
    -> Shared Storage

Evaluation & Safety Agent Service
    -> reads from Shared Storage
    -> evaluates all major artifacts

All agent services
    -> Together AI Client
```

---

## 7. Why These Boundaries Exist

These boundaries are intentionally chosen to preserve:

- clear ownership
- compiler/runtime separation
- traceable state transitions
- simple future extensibility

This is still a lightweight MVP because:
- the services are logical
- they can be modules, not separate deployments
- the graph remains the stable center of the system

---

## 8. Mapping from Old Docs to New Roles

The documentation filenames remain stable, but their meaning has changed:

- `definition-service.md` → Specialist Intake + Definition Agent
- `compiler-service.md` → Compiler Agent
- `runtime-service.md` → User Bot + Runtime Agent
- `report-service.md` → Report Agent
- `evaluation-service.md` → Evaluation & Safety Agent

---

## 9. Summary

The system now has:
- 2 bot-facing services
- 5 internal agent services
- 1 shared model client
- 1 shared state layer
- 1 canonical executable graph

That is the minimal service shape needed for the new agentic architecture.