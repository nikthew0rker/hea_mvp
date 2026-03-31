# publish-handoff.md

## 1. Purpose

Publish Handoff connects specialist authoring to patient-side usage.

A compiled graph is not enough by itself.  
It becomes useful only when publication makes it available to:
- active graph storage
- graph library / registry

---

## 2. Main outputs of publish

### 2.1 Active graph
The currently active graph record.

### 2.2 Graph registry entry
A searchable library record with:
- graph id
- graph metadata
- graph payload
- publication timestamp

---

## 3. Why graph registry matters

If publication only updates one active graph file, then the patient assistant is forced into a single-graph model.

To support graph discovery, publish must also write into the **graph registry**.

---

## 4. MVP storage model

At the moment, publish uses local file-backed JSON storage:
- `data/active_graph.json`
- `data/graph_registry.json`

This is acceptable for MVP because it is:
- simple
- transparent
- easy to debug
- sufficient for a lightweight graph library

