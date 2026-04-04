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

The platform is two complementary views of the same system. The **functional stack** shows what engineers interact with; the **NVIDIA CAE integration stack** shows the AI and compute libraries that power it, built gradually across phases.

### Functional stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER ACCESS LAYER                            │
│    JWT Auth · Web Dashboard · Role-Based Portal · OAuth2 + PKCE    │
├──────────────┬──────────────────┬─────────────────┬────────────────┤
│   DIGITAL    │   SIM TEMPLATES  │  KPI DASHBOARDS │  PHYSICAL AI   │
│  TWIN ENGINE │                  │                 │   ASSISTANT    │
│              │  ai_mode:        │  Live FOMs ·    │                │
│  OpenUSD ·   │  generative |    │  Pareto fronts· │  DSR-CRAG ·   │
│  3 fidelity  │  surrogate |     │  Convergence ·  │  Uncertainty · │
│  levels      │  principled_     │  Fabrication    │  NIM inference │
│              │  solve           │  readiness      │  confirmation  │
├──────────────┴──────────────────┴─────────────────┴────────────────┤
│                         PLATFORM CORE                               │
│   FastAPI Gateway · Pydantic v2 Schemas · Agentic Orchestration    │
│         Redis Job Queue · JWT Middleware · RBAC · Audit Log        │
├─────────────────────┬───────────────────┬──────────────────────────┤
│    MONGODB ATLAS    │    SIM BRIDGE     │   FABRICATION EXPORT     │
│  Projects · Twins · │  Adapter Pattern  │  OpenUSD · GDSII ·       │
│  Templates ·        │  CFD · FEM ·      │  STL · STEP/IGES ·       │
│  SimRuns ·          │  Thermal · EM ·   │  gdspy · numpy-stl ·     │
│  KPITimeSeries ·    │  EDA · Collision· │  Open CASCADE            │
│  AuditLog           │  Optical          │                          │
├─────────────────────┴───────────────────┴──────────────────────────┤
│              DEVSECOPS · CI/CD · SECURITY · OBSERVABILITY           │
│   GitHub Actions · SAST · Dependabot · Terraform · OpenTelemetry  │
└─────────────────────────────────────────────────────────────────────┘
```

### NVIDIA CAE integration stack (built across phases)

Each row maps to a platform phase. Libraries in earlier phases are available to all later phases.

```
┌─────────────────────────────────────────────────────────────────────┐
│  ◆ PHASE 0 — DIGITAL TWIN FORMAT (current)                          │
│  usd-core 25.08 · UsdGeom · UsdPhysics schemas                     │
│  → OpenUSD twin export/import · EWC custom .usda schema            │
├─────────────────────────────────────────────────────────────────────┤
│  ◆ PHASE 1 — AI INFERENCE SERVING                                   │
│  NVIDIA NIM microservices · Nemotron domain models                  │
│  → Physical AI Assistant backend · versioned model endpoints        │
├─────────────────────────────────────────────────────────────────────┤
│  ◆ PHASE 2 — CUDA-X SOLVER ROUTING (principled_solve mode)         │
│  cuDSS — direct sparse (FEM · structural · EDA)                    │
│  AmgX  — algebraic multigrid (large-scale CFD · electromagnetics)  │
│  cuSPARSE · cuBLAS · cuSOLVER — shared numerical kernels           │
│  Flow360 (Flexcompute) — GPU-native CFD · thermal (primary CFD)    │
│  Tidy3D (Flexcompute) — optical/photonic domain                    │
│  Ansys Fluent / LS-DYNA adapter — CFD · collision domains           │
│  → 20–500× speedups · Flow360 100× faster than CPU CFD             │
├─────────────────────────────────────────────────────────────────────┤
│  ◆ PHASE 2–3 — AI PHYSICS ENGINE (surrogate + generative modes)    │
│  PhysicsNeMo — AI surrogate training framework                      │
│    └─ cWGAN-GP architecture (generative mode)                       │
│    └─ PINNs / AB-UPT architecture (surrogate mode)                  │
│  Hard constraint enforcement · divergence-free formulations         │
│  → CAD → physics prediction in seconds · mesh-free inference        │
├─────────────────────────────────────────────────────────────────────┤
│  ◆ PHASE 3 — GPU SIMULATION KERNELS                                 │
│  NVIDIA Warp (warp-lang) — Python GPU kernel authoring              │
│  → Lightweight twin validation · fast synthetic data generation     │
│  → Bridges PhysicsNeMo and Sim Bridge for custom physics ops        │
├─────────────────────────────────────────────────────────────────────┤
│  ◆ PHASE 3 — OMNIVERSE PRODUCTION STACK                             │
│  OpenUSD Exchange SDK · SimReady SDK · ovphysx microservice         │
│  → SimReady-certified twin export · physics-in-USD validation       │
├─────────────────────────────────────────────────────────────────────┤
│  ◆ PHASE 4 — NUCLEUS COLLABORATION                                  │
│  Omniverse Nucleus · live multi-user USD authoring                  │
│  → Team / Enterprise tier shared twin workspaces                    │
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

