# API.md

# Internal API Specification

## 1. Scope

In the new architecture, Telegram is the main user-facing interface.

This API is now primarily **internal/admin/orchestration API** used for:
- debugging
- local development
- smoke tests
- future admin or web tooling

It is not the primary user interface.

---

## 2. API Groups

### Specialist-side
- draft creation from structured input
- draft retrieval
- draft compile
- graph publish

### Runtime-side
- session start
- session message processing
- session completion

### Report-side
- report generation
- report retrieval

### Evaluation-side
- compile checks
- runtime checks
- report checks
- eval result retrieval

---

## 3. Suggested Base Path

```text
/api/v2/internal
```

---

## 4. Definition / Draft Endpoints

### `POST /drafts`
Create or store a structured definition draft.

### `GET /drafts/{draft_id}`
Get one draft.

### `POST /drafts/{draft_id}/compile`
Send a structured draft to the Compiler Agent.

---

## 5. Graph Endpoints

### `GET /graphs/{graph_version_id}`
Get compiled graph metadata.

### `POST /graphs/{graph_version_id}/publish`
Publish a valid graph version.

---

## 6. Runtime Endpoints

### `POST /sessions/start`
Start a runtime session from a published graph.

### `POST /sessions/{session_id}/message`
Process one user message through the Runtime Agent.

### `POST /sessions/{session_id}/complete`
Complete the session.

### `GET /sessions/{session_id}`
Get current runtime session state.

---

## 7. Report Endpoints

### `POST /reports/generate/{session_id}`
Generate a report from a completed session.

### `GET /reports/{report_id}`
Get structured report.

### `GET /reports/{report_id}/html`
Get rendered HTML report.

---

## 8. Evaluation Endpoints

### `POST /evals/compile/{draft_id}`
Run compile-oriented checks.

### `POST /evals/runtime/{graph_version_id}`
Run runtime-oriented checks.

### `POST /evals/report/{session_id}`
Run report-oriented checks.

### `GET /evals/results/{run_id}`
Get evaluation result payload.

---

## 9. Telegram Adapters

The bots themselves should not expose public business logic through Telegram handlers.

Instead they should:
- receive Telegram message
- load conversation state
- call internal orchestration logic
- return message to Telegram

This keeps the Telegram layer thin and replaceable.

---

## 10. Why the API Still Exists

Even though Telegram is now the main interface, internal API remains useful because it supports:

- testing
- scripted demos
- deterministic smoke flows
- future web/admin tooling
- service decoupling if needed later

---

## 11. Summary

The API is now secondary but still important.

It serves as:
- internal control surface
- testing surface
- future extension point

Telegram is the human interface.  
Internal API is the engineering interface.