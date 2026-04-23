# ADR-001 — Technology Stack Selection

**Status:** Accepted
**Date:** March 2026
**Deciders:** Engineering World Company
**Relates to:** ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-007

---

## Context

EWC Compute is a general-purpose digital industrial engineering platform
targeting professional engineers and mid-size engineering firms. Before
writing a line of application code, the foundational technology stack
must be chosen and locked. These choices propagate through every
subsequent architectural decision — they are expensive to reverse.

The requirements that constrain the choice:

**Functional requirements**
- Serve four distinct pillars (Digital Twin Engine, Sim Templates, KPI
  Dashboards, Physical AI Assistant) under a single authenticated interface
- Handle long-running async simulation jobs (minutes to hours) without
  blocking the API
- Support vector search for retrieval-augmented generation (RAG)
- Store heterogeneous engineering objects: fluid dynamics twins and
  electromagnetic twins do not share the same parameter schema
- Generate OpenAPI documentation automatically for frontend type safety
- Support real-time updates (WebSocket) for KPI dashboard live feeds

**Non-functional requirements**
- Target audience: professional engineers, not enterprise IT departments.
  Stack must be learnable and operable by a small team
- Open standards at every layer where possible — no proprietary lock-in
  in the infrastructure layer
- Security-first from day one: SAST, dependency scanning, secret
  detection on every PR
- Deployable on AWS with a path to multi-cloud via IaC
- Python throughout the backend — the scientific computing and ML
  ecosystem (PhysicsNeMo, Warp, usd-core, flow360, tidy3d) is Python-native

**Phase 0 deliverable constraint**
The Phase 0 deliverable is a running, authenticated platform skeleton
with no engineering logic yet. The stack must be demonstrably working
end-to-end before any pillar logic is added. This means every layer
must support local development via Docker Compose with a single command.

---

## Decision

### Backend: FastAPI (Python 3.12) + Pydantic v2

**FastAPI** over Django REST Framework, Flask, or Litestar.

FastAPI generates OpenAPI documentation automatically from type
annotations. This is non-negotiable: the frontend is React/TypeScript
and the typed API client is generated from the OpenAPI spec. Manual
API documentation maintenance is an ongoing tax that grows with the
codebase. FastAPI eliminates it at source.

FastAPI is async-native. Simulation jobs are dispatched to a job queue
and take minutes to hours to complete. An async gateway means the API
remains responsive during job execution without threading complexity.

FastAPI is the de facto standard in the Python ML and scientific
computing ecosystem. Target developer contributors will be familiar with
it. The alternative frameworks require more onboarding investment for
the same capabilities.

**Pydantic v2** over dataclasses, attrs, or marshmallow.

Pydantic v2 provides strict runtime type validation for all engineering
models. A `SimTemplate` with an invalid mesh strategy or out-of-range
Reynolds number is caught at ingestion, not at solver dispatch.
`mypy --strict` integration means type errors are caught at development
time. Pydantic v2's performance improvement over v1 (10–50× faster
validation) matters when validating large simulation parameter sets.

**Python 3.12** — latest stable at time of decision. Required for
full compatibility with PhysicsNeMo, usd-core, and warp-lang.

### Database: MongoDB Atlas 7.0+

MongoDB Atlas over PostgreSQL (+ pgvector), Supabase, or a pure
vector database (Pinecone, Weaviate).

The engineering object schema is variable by domain. A CFD simulation
template has different parameters than an electromagnetic template. A
digital twin of a fluid dynamics system has a different physics
parameterisation than a structural twin. Forcing these into a relational
schema requires either a wide table with many nullable columns (brittle)
or a complex inheritance hierarchy (expensive to query). MongoDB's
flexible document model maps naturally to the variable-structure
engineering objects that are EWC Compute's core data.