| Value | Behaviour | NVIDIA library | When to use |
|---|---|---|---|
| `generative` | PhysicsNeMo cWGAN-GP explores design space broadly, returns candidate configurations | PhysicsNeMo | Early-stage design, unknown parameter space |
| `surrogate` | PhysicsNeMo PINNs / AB-UPT architecture predicts in seconds, hard physics constraints enforced | PhysicsNeMo + Warp | Rapid iteration, design space understood |
| `principled_solve` | Full-fidelity solver via Sim Bridge; cuDSS (direct) or AmgX (iterative) routed automatically | CUDA-X (cuDSS / AmgX) | Accuracy-critical validation, 20–500× speedup |

### 3 — KPI Dashboards
Real-time and historical monitoring of engineering figures of merit. Every template run populates a MongoDB time-series collection. Engineers configure drag-and-drop widgets — convergence history, parameter sweep Pareto fronts, fabrication readiness status, threshold alerts, queue position — across the full project lifetime.

### 4 — Physical AI Assistant
Prompt-driven engineering copilot grounded in a curated engineering corpus. Uses **DSR-CRAG** (Dual-State Corrective Retrieval-Augmented Generation) to validate candidate responses against retrieved sources before delivery. Inference is served via **NVIDIA NIM microservices**, giving versioned, swappable domain model endpoints without touching application code. Every numeric claim carries explicit provenance — `retrieved from [source], confidence: high` vs `model estimate, confidence: moderate — verify before use`. No platform action executes without explicit engineer confirmation.

---

## Technology Stack

