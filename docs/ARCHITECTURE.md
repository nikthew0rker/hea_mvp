# ARCHITECTURE.md

# Hea MVP v2 — Agentic Architecture

## 1. Overview

The system is implemented as a **two-bot, agent-based health assessment platform**.

### External interfaces
- **Specialist Bot** — collects assessment definitions from a specialist
- **User Bot** — interacts with end users and runs published assessments

### Internal agent roles
- Definition Agent
- Compiler Agent
- Runtime Agent
- Report Agent
- Evaluation & Safety Agent

### Shared model layer
All agentic reasoning and generation uses **Together AI API** through a shared internal client.

---

## 2. Core Principle

The architecture separates:

- **conversation**
- **definition**
- **execution**
- **reporting**

The system never treats Telegram chat history as the execution truth.

Instead:

1. specialist chat is converted into a structured draft
2. the draft is compiled into a canonical executable graph
3. the runtime agent executes that graph with the user
4. the report agent produces the final result

The canonical artifact is:

**Compiled Assessment Graph**

---

## 3. High-Level Architecture

```text
Specialist Telegram Chat
    -> Specialist Bot
    -> Definition Agent
    -> Compiler Agent
    -> Canonical Compiled Graph
    -> User Bot
    -> Runtime Agent
    -> Report Agent
    -> Final User Output

At any point:
    -> Evaluation & Safety Agent
```

---

## 4. Actors

### 4.1 Specialist
A medical or product specialist defines the assessment in free-form text through Telegram.

### 4.2 End User
A user completes the published assessment through Telegram.

### 4.3 Internal Agents
The system uses specialized internal agents to structure, compile, execute, report, and validate.

---

## 5. Architectural Principles

### 5.1 Agent-first interface, graph-first execution
Bots and LLMs handle interaction and transformation.  
Compiled graphs handle actual execution logic.

### 5.2 Compiler/runtime split
Specialist intent is not executed directly.  
It is first compiled into a stable artifact.

### 5.3 Regulated conversational freedom
The runtime graph controls goals and boundaries, not exact wording.  
The runtime agent may rephrase, confirm, and merge turns without bypassing logic.

### 5.4 Guardrails-first
Safety applies both:
- before publish
- during runtime
- during report generation

### 5.5 Eval-driven
Definitions, graphs, runtime outputs, and reports are checked through deterministic evaluation cases.

---

## 6. Main Components

### 6.1 Specialist Bot
Telegram interface for the specialist.

Responsibilities:
- receive free-form assessment descriptions
- maintain definition conversation state
- return clarification requests
- show compile and publish status

### 6.2 Definition Agent
Transforms specialist chat into a structured draft.

Responsibilities:
- extract questions
- infer missing structure
- detect ambiguity
- ask for missing fields
- output a normalized definition draft

### 6.3 Compiler Agent
Transforms structured draft into a compiled graph.

Responsibilities:
- validate structure
- build graph
- attach scoring
- attach report schema
- attach guardrails
- publish graph if valid

### 6.4 User Bot
Telegram interface for the end user.

Responsibilities:
- start assessment
- deliver runtime messages
- receive user answers
- return summary/report

### 6.5 Runtime Agent
Executes the compiled graph.

Responsibilities:
- maintain session state
- interpret free text
- extract structured values
- follow transitions
- update score
- finish assessment

### 6.6 Report Agent
Builds the final user-facing result.

Responsibilities:
- summarize outcome
- list contributing factors
- attach recommendations
- include disclaimer and safety notice

### 6.7 Evaluation & Safety Agent
Runs checks over all major artifacts.

Responsibilities:
- compile checks
- runtime checks
- report checks
- red-flag behavior checks

---

## 7. Conversational Freedom

One risk of graph-driven systems is that they feel like rigid questionnaires.

This architecture avoids that by separating:
- **information goals**
- **wording**

A runtime node should be interpreted as:
- “what must be learned”
not:
- “the exact sentence the bot must send”

This enables:
- confirmation instead of re-asking
- one answer satisfying multiple slots
- flexible phrasing
- reduced chat fatigue

The runtime remains graph-constrained while the interaction remains more natural.

---

## 8. Data Flow

### Specialist flow
1. specialist writes free-form text in Telegram
2. Specialist Bot stores messages
3. Definition Agent structures draft
4. Compiler Agent validates and compiles
5. graph is published if valid

### User flow
1. user starts Telegram bot
2. User Bot loads active graph
3. Runtime Agent executes the graph
4. Report Agent generates the final result
5. user receives summary/report

---

## 9. Why This Is Still Lightweight

Although the architecture uses agents, it is intentionally not enterprise-heavy.

In the MVP:
- bots can run in one backend
- agents can be implemented as internal modules
- one shared database is enough
- Together AI is one shared client
- only the graph is canonical

This keeps the system product-ready without overbuilding.

---

## 10. MVP Boundaries

### Included
- two Telegram bots
- Together AI integration
- draft structuring
- graph compilation
- runtime execution
- final report
- lightweight evals

### Deferred
- visual authoring UI
- specialist web console
- graph editor
- evidence platform
- advanced analytics
- multi-tenant control plane

---

## 11. Summary

The architecture is now **agentic at the interaction layer** and **graph-driven at the execution layer**.

This combination gives:
- flexible Telegram-based authoring
- conversational user flow
- deterministic assessment execution
- safe reporting
- clear product extensibility