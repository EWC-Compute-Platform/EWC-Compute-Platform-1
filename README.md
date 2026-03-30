<div align="center">

<h1>EWC Compute Platform</h1>
<h3>Engineering World Company · General-Purpose Digital Engineering Platform</h3>

[![CI Backend](https://github.com/EWC-Compute-Platform/EWC-Compute-Platform-1/actions/workflows/ci-backend.yml/badge.svg)](https://github.com/EWC-Compute-Platform/EWC-Compute-Platform-1/actions/workflows/ci-backend.yml)
[![CI Frontend](https://github.com/EWC-Compute-Platform/EWC-Compute-Platform-1/actions/workflows/ci-frontend.yml/badge.svg)](https://github.com/EWC-Compute-Platform/EWC-Compute-Platform-1/actions/workflows/ci-frontend.yml)
[![Security Scan](https://github.com/EWC-Compute-Platform/EWC-Compute-Platform-1/actions/workflows/security-scan.yml/badge.svg)](https://github.com/EWC-Compute-Platform/EWC-Compute-Platform-1/actions/workflows/security-scan.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![OpenUSD](https://img.shields.io/badge/OpenUSD-25.08-green.svg)](https://developer.nvidia.com/usd)
[![Phase](https://img.shields.io/badge/Phase-0%20Foundation-orange.svg)](#roadmap)

**[Substack](https://engineeringworldcompany.substack.com) · [GitHub Organisation](https://github.com/EWC-Compute-Platform) · [Architecture Decision Records](docs/adr/)**

</div>

---

## Overview

EWC Compute is a general-purpose digital industrial engineering platform built for professional engineers and engineering firms who need serious computational capability without enterprise-scale lock-in. It unifies four functional pillars — Digital Twin Engine, Sim Templates, KPI Dashboards, and Physical AI Assistant — under a single authenticated interface, built on open standards and a solver-agnostic architecture.

**The gap we fill:** The market bifurcates between expensive, monolithic enterprise suites (Siemens Xcelerator, Dassault 3DEXPERIENCE) and disconnected point tools (individual FEA packages, standalone dashboards, isolated CAD viewers). EWC Compute targets the professional engineering middle — practitioners who need real computational capability without seven-figure procurement cycles.

---

## Platform Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER ACCESS LAYER                            │
│    JWT Auth · Web Dashboard · Role-Based Portal · OAuth2 + PKCE    │
├──────────────┬──────────────────┬─────────────────┬────────────────┤
│   DIGITAL    │   SIM TEMPLATES  │  KPI DASHBOARDS │  PHYSICAL AI   │
│  TWIN ENGINE │                  │                 │   ASSISTANT    │
│              │  ai_mode:        │  Live FOMs ·    │                │
│  OpenUSD ·   │  generative |    │  Pareto fronts· │  DSR-CRAG ·   │
│  cWGAN-GP ·  │  surrogate |     │  Convergence ·  │  Uncertainty · │
│  3 fidelity  │  principled_     │  Fabrication    │  Human-in-loop │
│  levels      │  solve           │  readiness      │  confirmation  │
├──────────────┴──────────────────┴─────────────────┴────────────────┤
│                         PLATFORM CORE                               │
│   FastAPI Gateway · Pydantic v2 Schemas · Agentic Orchestration    │
│         Redis Job Queue · JWT Middleware · RBAC · Audit Log        │
├─────────────────────┬───────────────────┬──────────────────────────┤
│    MONGODB ATLAS    │    SIM BRIDGE     │   FABRICATION EXPORT     │
│  Projects · Twins · │  Adapter Pattern  │  OpenUSD · GDSII ·       │
│  Templates ·        │  Lumerical FDTD · │  STL · STEP/IGES ·       │
│  SimRuns ·          │  COMSOL · OpenFOAM│  gdspy · numpy-stl ·     │
│  KPITimeSeries ·    │  (solver-agnostic)│  Open CASCADE            │
│  AuditLog           │                   │                          │
├─────────────────────┴───────────────────┴──────────────────────────┤
│              DEVSECOPS · CI/CD · SECURITY · OBSERVABILITY           │
│   GitHub Actions · SAST · Dependabot · Terraform · OpenTelemetry  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The Four Pillars

### 1 — Digital Twin Engine
Engineers upload a CAD file (STEP, IGES, DXF), submit a parametric specification, or describe a design in natural language via the Physical AI Assistant. The engine produces a digital twin — geometry, physics parameterisation, material library association, boundary condition set — stored natively in **OpenUSD** (USD 25.08).

Twin fidelity operates at three levels:
- **Geometric** — shape, dimensions, interference checking
- **Behavioural** — physics parameterisation, material properties, coupled to Sim Bridge for validation runs
- **Predictive** — trained surrogate model generating physics predictions in seconds, bypassing full solver

OpenUSD is the native twin format, ensuring interoperability with NVIDIA Omniverse, Siemens Simcenter, Dassault Systèmes, PTC, Microsoft, Cadence, and ABB — without conversion steps.

### 2 — Sim Templates
Software-defined computational workflow templates: versioned, reproducible, schema-validated. Every template is a Pydantic v2 model defining solver type, mesh strategy, boundary conditions, convergence criteria, and output targets.

Every template exposes an **`ai_mode`** field:

| Value | Behaviour | When to use |
|---|---|---|
| `generative` | cWGAN-GP explores design space broadly, returns candidate configurations | Early-stage design, unknown parameter space |
| `surrogate` | Physics-informed neural network predicts results in seconds (AB-UPT reference architecture) | Rapid iteration, design space understood |
| `principled_solve` | Full-fidelity solver run via Sim Bridge (CUDA-X accelerated: 20–50× FEM/CFD) | Accuracy-critical validation |

### 3 — KPI Dashboards
Real-time and historical monitoring of engineering figures of merit. Every template run populates a MongoDB time-series collection. Engineers configure drag-and-drop widgets — convergence history, parameter sweep Pareto fronts, fabrication readiness status, threshold alerts, queue position — across the full project lifetime.

### 4 — Physical AI Assistant
Prompt-driven engineering copilot grounded in a curated engineering corpus. Uses **DSR-CRAG** (Dual-State Corrective Retrieval-Augmented Generation) to validate candidate responses against retrieved sources before delivery. Every numeric claim carries explicit provenance — `retrieved from [source], confidence: high` vs `model estimate, confidence: moderate — verify before use`. No platform action executes without explicit engineer confirmation.

---

## Technology Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Frontend | React + TypeScript | 18 / 5 | Lovable for rapid UI iteration |
| Backend | FastAPI (Python) | 0.115+ | Async, auto OpenAPI docs |
| Schema validation | Pydantic | v2 | Strict types for all engineering models |
| Database | MongoDB Atlas | 7.0+ | Flexible schema, vector search for RAG |
| AI / RAG | DSR-CRAG architecture | — | Corrective retrieval, hallucination mitigation |
| Generative engine | cWGAN-GP + PINNs | — | Physics-informed twin synthesis |
| Digital twin format | OpenUSD (`usd-core`) | 25.08 | `pip install usd-core` |
| Omniverse SDK | OpenUSD Exchange SDK | latest | USD I/O, SimReady compatibility |
| Physics-in-USD | `ovphysx` | GTC 2026 | Agent-native physics microservice |
| Sim Bridge | Lumerical SDK, COMSOL API | — | Adapter pattern; solver-agnostic |
| Fabrication export | gdspy, numpy-stl, Open CASCADE | — | GDSII, STL, STEP/IGES |
| Auth | JWT + OAuth2 + PKCE | — | Stateless, standards-compliant |
| Job queue | Redis + Celery | 7 / 5 | Async simulation dispatch |
| CI/CD | GitHub Actions | — | Lint, test, SAST, deploy |
| IaC | Terraform | 1.9+ | AWS primary, multi-cloud portable |
| Observability | OpenTelemetry + Grafana | — | Vendor-neutral, structured JSON logs |

---

## Repository Structure

```
EWC-Compute-Platform-1/
├── .github/
│   ├── workflows/
│   │   ├── ci-backend.yml          # pytest · ruff · mypy · coverage
│   │   ├── ci-frontend.yml         # vitest · eslint · tsc
│   │   ├── security-scan.yml       # Bandit · Safety · Trivy · Gitleaks
│   │   └── deploy-dev.yml          # Deploy to dev environment on main merge
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py         # /auth/login · /auth/refresh · /auth/logout
│   │   │       ├── projects.py     # CRUD project management
│   │   │       ├── twins.py        # Digital Twin Engine endpoints
│   │   │       ├── templates.py    # Sim Templates CRUD + dispatch
│   │   │       ├── dashboards.py   # KPI Dashboard config + data
│   │   │       ├── assistant.py    # Physical AI Assistant chat
│   │   │       └── health.py       # /health liveness probe
│   │   ├── core/
│   │   │   ├── config.py           # Settings via pydantic-settings
│   │   │   ├── security.py         # JWT creation / validation
│   │   │   ├── logging.py          # Structured JSON logger
│   │   │   └── middleware.py       # CORS · audit log · request tracing
│   │   ├── models/
│   │   │   ├── user.py             # User · Role · Token schemas
│   │   │   ├── project.py          # Project schema
│   │   │   ├── twin.py             # DigitalTwin · FidelityLevel · AiMode
│   │   │   ├── template.py         # SimTemplate · AiMode enum · solver config
│   │   │   ├── sim_run.py          # SimRun · status · results
│   │   │   ├── dashboard.py        # Dashboard · Widget · KPISeries
│   │   │   └── audit.py            # AuditEvent
│   │   ├── services/
│   │   │   ├── twin_engine.py      # Twin creation · OpenUSD write · fidelity dispatch
│   │   │   ├── sim_templates.py    # Template validation · job dispatch
│   │   │   ├── dashboard_service.py
│   │   │   └── assistant_service.py # DSR-CRAG pipeline · corpus retrieval
│   │   ├── agents/
│   │   │   ├── orchestrator.py     # Multi-step workflow coordination
│   │   │   └── confirmation_gate.py # Human-in-the-loop action confirmation
│   │   └── sim_bridge/
│   │       ├── __init__.py
│   │       ├── base.py             # Abstract SolverAdapter interface
│   │       ├── lumerical.py        # Lumerical FDTD/MODE adapter
│   │       ├── comsol.py           # COMSOL Multiphysics adapter
│   │       └── openfoam.py         # OpenFOAM adapter (Phase 2+)
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── requirements-dev.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── auth/               # Login · protected route wrapper
│   │   │   ├── dashboard/          # KPI widget library
│   │   │   ├── twin/               # Twin viewer (Three.js / OpenUSD web)
│   │   │   ├── templates/          # Sim Template builder UI
│   │   │   └── assistant/          # Chat interface · citation display
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Projects.tsx
│   │   │   ├── TwinEngine.tsx
│   │   │   ├── SimTemplates.tsx
│   │   │   ├── Dashboards.tsx
│   │   │   └── Assistant.tsx
│   │   ├── hooks/
│   │   ├── api/                    # Typed API client (OpenAPI-generated)
│   │   └── types/                  # TypeScript interfaces mirroring Pydantic models
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.ts
│
├── omniverse/                       # NVIDIA Omniverse / OpenUSD integration layer
│   ├── README.md                    # Omniverse integration guide
│   ├── usd_io/
│   │   ├── twin_exporter.py        # EWC Twin → OpenUSD stage writer
│   │   ├── twin_importer.py        # OpenUSD stage → EWC Twin reader
│   │   └── simready_adapter.py     # SimReady SDK asset ingestion
│   ├── physics/
│   │   └── ovphysx_bridge.py       # ovphysx physics microservice client
│   └── schemas/
│       └── ewc_twin.usda           # EWC custom USD schema template
│
├── infrastructure/
│   ├── terraform/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── docker-compose.yml          # Full local dev stack
│   └── docker-compose.test.yml     # Integration test stack
│
├── docs/
│   ├── adr/
│   │   ├── ADR-001-technology-stack.md
│   │   ├── ADR-002-openusd-twin-format.md
│   │   ├── ADR-003-sim-bridge-adapter-pattern.md
│   │   └── ADR-004-ai-mode-explicit-field.md
│   ├── api/                        # OpenAPI specs (auto-generated)
│   └── engineering/                # Domain documentation
│
├── scripts/
│   ├── seed_corpus.py              # Seed Physical AI Assistant knowledge base
│   └── setup_dev.sh                # One-command local dev setup
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── README.md
├── CONTRIBUTING.md
└── LICENSE
```

---

## Local Development Setup

### Prerequisites

- Docker Desktop ≥ 4.28 and Docker Compose v2
- Python 3.12
- Node.js 20 LTS
- Git

### Quickstart

```bash
# 1. Clone the repository
git clone https://github.com/EWC-Compute-Platform/EWC-Compute-Platform-1.git
cd EWC-Compute-Platform-1

# 2. Copy environment template
cp .env.example .env
# Edit .env — set MongoDB URI, JWT secret, API keys

# 3. Start the full local stack (FastAPI + MongoDB + Redis)
docker compose up --build

# 4. Verify services
curl http://localhost:8000/health    # → {"status": "ok"}
open http://localhost:3000           # → EWC Compute web interface
```

### Backend only (without Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Install OpenUSD Python bindings
pip install usd-core

# Run development server
uvicorn app.main:app --reload --port 8000
```

### Frontend only

```bash
cd frontend
npm install
npm run dev    # → http://localhost:3000
```

---

## Environment Variables

```bash
# .env.example

# ── Application ──────────────────────────────────────────────────────
APP_ENV=development
APP_SECRET_KEY=changeme-use-openssl-rand-hex-32
APP_ALLOWED_ORIGINS=http://localhost:3000

# ── Authentication ───────────────────────────────────────────────────
JWT_SECRET=changeme-32-chars-minimum
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ── Database ─────────────────────────────────────────────────────────
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=ewc_compute_dev

# ── Redis / Job Queue ────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── NVIDIA Omniverse / OpenUSD ───────────────────────────────────────
OMNIVERSE_NUCLEUS_URL=omniverse://localhost/Projects/EWCCompute
USD_EXCHANGE_SDK_PATH=/opt/omniverse/exchange-sdk

# ── Simulation Bridge ────────────────────────────────────────────────
LUMERICAL_API_URL=http://localhost:8001
LUMERICAL_API_KEY=
COMSOL_API_URL=http://localhost:8002
COMSOL_API_KEY=

# ── AI / RAG ─────────────────────────────────────────────────────────
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=
EMBEDDING_MODEL=text-embedding-3-small
VECTOR_SEARCH_INDEX=ewc_engineering_corpus

# ── Observability ────────────────────────────────────────────────────
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
LOG_LEVEL=INFO
```

---

## CI/CD Pipeline Overview

Four GitHub Actions workflows govern every change:

| Workflow | Trigger | What it does |
|---|---|---|
| `ci-backend.yml` | Push / PR to any branch | ruff lint · mypy type check · pytest · coverage ≥ 80% |
| `ci-frontend.yml` | Push / PR to any branch | eslint · tsc · vitest |
| `security-scan.yml` | Push / PR to any branch | Bandit (SAST) · Safety (CVEs) · Trivy (containers) · Gitleaks (secrets) |
| `deploy-dev.yml` | Merge to `main` | Build Docker images · push to registry · deploy to dev environment |

**Branch protection on `main`:** All four workflows must pass. Two reviewer approvals required. No force-push.

---

## NVIDIA Omniverse & OpenUSD Integration Roadmap

EWC Compute adopts OpenUSD as its native 3D scene description format for digital twins. Integration is delivered in three phases aligned with the platform build roadmap.

### Phase 0 — Core USD I/O (Current)

Install `usd-core` via pip. Implement the twin exporter and importer. Every digital twin created in EWC Compute is written as a valid `.usda` / `.usdz` stage.

```python
# Minimal twin export — EWC Twin → OpenUSD stage
from pxr import Usd, UsdGeom, UsdPhysics

def export_twin_to_usd(twin: DigitalTwin, output_path: str) -> None:
    stage = Usd.Stage.CreateNew(output_path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

    root = UsdGeom.Xform.Define(stage, f"/{twin.name}")
    mesh = UsdGeom.Mesh.Define(stage, f"/{twin.name}/geometry")
    mesh.GetPointsAttr().Set(twin.geometry.vertices)
    mesh.GetFaceVertexIndicesAttr().Set(twin.geometry.face_indices)
    mesh.GetFaceVertexCountsAttr().Set(twin.geometry.face_counts)

    # Physics schema — mass, material properties
    physics_api = UsdPhysics.RigidBodyAPI.Apply(root.GetPrim())
    stage.GetRootLayer().Save()
```

**Dependencies:** `usd-core==25.08`

### Phase 1 — OpenUSD Exchange SDK (Phase 2 platform build)

Integrate the **OpenUSD Exchange SDK** for production-grade USD I/O. This provides higher-level convenience functions, consistent USD asset production, and SimReady compatibility — ensuring twins exported from EWC Compute are valid against the SimReady standard used by ABB, Caterpillar, Fanuc, Siemens, and other manufacturers.

```python
# OpenUSD Exchange SDK — SimReady-compatible asset export
from omni.asset_validator import AssetValidator
from omni.usd.exchange import USDExchangeHelper

def export_simready_twin(twin: DigitalTwin, output_path: str) -> None:
    helper = USDExchangeHelper(output_path)
    helper.add_geometry(twin.geometry)
    helper.add_physics_properties(twin.material, twin.boundary_conditions)
    helper.add_semantic_labels(twin.tags)  # Required for SimReady compliance
    helper.save()

    # Validate against SimReady schema
    validator = AssetValidator()
    result = validator.validate(output_path)
    if not result.is_valid:
        raise ValueError(f"SimReady validation failed: {result.errors}")
```

**Dependencies:** OpenUSD Exchange SDK (Omniverse NGC container or local install)

### Phase 2 — Omniverse Physics Bridge (Phase 3 platform build)

Integrate **`ovphysx`** — NVIDIA's new agent-native physics simulation microservice announced at GTC 2026. This enables physics-based twin validation directly within the OpenUSD workflow, without requiring a separate solver call for behavioural-level twin queries.

```python
# ovphysx client — physics simulation within OpenUSD context
from ewc.omniverse.physics import OvphysxBridge

async def run_physics_validation(twin_path: str, scenario: PhysicsScenario) -> PhysicsResult:
    bridge = OvphysxBridge(endpoint=settings.OVPHYSX_ENDPOINT)
    result = await bridge.simulate(
        usd_stage_path=twin_path,
        scenario=scenario,
        max_steps=scenario.max_steps,
    )
    return result
```

**Note:** `ovphysx` availability and API surface will be confirmed against NVIDIA NGC release cadence. The adapter pattern in `sim_bridge/base.py` ensures this integration does not affect the upstream platform API.

### Phase 3 — Omniverse Nucleus Collaboration (Phase 4 platform build)

Connect EWC Compute's project data layer to **Omniverse Nucleus** — NVIDIA's USD collaboration server — enabling multi-user real-time twin authoring for Team and Enterprise tier users. Twins live in Nucleus; EWC Compute's MongoDB Atlas stores project metadata, simulation run history, and KPI time series.

```
EWC Compute Team Project
├── MongoDB Atlas             ← project metadata, sim runs, KPI series, user data
└── Omniverse Nucleus         ← OpenUSD twin stages (live, collaborative)
    ├── /Projects/{project_id}/twins/{twin_id}.usdz
    └── /Projects/{project_id}/assets/
```

### Ecosystem Partner Integration Summary

| Partner | Integration path | EWC Compute relevance |
|---|---|---|
| NVIDIA Omniverse | OpenUSD Exchange SDK + Nucleus + ovphysx | Native twin format, physics, collaboration |
| SimReady SDK | OpenUSD Exchange SDK validation layer | Certified SimReady twin export |
| COMSOL | Sim Bridge COMSOL adapter (REST/LiveLink) | principled\_solve mode, cuDSS-accelerated |
| Lumerical (Ansys) | Sim Bridge Lumerical adapter (Python API) | Photonic/optical simulation domains |
| Siemens Simcenter | OpenUSD import/export (Xcelerator ecosystem) | Twin interoperability, no native API |
| Dassault 3DEXPERIENCE | OpenUSD exchange | Twin interoperability |
| ABB / Fanuc / Caterpillar | SimReady asset consumption | Pre-certified component twins |

---

## DevSecOps Standards

### Security Gates (enforced on every PR)

| Tool | Type | Blocks merge if |
|---|---|---|
| Bandit | Python SAST | Any HIGH severity finding |
| Safety | Dependency CVE scan | Known CVE in any dependency |
| Trivy | Container image scan | CRITICAL vulnerability in image |
| Gitleaks | Secret detection | Any credential or API key in diff |
| Dependabot | Dependency updates | (Auto-creates PRs; does not block) |

### Code Quality Gates

- Python: `ruff` (lint + format) · `mypy --strict` (type checking) · `pytest` with ≥ 80% coverage
- TypeScript: `eslint` · `tsc --noEmit` · `vitest`
- All PRs: Conventional Commits format enforced · two reviewer approvals · passing CI

### Conventional Commit Format

```
<type>(<scope>): <description>

Types: feat | fix | docs | style | refactor | test | chore | security
Scopes: backend | frontend | omniverse | sim-bridge | ci | infra | docs

Examples:
feat(backend): add OpenUSD twin export endpoint
fix(sim-bridge): handle COMSOL connection timeout gracefully
docs(adr): add ADR-002 OpenUSD format rationale
security(backend): rotate JWT secret key handling to env-only
```

### Architecture Decision Records

All significant technical decisions are documented in `docs/adr/`. ADR format: status, context, decision, consequences. A PR that changes architecture must reference or create an ADR.

Current ADRs:
- **ADR-001** — Technology stack selection (FastAPI, MongoDB Atlas, React/TypeScript)
- **ADR-002** — OpenUSD as native digital twin format
- **ADR-003** — Sim Bridge adapter pattern (solver-agnostic abstraction)
- **ADR-004** — `ai_mode` as an explicit schema field (generative / surrogate / principled\_solve)

---

## Roadmap

| Phase | Weeks | Deliverable | Key outputs |
|---|---|---|---|
| **0 — Foundation** | 1–4 | Authenticated platform skeleton | FastAPI health + auth, Pydantic base schemas, CI/CD live, Docker Compose dev env, ADRs 001–004, OpenUSD `usd-core` installed |
| **1 — Physical AI MVP** | 5–10 | Engineering copilot v1 | DSR-CRAG pipeline, corpus ingest tooling, chat UI with citation display, human-confirmation gate |
| **2 — Sim Templates** | 11–18 | End-to-end simulation workflow | Pydantic template schemas, Sim Bridge v1 (COMSOL or Lumerical), `ai_mode` dispatch, result viewer in dashboard |
| **3 — Digital Twin Engine** | 19–28 | Full twin creation + export | CAD upload + validation, OpenUSD Exchange SDK, ovphysx integration, GDSII/STL export, Three.js twin viewer |
| **4 — KPI Dashboards + Beta** | 29–36 | Complete four-pillar platform | Dashboard builder, WebSocket live updates, alert system, security audit, beta onboarding |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide. Key points:

- Branch from `develop`, not `main`
- Follow Conventional Commits format
- All PRs require the checklist in [PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md) to be completed
- Architecture-changing PRs must reference an ADR
- Test coverage must not decrease below 80%

---

## Community & Follow the Build

- **Substack:** [engineeringworldcompany.substack.com](https://engineeringworldcompany.substack.com) — technical deep-dives and build-in-public updates
- **GitHub Discussions:** Architecture questions, feature proposals, integration discussions
- **Issues:** Bug reports and well-scoped feature requests via issue templates

---

## License

MIT License — see [LICENSE](LICENSE).

---

*Engineering World Company · Building the platform layer for professional engineering.*



   

