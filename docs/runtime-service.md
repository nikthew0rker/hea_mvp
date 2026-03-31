# runtime-service.md

## 1. Purpose

Runtime Service executes the currently active assessment graph for the patient assistant.

It is the main patient-side orchestration layer.

---

## 2. Input

Runtime receives:
- patient conversation id
- latest patient message
- active graph version id

In practice, the Patient Bot is responsible for resolving the currently active published graph before interacting with runtime.

---

## 3. Responsibilities

- advance the conversational graph
- choose next question or state transition
- update patient session state
- determine when the assessment is complete
- signal report generation

---

## 4. API contract

### Endpoint
`POST /message`

### Request
```json
{
  "conversation_id": "user_conv_123",
  "user_message": "I feel tired",
  "active_graph_version_id": "graph_v1_demo"
}
```

### Response
```json
{
  "conversation_id": "user_conv_123",
  "status": "in_progress",
  "reply_text": "Next question...",
  "session_state": {},
  "should_generate_report": false
}
```

---

## 5. Runtime dependencies

Runtime depends on:
- a valid active graph id
- the graph structure already published by specialist workflow

The patient bot is responsible for ensuring a graph has been published before runtime is called.

---

## 6. Completion semantics

When runtime decides the graph is complete:
- `should_generate_report = true`
- patient bot then calls Report Service with:
  - session state
  - active graph payload

---

## 7. MVP boundaries

Not included yet:
- durable patient session persistence
- graph replay
- audit trace export
- partial recovery after runtime crash
- multiple simultaneous active graphs with dynamic routing
