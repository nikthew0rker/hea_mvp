# techspec-report-service.md

# Technical Spec: Report Generation Service

## 1. Goal

The Report Generation Service converts a completed assessment session into a readable, safe, user-facing final report.

It is responsible for formatting the outcome of the assessment, not for generating assessment logic.

---

## 2. Functional Goal

Produce a final report that:

- summarizes the result clearly
- explains the risk level
- identifies main contributing factors
- includes safe recommendations
- includes mandatory disclaimer and safety messaging

---

## 3. Scope

### In scope for MVP

- build structured final result
- map score to risk level
- generate summary text
- assemble contributing factors
- generate recommendations
- render HTML
- optionally export PDF
- persist generated report

### Out of scope for MVP

- clinician-oriented reporting
- longitudinal history views
- theming system
- localization engine
- comparative benchmark reports

---

## 4. Inputs / Outputs

## Input
- completed session
- graph version metadata
- final score
- risk band
- factors/flags from runtime

## Output
- `FinalReport`
- rendered HTML
- optional PDF

---

## 5. Domain Model

### FinalReport

Fields:

- `report_id`
- `session_id`
- `graph_version_id`
- `score`
- `risk_level`
- `summary`
- `main_contributing_factors`
- `recommendations`
- `disclaimer`
- `safety_notice`

---

## 6. Storage

### Table: `assessment_reports`

| Field | Type | Required |
|------|------|----------|
| `report_id` | string | yes |
| `session_id` | string | yes |
| `graph_version_id` | string | yes |
| `report_json` | json/text | yes |
| `html_snapshot` | text | yes |
| `pdf_path` | string | no |
| `created_at` | datetime | yes |

---

## 7. Report Generation Flow

```text
Load completed session
  -> Load graph version metadata
  -> Build structured report object
  -> Generate summary text
  -> Attach factors and recommendations
  -> Attach disclaimer and safety notice
  -> Render HTML
  -> Optionally export PDF
  -> Persist report
```

---

## 8. Report Rules

### Required sections
- summary
- risk level
- main contributing factors
- recommendations
- disclaimer

### Optional section
- safety notice

### Language requirements
- plain language
- short and readable
- non-diagnostic
- consumer-facing

---

## 9. API

### POST /reports/generate/{session_id}

Generate report for completed session.

#### Response
```json
{
  "report_id": "rep_123",
  "session_id": "sess_123",
  "graph_version_id": "graph_v1"
}
```

---

### GET /reports/{report_id}

Return structured report.

---

### GET /reports/{report_id}/html

Return rendered HTML.

---

### GET /reports/{report_id}/pdf

Return rendered PDF if enabled.

---

## 10. Guardrails

The Report Service must enforce:

- no diagnosis language
- no treatment plan
- no medication recommendation
- disclaimer always included
- safety notice included when red flag is triggered
- cautious wording when information is incomplete

---

## 11. Errors

- `404 session_not_found`
- `409 session_not_completed`
- `404 graph_version_not_found`
- `422 invalid_report_payload`
- `500 pdf_render_failure`

PDF failure must not block HTML report creation in MVP.

---

## 12. Non-Functional Requirements

- same completed session should produce reproducible structured report
- report must always reference graph version id
- HTML rendering must be simple and stable
- PDF export should remain optional
- report should be easy to inspect in demo and debugging

---

## 13. Acceptance Criteria

- report can be generated from a completed session
- report contains all required sections
- disclaimer is always present
- safety notice appears for red-flag cases
- HTML output is available
- PDF export works if enabled
- report stores session id and graph version id

---

## 14. Notes

The report is part of the product value.

In MVP it should stay simple, readable, and safe.  
It is not a medical document generator; it is the final output of a consumer-facing micro-assessment.