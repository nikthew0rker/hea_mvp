# techspec-evaluation-service.md

# Technical Spec: Evaluation & Safety Service

## 1. Goal

The Evaluation & Safety Service provides a lightweight quality layer for the MVP.

It checks that:

- definitions and graphs are valid
- runtime behavior matches expectations
- reports are complete and safe

---

## 2. Functional Goal

Catch broken graphs, broken execution paths, and unsafe or incomplete outputs before or during local MVP development and demo preparation.

---

## 3. Scope

### In scope for MVP

- compile-time checks
- runtime eval cases
- report validation checks
- red-flag handling checks
- machine-readable evaluation output
- persisted eval results

### Out of scope for MVP

- model benchmarking platform
- full red-team system
- interactive eval dashboard
- scheduled production monitoring
- broad telemetry platform

---

## 4. Evaluation Targets

The service evaluates:

- definitions / compiled graphs
- runtime sessions
- reports

---

## 5. Data Model

### Table: `evaluation_runs`

| Field | Type | Required |
|------|------|----------|
| `run_id` | string | yes |
| `target_type` | string | yes |
| `target_id` | string | yes |
| `status` | string | yes |
| `results_json` | json/text | yes |
| `created_at` | datetime | yes |

---

## 6. Required Checks

### 6.1 Compile checks
- valid definition compiles
- invalid definition is rejected
- required nodes exist
- transitions target valid nodes
- scoring rules are valid
- report schema includes required sections
- disclaimer requirement exists

### 6.2 Runtime evals
- expected answers produce expected branch path
- expected answers produce expected score
- graph version id is stored in session
- one free-text answer may satisfy multiple nodes if confidence is sufficient
- known facts are confirmed instead of re-asked
- conversational freedom never bypasses mandatory graph logic
- red-flag response triggers safety behavior

### 6.3 Report checks
- report includes mandatory sections
- disclaimer is present
- no diagnosis language
- no treatment plan
- no medication recommendation
- safety notice appears when required
- graph version id is included in report metadata

---

## 7. API

### POST /evals/compile/{definition_id}

Run compile checks.

---

### POST /evals/runtime/{graph_version_id}

Run runtime eval suite for graph version.

---

### POST /evals/report/{session_id}

Run report validation checks.

---

### GET /evals/results/{run_id}

Return stored eval results.

---

## 8. Result Format

Example shape:

```json
{
  "run_id": "eval_123",
  "target_type": "graph",
  "target_id": "graph_v1",
  "status": "passed",
  "checks": [
    {
      "check_name": "required_sections_present",
      "status": "passed",
      "message": "All required sections exist"
    }
  ],
  "passed_count": 8,
  "failed_count": 0,
  "warnings": []
}
```

---

## 9. Safety Policy

The service verifies compliance with MVP safety policy:

- no diagnosis
- no treatment recommendation
- no medication advice
- explicit disclaimer required
- urgent escalation for red flags
- lower-confidence wording for incomplete information

The service validates policy conformance.  
It does not invent new business logic.

---

## 10. Errors

- `404 target_not_found`
- `400 invalid_target_type`
- `422 malformed_fixture`
- `500 evaluation_execution_failed`

---

## 11. Non-Functional Requirements

- eval runs should be deterministic where possible
- results should be machine-readable
- service should be easy to execute locally
- output should be readable enough for debugging/demo confidence
- eval layer should stay lightweight

---

## 12. Acceptance Criteria

- compile checks can be run against a definition
- runtime eval suite can be run against a graph version
- report checks can be run against a completed session
- failed checks are persisted with machine-readable payload
- successful runs are inspectable
- red-flag safety behavior is covered by at least one eval

---

## 13. Notes

The Evaluation & Safety Service is intentionally small.

Its purpose is practical, not ceremonial:
- catch errors early
- support confidence in the demo
- make the MVP easier to trust
- prevent obvious unsafe output patterns