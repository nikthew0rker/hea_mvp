# Production Architecture v1

## Goal

Production v1 should turn Hea from an MVP bot pair into a multi-service clinical workflow platform with:

- safe specialist authoring
- reliable patient delivery
- searchable published artifacts
- longitudinal patient monitoring
- external evidence retrieval
- operational observability

The core architectural rule stays the same:

- canonical clinical artifacts live as structured data
- embeddings are only a retrieval index
- LLMs assist authoring and interpretation, but do not become the source of truth

## v1 Principles

### 1. Structured truth, semantic retrieval

Published graphs, draft specs, reports, and monitoring rules should be stored as typed records in the main database.

Use embeddings for:

- semantic graph search
- evidence retrieval
- similar artifact lookup
- patient-to-assessment matching

Do not store executable graph logic only in embeddings.

### 2. Hybrid intelligence

Use three layers together:

- deterministic workflow logic
- model-assisted reasoning
- retrieval over approved evidence and published artifacts

### 3. Specialist and patient isolation

Keep:

- authoring state separate from published registry
- patient-facing delivery separate from specialist drafts
- approved evidence separate from raw internet retrieval

### 4. Compliance-friendly architecture

Design from the start for:

- RBAC
- audit trail
- consent
- tenant isolation
- explainability

## Recommended Service Topology

```text
Web UI / Telegram / WhatsApp
  -> API Gateway / BFF
  -> Auth / RBAC

Clinical Authoring Domain
  -> Specialist API
  -> Authoring Orchestrator
  -> Validation / Critic Service
  -> Graph Compiler
  -> Versioning / Audit Service

Patient Delivery Domain
  -> Patient API
  -> Search / Matching Service
  -> Runtime Orchestrator
  -> Report Service
  -> Monitoring / Red Flag Service

Shared Platform Services
  -> Postgres + pgvector
  -> Redis
  -> Object Storage
  -> Workflow Engine
  -> Observability Stack
  -> Embedding / LLM Gateway
  -> Evidence Retrieval Service
  -> Integration Connectors
```

## Core Infrastructure

## 1. Primary database: Postgres

Recommended:

- `Postgres 16`
- `JSONB` for graph/spec documents
- relational tables for sessions, versions, audit, jobs

Why:

- stronger concurrency than SQLite
- transactional publish/version flows
- `JSONB` fits typed graph specs well
- works well with `pgvector`

Suggested tables:

- `artifacts`
- `artifact_versions`
- `artifact_publications`
- `artifact_embeddings`
- `artifact_node_embeddings`
- `specialist_sessions`
- `patient_sessions`
- `patient_reports`
- `patient_monitoring_rules`
- `audit_events`
- `tenants`
- `users`
- `consents`

Suggested implementation:

- `SQLAlchemy 2` or `SQLModel`
- `Alembic` for migrations

## 2. Vector layer: pgvector

Recommended first choice:

- `pgvector` inside Postgres

Why:

- avoids extra infrastructure early
- allows hybrid SQL + vector search
- keeps embeddings close to artifact metadata

Use it for:

- semantic search over published graphs
- retrieval of question blocks and rule nodes
- evidence passage retrieval
- similar prompt / similar graph search

Example storage layout:

- `artifact_embeddings(artifact_id, version_id, embedding, summary_text, language, tenant_id)`
- `artifact_node_embeddings(artifact_id, node_id, embedding, node_text, node_kind)`
- `evidence_embeddings(source_id, chunk_id, embedding, citation_json)`

Example search flow:

1. normalize user intake
2. expand concepts with domain synonyms
3. apply metadata filters:
- language
- artifact type
- intended population
- specialty
4. run vector search over artifact summaries and entry signals
5. rerank top candidates with a lightweight model or rules

## 3. Cache and coordination: Redis

Use `Redis` for:

- session cache
- rate limiting
- model response cache
- distributed locks on publish/version operations
- short-lived disambiguation state

Do not use Redis as the source of truth.

## 4. Object storage

Recommended:

- `S3`
- or `MinIO` in self-hosted environments

Use for:

- HTML/PDF reports
- uploaded guidelines and PDFs
- processed evidence files
- screenshots / exports
- large prompt bundles

## 5. Workflow engine

Recommended:

- `Temporal`

Use for:

- long-running patient follow-up workflows
- red-flag escalation chains
- reminder schedules
- retrying integration calls
- asynchronous graph compilation / review pipelines

Example workflows:

- `patient_followup_7d`
- `high_risk_red_flag_review`
- `artifact_publish_review`
- `wearable_signal_recheck_24h`

## 6. API and async boundary

Recommended:

- `FastAPI` for synchronous APIs
- `NATS` or `Kafka` for event streams later if volume grows

Production v1 can start with:

- FastAPI
- Temporal
- Postgres
- Redis

Kafka becomes useful when you need:

- high-volume telemetry ingestion
- analytics fan-out
- event replay across multiple downstream consumers

## Domain Services

## 1. Specialist Authoring Service

Responsibilities:

- specialist chat copilot
- direct prompt ingestion
- draft editing
- proposal generation
- validation and critique
- compile and publish orchestration

Suggested internal modules:

- `intent-analysis`
- `prompt-to-spec compiler`
- `spec validator`
- `critic reviewer`
- `publish gate`

Possible implementation:

- keep `LangGraph` for orchestrating authoring state
- move persistence from local SQLite adapter to Postgres repositories

## 2. Patient Delivery Service

Responsibilities:

- patient intake
- graph matching
- consent
- runtime execution
- result explanation
- report rendering

Suggested additions:

- structured `PatientSymptomIntake`
- multilingual normalization layer
- richer report templates
- event emission after completion

