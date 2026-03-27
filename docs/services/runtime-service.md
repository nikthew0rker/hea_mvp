# runtime-service.md

# Assessment Runtime Service

## 1. Purpose

The Assessment Runtime Service executes a published compiled assessment graph and guides the end user through the assessment flow.

It is responsible for session state, branching, score updates, and user interaction orchestration.

This is the core user-facing execution engine of the system.

---

## 2. Responsibilities

The Runtime Service is responsible for:

- starting assessment sessions
- loading a published graph version
- deciding the next required information goal
- presenting the next question or confirmation
- accepting user answers
- extracting structured values from free text
- updating score and flags
- moving through graph transitions
- completing the session
- triggering report generation

---

## 3. Out of Scope

The service does not:

- accept raw specialist definitions
- compile graphs
- own authoring state
- define the graph structure
- replace final report rendering
- act as a long-term personal health assistant in MVP

---

## 4. MVP Scope

### Included in MVP

- create session
- load published compiled graph
- ask next question
- accept answers
- parse free-text answers
- minimal multi-slot extraction
- branching
- score accumulation
- risk band assignment
- session completion

### Planned for Later

- memory across assessments
- re-engagement flows
- planner/task integration
- richer personalization
- asynchronous messaging workflows

---

## 5. Internal Components

## 5.1 Graph Engine

The Graph Engine is responsible for:

- enforcing graph transitions
- checking node completion
- applying scoring rules
- maintaining deterministic flow
- enforcing mandatory path rules

## 5.2 Conversation Orchestrator

The Conversation Orchestrator improves the chat experience while preserving graph logic.

Responsibilities:

- interpret free-text responses
- extract one or more structured values from one answer
- confirm inferred values instead of re-asking
- merge nearby information requests where allowed
- reduce scripted-chat fatigue
- respect node-level freedom policies

The graph controls logic.  
The conversation layer controls phrasing.

---

## 6. Core Domain Model

## 6.1 SessionState

Represents one active or completed runtime session.

Contains:

- session id
- graph version id
- current node id
- answers
- visited path
- score
- flags
- status
- timestamps

---

## 7. Data Model

### Table: `assessment_sessions`

| Field | Type | Description |
|------|------|-------------|
| `session_id` | string | Unique session id |
| `graph_version_id` | string | Linked compiled graph version |
| `status` | string | `in_progress` / `completed` / `aborted` |
| `current_node_id` | string | Active node |
| `score` | number | Current score |
| `risk_level` | string | Final risk level when completed |
| `started_at` | datetime | Start time |
| `completed_at` | datetime | Completion time |

### Table: `assessment_answers`

| Field | Type | Description |
|------|------|-------------|
| `id` | string | Answer id |
| `session_id` | string | Linked session |
| `node_id` | string | Related node |
| `raw_answer` | text | Original user answer |
| `parsed_answer_json` | json/text | Structured parsed value(s) |
| `confidence` | float | Extraction confidence |
| `score_delta` | number | Score change |
| `created_at` | datetime | Timestamp |

### Table: `session_paths`

| Field | Type | Description |
|------|------|-------------|
| `id` | string | Path event id |
| `session_id` | string | Linked session |
| `node_id` | string | Visited node |
| `action_type` | string | Ask / confirm / infer / finish |
| `details_json` | json/text | Extra details |
| `created_at` | datetime | Timestamp |

---

## 8. Runtime Flow

```text
Start session
  -> Load graph version
  -> Initialize state
  -> Determine next required information goal
  -> Ask or confirm
  -> Receive answer
  -> Parse answer
  -> Fill slots
  -> Apply score updates
  -> Select next node
  -> Repeat
  -> Complete session
  -> Trigger report generation
```

---

## 9. API Contract

### 9.1 Start Session

`POST /runtime/sessions`

Creates a new session for a published graph version.

#### Request body
- `graph_version_id`

#### Response
- `session_id`
- `status`
- `first_action`

---

### 9.2 Get Session

`GET /runtime/sessions/{session_id}`

Returns the current session state.

---

### 9.3 Submit Answer

`POST /runtime/sessions/{session_id}/answer`

Accepts a user answer and advances the session.

#### Request body
- `answer_text`

#### Response
- updated session state
- next action
- optional extracted values

---

### 9.4 Get Next Action

`GET /runtime/sessions/{session_id}/next`

Returns the next action without writing a new answer.

Useful for UI reload/recovery.

---

### 9.5 Complete Session

`POST /runtime/sessions/{session_id}/complete`

Marks the session as complete if the graph is finished.

---

## 10. Conversational Freedom Model

The Runtime Service supports regulated conversational freedom.

This means:

- graph nodes define information goals
- the runtime does not treat every node as one fixed chatbot message
- the conversation layer may rephrase, merge, or confirm information
- mandatory branching and scoring remain deterministic

### Freedom levels

- `strict`
- `guided`
- `flexible`

### Rules

Conversational freedom must never:

- skip required nodes
- bypass red-flag checks
- invent missing logic
- produce stronger claims than supported by collected data

---

## 11. Safety Rules

The Runtime Service enforces:

- mandatory safety nodes where defined
- red-flag escalation behavior
- no unsafe bypass of mandatory graph logic
- confirmation when inferred values are low-confidence and must not be assumed

The Runtime Service must not generate diagnosis or treatment recommendations.

---

## 12. Error Cases

The service must handle:

- unknown session
- non-published graph version
- invalid answer payload
- incomplete graph state
- parsing failure
- unsupported node action
- answer that does not satisfy required information goal

In such cases, the runtime should recover gracefully where possible.

---

## 13. Non-Functional Requirements

- session must be pinned to the graph version it started with
- path history must be reproducible
- transitions must remain deterministic
- service should support local development and testing easily
- flow should remain understandable in logs/debug output

---

## 14. Notes for MVP

The Runtime Service is the main user-visible engine of the system.

The MVP goal is not to build a highly autonomous chat agent.  
The goal is to build a reliable graph-driven assessment flow that feels conversational enough to avoid form-like fatigue, while preserving deterministic logic for branching and scoring.