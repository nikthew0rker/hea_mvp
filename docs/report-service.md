# report-service.md

## 1. Purpose

Report Service generates patient-facing output at the end of an assessment.

It transforms:
- runtime session state
- graph payload

into:
- a short summary
- a fuller structured report object

---

## 2. Input

Report Service accepts:
- `session_state`
- `graph`

The graph payload should come from the currently published active graph used during runtime.

---

## 3. Output

The service returns:
- `short_summary`
- `full_report`

---

## 4. API contract

### Endpoint
`POST /generate`

### Request
```json
{
  "session_state": {},
  "graph": {}
}
```

### Response
```json
{
  "short_summary": "Summary text",
  "full_report": {
    "summary": "Summary text"
  }
}
```

---

## 5. Role in system

Report Service is intentionally separate from Runtime Service.

Reason:
- runtime focuses on graph progression
- reporting focuses on final structured communication

This keeps responsibilities clearer and makes future report evolution easier.

---

## 6. Product boundaries

Report generation must stay inside non-diagnostic product behavior.

It must not:
- diagnose disease
- prescribe medication
- output treatment plans

It may:
- summarize answers
- summarize graph result
- explain risk category defined by graph configuration
