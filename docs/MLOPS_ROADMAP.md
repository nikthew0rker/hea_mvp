# MLOps and Platform Roadmap

## Goal

This roadmap describes how Hea can evolve from a local MVP into a production-ready ML and platform system with:

- reliable CI/CD
- reproducible environments
- model governance
- scalable orchestration
- Kubernetes deployment
- observability
- safe rollout and rollback

The roadmap covers both:

- application platform engineering
- LLM/MLOps operations

## Guiding Principles

### 1. Separate app deployment from model governance

The API, bots, search, and orchestration stack should not be coupled to one model provider or one prompt version.

Track separately:

- app versions
- prompt versions
- model versions
- artifact schema versions
- retrieval index versions

### 2. Reproducibility first

Every production build should be reproducible via:

- locked Python dependencies
- versioned Dockerfiles
- migration history
- versioned prompts and scenario templates
- versioned evaluation datasets

### 3. Observability before autoscaling

Do not start with complex autoscaling before measuring:

- request rate
- latency
- token usage
- queue depth
- workflow backlog
- report generation time

## Phase 0: Hardening the Current Repository

### Must implement

- commit `uv.lock`
- enforce lint/test/build in CI
- pin Docker image versions
- add schema migration tooling
- add environment validation on startup

Recommended tools:

- `uv`
- `ruff`
- `pytest` or keep `unittest` but run in CI
- `Alembic`
- `pre-commit`
- `GitHub Actions`

Concrete CI steps:

1. `uv sync --frozen`
2. static checks
3. unit tests
4. integration tests
5. build Docker images
6. smoke tests against built containers

## Phase 1: CI/CD Baseline

## CI pipeline

Recommended GitHub Actions jobs:

### 1. `lint-and-test`

- install with `uv`
- run formatting/linting
- run unit tests
- run integration tests

### 2. `build-images`

- build specialist controller
- build patient controller
- build specialist bot
- build user bot

### 3. `security-and-sbom`

- dependency audit
- image scanning
- SBOM generation

Recommended tools:

- `Trivy`
- `Syft`
- `Grype`

### 4. `migration-check`

- validate DB migrations
- run ephemeral Postgres
- run startup checks

## CD pipeline

Recommended promotion path:

- `dev`
- `staging`
- `production`

Recommended deployment strategy:

- GitOps with `Argo CD`
- or simpler initial pipeline with `Helm` deploy from GitHub Actions

## Phase 2: Move from Docker Compose to Kubernetes

## Target cluster topology

Namespaces:

- `hea-dev`
- `hea-staging`
- `hea-prod`

Core workloads:

- `specialist-controller`
- `patient-controller`
- `specialist-bot`
- `user-bot`
- `worker` for async jobs
- `scheduler` or Temporal worker pods

Platform dependencies:

- `Postgres`
- `Redis`
- `Temporal`
- `MinIO` or cloud object storage
- ingress controller
- observability stack

## Kubernetes packaging

Recommended:

- `Helm` charts for each service group
- separate values files per environment

Useful features:

- resource requests/limits
- readiness and liveness probes
- secret mounts
- config maps
- horizontal pod autoscaling

## Traffic and ingress

Recommended:

- `NGINX Ingress Controller`
- or cloud-native ingress / gateway

For APIs:

- TLS termination
- request timeouts
- rate limits
- auth integration

## Phase 3: Orchestration and Async Execution

## Durable workflows

Recommended:

- `Temporal`

Use it for:

- patient follow-up scheduling
- red-flag reevaluation
- report generation retries
- evidence ingestion pipelines
- graph publish review flows

## Async job classes

Separate workloads by queue:

- `llm-low-latency`
- `llm-heavy`
- `report-generation`
- `evidence-ingestion`
- `monitoring`
- `ehr-sync`

This allows:

- different concurrency limits
- separate autoscaling policies
- different retry strategies

## Phase 4: Scaling Strategy

## Horizontal scaling

Scale independently:

- specialist APIs
- patient APIs
- bots
- async workers
- retrieval services

Good scaling signals:

- request latency
- CPU and memory
- queue backlog
- Temporal workflow backlog
- LLM call concurrency

## Caching

Use Redis for:

- repeated retrieval results
- session lookup cache
- compiled report fragments
- model response cache for low-risk prompts

## Model gateway and routing

Add a dedicated model gateway service.

Responsibilities:

- route by model role
- enforce timeouts
- log usage
- maintain fallback chains
- isolate provider-specific behavior

Possible implementation:

- internal FastAPI service
- or `LiteLLM` as a gateway layer if needed

## Phase 5: LLMOps and Evaluation

## Prompt and model versioning

Track:

- system prompts
- prompt templates
- model role mappings
- fallback rules
- temperature / decoding settings

Store them as versioned config, not only in code comments.

## Evaluation datasets

Build internal eval sets for:

