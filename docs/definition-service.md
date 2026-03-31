# definition-service.md

## 1. Purpose

Definition Service is responsible for converting specialist input into a structured draft and for applying edits to that draft.

It supports two specialist-side modes:

- **update mode** — parse new source material and merge it into the draft
- **edit mode** — apply a natural-language change request to the existing draft

This is the main structured authoring layer of the system.

---

## 2. Inputs

Definition Service accepts:
- specialist free text
- questionnaire scales
- scoring tables
- guideline fragments
- noisy webpage content
- natural-language edit instructions

It also accepts the current draft state so it can merge or modify instead of starting from zero.

---

## 3. Output artifact

The output is a **DraftResponse** object containing:
- `language`
- `status`
- `understood`
- `candidate_questions`
- `candidate_scoring_rules`
- `candidate_risk_bands`
- `candidate_report_requirements`
- `candidate_safety_requirements`
- `missing_fields`
- `suggested_next_question`
- `draft`

---

## 4. Internal pipeline

### 4.1 Update mode
1. receive specialist content
2. normalize noisy input
3. run structured extraction
4. sanitize model output
5. merge with existing draft
6. compute missing fields
7. return updated draft object

### 4.2 Edit mode
1. receive edit instruction
2. receive current draft
3. ask model to apply a conservative change
4. sanitize returned structure
5. merge with current draft
6. recompute missing fields
7. return updated draft

---

## 5. Sanitization requirement

The service must never trust raw model output directly.

Reason:
LLM output may contain:
- booleans instead of dicts
- strings instead of arrays
- null values
- incomplete keys

Therefore the service includes explicit shape sanitization before merge.

This is a core technical requirement, not an optional improvement.

---

## 6. Draft merge rules

Priority:
1. explicit new extracted or edited content
2. existing current draft
3. heuristic fallback from normalized input

Deduplication is applied for:
- questions
- risk bands
- generic requirements

---

## 7. API contract

### Endpoint
`POST /draft`

### Request
```json
{
  "specialist_text": "text from specialist",
  "conversation_id": "specialist_chat_123",
  "current_draft": {},
  "current_language": "ru",
  "conversation_summary": null,
  "operation": "update"
}
```

### Response
```json
{
  "conversation_id": "specialist_chat_123",
  "status": "needs_clarification",
  "language": "ru",
  "understood": {
    "topic": "diabetes",
    "target_audience": "adults",
    "questions_count": 8
  },
  "candidate_questions": [],
  "candidate_scoring_rules": {},
  "candidate_risk_bands": [],
  "candidate_report_requirements": [],
  "candidate_safety_requirements": [],
  "missing_fields": ["risk_bands"],
  "suggested_next_question": "Есть ли диапазоны итогового риска?",
  "draft": {}
}
```

---

## 8. Status semantics

### `needs_clarification`
The draft is not yet complete for compilation.

### `ready_to_compile`
The draft has enough structure for compilation.

---

## 9. Main failure modes

- malformed model JSON
- missing required extracted fields
- conflicting edits
- noisy source material with weak signal

Mitigations:
- sanitization
- merge priority rules
- explicit missing field computation
- clarification questions

---

## 10. MVP boundaries

Not included yet:
- source document upload persistence
- citation alignment with extracted draft pieces
- confidence scoring per field
- human approval state machine beyond current bot workflow
