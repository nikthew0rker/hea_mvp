# DATA_MODEL.md

# Data Model

This document describes the MVP data model for the prompt-driven health assessment engine.

The goal of the model is to support:

- specialist-defined assessment inputs
- compiled graph artifacts
- runtime user sessions
- final reports
- evaluation and safety checks

The model is intentionally lightweight and suitable for a single-service MVP backed by SQLite or PostgreSQL.

---

## 1. Design Principles

The data model follows a few core rules:

- the **compiled graph** is the canonical executable artifact
- runtime sessions are always tied to a specific graph version
- reports are always tied to a specific session and graph version
- definitions, compiled artifacts, runtime state, and evaluations are stored separately
- the model supports reproducibility and simple debugging

---

## 2. Entity Overview

Main entities:

- `assessment_definitions`
- `compiled_assessment_graphs`
- `compiled_graph_validation_results`
- `assessment_sessions`
- `assessment_answers`
- `session_paths`
- `assessment_reports`
- `evaluation_runs`

Optional future entities:

- `definition_reviews`
- `evidence_references`
- `graph_publication_events`
- `user_profiles`
- `assessment_catalog`

---

## 3. Entity Relationships

```text
assessment_definitions
    |
    | 1 -> many
    v
compiled_assessment_graphs
    |
    | 1 -> many
    v
assessment_sessions
    | \
    |  \-> many assessment_answers
    |   \
    |    -> many session_paths
    |
    -> 1 assessment_reports

compiled_assessment_graphs
    |
    -> many compiled_graph_validation_results

assessment_definitions / compiled_assessment_graphs / assessment_sessions / assessment_reports
    |
    -> many evaluation_runs
```

---

## 4. assessment_definitions

Stores specialist-authored source definitions.

This is the authoring source, but not the canonical runtime artifact.

### Purpose

- store raw assessment definitions
- preserve source input exactly as written
- provide input to compiler pipeline

### Fields

| Field | Type | Required | Notes |
|------|------|----------|------|
| `id` | string | yes | Primary key |
| `name` | string | yes | Human-readable name |
| `slug` | string | yes | Unique logical key |
| `raw_spec` | text | yes | Full source definition |
| `status` | string | yes | `draft` in MVP |
| `created_at` | datetime | yes | |
| `updated_at` | datetime | yes | |

### Constraints

- `id` must be unique
- `slug` must be unique
- `raw_spec` must not be empty

### Example

```json
{
  "id": "def_123",
  "name": "Sleep Risk Assessment",
  "slug": "sleep-risk",
  "raw_spec": "name: Sleep Risk Assessment\nquestions:\n  ...",
  "status": "draft",
  "created_at": "2026-03-27T18:30:00Z",
  "updated_at": "2026-03-27T18:30:00Z"
}
```

---

## 5. compiled_assessment_graphs

Stores compiled graph artifacts produced by the Compiler Service.

This is the canonical executable artifact of the system.

### Purpose

- store runtime-ready graph versions
- store scoring rules, report schema, and guardrails
- provide immutable runtime input

### Fields

| Field | Type | Required | Notes |
|------|------|----------|------|
| `graph_version_id` | string | yes | Primary key |
| `definition_id` | string | yes | FK to `assessment_definitions.id` |
| `graph_payload` | json/text | yes | Serialized compiled graph |
| `validation_status` | string | yes | `valid`, `invalid`, `warning` |
| `is_published` | boolean | yes | Default `false` |
| `created_at` | datetime | yes | |

### Constraints

- `graph_version_id` must be unique
- `definition_id` must exist
- published graph should be immutable

### Example

```json
{
  "graph_version_id": "graph_v1",
  "definition_id": "def_123",
  "graph_payload": {
    "nodes": [],
    "edges": [],
    "scoring_rules": [],
    "risk_bands": [],
    "report_schema": {},
    "guardrails": {}
  },
  "validation_status": "valid",
  "is_published": true,
  "created_at": "2026-03-27T18:50:00Z"
}
```

---

## 6. compiled_graph_validation_results

Stores compiler validation results for a compiled graph.

### Purpose

- persist compile-time errors and warnings
- support traceability and debugging
- enable machine-readable validation reporting

### Fields

| Field | Type | Required | Notes |
|------|------|----------|------|
| `id` | string | yes | Primary key |
| `graph_version_id` | string | yes | FK to `compiled_assessment_graphs.graph_version_id` |
| `severity` | string | yes | `error` or `warning` |
| `code` | string | yes | Machine-readable code |
| `message` | text | yes | Human-readable message |
| `details_json` | json/text | no | Extra structured payload |

### Example

