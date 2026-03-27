# techspec-definition-service.md

# Technical Spec: Assessment Definition Service

## 1. Goal

The Assessment Definition Service stores and serves specialist-authored assessment definitions.

It is the entry point for non-code assessment configuration and the source input for the compiler pipeline.

---

## 2. Functional Goal

Allow a specialist or developer to define an assessment scenario in structured text form and persist it so that:

- it can be edited without code changes
- it can be compiled into an executable graph
- it can be versioned and traced

---

## 3. Scope

### In scope for MVP

- create definition
- update definition
- fetch definition
- list definitions
- submit definition for compilation
- persist raw source exactly as written

### Out of scope for MVP

- visual editor
- collaborative editing
- review comments
- role-based permissions
- graph editing UI

---

## 4. Users

### Primary users
- specialist
- developer
- product owner / reviewer

### System consumers
- Compiler Service

---

## 5. Inputs / Outputs

## Input
Structured text definition:
- YAML
- JSON
- Markdown with structured sections

## Output
Persisted definition object:
- `definition_id`
- `name`
- `slug`
- `raw_spec`
- `status`
- timestamps

---

## 6. Domain Model

### DefinitionInput

Fields:

- `id: str`
- `name: str`
- `slug: str`
- `raw_spec: str`
- `status: str`
- `created_at: datetime`
- `updated_at: datetime`

### Suggested future extension
- `source_format`
- `author_id`
- `notes`
- `labels`

---

## 7. Storage

### Table: `assessment_definitions`

| Field | Type | Required | Notes |
|------|------|----------|------|
| `id` | string | yes | UUID or stable generated id |
| `name` | string | yes | Human-readable |
| `slug` | string | yes | Unique logical key |
| `raw_spec` | text | yes | Full source content |
| `status` | string | yes | `draft` in MVP |
| `created_at` | datetime | yes | |
| `updated_at` | datetime | yes | |

### Constraints
- `slug` must be unique
- `raw_spec` must not be empty

---

## 8. API

### POST /definitions

Create a new definition.

#### Request
```json
{
  "name": "Sleep Risk Assessment",
  "slug": "sleep-risk",
  "raw_spec": "..."
}
```

#### Response
```json
{
  "definition_id": "def_123",
  "status": "draft",
  "created_at": "..."
}
```

---

### GET /definitions

List stored definitions.

#### Response
```json
[
  {
    "definition_id": "def_123",
    "name": "Sleep Risk Assessment",
    "slug": "sleep-risk",
    "status": "draft",
    "updated_at": "..."
  }
]
```

---

### GET /definitions/{definition_id}

Fetch one definition.

---

### PUT /definitions/{definition_id}

Update definition content.

#### Request
```json
{
  "name": "Sleep Risk Assessment v2",
  "raw_spec": "..."
}
```

---

### POST /definitions/{definition_id}/compile

Trigger compile workflow.

#### Response
```json
{
  "definition_id": "def_123",
  "compile_requested": true
}
```

---

## 9. Validation

### Service-level validation only
This service performs lightweight validation:

- required fields present
- slug uniqueness
- raw_spec non-empty
- definition exists on update/fetch

### Not validated here
- graph consistency
- score rules
- report schema
- guardrails logic

These are delegated to the Compiler Service.

---

## 10. State Model

### MVP states
- `draft`

### Future states
- `under_review`
- `compiled`
- `published`
- `archived`

For MVP, publication is represented by a compiled graph version, not by a richer definition state machine.

---

## 11. Sequence Flow

```text
Client creates or edits definition
  -> Definition Service validates minimal fields
  -> Definition Service stores raw source
  -> Compiler Service can later read definition by id
```

---

## 12. Errors

### Possible errors
- `400 invalid_payload`
- `400 empty_raw_spec`
- `409 duplicate_slug`
- `404 definition_not_found`

### Error format
```json
{
  "error": "duplicate_slug",
  "message": "Slug 'sleep-risk' already exists"
}
```

---

## 13. Non-Functional Requirements

- raw source must be stored exactly as received
- ids must remain stable
- service should be fully local-dev friendly
- API must be simple enough for manual testing
- definition retrieval must be deterministic

---

## 14. Acceptance Criteria

- a new definition can be created via API
- definition can be edited without touching runtime code
- definition can be fetched by id
- compiler can load definition by id
- duplicate slug is rejected
- empty spec is rejected

---

## 15. Notes

This service should remain intentionally small.

Its purpose is not to become a full content management platform in MVP.  
Its purpose is to support the core assignment requirement: assessment behavior changes without code changes.