MongoDB Atlas provides native vector search (`$vectorSearch`) in the
same database that stores the rest of the application data. This
eliminates a separate vector database service, a separate connection,
and a separate consistency concern. The RAG corpus, the twin records,
the simulation runs, and the KPI time series all live in one place with
one operational model.

MongoDB Atlas also provides native time-series collections, which map
directly to the KPI Dashboard's convergence history and parameter sweep
data.

**Motor** (async Python MongoDB driver) integrates cleanly with
FastAPI's async model.

**Beanie ODM** is available for higher-level document modelling in
Phase 2+ if needed; Motor is used directly in Phase 1 for explicit
control over queries.

**Rejection of PostgreSQL + pgvector:** pgvector is production-ready
but requires a separate operational model from any NoSQL store needed
for flexible-schema objects. Running two databases (PostgreSQL for
structured data, a document store for flexible objects) increases
operational complexity for a small team. Atlas consolidates both
requirements.

### Frontend: React 18 + TypeScript 5

React over Vue, Svelte, or Angular.

React is the dominant choice in the engineering software UI ecosystem.
Target developer contributors will be familiar with it. The Three.js
ecosystem for 3D geometry visualisation (needed for the Digital Twin
viewer) is best supported in React.

TypeScript is non-negotiable. Engineering data has strict type
requirements. The frontend mirrors the Pydantic models in TypeScript
interfaces, generated from the OpenAPI spec. Type errors in engineering
parameter inputs are caught at compile time, not at runtime when they
would cause solver failures.

**Vite** as the build tool — faster development server than
Create React App, better TypeScript support.

**Lovable** for rapid UI iteration in Phase 0–1, transitioning to
direct component development as the design system stabilises.

### Job Queue: Redis 7 + Celery 5

Simulation jobs are long-running. Dispatching them synchronously in
an HTTP handler would block the event loop for hours. Redis + Celery
provides a battle-tested async job queue pattern that is well-understood
in the Python ecosystem, integrates cleanly with FastAPI, and requires
minimal operational overhead at the scale of Phase 1–2.

Redis also serves as the cache layer for session data and rate limiting.

**Rejection of alternatives:** RQ (Redis Queue) lacks the monitoring
and routing capabilities needed for multi-domain simulation dispatch.
Dramatiq is an option but has a smaller ecosystem. Celery's overhead
is acceptable given the simulation job durations involved.

### CI/CD: GitHub Actions

The monorepo lives on GitHub. GitHub Actions is the obvious choice —
zero integration overhead, free for public repositories, and the
workflows (lint, test, SAST, deploy) are well-documented.

Four workflows from Phase 0:
- `ci-backend.yml` — ruff, mypy, pytest, coverage ≥ 80%
- `ci-frontend.yml` — eslint, tsc, vitest
- `security-scan.yml` — Bandit, Safety, Trivy, Gitleaks
- `deploy-dev.yml` — build, push, deploy on merge to main

### Infrastructure as Code: Terraform 1.9+

AWS primary deployment. Terraform over AWS CDK or Pulumi for
portability — the HCL configuration is cloud-agnostic and the
modules can be adapted for Azure or GCP without rewriting in a
different language. Multi-cloud portability is a future requirement
for Enterprise tier on-premise deployments.

### Observability: OpenTelemetry + Grafana

OpenTelemetry is the vendor-neutral standard for distributed tracing,
metrics, and logging. Grafana provides the visualisation layer.
This choice avoids lock-in to a proprietary observability vendor —
the instrumentation code is the same regardless of whether the backend
is Grafana Cloud, Datadog, or a self-hosted stack.

Structured JSON logging throughout (no unstructured log lines) from
Phase 0, so every log entry is queryable and filterable.

### Auth: JWT + OAuth2 + PKCE

Stateless JWT authentication. Access tokens expire at 60 minutes;
refresh tokens at 7 days (configurable via env). PKCE flow for
OAuth2 compatibility. No sessions stored server-side — the platform
must scale horizontally without sticky sessions.