| Layer | Technology | Version | Phase | Notes |
|---|---|---|---|---|
| Frontend | React + TypeScript | 18 / 5 | 0 | Lovable for rapid UI iteration |
| Backend | FastAPI (Python) | 0.115+ | 0 | Async, auto OpenAPI docs |
| Schema validation | Pydantic | v2 | 0 | Strict types for all engineering models |
| Database | MongoDB Atlas | 7.0+ | 0 | Flexible schema, vector search for RAG |
| AI / RAG | DSR-CRAG architecture | — | 0 | Corrective retrieval, hallucination mitigation |
| AI inference serving | NVIDIA NIM microservices | latest | 1 | Versioned domain model endpoints for Physical AI Assistant |
| AI physics framework | PhysicsNeMo | latest | 2–3 | cWGAN-GP + PINNs architectures; hard physics constraint enforcement |
| GPU simulation kernels | NVIDIA Warp (`warp-lang`) | latest | 3 | Python GPU kernel authoring; fast data generation; twin validation |
| Digital twin format | OpenUSD (`usd-core`) | 25.08 | 0 | `pip install usd-core`; native twin format |
| Omniverse SDK | OpenUSD Exchange SDK | latest | 3 | Production USD I/O, SimReady compatibility |
| Physics-in-USD | `ovphysx` | GTC 2026 | 3 | Agent-native physics microservice |
| Solver acceleration | CUDA-X: cuDSS · AmgX · cuSPARSE · cuBLAS | — | 2+ | cuDSS = direct sparse; AmgX = iterative multigrid; 20–500× speedups |
| **CFD / thermal solver** | **Flow360 (Flexcompute)** | **25.5.5+** | **2** | **GPU-native, cloud-hosted, `pip install flow360`; 100× faster than CPU CFD** |
| **Optical solver** | **Tidy3D (Flexcompute)** | **latest** | **2** | **FDTD photonics/EM; `pip install tidy3d`; shared Flexcompute account** |
| Sim Bridge | Lumerical · COMSOL · Ansys (Fluent/LS-DYNA) | — | 2 | Solver-agnostic adapter pattern; secondary solvers for on-premise/Enterprise |
| Fabrication export | gdspy · numpy-stl · Open CASCADE | — | 3 | GDSII, STL, STEP/IGES |
| Auth | JWT + OAuth2 + PKCE | — | 0 | Stateless, standards-compliant |
| Job queue | Redis + Celery | 7 / 5 | 0 | Async simulation dispatch |
| CI/CD | GitHub Actions | — | 0 | Lint, test, SAST, deploy |
| IaC | Terraform | 1.9+ | 0 | AWS primary, multi-cloud portable |
| Observability | OpenTelemetry + Grafana | — | 0 | Vendor-neutral, structured JSON logs |

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
│   │   │   ├── sim_templates.py    # Template validation · job dispatch · ai_mode routing
│   │   │   ├── dashboard_service.py
│   │   │   └── assistant_service.py # DSR-CRAG pipeline · NIM inference · corpus retrieval
│   │   ├── agents/
│   │   │   ├── orchestrator.py     # Multi-step workflow coordination
│   │   │   └── confirmation_gate.py # Human-in-the-loop action confirmation
│   │   ├── ai_physics/             # NVIDIA PhysicsNeMo + Warp integration (Phase 2–3)
│   │   │   ├── __init__.py
│   │   │   ├── physicsnemo_client.py  # PhysicsNeMo surrogate training + inference
│   │   │   ├── warp_kernels.py        # NVIDIA Warp GPU kernel definitions
│   │   │   └── surrogate_router.py    # Routes surrogate vs principled_solve by domain
│   │   └── sim_bridge/
│   │       ├── __init__.py
│   │       ├── base.py             # Abstract SolverAdapter interface + domain enum
│   │       │                       # domain: cfd|fem|thermal|electromagnetic|eda|collision|optical
│   │       │                       # cuda_x_solver: cudss|amgx|cusparse|auto
│   │       ├── lumerical.py        # Lumerical FDTD/MODE adapter (optical domain)
│   │       ├── comsol.py           # COMSOL Multiphysics adapter (multiphysics)
│   │       ├── ansys_fluent.py     # Ansys Fluent adapter (CFD domain) — Phase 2+
│   │       ├── ansys_lsdyna.py     # Ansys LS-DYNA adapter (collision domain) — Phase 3+
│   │       ├── openfoam.py         # OpenFOAM adapter (CFD open-source) — Phase 2+
│   │       ├── eda.py              # EDA domain stub (Cadence/Synopsys) — Phase 3+
│   │       └── cuda_x_router.py   # cuDSS vs AmgX routing by problem type + size
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
├── nvidia_cae/                      # NVIDIA CAE integration layer (all phases)
│   ├── README.md                    # CAE integration guide + phase schedule
│   ├── omniverse/                   # Omniverse / OpenUSD stack
│   │   ├── usd_io/
│   │   │   ├── twin_exporter.py    # EWC Twin → OpenUSD stage (Phase 0)
│   │   │   ├── twin_importer.py    # OpenUSD stage → EWC Twin (Phase 0)
│   │   │   └── simready_adapter.py # SimReady SDK asset ingestion (Phase 3)
│   │   ├── physics/
│   │   │   └── ovphysx_bridge.py   # ovphysx microservice client (Phase 3)
│   │   └── schemas/
│   │       └── ewc_twin.usda       # EWC custom USD schema template
│   ├── physicsnemo/                 # PhysicsNeMo AI physics framework (Phase 2–3)
│   │   ├── surrogate_configs/      # Model architecture configs (cWGAN-GP, PINN)
│   │   ├── training/               # Training scripts per domain
│   │   └── inference/              # Inference endpoint wrappers
│   └── warp/                        # NVIDIA Warp GPU kernels (Phase 3)
│       ├── cfd_kernels.py          # Lightweight CFD primitive kernels
│       ├── fem_kernels.py          # FEM validation kernels
│       └── data_gen.py             # Synthetic training data generation
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
│   │   ├── ADR-004-ai-mode-explicit-field.md
│   │   ├── ADR-005-physicsnemo-ai-physics-framework.md
│   │   └── ADR-006-flow360-flexcompute-integration.md
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

