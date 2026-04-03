# definition-service.md

## 1. Purpose

Definition Service converts specialist input into a structured draft and applies edits to that draft.

---

## 2. Supported operations

### Update mode
Parse new source material and merge it into the current draft.

### Edit mode
Apply natural-language edits to the current draft.

---

## 3. Inputs

- specialist free text
- guideline fragments
- scoring tables
- noisy documents
- current draft object
- current language

---

## 4. Output draft fields

- understood
- candidate_questions
- candidate_scoring_rules
- candidate_risk_bands
- candidate_report_requirements
- candidate_safety_requirements
- missing_fields
- suggested_next_question
- draft

---

## 5. Important requirement

Model output must be sanitized before merge.

The service must never assume that raw LLM JSON is already structurally safe.

---

## 6. Status semantics

### `needs_clarification`
Draft is not yet compile-ready.

### `ready_to_compile`
Draft has enough required structure to compile.