```json
{
  "id": "val_001",
  "graph_version_id": "graph_v1",
  "severity": "warning",
  "code": "unused_optional_node",
  "message": "Optional node is not reachable from the default path",
  "details_json": {}
}
```

---

## 7. assessment_sessions

Stores runtime assessment sessions.

A session is always tied to one compiled graph version.

### Purpose

- represent one user run of one graph version
- preserve runtime state
- store score and completion outcome

### Fields

| Field | Type | Required | Notes |
|------|------|----------|------|
| `session_id` | string | yes | Primary key |
| `graph_version_id` | string | yes | FK to `compiled_assessment_graphs.graph_version_id` |
| `status` | string | yes | `in_progress`, `completed`, `aborted` |
| `current_node_id` | string | yes | Active node |
| `score` | number | yes | Current score |
| `risk_level` | string | no | Final risk level when completed |
| `started_at` | datetime | yes | |
| `completed_at` | datetime | no | |

### Constraints

- `graph_version_id` must exist
- session must remain pinned to one graph version for its whole lifecycle

### Example

```json
{
  "session_id": "sess_123",
  "graph_version_id": "graph_v1",
  "status": "in_progress",
  "current_node_id": "sleep_duration",
  "score": 2,
  "risk_level": null,
  "started_at": "2026-03-27T19:00:00Z",
  "completed_at": null
}
```

---

## 8. assessment_answers

Stores user answers and parsed structured values for a session.

### Purpose

- keep original user answer
- store structured extraction result
- store score delta
- support traceability and debugging

### Fields

| Field | Type | Required | Notes |
|------|------|----------|------|
| `id` | string | yes | Primary key |
| `session_id` | string | yes | FK to `assessment_sessions.session_id` |
| `node_id` | string | yes | Related graph node |
| `raw_answer` | text | yes | Original user answer |
| `parsed_answer_json` | json/text | yes | Structured extracted value(s) |
| `confidence` | float | no | Parsing/extraction confidence |
| `score_delta` | number | yes | Score contribution from this answer |
| `created_at` | datetime | yes | |

### Example

```json
{
  "id": "ans_001",
  "session_id": "sess_123",
  "node_id": "sleep_duration",
  "raw_answer": "Usually around 5 to 6 hours, and I wake up a lot.",
  "parsed_answer_json": {
    "sleep_duration_hours": "5-6",
    "night_awakenings": "frequent"
  },
  "confidence": 0.92,
  "score_delta": 4,
  "created_at": "2026-03-27T19:02:00Z"
}
```

---

## 9. session_paths

Stores execution path events for a session.

### Purpose

- reconstruct runtime behavior
- support debugging and evals
- observe which nodes were visited and how

### Fields

| Field | Type | Required | Notes |
|------|------|----------|------|
| `id` | string | yes | Primary key |
| `session_id` | string | yes | FK to `assessment_sessions.session_id` |
| `node_id` | string | yes | Related node |
| `action_type` | string | yes | `ask`, `confirm`, `infer`, `finish` |
| `details_json` | json/text | no | Extra action details |
| `created_at` | datetime | yes | |

### Example

```json
{
  "id": "path_001",
  "session_id": "sess_123",
  "node_id": "sleep_duration",
  "action_type": "infer",
  "details_json": {
    "filled_slots": [
      "sleep_duration_hours",
      "night_awakenings"
    ]
  },
  "created_at": "2026-03-27T19:02:01Z"
}
```

---

## 10. assessment_reports

Stores final generated reports.

### Purpose

- persist structured report output
- store HTML snapshot
- optionally reference a PDF artifact
- tie the report to session and graph version

### Fields

| Field | Type | Required | Notes |
|------|------|----------|------|
| `report_id` | string | yes | Primary key |
| `session_id` | string | yes | FK to `assessment_sessions.session_id` |
| `graph_version_id` | string | yes | FK to `compiled_assessment_graphs.graph_version_id` |
| `report_json` | json/text | yes | Structured report |
| `html_snapshot` | text | yes | Rendered HTML |
| `pdf_path` | string | no | Optional PDF location |
| `created_at` | datetime | yes | |

### Example

```json
{
  "report_id": "rep_123",
  "session_id": "sess_123",
  "graph_version_id": "graph_v1",
  "report_json": {
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
  },
  "html_snapshot": "<html>...</html>",
  "pdf_path": null,
  "created_at": "2026-03-27T19:09:00Z"
}
```

---

## 11. evaluation_runs

Stores evaluation and safety run results.

### Purpose

- record compile checks
- record runtime evals
- record report checks
- provide reproducible machine-readable validation results

### Fields