# Install NVIDIA CAE libraries (Phase 0: USD core; others locked for later phases)
pip install usd-core          # OpenUSD Python bindings — Phase 0
pip install warp-lang         # NVIDIA Warp GPU kernels — locked now, used Phase 3
pip install physicsnemo       # PhysicsNeMo AI physics framework — locked now, used Phase 2–3

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

# ── NVIDIA NIM — AI Inference Serving (Phase 1) ──────────────────────
NIM_BASE_URL=https://integrate.api.nvidia.com/v1
NIM_API_KEY=
NIM_MODEL_ENGINEERING=nvidia/nemotron-4-340b-instruct
NIM_EMBEDDING_MODEL=nvidia/nv-embedqa-e5-v5

# ── NVIDIA PhysicsNeMo — AI Physics Framework (Phase 2–3) ────────────
PHYSICSNEMO_MODEL_STORE=/opt/ewc/physicsnemo/models
PHYSICSNEMO_CACHE_DIR=/opt/ewc/physicsnemo/cache

# ── NVIDIA Omniverse / OpenUSD (Phase 0 / Phase 3) ───────────────────
OMNIVERSE_NUCLEUS_URL=omniverse://localhost/Projects/EWCCompute
USD_EXCHANGE_SDK_PATH=/opt/omniverse/exchange-sdk
OVPHYSX_ENDPOINT=http://localhost:8010

# ── Simulation Bridge ────────────────────────────────────────────────
LUMERICAL_API_URL=http://localhost:8001
LUMERICAL_API_KEY=
COMSOL_API_URL=http://localhost:8002
COMSOL_API_KEY=
ANSYS_API_URL=http://localhost:8003
ANSYS_API_KEY=

# ── AI / RAG ─────────────────────────────────────────────────────────
EMBEDDING_MODEL=nvidia/nv-embedqa-e5-v5
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

## NVIDIA CAE Integration Roadmap

EWC Compute is built on NVIDIA's CAE library stack. Integration is phased — each library enters the active codebase when its platform phase begins, but all are locked into `requirements.txt` from Phase 0 so dependency resolution is never a surprise.

### Phase 0 — OpenUSD core (current)

```python
# usd-core 25.08 — EWC Twin → OpenUSD stage
from pxr import Usd, UsdGeom, UsdPhysics

def export_twin_to_usd(twin: DigitalTwin, output_path: str) -> None:
    stage = Usd.Stage.CreateNew(output_path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    root  = UsdGeom.Xform.Define(stage, f"/{twin.name}")
    mesh  = UsdGeom.Mesh.Define(stage, f"/{twin.name}/geometry")
    mesh.GetPointsAttr().Set(twin.geometry.vertices)
    mesh.GetFaceVertexIndicesAttr().Set(twin.geometry.face_indices)
    mesh.GetFaceVertexCountsAttr().Set(twin.geometry.face_counts)
    UsdPhysics.RigidBodyAPI.Apply(root.GetPrim())
    stage.GetRootLayer().Save()
```