- specialist authoring
- patient search and matching
- branching correctness
- report quality
- multilingual behavior
- safety / red-flag routing

Recommended tooling:

- start with simple versioned JSON fixtures
- later add `LangSmith`, `Weights & Biases`, or custom eval dashboards

## Offline evaluation

Run on each release:

- graph classification accuracy
- extraction fidelity
- risk-band parsing accuracy
- patient retrieval relevance
- report completeness

## Online evaluation

Track in production:

- completion rate
- dropout by question
- specialist correction rate
- publish rejection rate
- red-flag false-positive rate
- assessment recommendation acceptance rate

## Phase 6: RetrievalOps

## Index lifecycle

Treat retrieval indexes as deployable artifacts.

Track:

- embedding model version
- chunking strategy
- language normalization version
- concept dictionary version
- reindex timestamp

## Reindex workflows

Trigger reindex when:

- graph published
- graph updated
- evidence source updated
- synonym dictionary changed

Use background workflows to:

- chunk
- embed
- write vectors
- validate index health

## Hybrid search quality

Recommended architecture:

- Postgres full-text search
- `pgvector`
- metadata filters
- reranker

Track search quality metrics:

- top-1 match rate
- top-3 recall
- disambiguation frequency
- zero-result rate

## Phase 7: Kubernetes Operations

## Deployment strategies

Use:

- rolling updates for stateless APIs
- canary deploys for model-routing changes
- blue/green when changing critical workflow logic

Recommended tools:

- `Argo Rollouts`
- or cloud-native rollout support

## Autoscaling

Use:

- `HPA` for APIs
- `KEDA` for queue-driven workers and Temporal workers

Good KEDA triggers:

- Redis queue depth
- Kafka lag
- custom metrics from Temporal task queues

## Secrets and config

Use:

- cloud secret manager or `Vault`
- external secrets operator in Kubernetes

Do not keep live secrets only in `.env`.

## Phase 8: Reliability and Incident Readiness

## Observability

Implement:

- distributed tracing with `OpenTelemetry`
- metrics with `Prometheus`
- dashboards in `Grafana`
- exception tracking in `Sentry`
- structured logs with request IDs and conversation IDs

Essential dashboards:

- API latency by service
- model latency by role
- token consumption by role
- search success / zero-hit rate
- Temporal workflow failures
- publish gate failures
- patient assessment completion funnel

## SLOs

Define initial SLOs:

- patient API availability
- specialist API availability
- median patient assessment step latency
- report generation success
- publish flow success

## Backups and disaster recovery

Need:

- Postgres backups
- object storage versioning
- retrieval index rebuild procedure
- migration rollback procedure

## Phase 9: Compliance and Access Governance

## Identity and access

Introduce:

- OIDC / SSO
- RBAC
- tenant-aware permissions
- environment separation

Suggested technologies:

- `Keycloak`
- `Auth0`
- `Okta`

## Auditability

Audit:

- who changed a graph
- which model version generated a proposal
- what evidence sources were used
- who published a graph
- what patient data was accessed

## Phase 10: Multi-Region and Advanced Scale

Later-stage concerns:

- multi-region API deployment
- read replicas for Postgres
- regional object storage replication
- event streaming backbone
- dedicated retrieval service

Not needed for v1, but design schemas and IDs with that future in mind.

## Suggested Environment Timeline

### Dev

- local Kubernetes optional
- ephemeral Postgres
- fake or sandbox provider keys
- reduced observability

### Staging

- production-like cluster
- real migrations
- canary tests
- end-to-end scenario tests

### Production

- managed Postgres
- managed Redis
- Temporal
- object storage
- secret manager
- full observability

## Reference Stack by Layer

Application:

- `FastAPI`
- `LangGraph`
- `Pydantic`

Packaging and CI:

- `uv`
- `GitHub Actions`
- `Helm`
- `Argo CD`

Infra:

- `Kubernetes`
- `Postgres`
- `pgvector`
- `Redis`
- `Temporal`
- `MinIO` or `S3`

Scaling:

- `HPA`
- `KEDA`
- `Argo Rollouts`

Observability:

- `OpenTelemetry`
- `Prometheus`
- `Grafana`
- `Sentry`

Security:

- `Keycloak` or `Auth0`
- `Vault` or cloud secret manager

## Practical Roadmap Summary

### Step 1

- lock dependencies
- add CI
- add migrations
- switch to Postgres

### Step 2

- add pgvector
- add Redis
- move reports to object storage
- add structured observability

### Step 3

- deploy to Kubernetes
- add Helm and GitOps
- add HPA

### Step 4

- add Temporal workflows
- split heavy async workers
- add RetrievalOps pipeline

### Step 5

- add model gateway
- add eval datasets
- add canary deploys for prompts and model routing

### Step 6

- add FHIR / wearable integrations
- add tenant-aware RBAC
- add production monitoring workflows

This roadmap keeps the current MVP architecture recognizable while making it operable at real production scale.
