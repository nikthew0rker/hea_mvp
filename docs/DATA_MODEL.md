# DATA_MODEL.md

# Data Model — Agentic Architecture

## 1. Overview

The data model now supports:

- specialist Telegram conversations
- structured definition drafts
- compiled graph artifacts
- user runtime sessions
- final reports
- evaluation runs

The central rule remains:

**Compiled graph is the canonical executable artifact**

---

## 2. Main Entity Groups

### Specialist-side entities
- `specialist_conversations`
- `specialist_messages`
- `definition_drafts`

### Execution entities
- `compiled_assessment_graphs`
- `assessment_sessions`
- `assessment_answers`
- `session_paths`

### Output entities
- `assessment_reports`

### Validation entities
- `evaluation_runs`

---

## 3. Specialist-Side Model

### `specialist_conversations`
Represents an authoring chat with the specialist.

Fields:
- `conversation_id`
- `telegram_chat_id`
- `telegram_user_id`
- `status`
- `active_definition_draft_id`
- `created_at`
- `updated_at`

### `specialist_messages`
Stores specialist and bot messages.

Fields:
- `message_id`
- `conversation_id`
- `role`
- `text`
- `created_at`

### `definition_drafts`
Stores structured drafts extracted from specialist chat.

Fields:
- `draft_id`
- `conversation_id`
- `draft_json`
- `status`
- `created_at`
- `updated_at`

---

## 4. Canonical Artifact Model

### `compiled_assessment_graphs`
Stores the compiled graph artifact.

Fields:
- `graph_version_id`
- `draft_id` or `definition_id`
- `graph_payload`
- `validation_status`
- `is_published`
- `created_at`

This table remains the source of runtime truth.

---

## 5. User Runtime Model

### `user_conversations`
Represents user-side Telegram interaction state.

Fields:
- `conversation_id`
- `telegram_chat_id`
- `telegram_user_id`
- `active_session_id`
- `status`
- `created_at`
- `updated_at`

### `assessment_sessions`
One runtime execution of one graph version.

Fields:
- `session_id`
- `graph_version_id`
- `status`
- `current_node_id`
- `score`
- `risk_level`
- `started_at`
- `completed_at`

### `assessment_answers`
Stores user answers and structured extraction results.

Fields:
- `answer_id`
- `session_id`
- `node_id`
- `raw_answer`
- `parsed_answer_json`
- `confidence`
- `score_delta`
- `created_at`

### `session_paths`
Stores runtime path events.

Fields:
- `path_id`
- `session_id`
- `node_id`
- `action_type`
- `details_json`
- `created_at`

---

## 6. Output Model

### `assessment_reports`
Stores final generated reports.

Fields:
- `report_id`
- `session_id`
- `graph_version_id`
- `report_json`
- `html_snapshot`
- `pdf_path`
- `created_at`

Reports must always reference the graph version that produced them.

---

## 7. Evaluation Model

### `evaluation_runs`
Stores machine-readable evaluation results.

Fields:
- `run_id`
- `target_type`
- `target_id`
- `status`
- `results_json`
- `created_at`

Targets may include:
- draft
- graph
- session
- report

---

## 8. Relationships

```text
specialist_conversations
    -> specialist_messages
    -> definition_drafts
        -> compiled_assessment_graphs
            -> assessment_sessions
                -> assessment_answers
                -> session_paths
                -> assessment_reports

evaluation_runs
    -> reference any major artifact
```

---

## 9. Versioning Rules

### Drafts
Drafts are editable and represent pre-compile state.

### Compiled graphs
Compiled graphs are versioned artifacts.

### Published graphs
Published graphs are immutable.

### Sessions
Sessions stay pinned to the graph version they started with.

### Reports
Reports must reference the graph version and session that produced them.

---

## 10. Why This Model Works

This model keeps the system:

- traceable
- reproducible
- agent-friendly
- runtime-safe

It allows flexible Telegram conversations while preserving deterministic execution through compiled graphs.