**Install:** `pip install usd-core==25.08`

---

### Phase 1 — NVIDIA NIM inference serving

NIM replaces a raw LLM API call with a versioned, domain-tuned model endpoint. The Physical AI Assistant calls NIM; swapping the underlying model does not touch application code.

```python
# NIM client — Physical AI Assistant inference
from openai import OpenAI   # NIM exposes an OpenAI-compatible API

nim_client = OpenAI(
    base_url=settings.NIM_BASE_URL,
    api_key=settings.NIM_API_KEY,
)

async def query_engineering_assistant(prompt: str, context: str) -> str:
    response = nim_client.chat.completions.create(
        model=settings.NIM_MODEL_ENGINEERING,
        messages=[
            {"role": "system", "content": ENGINEERING_SYSTEM_PROMPT},
            {"role": "user",   "content": f"Context: {context}\n\nQuery: {prompt}"},
        ],
        temperature=0.1,   # Low temperature: engineering queries need determinism
        max_tokens=1024,
    )
    return response.choices[0].message.content
```

**Install:** NIM is API-only — no local install. Set `NIM_API_KEY` in `.env`.

---

### Phase 2 — CUDA-X solver routing

The Sim Bridge `base.py` exposes a `cuda_x_solver` field. The router selects cuDSS for direct sparse problems (FEM, structural, EDA) and AmgX for large-scale iterative problems (CFD, electromagnetics).

```python
# cuda_x_router.py — solver selection by domain and problem size
from enum import Enum

class CudaXSolver(str, Enum):
    CUDSS   = "cudss"    # Direct sparse — FEM, structural, EDA
    AMGX    = "amgx"     # Algebraic multigrid — large CFD, electromagnetics
    CUSPARSE = "cusparse" # General sparse — intermediate cases
    AUTO    = "auto"     # Platform selects based on domain + mesh size

class SimDomain(str, Enum):
    CFD           = "cfd"
    FEM           = "fem"
    THERMAL       = "thermal"
    ELECTROMAGNETIC = "electromagnetic"
    EDA           = "eda"
    COLLISION     = "collision"
    OPTICAL       = "optical"

def select_cuda_x_solver(domain: SimDomain, mesh_cells: int) -> CudaXSolver:
    """Route to cuDSS or AmgX based on domain characteristics."""
    if domain in (SimDomain.EDA, SimDomain.FEM, SimDomain.COLLISION):
        return CudaXSolver.CUDSS       # Direct sparse optimal for these
    if domain == SimDomain.CFD and mesh_cells > 5_000_000:
        return CudaXSolver.AMGX        # Iterative multigrid for large CFD
    if domain == SimDomain.ELECTROMAGNETIC:
        return CudaXSolver.AMGX        # Iterative preferred for EM
    return CudaXSolver.CUDSS           # Default to direct sparse
```

---

### Phase 2–3 — PhysicsNeMo AI physics framework

PhysicsNeMo is the framework for `surrogate` and `generative` ai_mode runs. cWGAN-GP and PINNs run inside it; hard physics constraints (divergence-free vorticity, energy conservation) are enforced by construction.

```python
# physicsnemo_client.py — surrogate inference wrapper
import physicsnemo
from physicsnemo.models import FullyConnected
from physicsnemo.sym.eq.pdes.navier_stokes import NavierStokes

async def run_surrogate_inference(
    twin: DigitalTwin,
    template: SimTemplate,
) -> SurrogateResult:
    """
    Load a trained PhysicsNeMo surrogate for the given domain
    and return physics predictions without invoking the full solver.
    """
    model_path = f"{settings.PHYSICSNEMO_MODEL_STORE}/{template.domain}.pt"
    model = FullyConnected.from_checkpoint(model_path)
    model.eval()

    input_tensor = twin.to_physicsnemo_input()
    with physicsnemo.no_grad():
        predictions = model(input_tensor)

    return SurrogateResult.from_physicsnemo_output(predictions, template)
```

