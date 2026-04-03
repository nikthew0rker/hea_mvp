# report-service.md

## 1. Purpose

Report Service generates a final summary from:
- runtime state
- result
- graph metadata

---

## 2. Responsibilities

- produce short patient-facing summary
- optionally produce fuller structured result object
- preserve safe product boundaries

---

## 3. Important boundary

Report Service may describe:
- score
- category
- graph-defined meaning

It must not:
- diagnose
- prescribe treatment
- provide medical recommendations

