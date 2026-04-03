# compiler-service.md

## 1. Purpose

Compiler Service transforms a structured draft into a runtime-ready graph artifact.

---

## 2. Responsibilities

- validate minimum graph readiness
- compile draft into a graph payload
- assign a unique graph id
- preserve enough information for publication and patient-side execution

---

## 3. Required minimum compile inputs

- topic
- at least one question
- scoring logic

---

## 4. Output

Compiler returns:
- status
- graph_version_id
- graph
- feedback

---

## 5. Important architectural note

Compiler must not just copy the draft blindly.  
It should produce a graph payload suitable for runtime and graph library registration.

That includes:
- title/topic
- questions or nodes
- scoring
- risk bands
- source_draft linkage
- stable unique graph id

