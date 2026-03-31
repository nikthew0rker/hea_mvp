# graph-registry.md

## 1. Purpose

Graph Registry is the searchable collection of all published assessment graphs.

---

## 2. Why it exists

The patient assistant must search across multiple assessments.

This is impossible if only one active graph exists.

---

## 3. Required registry fields

Each graph entry should expose:
- graph_id
- title
- topic
- description
- tags
- entry_signals
- questions_count
- estimated_time_minutes
- search_text
- graph payload

---

## 4. Role in patient flow

Graph Registry is used by:
- graph search
- graph selection
- assessment offer generation
- runtime graph loading after consent

