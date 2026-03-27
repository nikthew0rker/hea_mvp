# definition-service.md

# Assessment Definition Service

## 1. Purpose

The Assessment Definition Service accepts, stores, and manages specialist-authored assessment definitions.

Its main role is to keep assessment logic outside application code so that new assessment scenarios can be introduced without changing the runtime implementation.

This service owns the **authoring source**, but not the canonical executable artifact.  
The canonical executable artifact is created later by the Compiler Service.

---

## 2. Responsibilities

The service is responsible for:

- accepting text-based assessment definitions
- storing draft definitions
- versioning authoring inputs
- exposing definitions to the Compiler Service
- preserving raw source content for traceability

---

## 3. Out of Scope

The service does not:

- execute assessments
- calculate score
- generate reports
- own runtime session state
- provide a visual authoring UI in the MVP
- perform graph compilation

---

## 4. MVP Scope

### Included in MVP

- create definition
- update definition
- fetch definition
- list definitions
- submit definition for compilation
- store raw definition content

### Planned for Later

- specialist-facing authoring UI
- rich validation editor
- collaborative editing
- comment/review workflow
- visual graph editing

---

## 5. Main Entity

## 5.1 DefinitionInput

A specialist-authored structured definition of an assessment.

Typical content includes:

- metadata
- question definitions
- branching rules
- scoring rules
- risk bands
- report structure
- safety requirements
- optional references

The definition may be stored in YAML, JSON, or another structured text format.

---

## 6. Data Model

### Table: `assessment_definitions`

| Field | Type | Description |
|------|------|-------------|
| `id` | string | Unique definition identifier |
| `name` | string | Human-readable name |
| `slug` | string | Stable key |
| `raw_spec` | text | Full source definition |
| `status` | string | Usually `draft` in MVP |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

### Optional future fields

- `author_id`
- `review_status`
- `notes`
- `source_format`

---

## 7. API Contract

### 7.1 Create Definition

`POST /definitions`

Creates a new assessment definition.

#### Request body
- `name`
- `slug`
- `raw_spec`

#### Response
- `definition_id`
- `status`
- `created_at`

---

### 7.2 List Definitions

`GET /definitions`

Returns a list of stored definitions.

#### Response
List of:
- `definition_id`
- `name`
- `slug`
- `status`
- `updated_at`

---

### 7.3 Get Definition

`GET /definitions/{definition_id}`

Returns the full stored definition.

---

### 7.4 Update Definition

`PUT /definitions/{definition_id}`

Updates raw definition content.

#### Request body
- `raw_spec`
- optional `name`

#### Response
- updated definition metadata

---

### 7.5 Submit for Compilation

`POST /definitions/{definition_id}/compile`

Triggers compilation in the Compiler Service.

#### Response
- `definition_id`
- `compile_requested: true`

---

## 8. Validation Rules

The Definition Service performs only lightweight validation in MVP.

### Required checks

- definition exists
- `name` is present
- `slug` is unique
- `raw_spec` is not empty

### Not performed here

- graph validation
- scoring validation
- report schema validation

These belong to the Compiler Service.

---

## 9. State Model

In MVP, definition lifecycle is intentionally simple.

### Possible states

- `draft`

### Later possible states

- `under_review`
- `compiled`
- `published`
- `archived`

For the MVP, publication is represented by the compiled graph artifact, not by a rich state machine in the Definition Service.

---

## 10. Sequence Flow

```text
Specialist creates or edits definition
  -> Definition Service stores raw spec
  -> Compiler request can be triggered
  -> Compiler Service reads definition by id
```

---

## 11. Error Cases

The service should handle:

- missing definition id
- invalid request format
- duplicate slug
- empty raw spec
- unknown definition on update/fetch

---

## 12. Non-Functional Requirements

- raw definition must be stored without lossy transformation
- ids must remain stable
- storage model must be simple and debuggable
- responses must be machine-readable
- service should be easy to run locally in MVP

---

## 13. Notes for MVP

The Definition Service is intentionally small.

Its purpose is not to become a full authoring platform in the first version.  
It exists to support the main assignment requirement: **assessment behavior must change without code changes**.

The richer specialist experience remains a natural next iteration, not a dependency for MVP delivery.