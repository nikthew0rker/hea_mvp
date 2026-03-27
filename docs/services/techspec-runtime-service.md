# techspec-runtime-service.md

# Technical Spec: Assessment Runtime Service

## 1. Goal

The Assessment Runtime Service executes a published compiled graph and guides the user through the assessment flow.

It is the main end-user execution engine.

---

## 2. Functional Goal

Run an adaptive assessment session that:

- asks for required information
- accepts free-text responses
- updates score deterministically
- follows graph transitions
- produces a completed session ready for report generation

---

## 3. Scope

### In scope for MVP

- create session
- load published graph version
- determine next required information goal
- render next action
- accept answer
- parse answer into structured values
- minimal multi-slot extraction
- apply score deltas
- update session path
- finish session
- trigger report generation

### Out of scope for MVP

- persistent user profile across assessments
- long-term memory
- async outreach/reminders
- multi-channel orchestration
- planning/task management

---

## 4. Internal Components

### 4.1 Graph Engine
Responsible for:
- node transitions
- required path enforcement
- score rules
- finish conditions
- graph-level correctness during execution

### 4.2 Conversation Orchestrator
Responsible for:
- interpreting free-text responses
- extracting structured slots
- confirming inferred values
- reducing repeated scripted prompts
- respecting node freedom policies

The graph controls logic.  
The conversation layer controls phrasing.

---

## 5. Domain Model

### SessionState

Fields:

- `session_id`
- `graph_version_id`
- `current_node_id`
- `status`
- `score`
- `risk_level`
- `answers`
- `visited_path`
- `flags`
- `started_at`
- `completed_at`

### AnswerRecord

Fields:

- `node_id`
- `raw_answer`
- `parsed_answer`
- `confidence`
- `score_delta`
- `timestamp`

---

## 6. Storage

### Table: `assessment_sessions`

| Field | Type | Required |
|------|------|----------|
| `session_id` | string | yes |
| `graph_version_id` | string | yes |
| `status` | string | yes |
| `current_node_id` | string | yes |
| `score` | number | yes |
| `risk_level` | string | no |
| `started_at` | datetime | yes |
| `completed_at` | datetime | no |

### Table: `assessment_answers`

| Field | Type | Required |
|------|------|----------|
| `id` | string | yes |
| `session_id` | string | yes |
| `node_id` | string | yes |
| `raw_answer` | text | yes |
| `parsed_answer_json` | json/text | yes |
| `confidence` | float | no |
| `score_delta` | number | yes |
| `created_at` | datetime | yes |

### Table: `session_paths`

| Field | Type | Required |
|------|------|----------|
| `id` | string | yes |
| `session_id` | string | yes |
| `node_id` | string | yes |
| `action_type` | string | yes |
| `details_json` | json/text | no |
| `created_at` | datetime | yes |

---

## 7. Runtime Flow

```text
Start session
  -> Load published graph
  -> Initialize session state
  -> Determine next required node/goal
  -> Ask or confirm
  -> Receive answer
  -> Parse structured values
  -> Fill slots
  -> Apply score changes
  -> Move to next node
  -> Repeat
  -> Finish session
  -> Call Report Service
```

---

## 8. Conversational Freedom Model

The runtime supports controlled conversational freedom.

### Principles
- nodes represent information goals, not one fixed utterance
- one user answer may satisfy multiple slots
- already known facts may be confirmed instead of re-asked
- freedom must never bypass required graph logic

### Freedom levels
- `strict`
- `guided`
- `flexible`

### Examples
- strict: red-flag / safety / exact value capture
- guided: standard assessment questions
- flexible: low-risk contextual clarification

---

## 9. API

### POST /runtime/sessions

Create a new session.

#### Request
```json
{
  "graph_version_id": "graph_v1"
}
```

#### Response
```json
{
  "session_id": "sess_123",
  "status": "in_progress",
  "next_action": {
    "type": "ask",
    "node_id": "sleep_duration",
    "message": "How many hours do you usually sleep per night?"
  }
}
```

---

### GET /runtime/sessions/{session_id}

Fetch current session state.

---

### POST /runtime/sessions/{session_id}/answer

Submit answer and advance session.

#### Request
```json
{
  "answer_text": "Usually around 5 to 6 hours, and I wake up a lot."
}
```

#### Response
```json
{
  "session_id": "sess_123",
  "score": 4,
  "filled_slots": ["sleep_duration_hours", "night_awakenings"],
  "next_action": {
    "type": "confirm",
    "node_id": "daytime_sleepiness",
    "message": "Got it — around 5–6 hours and frequent night awakenings. Do you also feel sleepy during the day?"
  }
}
```

---

### GET /runtime/sessions/{session_id}/next

Fetch next action without modifying state.

---

### POST /runtime/sessions/{session_id}/complete

Mark session complete when finish conditions are satisfied.

---

## 10. Scoring Logic

- score updates are driven only by compiled graph rules
- runtime does not invent scoring logic
- score deltas are recorded per answer
- final risk band is computed from compiled graph risk bands

---

## 11. Safety Rules

Runtime must enforce:

- required safety nodes and red-flag transitions
- no unsafe skipping of required questions
- low-confidence inferred facts must be confirmed when configured
- no diagnosis
- no treatment advice
- no medication recommendation

---

## 12. Errors

- `404 session_not_found`
- `404 graph_not_found`
- `409 graph_not_published`
- `400 invalid_answer_payload`
- `422 unsupported_node_state`
- `422 finish_conditions_not_met`

---

## 13. Non-Functional Requirements

- session must stay pinned to its graph version
- transitions must be deterministic
- path history must be reproducible
- service must be debuggable via logs/path records
- runtime behavior must remain stable across repeated runs

---

## 14. Acceptance Criteria

- user can start a session from a published graph
- free-text answer is accepted
- branching follows compiled graph
- score changes are stored
- session can complete successfully
- session stores graph version id
- runtime does not bypass required safety logic
- one rich answer can satisfy multiple nodes where supported

---

## 15. Notes

This service should not become an autonomous health agent in MVP.

Its role is narrower and more valuable for the assignment:
a graph-driven, conversationally tolerable, deterministic assessment runtime.