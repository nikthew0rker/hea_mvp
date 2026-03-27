# API.md

# API Specification

This document describes the MVP API of the prompt-driven health assessment engine.

The API is grouped by logical service boundaries, but in the MVP it can be implemented as a **single FastAPI application**.

---

## 1. General Conventions

### Base URL

```text
/api/v1
```

### Content Type

All request and response bodies use:

```http
Content-Type: application/json
```

### Authentication

Authentication is out of scope for the MVP.

### Timestamps

All timestamps should be returned in ISO 8601 format.

Example:

```json
"created_at": "2026-03-27T18:30:00Z"
```

### IDs

All main entities use stable string identifiers.

Examples:

- `def_123`
- `graph_v1`
- `sess_123`
- `rep_123`
- `eval_123`

---

## 2. Error Format

All error responses should follow a consistent format.

Example:

```json
{
  "error": "duplicate_slug",
  "message": "Slug 'sleep-risk' already exists",
  "details": null
}
```

### Standard fields

- `error` — machine-readable error code
- `message` — human-readable explanation
- `details` — optional structured payload

---

## 3. Common Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Resource created |
| `400` | Invalid request |
| `404` | Resource not found |
| `409` | Conflict |
| `422` | Validation failed |
| `500` | Internal error |

---

# 4. Definition Service API

## 4.1 Create Definition

**POST** `/definitions`

Creates a new assessment definition.

### Request body

```json
{
  "name": "Sleep Risk Assessment",
  "slug": "sleep-risk",
  "raw_spec": "name: Sleep Risk Assessment\nquestions:\n  ..."
}
```

### Response

```json
{
  "definition_id": "def_123",
  "name": "Sleep Risk Assessment",
  "slug": "sleep-risk",
  "status": "draft",
  "created_at": "2026-03-27T18:30:00Z",
  "updated_at": "2026-03-27T18:30:00Z"
}
```

### Possible errors

- `400 invalid_payload`
- `400 empty_raw_spec`
- `409 duplicate_slug`

---

## 4.2 List Definitions

**GET** `/definitions`

Returns stored definitions.

### Response

```json
[
  {
    "definition_id": "def_123",
    "name": "Sleep Risk Assessment",
    "slug": "sleep-risk",
    "status": "draft",
    "updated_at": "2026-03-27T18:30:00Z"
  }
]
```

---

## 4.3 Get Definition

**GET** `/definitions/{definition_id}`

Returns one stored definition.

### Response

```json
{
  "definition_id": "def_123",
  "name": "Sleep Risk Assessment",
  "slug": "sleep-risk",
  "raw_spec": "name: Sleep Risk Assessment\nquestions:\n  ...",
  "status": "draft",
  "created_at": "2026-03-27T18:30:00Z",
  "updated_at": "2026-03-27T18:30:00Z"
}
```

### Possible errors

- `404 definition_not_found`

---

## 4.4 Update Definition

**PUT** `/definitions/{definition_id}`

Updates definition content.

### Request body

```json
{
  "name": "Sleep Risk Assessment v2",
  "raw_spec": "name: Sleep Risk Assessment v2\nquestions:\n  ..."
}
```

### Response

```json
{
  "definition_id": "def_123",
  "name": "Sleep Risk Assessment v2",
  "slug": "sleep-risk",
  "status": "draft",
  "updated_at": "2026-03-27T18:45:00Z"
}
```

### Possible errors

- `404 definition_not_found`
- `400 invalid_payload`

---

## 4.5 Request Compilation

**POST** `/definitions/{definition_id}/compile`

Requests compilation of a stored definition.

### Response

```json
{
  "definition_id": "def_123",
  "compile_requested": true
}
```

### Possible errors

- `404 definition_not_found`

---

# 5. Compiler Service API

## 5.1 Compile Definition

**POST** `/compiler/compile/{definition_id}`

Compiles a stored definition into a compiled graph.

### Response

```json
{
  "graph_version_id": "graph_v1",
  "definition_id": "def_123",
  "validation_status": "valid",
  "errors": [],
  "warnings": []
}
```

### Possible errors

- `404 definition_not_found`
- `400 invalid_definition_format`
- `422 graph_validation_failed`
- `422 scoring_validation_failed`
- `422 report_validation_failed`

---

## 5.2 Get Compiled Graph

**GET** `/compiler/compiled/{graph_version_id}`

Returns the compiled graph artifact.

### Response

```json
{
  "graph_version_id": "graph_v1",
  "definition_id": "def_123",
  "is_published": false,
  "validation_status": "valid",
  "graph_payload": {
    "nodes": [],
    "edges": [],
    "scoring_rules": [],
    "risk_bands": [],
    "report_schema": {},
    "guardrails": {}
  },
  "created_at": "2026-03-27T18:50:00Z"
}
```

