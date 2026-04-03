# DATA_AND_STORAGE.md

## 1. Current storage model

The MVP currently uses file-backed JSON persistence.

Main files:
- `data/active_graph.json`
- `data/graph_registry.json`
- `data/patient_sessions.json`

---

## 2. Why JSON storage is acceptable for MVP

It is:
- lightweight
- transparent
- easy to inspect
- easy to repair
- enough for local prototype operation

---

## 3. Persistent storage rule

JSON files must:
- be created only if missing
- not be overwritten on startup
- be written atomically when updated

---

## 4. Main storage roles

### active_graph.json
The most recently active published graph.

### graph_registry.json
Searchable graph library.

### patient_sessions.json
Persisted patient-side orchestration and runtime state.

---

## 5. Future migration path

Likely future replacement:
- SQLite for MVP+
- PostgreSQL for larger multi-user version

