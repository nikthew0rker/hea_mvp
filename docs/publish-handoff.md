# publish-handoff.md

## 1. Purpose

Publish handoff is the bridge between:
- specialist-side graph authoring
- patient-side graph execution

Without publish, a compiled graph exists but is not active for patient assistant runtime.

---

## 2. Problem this solves

Earlier MVP behavior:
- specialist bot could compile
- but publish was only a placeholder
- patient assistant used a hardcoded graph id or no active graph at all

This broke the end-to-end platform story.

The current publish handoff fixes that.

---

## 3. Current MVP design

The MVP uses **file-based shared storage**.

### Active graph file
`data/active_graph.json`

Stores:
- graph id
- publication metadata
- graph payload

### Registry file
`data/graph_registry.json`

Stores:
- publish history entries
- graph ids
- publication timestamps
- metadata

---

## 4. Publish flow

### Step 1 — compile
Specialist workflow compiles the current draft and receives:
- `graph_version_id`
- graph payload

### Step 2 — publish
Specialist workflow calls publish logic:
- graph becomes active
- `data/active_graph.json` is overwritten
- `data/graph_registry.json` is appended

### Step 3 — patient assistant uses active graph
Patient bot loads `data/active_graph.json` on `/start` and on subsequent interaction.

---

## 5. Data contract

### `active_graph.json`
```json
{
  "graph_id": "graph_v1_demo",
  "status": "published",
  "is_active": true,
  "published_at": "2026-03-31T00:00:00Z",
  "metadata": {},
  "graph": {}
}
```

---

## 6. Why this is enough for MVP

This is intentionally simple and practical:
- no extra service required
- easy to debug
- easy to inspect manually
- enough for one-active-graph demo flow

This gives a real end-to-end story:
specialist bot -> compile -> publish -> patient bot test

---

## 7. Docker requirement

Because publish uses local shared storage, the bots must share the same `data` directory.

Current compose requirement:
- `./data:/app/data` mounted into:
  - specialist-bot
  - user-bot

Without this, specialist-side publish and patient-side load would not see the same files.

---

## 8. Future expansion path

Likely future evolution:
- database-backed graph registry
- explicit graph activation / deactivation
- multiple active graph environments
- graph history UI
- rollout strategies between published graphs
- access control and approvals

For MVP, file-based publish storage is sufficient and intentionally lightweight.