### Possible errors

- `404 graph_not_found`

---

## 5.3 Get Validation Results

**GET** `/compiler/validation/{graph_version_id}`

Returns validation results for a compiled graph.

### Response

```json
{
  "graph_version_id": "graph_v1",
  "validation_status": "valid",
  "results": [
    {
      "severity": "warning",
      "code": "unused_optional_node",
      "message": "Optional node is not reachable from the default path",
      "details": {}
    }
  ]
}
```

### Possible errors

- `404 graph_not_found`

---

## 5.4 Publish Compiled Graph

**POST** `/compiler/publish/{graph_version_id}`

Publishes a valid compiled graph version for runtime use.

### Response

```json
{
  "graph_version_id": "graph_v1",
  "published": true
}
```

### Possible errors

- `404 graph_not_found`
- `409 already_published`
- `422 graph_not_valid`

---

# 6. Runtime Service API

## 6.1 Start Session

**POST** `/runtime/sessions`

Creates a new runtime session from a published compiled graph.

### Request body

```json
{
  "graph_version_id": "graph_v1"
}
```

### Response

```json
{
  "session_id": "sess_123",
  "graph_version_id": "graph_v1",
  "status": "in_progress",
  "score": 0,
  "next_action": {
    "type": "ask",
    "node_id": "sleep_duration",
    "message": "How many hours do you usually sleep per night?"
  },
  "started_at": "2026-03-27T19:00:00Z"
}
```

### Possible errors

- `404 graph_not_found`
- `409 graph_not_published`

---

## 6.2 Get Session

**GET** `/runtime/sessions/{session_id}`

Returns current session state.

### Response

```json
{
  "session_id": "sess_123",
  "graph_version_id": "graph_v1",
  "status": "in_progress",
  "current_node_id": "sleep_duration",
  "score": 0,
  "risk_level": null,
  "started_at": "2026-03-27T19:00:00Z",
  "completed_at": null
}
```

### Possible errors

- `404 session_not_found`

---

## 6.3 Get Next Action

**GET** `/runtime/sessions/{session_id}/next`

Returns the next action for the session.

### Response

```json
{
  "session_id": "sess_123",
  "next_action": {
    "type": "ask",
    "node_id": "sleep_duration",
    "message": "How many hours do you usually sleep per night?"
  }
}
```

### Possible errors

- `404 session_not_found`

---

## 6.4 Submit Answer

**POST** `/runtime/sessions/{session_id}/answer`

Submits a user answer and advances the session.

### Request body

```json
{
  "answer_text": "Usually around 5 to 6 hours, and I wake up a lot."
}
```

### Response

```json
{
  "session_id": "sess_123",
  "score": 4,
  "filled_slots": [
    "sleep_duration_hours",
    "night_awakenings"
  ],
  "next_action": {
    "type": "confirm",
    "node_id": "daytime_sleepiness",
    "message": "Got it — around 5–6 hours and frequent night awakenings. Do you also feel sleepy during the day?"
  }
}
```

### Possible errors

- `404 session_not_found`
- `400 invalid_answer_payload`
- `422 unsupported_node_state`

---

## 6.5 Complete Session

**POST** `/runtime/sessions/{session_id}/complete`

Marks the session as complete if finish conditions are met.

### Response

```json
{
  "session_id": "sess_123",
  "status": "completed",
  "score": 5,
  "risk_level": "moderate",
  "completed_at": "2026-03-27T19:08:00Z"
}
```

### Possible errors

- `404 session_not_found`
- `422 finish_conditions_not_met`

---

# 7. Report Service API

## 7.1 Generate Report

**POST** `/reports/generate/{session_id}`

Generates a report for a completed session.

### Response

```json
{
  "report_id": "rep_123",
  "session_id": "sess_123",
  "graph_version_id": "graph_v1",
  "created_at": "2026-03-27T19:09:00Z"
}
```

### Possible errors

- `404 session_not_found`
- `409 session_not_completed`

---

## 7.2 Get Report

**GET** `/reports/{report_id}`

Returns the structured report.

### Response

```json
{
  "report_id": "rep_123",
  "session_id": "sess_123",
  "graph_version_id": "graph_v1",
  "score": 5,
  "risk_level": "moderate",
  "summary": "Your answers suggest a moderate level of sleep-related risk.",
  "main_contributing_factors": [
    "Short sleep duration",
    "Frequent night awakenings"
  ],
  "recommendations": [
    "Try to maintain a more consistent sleep schedule.",
    "Pay attention to factors that may interrupt sleep."
  ],
  "disclaimer": "This assessment is informational and does not provide a medical diagnosis.",
  "safety_notice": null
}
```

