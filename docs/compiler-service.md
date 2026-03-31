# compiler-service.md

## 1. Purpose

Compiler Service converts a structured draft into a compiled graph artifact that can be used by runtime and publication.

This is the transition point between:
- specialist authoring
- executable patient-side assessment flow

---

## 2. Input

The service accepts a structured draft that should already contain:
- topic
- questions
- scoring logic

Optional but preferred:
- risk bands
- report requirements
- safety requirements

---

## 3. Output

The compiler returns:
- `status`
- `graph_version_id`
- compiled `graph`
- optional `feedback`

---

## 4. Core responsibilities

- validate minimum graph readiness
- transform draft structure into graph-friendly structure
- preserve graph identity
- provide compile result back to specialist workflow

---

## 5. API contract

### Endpoint
`POST /compile`

### Request
```json
{
  "draft": {
    "understood": {
      "topic": "diabetes"
    },
    "candidate_questions": [],
    "candidate_scoring_rules": {}
  }
}
```

### Response
```json
{
  "status": "compiled",
  "graph_version_id": "graph_v1_demo",
  "graph": {
    "graph_version_id": "graph_v1_demo",
    "nodes": [],
    "edges": []
  },
  "feedback": []
}
```

---

## 6. Compile readiness

Blocking requirements:
- topic
- at least one question
- scoring logic

If one or more are missing, the service should return feedback suitable for specialist-side correction.

---

## 7. Relationship to publish

Compilation alone is not enough for patient runtime.

After compilation:
- the graph exists
- but it is not yet active for patient assistant

Only the publish step makes the graph available to patient runtime.

---

## 8. MVP boundaries

The current compiler is lightweight and suitable for MVP demo purposes.

Not included yet:
- graph schema versioning
- migration support
- static graph optimization
- formal node type registry
- compile-time evaluation hooks