**Install:** `pip install physicsnemo`

---

### Phase 3 — NVIDIA Warp GPU kernels

Warp enables lightweight physics operations on GPU without routing through a full solver — fast twin validation, synthetic data generation for PhysicsNeMo training, and custom simulation primitives.

```python
# warp_kernels.py — GPU kernel for pressure field validation
import warp as wp

wp.init()

@wp.kernel
def validate_pressure_field(
    pressure: wp.array(dtype=wp.float32),
    mesh_coords: wp.array(dtype=wp.vec3),
    violations: wp.array(dtype=wp.int32),
) -> None:
    """
    GPU kernel: flag mesh cells where pressure gradient
    exceeds physical plausibility threshold.
    """
    tid = wp.tid()
    p = pressure[tid]
    if p < 0.0 or p > 1e8:            # Domain-specific plausibility bounds
        violations[tid] = 1
    else:
        violations[tid] = 0
```

**Install:** `pip install warp-lang`

---

### Phase 3 — OpenUSD Exchange SDK + ovphysx

```python
# simready_adapter.py — SimReady-certified twin export
from omni.asset_validator import AssetValidator
from omni.usd.exchange import USDExchangeHelper

def export_simready_twin(twin: DigitalTwin, output_path: str) -> None:
    helper = USDExchangeHelper(output_path)
    helper.add_geometry(twin.geometry)
    helper.add_physics_properties(twin.material, twin.boundary_conditions)
    helper.add_semantic_labels(twin.tags)
    helper.save()
    result = AssetValidator().validate(output_path)
    if not result.is_valid:
        raise ValueError(f"SimReady validation failed: {result.errors}")
```

```python
# ovphysx_bridge.py — physics validation within OpenUSD context
from ewc.nvidia_cae.omniverse.physics import OvphysxBridge

async def run_physics_validation(
    twin_path: str, scenario: PhysicsScenario
) -> PhysicsResult:
    bridge = OvphysxBridge(endpoint=settings.OVPHYSX_ENDPOINT)
    return await bridge.simulate(usd_stage_path=twin_path, scenario=scenario)
```

**Note:** `ovphysx` API surface will be confirmed against NVIDIA NGC release cadence. The adapter pattern ensures no upstream API change when it ships.

---

### Phase 4 — Omniverse Nucleus collaboration

```
EWC Compute Team Project
├── MongoDB Atlas         ← metadata, sim runs, KPI time series, users
└── Omniverse Nucleus     ← OpenUSD twin stages (live, multi-user)
    ├── /Projects/{project_id}/twins/{twin_id}.usdz
    └── /Projects/{project_id}/assets/
```

---

### Ecosystem partner integration summary