### Possible errors

- `404 report_not_found`

---

## 7.3 Get HTML Report

**GET** `/reports/{report_id}/html`

Returns rendered HTML.

### Response

```html
<html>
  <body>
    <h1>Sleep Risk Assessment Report</h1>
    ...
  </body>
</html>
```

### Possible errors

- `404 report_not_found`

---

## 7.4 Get PDF Report

**GET** `/reports/{report_id}/pdf`

Returns PDF if enabled.

### Response

Binary PDF response.

### Possible errors

- `404 report_not_found`
- `404 pdf_not_available`

---

# 8. Evaluation & Safety Service API

## 8.1 Run Compile Checks

**POST** `/evals/compile/{definition_id}`

Runs compile-time validation checks.

### Response

```json
{
  "run_id": "eval_123",
  "target_type": "definition",
  "target_id": "def_123",
  "status": "passed"
}
```

### Possible errors

- `404 definition_not_found`

---

## 8.2 Run Runtime Evals

**POST** `/evals/runtime/{graph_version_id}`

Runs runtime evaluation cases against a graph version.

### Response

```json
{
  "run_id": "eval_124",
  "target_type": "graph",
  "target_id": "graph_v1",
  "status": "passed"
}
```

### Possible errors

- `404 graph_not_found`

---

## 8.3 Run Report Checks

**POST** `/evals/report/{session_id}`

Runs report validation checks for a completed session.

### Response

```json
{
  "run_id": "eval_125",
  "target_type": "session",
  "target_id": "sess_123",
  "status": "passed"
}
```

### Possible errors

- `404 session_not_found`
- `409 session_not_completed`

---

## 8.4 Get Evaluation Results

**GET** `/evals/results/{run_id}`

Returns stored evaluation results.

### Response

```json
{
  "run_id": "eval_123",
  "target_type": "definition",
  "target_id": "def_123",
  "status": "passed",
  "checks": [
    {
      "check_name": "valid_definition_compiles",
      "status": "passed",
      "message": "Definition compiled successfully"
    }
  ],
  "passed_count": 1,
  "failed_count": 0,
  "warnings": []
}
```

### Possible errors

- `404 eval_run_not_found`

---

# 9. Suggested Response Models

## 9.1 NextAction

```json
{
  "type": "ask",
  "node_id": "sleep_duration",
  "message": "How many hours do you usually sleep per night?"
}
```

Possible `type` values:

- `ask`
- `confirm`
- `finish`

---

## 9.2 ValidationResult

```json
{
  "severity": "error",
  "code": "missing_finish_node",
  "message": "Graph does not define a finish node",
  "details": {}
}
```

---

## 9.3 FinalReport

```json
{
  "report_id": "rep_123",
  "session_id": "sess_123",
  "graph_version_id": "graph_v1",
  "score": 5,
  "risk_level": "moderate",
  "summary": "Your answers suggest a moderate level of sleep-related risk.",
  "main_contributing_factors": [
    "Short sleep duration",
    "Frequent night awakenings"
  ],
  "recommendations": [
    "Try to maintain a more consistent sleep schedule."
  ],
  "disclaimer": "This assessment is informational and does not provide a medical diagnosis.",
  "safety_notice": null
}
```

---

# 10. API Flow Summary

## Authoring / Compile

```text
POST   /definitions
PUT    /definitions/{definition_id}
POST   /definitions/{definition_id}/compile
POST   /compiler/compile/{definition_id}
POST   /compiler/publish/{graph_version_id}
```

## Runtime

```text
POST   /runtime/sessions
GET    /runtime/sessions/{session_id}
GET    /runtime/sessions/{session_id}/next
POST   /runtime/sessions/{session_id}/answer
POST   /runtime/sessions/{session_id}/complete
```

## Report

```text
POST   /reports/generate/{session_id}
GET    /reports/{report_id}
GET    /reports/{report_id}/html
GET    /reports/{report_id}/pdf
```

## Evaluation

```text
POST   /evals/compile/{definition_id}
POST   /evals/runtime/{graph_version_id}
POST   /evals/report/{session_id}
GET    /evals/results/{run_id}
```

---

# 11. Notes for MVP

This API is intentionally small and focused on one end-to-end flow:

- define assessment
- compile graph
- run session
- generate report
- validate behavior

It is designed to support a working MVP within a few days, while preserving clear boundaries for future product growth.