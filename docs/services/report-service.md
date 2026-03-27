# report-service.md

# Report Generation Service

## 1. Purpose

The Report Generation Service builds the final end-user report from a completed assessment session.

It transforms structured session outcomes into a readable, safe, consumer-facing report.

The report is web-first in MVP, with optional PDF export.

---

## 2. Responsibilities

The service is responsible for:

- building the final structured report result
- mapping score to risk level
- assembling contributing factors
- generating readable report text
- rendering HTML output
- optionally rendering PDF
- attaching disclaimer and safety notice

---

## 3. Out of Scope

The service does not:

- control branching
- own runtime session state
- compile assessment graphs
- store raw assessment definitions
- act as a clinician-facing reporting system in MVP

---

## 4. MVP Scope

### Included in MVP

- structured report generation
- summary section
- risk level section
- main contributing factors section
- recommendations section
- disclaimer section
- optional safety notice
- HTML rendering
- optional PDF export

### Planned for Later

- branded report themes
- localization
- clinician mode
- comparative longitudinal reporting
- report personalization beyond current session

---

## 5. Core Domain Model

## 5.1 FinalReport

Represents the final structured report.

Contains:

- score
- risk level
- summary
- main contributing factors
- recommendations
- disclaimer
- optional safety notice
- graph version id
- session id

---

## 6. Data Model

### Table: `assessment_reports`

| Field | Type | Description |
|------|------|-------------|
| `report_id` | string | Unique report id |
| `session_id` | string | Linked completed session |
| `graph_version_id` | string | Source graph version |
| `report_json` | json/text | Structured report payload |
| `html_snapshot` | text | Rendered HTML |
| `pdf_path` | string | Optional PDF artifact location |
| `created_at` | datetime | Creation timestamp |

---

## 7. Inputs and Outputs

## 7.1 Input

- completed session
- graph version
- collected answers
- final score
- risk level
- relevant factors and flags

## 7.2 Output

- `FinalReport`
- HTML report
- optional PDF

---

## 8. Report Generation Flow

```text
Load completed session
  -> Load graph version metadata
  -> Build structured result
  -> Assemble contributing factors
  -> Generate readable report text
  -> Attach disclaimer / safety notice
  -> Render HTML
  -> Optionally render PDF
  -> Persist report
```

---

## 9. API Contract

### 9.1 Generate Report

`POST /reports/generate/{session_id}`

Generates a report for a completed session.

#### Response
- `report_id`
- `session_id`
- `graph_version_id`

---

### 9.2 Get Report

`GET /reports/{report_id}`

Returns the structured report payload.

---

### 9.3 Get HTML Report

`GET /reports/{report_id}/html`

Returns rendered HTML.

---

### 9.4 Get PDF Report

`GET /reports/{report_id}/pdf`

Returns PDF if enabled.

---

## 10. Guardrails

The service must enforce report-level safety rules.

### Required constraints

- no diagnosis language
- no treatment plan
- no medication recommendation
- explicit disclaimer required
- safety notice required when red flags are triggered
- low-confidence wording when answers are incomplete or ambiguous

---

## 11. Readability Rules

The report must be written for a consumer, not for a clinician.

Desired qualities:

- short and readable
- clear explanation of risk level
- clear explanation of main factors
- actionable but safe suggestions
- no unnecessary medical jargon

---

## 12. Error Cases

The service must handle:

- report requested for incomplete session
- missing session
- missing graph version reference
- invalid structured result
- PDF rendering failure

In MVP, PDF failure should not block HTML report availability.

---

## 13. Non-Functional Requirements

- report must be reproducible from the same completed session
- report must always reference graph version id
- HTML output must be simple and stable
- PDF export must remain optional
- output must be easy to inspect during demo/testing

---

## 14. Notes for MVP

The Report Generation Service exists to make the final outcome understandable and presentable.

It should stay deliberately simple in MVP.  
Its job is to turn structured runtime results into a safe, readable microproduct output — not to become a complex document generation platform.