| Field | Type | Required | Notes |
|------|------|----------|------|
| `run_id` | string | yes | Primary key |
| `target_type` | string | yes | `definition`, `graph`, `session`, `report` |
| `target_id` | string | yes | Linked target id |
| `status` | string | yes | `passed`, `failed`, `warning` |
| `results_json` | json/text | yes | Full check results |
| `created_at` | datetime | yes | |

### Example

```json
{
  "run_id": "eval_123",
  "target_type": "graph",
  "target_id": "graph_v1",
  "status": "passed",
  "results_json": {
    "checks": [
      {
        "check_name": "required_sections_present",
        "status": "passed",
        "message": "All required sections exist"
      }
    ],
    "passed_count": 1,
    "failed_count": 0,
    "warnings": []
  },
  "created_at": "2026-03-27T19:10:00Z"
}
```

---

## 12. Suggested SQL Schema (MVP)

Below is a simplified SQL-oriented schema outline.

```sql
CREATE TABLE assessment_definitions (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  raw_spec TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE compiled_assessment_graphs (
  graph_version_id TEXT PRIMARY KEY,
  definition_id TEXT NOT NULL,
  graph_payload TEXT NOT NULL,
  validation_status TEXT NOT NULL,
  is_published INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (definition_id) REFERENCES assessment_definitions(id)
);

CREATE TABLE compiled_graph_validation_results (
  id TEXT PRIMARY KEY,
  graph_version_id TEXT NOT NULL,
  severity TEXT NOT NULL,
  code TEXT NOT NULL,
  message TEXT NOT NULL,
  details_json TEXT,
  FOREIGN KEY (graph_version_id) REFERENCES compiled_assessment_graphs(graph_version_id)
);

CREATE TABLE assessment_sessions (
  session_id TEXT PRIMARY KEY,
  graph_version_id TEXT NOT NULL,
  status TEXT NOT NULL,
  current_node_id TEXT NOT NULL,
  score REAL NOT NULL,
  risk_level TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  FOREIGN KEY (graph_version_id) REFERENCES compiled_assessment_graphs(graph_version_id)
);

CREATE TABLE assessment_answers (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  raw_answer TEXT NOT NULL,
  parsed_answer_json TEXT NOT NULL,
  confidence REAL,
  score_delta REAL NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (session_id) REFERENCES assessment_sessions(session_id)
);

CREATE TABLE session_paths (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  details_json TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (session_id) REFERENCES assessment_sessions(session_id)
);

CREATE TABLE assessment_reports (
  report_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  graph_version_id TEXT NOT NULL,
  report_json TEXT NOT NULL,
  html_snapshot TEXT NOT NULL,
  pdf_path TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (session_id) REFERENCES assessment_sessions(session_id),
  FOREIGN KEY (graph_version_id) REFERENCES compiled_assessment_graphs(graph_version_id)
);

CREATE TABLE evaluation_runs (
  run_id TEXT PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  status TEXT NOT NULL,
  results_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

---

## 13. Canonical Artifact and Source of Truth

The data model distinguishes between:

### Authoring Source
- `assessment_definitions.raw_spec`

### Canonical Executable Artifact
- `compiled_assessment_graphs.graph_payload`

This means:

- the specialist writes the source definition
- the compiler transforms it into the canonical graph
- runtime always executes the canonical graph
- reports and evals are always tied to a graph version

---

## 14. Versioning Rules

### Definitions
Definitions may be edited in MVP.

### Compiled graphs
Compiled graphs must be treated as versioned artifacts.

### Published graphs
Published compiled graphs must be immutable.

### Runtime sessions
A session must stay pinned to the graph version it started with.

### Reports
A report must always reference the graph version that produced it.

---

## 15. Observability-Oriented Fields

The model intentionally includes fields that support debugging and observability:

- `graph_version_id` in sessions
- `score_delta` in answers
- `action_type` in session paths
- `results_json` in evaluation runs
- `report_json` and `html_snapshot` in reports

These make it easier to understand what happened in a demo or during local debugging without introducing a heavy telemetry stack.

---

## 16. Future Extensions

Possible future model additions:

### definition_reviews
For formal specialist review and approval.

### evidence_references
For storing linked source references used during compilation.

### graph_publication_events
For audit trail of compile/publish actions.

### user_profiles
For persistent user identity and history.

### assessment_catalog
For grouping and organizing multiple assessments.

These are intentionally excluded from the MVP schema.

---

## 17. Summary

The MVP data model is built around one central idea:

**the compiled graph is the canonical executable artifact**

Everything else supports that:

- definitions provide authoring input
- sessions execute one graph version
- answers and paths make runtime traceable
- reports make output persistent
- evaluation runs make behavior testable

This keeps the system simple, reproducible, and extensible without turning the MVP into an enterprise platform.