## 3. Search and Matching Service

Responsibilities:

- hybrid retrieval over published artifacts
- graph ranking
- disambiguation candidate generation
- similar artifact search for specialists

Recommended search stack:

- Postgres full-text search
- `pgvector`
- concept/synonym expansion
- metadata filters
- reranker model

## 4. Evidence Retrieval Service

Responsibilities:

- retrieve approved evidence from external sources
- chunk and embed documents
- attach citations to authoring proposals
- maintain evidence freshness metadata

Recommended sources:

- `PubMed / NCBI E-utilities`
- `MedlinePlus Connect`
- licensed medical knowledge bases if contracts allow

Use cases:

- specialist asks for recent guideline support
- system suggests source-backed report text
- graph review cites evidence used in authoring

## 5. Monitoring and Red Flag Service

Responsibilities:

- evaluate device signals and patient-reported inputs
- detect threshold breaches and baseline deviations
- create follow-up tasks
- escalate to review or emergency guidance paths

Rule layers:

- fixed thresholds
- patient baseline deltas
- trend anomalies
- multi-signal fusion

## External Integrations

## 1. MCP layer for tool access

Use `MCP` servers as a controlled tool boundary for specialist and internal operators.

Good candidates:

- `PubMed MCP server`
- `filesystem/document MCP server` for uploaded source packs
- `FHIR MCP server` or internal wrapper for hospital APIs
- `analytics/query MCP server`

Why MCP helps:

- standard tool interface for models
- easier governance than ad hoc tool calls
- easier to audit which external system was queried

Production approach:

- keep direct service integrations for core paths
- expose selected tools to models through MCP where human-supervised research or authoring needs them

## 2. Clinical literature and educational sources

Safe production pattern:

- ingest approved source lists
- normalize metadata
- chunk and embed
- store citations
- expose only reviewed evidence to patient-facing outputs

Suggested source split:

- `PubMed` for evidence retrieval
- `MedlinePlus` for patient education
- `YouTube` only for educational content linking, not clinical truth

## 3. Hospital systems and EHR

Recommended path:

- `HL7 FHIR`
- `SMART on FHIR`

Use for:

- importing `Patient`, `Observation`, `Condition`, `MedicationRequest`, `DiagnosticReport`
- launching assessments in chart context
- writing back results where appropriate and allowed

Do not plan for direct database access into hospital systems as the default integration mode.

## 4. Wearables and smart devices

Possible sources:

- `Apple HealthKit`
- `Android Health Connect`
- `Fitbit`
- CGM vendor APIs where available
- smart blood pressure devices

Useful signals:

- heart rate
- resting heart rate
- HRV
- sleep
- activity
- weight
- blood pressure
- glucose

Production pattern:

1. ingest raw signal
2. normalize units and timestamps
3. compute baseline and deviations
4. evaluate red-flag rules
5. trigger notification / review workflow

## Data Model Guidance

## Canonical artifact storage

Store artifacts as structured JSONB plus indexed relational metadata.

Example:

- `artifact_type`
- `topic`
- `framework`
- `language`
- `intended_population`
- `graph_json`
- `report_template_json`
- `safety_policy_json`
- `source_manifest_json`

## Embeddings

Embeddings are an index, not the artifact itself.

Embed:

- artifact summary
- entry signals
- question prompts
- rule node explanations
- source chunks

Do not rely on embeddings to reconstruct executable flow.

## Security and Governance

Production v1 should include:

- tenant isolation
- role-based permissions
- specialist review states
- audit log for graph changes
- consent records for patient data use
- encryption at rest and in transit
- secret management

Suggested components:

- `Keycloak`, `Auth0`, or internal OIDC provider
- `Vault` or cloud secret manager
- row-level security in Postgres if multi-tenant pressure grows

## Observability

Use:

- `OpenTelemetry`
- `Prometheus`
- `Grafana`
- `Sentry`
- centralized logs

Track:

- graph publish failures
- model latency by role
- retrieval quality
- patient drop-off points
- red-flag escalation latency
- report generation success rate

## UI Direction

The best production UI is a clinical IDE for specialists.

Suggested panes:

1. `Copilot Chat`
- discuss scenario
- ask for guidance
- import sources

2. `Structured Spec Editor`
- questions
- branching
- scoring
- risk bands
- report sections

3. `Visual Graph Editor`
- nodes and edges
- branching paths
- rule nodes
- red-flag exits

4. `Simulation and Preview`
- test patient run
- inspect report
- inspect why a branch triggered

Useful technology choices:

- `Next.js`
- `React Flow` for visual graph editing
- `Monaco Editor` for raw prompt / DSL mode
- `TipTap` or structured form editors for report templates

## Recommended Production v1 Rollout

### Phase 1

- move to `Postgres + pgvector`
- add `Redis`
- add `S3/MinIO`
- keep LangGraph orchestration
- keep FastAPI

### Phase 2

- add `Temporal`
- add specialist web IDE
- add hybrid semantic retrieval
- add evidence retrieval service

### Phase 3

- add FHIR integrations
- add wearable ingestion
- add red-flag monitoring workflows
- add reviewer workflows and organizational RBAC

## Concrete Technology Reference Stack

Recommended v1 stack:

- `FastAPI`
- `LangGraph`
- `Pydantic`
- `Postgres 16`
- `pgvector`
- `Redis`
- `Temporal`
- `S3` or `MinIO`
- `OpenTelemetry`
- `Prometheus + Grafana`
- `Sentry`
- `Keycloak` or `Auth0`
- `Next.js`
- `React Flow`
- `Monaco Editor`
- `MCP` for controlled external tools

This stack keeps the current architectural strengths and replaces only the parts that are currently MVP-bound.