RBAC (Role-Based Access Control) enforced at the database query level,
not just at the API level. Multi-tenant project data isolation requires
query-level enforcement — API-level isolation alone creates a class
of data exposure risk that is unacceptable in an engineering context
where project data is commercially sensitive.

---

## Consequences

### Positive

**Single language backend.** Python throughout the backend means no
context switching between languages, and the scientific computing
libraries (PhysicsNeMo, usd-core, flow360, tidy3d, warp-lang) install
with `pip`. There is no FFI layer, no subprocess wrapping, no polyglot
complexity.

**Automatic API contract.** FastAPI + Pydantic v2 generates the OpenAPI
spec at runtime. The TypeScript frontend client is generated from it.
Adding a new endpoint or changing a model field propagates to the
frontend type system automatically.

**One data store.** MongoDB Atlas consolidates the application
database, the vector search index, and the time-series KPI store.
One connection string, one operational model, one backup strategy.

**Flexible schema without sacrifice.** Variable-structure engineering
objects are modelled naturally in MongoDB without nullable columns or
inheritance hierarchies.

**Security from commit one.** Four CI workflows from Phase 0 mean
no security debt accumulates. Retrofitting security discipline into
a codebase is significantly more expensive than building it in.

### Negative / risks

**MongoDB Atlas vector search requires M10+.** The free tier (M0)
does not support `$vectorSearch`. The Physical AI Assistant's retrieval
pipeline is non-functional on M0. Mitigation: `seed_corpus.py` and
the embedding pipeline work on any tier; the vector index is created
when the cluster is upgraded. The `--dry-run` flag allows full pipeline
testing on M0.

**Celery operational complexity at scale.** Celery is well-understood
but has operational overhead (worker monitoring, task routing, retry
policies). At Phase 1–2 scale this is manageable. Phase 4+ with many
concurrent simulation jobs may require migration to a managed queue
(AWS SQS + Lambda or similar). The job dispatch interface in
`sim_templates.py` is abstracted enough to allow this.

**React 3D performance.** Three.js in React for the Digital Twin
viewer has known performance limits for very large meshes. For Phase
3 with full OpenUSD support, the viewer may need to transition to
a WebGL-native or Omniverse-based rendering approach. The component
boundary is clean enough to allow this without affecting other pillars.

---

## Alternatives considered

### Django REST Framework

Rejected. DRF's synchronous-first model requires explicit async
workarounds for simulation job dispatch. Auto-generated OpenAPI
documentation is less capable than FastAPI's. The ORM dependency
is overhead given the MongoDB document model.

### Supabase (PostgreSQL-based)

Rejected. Supabase's pgvector integration is production-ready, but
the relational model is a poor fit for variable-structure engineering
objects. Running a separate document store alongside PostgreSQL adds
operational complexity.

### Vue / Svelte

Rejected. React's ecosystem advantage (Three.js, engineering UI
component libraries, developer familiarity) outweighs the developer
experience advantages of Vue and Svelte for this domain.

### Proprietary observability (Datadog, New Relic)

Rejected. Vendor lock-in in the observability layer is unnecessary.
OpenTelemetry instrumentation is identical regardless of backend;
changing the observability vendor is a configuration change.

---

## References

- FastAPI documentation: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- Pydantic v2: [docs.pydantic.dev](https://docs.pydantic.dev)
- MongoDB Atlas vector search: [mongodb.com/docs/atlas/atlas-vector-search](https://www.mongodb.com/docs/atlas/atlas-vector-search/)
- Motor async driver: [motor.readthedocs.io](https://motor.readthedocs.io)
- OpenTelemetry: [opentelemetry.io](https://opentelemetry.io)
- EWC Compute Kickoff post (2026): architecture rationale in prose form

---

*Engineering World Company · EWC Compute Platform*
*ADRs record the reasoning behind significant architectural decisions.
They are never deleted — superseded ADRs are marked as such.*
