# evaluation-service.md

## 1. Purpose

Evaluation Service is the quality and validation layer for the platform.

Its role is to support:
- graph validation
- runtime QA
- report QA
- future automated checks for safety and consistency

---

## 2. Current MVP role

In the current MVP, Evaluation Service is a light scaffold.

It exists to make the architecture complete and to reserve a clear place for:
- graph integrity checks
- compile output checks
- report quality checks
- regression tests

---

## 3. Example use cases

### 3.1 Graph checks
- graph contains nodes
- graph contains edges
- graph has start and finish semantics
- graph metadata exists

### 3.2 Specialist-side checks
- draft has required core fields
- risk bands do not overlap
- scoring rule exists if graph expects scoring

### 3.3 Patient-side checks
- runtime produced a final state
- report exists after completion
- active graph is consistent with runtime usage

---

## 4. API contract

### Endpoint
`POST /run`

### Request
```json
{
  "target_type": "graph",
  "payload": {}
}
```

### Response
```json
{
  "status": "passed",
  "checks": []
}
```

---

## 5. Why it matters even in MVP

Even if full evaluation is not implemented yet, explicitly modeling this service is useful because it:
- shows platform maturity
- separates QA concerns from runtime concerns
- creates a natural place for future regression validation
