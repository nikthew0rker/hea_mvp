# techspec-compiler-service.md

# Technical Spec: Assessment Compiler Service

## 1. Goal

The Assessment Compiler Service converts a stored assessment definition into a validated canonical executable graph.

This service is the main boundary between authoring and execution.

---

## 2. Functional Goal

Transform specialist-defined assessment logic into an artifact that can be executed safely and deterministically by the runtime engine.

---

## 3. Scope

### In scope for MVP

- load definition by id
- parse raw definition
- normalize assessment structure
- construct node/edge graph
- validate graph structure
- validate score rules
- validate report schema
- attach guardrail metadata
- persist compiled graph
- mark compiled graph as published

### Out of scope for MVP

- visual graph debugger
- interactive compile review UI
- auto-repair of invalid specs
- advanced evidence-driven rule synthesis
- multi-user approval workflow

---

## 4. Inputs / Outputs

## Input
- `definition_id`
- raw definition from Definition Service

## Output
- `CompiledAssessmentGraph`
- compile status
- validation errors and warnings

---

## 5. Domain Model

### CompiledAssessmentGraph

Core fields:

- `graph_version_id: str`
- `definition_id: str`
- `nodes: list`
- `edges: list`
- `scoring_rules: list`
- `risk_bands: list`
- `report_schema: dict`
- `guardrails: dict`
- `compile_metadata: dict`

### ValidationResult

- `severity`
- `code`
- `message`
- `details`

---

## 6. Storage

### Table: `compiled_assessment_graphs`

| Field | Type | Required | Notes |
|------|------|----------|------|
| `graph_version_id` | string | yes | unique |
| `definition_id` | string | yes | source definition |
| `graph_payload` | json/text | yes | serialized graph |
| `validation_status` | string | yes | valid / invalid / warning |
| `is_published` | boolean | yes | default false |
| `created_at` | datetime | yes | |

### Table: `compiled_graph_validation_results`

| Field | Type | Required | Notes |
|------|------|----------|------|
| `id` | string | yes | |
| `graph_version_id` | string | yes | |
| `severity` | string | yes | error / warning |
| `code` | string | yes | machine-readable |
| `message` | text | yes | |
| `details_json` | json/text | no | |

---

## 7. Compiler Pipeline

```text
Load definition
  -> Parse raw source
  -> Normalize structure
  -> Build nodes
  -> Build edges
  -> Validate graph
  -> Validate scoring
  -> Validate report schema
  -> Attach guardrails
  -> Persist compiled graph
```

---

## 8. Compile Logic

### 8.1 Parsing
The service parses raw spec into an internal intermediate structure.

### 8.2 Normalization
The service converts author-friendly syntax into runtime-friendly structure:
- node ids
- transitions
- scoring expressions
- report sections
- safety config

### 8.3 Graph construction
The service builds:
- start node
- question nodes
- finish node
- optional warning node
- explicit transitions

### 8.4 Validation
The service validates graph consistency before persistence.

---

## 9. Validation Rules

### 9.1 Structural validation
- start node exists
- finish node exists
- all edges point to valid nodes
- node ids are unique
- mandatory nodes are reachable

### 9.2 Scoring validation
- scoring rules are parseable
- referenced fields exist
- risk bands are non-overlapping
- risk bands cover expected score range

### 9.3 Report validation
- required sections exist
- disclaimer exists
- report fields are valid

### 9.4 Safety validation
- no forbidden directives
- no diagnosis/treatment intent in report schema
- red-flag handling config is valid if present

---

## 10. Publish Rules

A compiled graph may be published only if:

- validation has no `error`
- required report sections exist
- guardrail policy is attached
- graph payload is persisted successfully

Published graphs are immutable.

---

## 11. API

### POST /compiler/compile/{definition_id}

Compile a definition.

#### Response
```json
{
  "graph_version_id": "graph_v1",
  "validation_status": "valid",
  "errors": [],
  "warnings": []
}
```

---

### GET /compiler/compiled/{graph_version_id}

Return compiled graph.

---

### GET /compiler/validation/{graph_version_id}

Return validation results.

---

### POST /compiler/publish/{graph_version_id}

Publish compiled graph.

#### Response
```json
{
  "graph_version_id": "graph_v1",
  "published": true
}
```

---

## 12. Errors

- `404 definition_not_found`
- `400 invalid_definition_format`
- `422 graph_validation_failed`
- `422 scoring_validation_failed`
- `422 report_validation_failed`
- `409 already_published`

---

## 13. Non-Functional Requirements

- compile must be deterministic for the same input
- published graphs must be immutable
- compiler output must be traceable back to definition_id
- compile result must be debuggable via validation records
- compiler must remain lightweight enough for local MVP use

---

## 14. Acceptance Criteria

- valid definition compiles into graph
- invalid definition returns machine-readable validation errors
- compiled graph can be fetched by version id
- published graph can later be loaded by runtime
- graph immutability holds after publish
- validation results are persisted

---

## 15. Notes

The compiler is the main control layer that prevents the runtime from behaving like a raw, unconstrained prompt chain.

For MVP, it should remain a deterministic transformation/validation pipeline, not a complex AI-driven authoring assistant.