| Partner | Integration | Phase | Relevance |
|---|---|---|---|
| NVIDIA NIM | REST API (OpenAI-compatible) | 1 | Physical AI Assistant inference |
| PhysicsNeMo | `pip install physicsnemo` | 2–3 | Surrogate + generative ai_mode |
| NVIDIA Warp | `pip install warp-lang` | 3 | GPU kernels, data generation |
| CUDA-X (cuDSS) | Via COMSOL / Ansys adapters | 2 | Direct sparse FEM / structural |
| CUDA-X (AmgX) | Via COMSOL / OpenFOAM adapters | 2–3 | Large-scale CFD / EM |
| **Flow360 (Flexcompute)** | **`pip install flow360`** | **2** | **Primary CFD + thermal solver; GPU-native cloud; 100× faster than CPU CFD** |
| **Tidy3D (Flexcompute)** | **`pip install tidy3d`** | **2** | **Optical / photonic domain; same Flexcompute account as Flow360** |
| **AutoInsight (Flexcompute)** | **Flexcompute API** | **3** | **AI aerodynamic optimisation → `generative` ai_mode for CFD domain** |
| **GeometryAI (Flexcompute)** | **Flexcompute API** | **3** | **Automated CAD geometry preprocessing in Digital Twin Engine** |
| OpenUSD Exchange SDK | NGC container | 3 | SimReady twin export |
| ovphysx | NGC microservice | 3 | Physics-in-USD validation |
| Omniverse Nucleus | Self-hosted / NGC | 4 | Team twin collaboration |
| COMSOL | REST / LiveLink API | 2 | Multiphysics principled_solve (on-premise / Enterprise) |
| Lumerical (Ansys) | Python API | 2 | Optical domain (alternative to Tidy3D) |
| Ansys Fluent | REST API | 2–3 | CFD domain (alternative to Flow360 for on-premise) |
| Ansys LS-DYNA | REST API | 3 | Collision simulation domain |
| Cadence / Synopsys | EDA adapter stub | 3 | EDA domain |
| SimReady SDK | Validation layer | 3 | Certified component asset consumption |
| Siemens Simcenter | OpenUSD exchange | 3+ | Twin interoperability |
| Dassault 3DEXPERIENCE | OpenUSD exchange | 3+ | Twin interoperability |
| ABB / Fanuc / Caterpillar | SimReady assets | 3 | Pre-certified component twins |

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
Scopes: backend | frontend | nvidia-cae | ai-physics | sim-bridge | ci | infra | docs

Examples:
feat(backend): add OpenUSD twin export endpoint
feat(ai-physics): add PhysicsNeMo surrogate inference wrapper
feat(sim-bridge): add CUDA-X solver routing for cuDSS and AmgX
fix(sim-bridge): handle COMSOL connection timeout gracefully
docs(adr): add ADR-005 PhysicsNeMo framework rationale
security(backend): rotate JWT secret key handling to env-only
```

### Architecture Decision Records

All significant technical decisions are documented in `docs/adr/`. ADR format: status, context, decision, consequences. A PR that changes architecture must reference or create an ADR.

Current ADRs:
- **ADR-001** — Technology stack selection (FastAPI, MongoDB Atlas, React/TypeScript)
- **ADR-002** — OpenUSD as native digital twin format
- **ADR-003** — Sim Bridge adapter pattern (solver-agnostic abstraction)
- **ADR-004** — `ai_mode` as an explicit schema field (generative / surrogate / principled\_solve)
- **ADR-005** — PhysicsNeMo as AI physics framework (replaces generic cWGAN-GP + PINNs description)
- **ADR-006** — Flow360 as primary CFD solver and Flexcompute integration strategy

---

## Roadmap

| Phase | Weeks | Deliverable | Key outputs |
|---|---|---|---|
| **0 — Foundation** | 1–4 | Authenticated platform skeleton | FastAPI + auth, Pydantic base schemas, CI/CD, Docker Compose dev env, ADRs 001–005, `usd-core` + `warp-lang` + `physicsnemo` locked in requirements |
| **1 — Physical AI MVP** | 5–10 | Engineering copilot v1 | DSR-CRAG pipeline, NIM inference integration, corpus ingest tooling, citation display UI, human-confirmation gate |
| **2 — Sim Templates + Solver** | 11–18 | End-to-end simulation workflow | Pydantic template schemas, Sim Bridge v1 (COMSOL + Lumerical), CUDA-X routing (cuDSS first), `ai_mode` dispatch, result viewer |
| **3 — Digital Twin Engine** | 19–28 | Full twin creation + export | CAD upload, OpenUSD Exchange SDK, PhysicsNeMo surrogate integration, Warp validation kernels, ovphysx, GDSII/STL/STEP export |
| **4 — KPI Dashboards + Beta** | 29–36 | Complete four-pillar platform | Dashboard builder, WebSocket live updates, Nucleus collaboration (Team tier), alert system, security audit, beta onboarding |

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
