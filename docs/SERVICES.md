# SERVICES.md

# MVP Service Map

This document describes the logical services of the prompt-driven health assessment engine.

Important: in the MVP, these services can be implemented inside **one backend application** and deployed as **a single service**.  
The separation below is **architectural**, not necessarily infrastructural.

The goal of this decomposition is to:

- separate authoring/definition from runtime
- make the compiler/runtime split explicit
- support future product growth
- avoid turning the MVP into a heavy enterprise system

---

## 1. High-Level Service Map

```text
[ Assessment Definition Service ]
               |
               v
[ Assessment Compiler Service ]
               |
               v
[ Canonical Compiled Assessment Graph ]
               |
               v
[ Assessment Runtime Service ]
               |
               +--------------------+
               |                    |
               v                    v
[ Report Generation Service ]   [ Evaluation & Safety Service ]
```

---

## 2. Service Decomposition Principles

Services are separated by domain boundaries:

- **Definition** — owns specialist-defined assessment input
- **Compiler** — owns graph compilation and validation
- **Runtime** — owns end-user assessment execution
- **Report** — owns final user-facing output
- **Evaluation & Safety** — owns checks, guardrails, and evals

This decomposition helps:

- keep the core engine small
- localize changes
- evolve the product gradually
- preserve a clean path to future service extraction if needed

---

## 3. Service List

### 3.1 Assessment Definition Service

**Purpose:**  
Accept, store, and manage assessment definitions created by a specialist.

**Responsibilities:**

- store text-based assessment definitions
- manage draft versions
- expose definitions to the compiler
- support changing assessment behavior without code changes

**Does not do:**

- execute assessments
- calculate score
- generate end-user reports

**MVP status:**  
Required

---

### 3.2 Assessment Compiler Service

**Purpose:**  
Transform a definition input into a canonical executable graph.

**Responsibilities:**

- parse the definition
- normalize structure
- build graph nodes and transitions
- validate graph integrity
- validate scoring and report schema
- attach safety metadata
- create immutable compiled graph versions

**Does not do:**

- run end-user sessions
- own UI
- render final reports

**MVP status:**  
Required

---

### 3.3 Assessment Runtime Service

**Purpose:**  
Execute a compiled graph and guide the user through the assessment.

**Responsibilities:**

- create sessions
- present the next question or confirmation
- accept answers
- extract structured values from free text
- update score
- move to the next graph node
- complete the session

**Does not do:**

- accept raw authoring input
- compile definitions
- own the canonical graph structure

**MVP status:**  
Required

---

### 3.4 Report Generation Service

**Purpose:**  
Build the final user-facing report based on a completed session.

**Responsibilities:**

- assemble the structured report result
- render an HTML report
- optionally export PDF
- include disclaimer and safety notice

**Does not do:**

- control branching
- manage session flow
- store assessment definitions

**MVP status:**  
Required

---

### 3.5 Evaluation & Safety Service

**Purpose:**  
Validate graph correctness, runtime behavior, and report safety/completeness.

**Responsibilities:**

- run compile-time checks
- run runtime eval cases
- check report completeness
- check red-flag behavior
- enforce safety policy

**Does not do:**

- replace compiler/runtime logic
- participate in the normal end-user flow
- own business logic of a specific assessment

**MVP status:**  
Required, but intentionally lightweight

---

### 3.6 Evidence Adapter Service

**Purpose:**  
Provide access to external references and knowledge sources.

**Possible sources:**

- PubMed
- WHO
- NICE
- curated internal content

**Responsibilities:**

- search or fetch references
- normalize source data
- optionally support rule extraction for the compiler

**Does not do:**

- act as a critical runtime dependency for the MVP user flow
- become a separate knowledge platform in the first version

**MVP status:**  
Optional / internal module / future-ready extension point

---

## 4. Service Responsibilities Matrix

| Service | Definition Input | Compile Graph | Runtime Session | Report | Safety / Evals | External References |
|--------|-------------------|---------------|-----------------|--------|----------------|---------------------|
| Assessment Definition Service | Yes | No | No | No | No | No |
| Assessment Compiler Service | Reads | Yes | No | No | Partial | Optional |
| Assessment Runtime Service | No | No | Yes | No | Partial | No |
| Report Generation Service | No | No | Reads completed session | Yes | Partial | No |
| Evaluation & Safety Service | Reads | Validates | Validates | Validates | Yes | No |
| Evidence Adapter Service | No | Supports | No | No | No | Yes |

---

## 5. Main Flows Between Services

### 5.1 Authoring / Compile Flow

```text
Definition Service
  -> Compiler Service
      -> optional Evidence Adapter Service
      -> Validation
      -> Compiled Graph saved
```

### 5.2 Runtime Flow

```text
Runtime Service
  -> loads Compiled Graph
  -> creates Session
  -> receives answers
  -> updates path and score
  -> completes Session
  -> triggers Report Generation Service
```

### 5.3 Quality / Safety Flow

```text
Compiler Service / Runtime Service / Report Service
  -> Evaluation & Safety Service
  -> validation results / eval results
```

---

## 6. Canonical Artifact

The canonical artifact of the system is the:

**Compiled Assessment Graph**

This means:

- specialist-defined input is the authoring source
- the compiled graph is the approved executable representation
- runtime always executes a compiled graph version
- reports are always tied to a graph version
- evals always validate a concrete graph version

---

## 7. MVP Boundaries

### Included in MVP

- text-based definition input
- compile definition into graph
- runtime user flow
- final report
- lightweight safety and evals

### Planned for Next Iteration

- specialist-facing authoring UI
- graph visual editor
- visual review workflow
- richer evidence integrations
- analytics dashboard
- collaborative workflows

---

## 8. Deployment Model for MVP

Although the architecture is described as multiple services, the recommended MVP deployment model is:

- **one backend deployable**
- **one database**
- **one web UI**
- logical separation into service modules inside the codebase

### Why this is recommended

- faster to implement
- easier to run locally
- easier to deploy
- easier to demo as a working MVP
- still preserves clean domain boundaries

---

## 9. Suggested Code Layout

```text
app/
  definition/
  compiler/
  runtime/
  reports/
  evals/
  evidence/        # optional
  shared/
```

### Directory Roles

- `definition/` — models, schemas, endpoints for definitions
- `compiler/` — compile pipeline, graph builder, validation
- `runtime/` — session engine, branching, scoring, conversation orchestration
- `reports/` — final report builder, HTML/PDF rendering
- `evals/` — eval cases, checks, safety assertions
- `evidence/` — adapters to external references (optional)
- `shared/` — common models, utilities, config, DB layer
