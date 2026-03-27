# compiler-service.md

# Assessment Compiler Service

## 1. Purpose

The Assessment Compiler Service transforms a specialist-authored assessment definition into a **canonical compiled assessment graph**.

This service is the core of the compiler/runtime split.  
It separates authoring input from executable runtime logic.

The output of this service is the system’s canonical artifact:

**CompiledAssessmentGraph**

---

## 2. Responsibilities

The Compiler Service is responsible for:

- loading a stored assessment definition
- parsing and normalizing structured input
- building graph nodes and transitions
- validating graph integrity
- validating score rules
- validating report schema
- attaching guardrail metadata
- saving compiled graph versions
- optionally publishing a compiled graph version

---

## 3. Out of Scope

The service does not:

- run user-facing assessment sessions
- own conversation flow
- generate final user reports
- store runtime answers
- provide specialist-facing visual review UI in MVP

---

## 4. MVP Scope

### Included in MVP

- compile definition into graph
- validate graph structure
- validate scoring logic
- validate report schema
- attach safety metadata
- persist compiled graph version
- retrieve compiled graph version

### Planned for Later

- visual review loop
- interactive graph diffing
- rule suggestion from external evidence
- explainable compile warnings UI
- publish workflow with roles/approval

---

## 5. Inputs and Outputs

## 5.1 Input

- `DefinitionInput` from the Definition Service
- optional reference metadata
- optional future evidence enrichment

## 5.2 Output

- `CompiledAssessmentGraph`
- `ValidationResult[]`
- compile metadata

---

## 6. Main Domain Model

## 6.1 CompiledAssessmentGraph

A compiled, executable representation of an assessment.

Contains:

- graph version id
- node definitions
- transitions
- scoring rules
- risk bands
- report schema
- guardrail policy
- compile metadata

---

## 7. Data Model

### Table: `compiled_assessment_graphs`

| Field | Type | Description |
|------|------|-------------|
| `graph_version_id` | string | Unique compiled graph version id |
| `definition_id` | string | Source definition id |
| `graph_payload` | json/text | Serialized compiled graph |
| `validation_status` | string | `valid` / `invalid` / `warning` |
| `is_published` | boolean | Whether graph is available for runtime |
| `created_at` | datetime | Compile timestamp |

### Table: `compiled_graph_validation_results`

| Field | Type | Description |
|------|------|-------------|
| `id` | string | Validation result id |
| `graph_version_id` | string | Linked graph version |
| `severity` | string | `error` / `warning` |
| `code` | string | Validation code |
| `message` | string | Human-readable description |
| `details_json` | json/text | Additional structured details |

---

## 8. Compiler Pipeline

The MVP compiler pipeline is intentionally small and deterministic.

```text
Load definition
  -> Parse raw spec
  -> Normalize structure
  -> Build nodes
  -> Build transitions
  -> Validate graph integrity
  -> Validate scoring rules
  -> Validate report schema
  -> Attach guardrails
  -> Persist compiled graph version
```

---

## 9. Validation Rules

### 9.1 Graph Integrity

Checks include:

- there is a valid start node
- all transitions point to existing nodes
- there are no unreachable mandatory nodes
- finish condition exists
- node types are supported

### 9.2 Scoring Validation

Checks include:

- scoring rules are syntactically valid
- risk bands are coherent
- required score fields exist
- no invalid score ranges

### 9.3 Report Validation

Checks include:

- required sections are defined
- disclaimer requirement exists
- report schema is structurally valid

### 9.4 Safety Validation

Checks include:

- no forbidden output directives
- red-flag policy is present if required
- no diagnosis/treatment instructions in report directives

---

## 10. API Contract

### 10.1 Compile Definition

`POST /compiler/compile/{definition_id}`

Compiles a stored definition.

#### Response
- `graph_version_id`
- `validation_status`
- `errors`
- `warnings`

---

### 10.2 Get Compiled Graph

`GET /compiler/compiled/{graph_version_id}`

Returns the compiled graph artifact.

---

### 10.3 Publish Compiled Graph

`POST /compiler/publish/{graph_version_id}`

Marks a valid compiled graph version as available for runtime.

#### MVP note
This can remain a simple boolean publish action in MVP.

---

### 10.4 Get Validation Results

`GET /compiler/validation/{graph_version_id}`

Returns compile-time errors and warnings.

---

## 11. Error Cases

The service must handle:

- missing definition
- invalid source format
- unsupported node type
- invalid transition target
- invalid score logic
- invalid report schema
- compile on broken definition

---

## 12. Non-Functional Requirements

- compile output must be deterministic for the same input
- compiled graph must be immutable after publish
- graph version ids must be stable and traceable
- compile failures must be inspectable
- service must be runnable locally in MVP

---

## 13. Sequence Flow

```text
Definition Service stores raw definition
  -> Compiler Service loads definition
  -> Compiler validates and builds graph
  -> Compiler stores compiled graph version
  -> Runtime Service later loads published graph version
```

---

## 14. Notes for MVP

The Compiler Service is one of the most important parts of the architecture.

It makes the system:

- predictable
- testable
- safer than raw prompt execution
- suitable for multiple assessments without code changes

For MVP, it should stay small and deterministic rather than becoming a complex rule-authoring platform.