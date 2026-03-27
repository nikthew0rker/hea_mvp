# evaluation-service.md

# Evaluation & Safety Service

## 1. Purpose

The Evaluation & Safety Service validates graph correctness, runtime behavior, and report safety/completeness.

It provides the minimum quality layer required to make the MVP testable, reproducible, and safer.

This service is intentionally lightweight.

---

## 2. Responsibilities

The service is responsible for:

- running compile-time checks
- running deterministic runtime eval cases
- checking report completeness
- checking red-flag behavior
- validating key safety constraints
- storing evaluation results

---

## 3. Out of Scope

The service does not:

- replace compiler logic
- replace runtime logic
- replace report generation
- run a full observability platform
- benchmark model providers
- act as a production red-team system in MVP

---

## 4. MVP Scope

### Included in MVP

- compile validation checks
- deterministic runtime eval cases
- report completeness checks
- red-flag behavior checks
- safety policy assertions
- machine-readable evaluation results

### Planned for Later

- scheduled regression suite
- model quality dashboards
- interactive eval UI
- red-team scenarios
- dataset-backed benchmark workflows

---

## 5. Evaluation Targets

The service evaluates three main targets:

- assessment definitions / compiled graphs
- runtime execution behavior
- generated reports

---

## 6. Core Data Model

### Table: `evaluation_runs`

| Field | Type | Description |
|------|------|-------------|
| `run_id` | string | Evaluation run id |
| `target_type` | string | `definition`, `graph`, `session`, `report` |
| `target_id` | string | Evaluated target id |
| `status` | string | `passed`, `failed`, `warning` |
| `results_json` | json/text | Full structured results |
| `created_at` | datetime | Run timestamp |

---

## 7. Compile-Time Checks

Compile-time checks validate whether a definition or graph is structurally safe to execute.

### Required compile checks

- valid definition compiles successfully
- invalid definition is rejected
- required nodes exist
- transitions point to valid targets
- scoring rules are structurally valid
- report schema includes required sections
- disclaimer requirement is present

---

## 8. Runtime Evaluation Cases

Runtime evals validate the behavior of the execution engine.

### Required runtime evals

1. expected answers produce expected branch path
2. expected answers produce expected score
3. graph version is stored in the session
4. a single free-text answer can satisfy multiple nodes when confidence is sufficient
5. already-known information is confirmed instead of re-asked
6. conversational freedom does not bypass mandatory graph logic
7. red-flag responses trigger mandatory escalation behavior

---

## 9. Report Checks

Report checks validate the final output structure and safety.

### Required report checks

- report contains mandatory sections
- disclaimer is present
- no diagnosis language
- no treatment plan
- no medication recommendation
- safety notice appears when required
- graph version id is present in report metadata

---

## 10. Safety Policy

The service checks compliance with MVP safety policy.

### Safety rules

- no diagnosis
- no treatment recommendation
- no medication advice
- explicit disclaimer required
- urgent escalation wording for red flags
- lower-confidence wording when information is incomplete

The service does not invent safety logic.
It checks whether the system behavior conforms to predefined rules.

---

## 11. API Contract

### 11.1 Run Compile Checks

`POST /evals/compile/{definition_id}`

Runs definition/compile validation.

---

### 11.2 Run Runtime Evals

`POST /evals/runtime/{graph_version_id}`

Runs runtime evaluation cases against a graph version.

---

### 11.3 Run Report Checks

`POST /evals/report/{session_id}`

Runs report validation for a completed session.

---

### 11.4 Get Evaluation Results

`GET /evals/results/{run_id}`

Returns machine-readable evaluation results.

---

## 12. Result Format

A typical evaluation result should include:

- `run_id`
- `target_type`
- `target_id`
- `status`
- `checks`
- `passed_count`
- `failed_count`
- `warnings`

Each check should include:

- `check_name`
- `status`
- `message`
- optional `details`

---

## 13. Error Cases

The service must handle:

- unknown definition/graph/session/report
- missing required artifacts
- invalid test fixtures
- malformed results payload
- safety check failure
- unsupported target type

---

## 14. Non-Functional Requirements

- evaluation runs must be deterministic where possible
- results must be machine-readable
- results must be easy to inspect locally
- service must be lightweight enough for MVP development flow
- evaluation should be runnable during local iteration, not only in CI

---

## 15. Notes for MVP

The Evaluation & Safety Service should not become a large platform in the first version.

Its purpose is practical:

- catch broken graphs
- catch broken runtime behavior
- catch unsafe or incomplete reports
- make the MVP easier to trust and debug

A small, deterministic eval layer is enough to significantly improve the quality of the assessment engine without adding unnecessary platform complexity.
