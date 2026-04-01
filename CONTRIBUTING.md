# Contributing to EWC Compute Platform

Thank you for contributing. EWC Compute is built with engineering rigour as a first principle — the same standard that applies to the platform's outputs applies to the code that produces them.

---

## Before You Start

1. Open an Issue first for any significant feature, API change, or architectural decision. Describe the problem and your proposed approach before writing code.
2. For architectural changes, check whether an existing ADR covers the area (`docs/adr/`). If your change deviates from an existing ADR, open a discussion before submitting a PR.
3. Security findings should be reported privately via GitHub's Security Advisory feature — not as public issues.

---

## Development Workflow

```
main          ← protected; production-ready at all times
  └── develop ← integration branch; all feature PRs target here
        └── feat/your-feature-name
        └── fix/issue-description
        └── docs/adr-005-description
```

**Never commit directly to `main` or `develop`.**

### Branch naming

```
feat/<short-description>
fix/<short-description>
refactor/<short-description>
docs/<short-description>
chore/<short-description>
security/<short-description>
```

---

## Commit Messages — Conventional Commits

All commits must follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description in sentence case>

[optional body — explain WHY, not just what]

[optional footer — Closes #N]
```

**Types:** `feat` · `fix` · `docs` · `style` · `refactor` · `test` · `chore` · `security`

**Scopes:** `backend` · `frontend` · `nvidia-cae` · `ai-physics` · `sim-bridge` · `ci` · `infra` · `docs`

Scope guidance:
- `nvidia-cae` — anything in `nvidia_cae/` (USD I/O, Omniverse, ovphysx, Nucleus)
- `ai-physics` — PhysicsNeMo model configs/training, NVIDIA Warp kernels, NIM client
- `sim-bridge` — solver adapters, CUDA-X routing, domain enum changes
- `backend` — FastAPI routes, Pydantic models, services, agents, core config

**Examples:**

```
feat(backend): add OpenUSD twin export endpoint with physics schema

Writes DigitalTwin objects to .usda stages using usd-core 25.08.
Includes UsdPhysics.RigidBodyAPI for mass and material properties.

Closes #42
```

```
feat(ai-physics): add PhysicsNeMo surrogate inference wrapper

Implements surrogate_router.py selecting between cWGAN-GP and
PINN/AB-UPT architectures based on domain and mesh size.
PhysicsNeMo enforces hard physics constraints by construction.

Closes #87
```

```
feat(sim-bridge): add CUDA-X solver routing for cuDSS and AmgX

cuda_x_router.py selects cuDSS for direct sparse domains (FEM,
structural, EDA) and AmgX for large-scale iterative problems
(CFD >5M cells, electromagnetics). Domain enum defined in base.py.

Closes #91
```

```
security(backend): move JWT secret to environment-only resolution

Previously the secret had a hardcoded fallback. Removed fallback;
app now raises on startup if JWT_SECRET is not set in environment.
```

---

## Local Setup

See the README for the full quickstart. Short version:

```bash
cp .env.example .env
docker compose up --build
```

Run backend tests:
```bash
cd backend && pytest tests/ -v --cov=app --cov-fail-under=80
```

Run frontend tests:
```bash
cd frontend && npm run test
```

---

## Pull Request Requirements

All PRs must:

- Target `develop` (not `main`)
- Complete the PR checklist in `.github/PULL_REQUEST_TEMPLATE.md`
- Pass all four CI workflows (backend, frontend, security, and deploy-dry-run)
- Have two reviewer approvals
- Not decrease test coverage below 80%
- Not introduce any Bandit HIGH findings, Safety CVEs, or Trivy CRITICAL vulnerabilities
- Not introduce secrets or credentials (enforced by Gitleaks)

Architecture-changing PRs must additionally reference an ADR.

---

## Architecture Decision Records (ADRs)

Significant technical decisions are documented in `docs/adr/`. When your PR changes an architectural decision:

1. Create `docs/adr/ADR-NNN-short-title.md` using the template below
2. Reference it in your PR description

**ADR template:**

```markdown
# ADR-NNN — Title

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-NNN

## Context
What is the problem or situation that requires a decision?

## Decision
What was decided, and why?

## Consequences
What are the positive and negative outcomes of this decision?
What becomes easier or harder?
```

---

## Code Standards

### Python (backend)

- Python 3.12. Type annotations on all public functions and class attributes.
- `ruff` for lint and format. `mypy --strict` for type checking.
- All API request/response types defined as Pydantic v2 models — no untyped dicts in route handlers.
- Use `async def` for all route handlers and service functions. Blocking I/O (solver calls, file I/O) must run in a thread executor or Celery task.
- Docstrings on all public classes and non-trivial functions.

### TypeScript (frontend)

- TypeScript strict mode. No `any`.
- ESLint with project config. All warnings are errors.
- API types must be generated from or consistent with the backend OpenAPI spec.
- React components: functional only. Props typed with interfaces.

### Sim Bridge (`backend/app/sim_bridge/`)

The Sim Bridge is solver-agnostic by design. Every adapter inherits from `base.py`, which defines two enums that must be present on every simulation request and must never be inferred — they are always set explicitly by the template or the router:

```python
class SimDomain(str, Enum):
    CFD            = "cfd"           # Computational fluid dynamics
    FEM            = "fem"           # Finite element method — structural, thermal
    THERMAL        = "thermal"       # Standalone thermal analysis
    ELECTROMAGNETIC = "electromagnetic"
    EDA            = "eda"           # Electronic design automation
    COLLISION      = "collision"     # Explicit dynamics / crashworthiness
    OPTICAL        = "optical"       # Photonics / optical simulation

class CudaXSolver(str, Enum):
    CUDSS    = "cudss"    # Direct sparse — FEM, structural, EDA (Phase 2)
    AMGX     = "amgx"     # Algebraic multigrid — large CFD, EM (Phase 2–3)
    CUSPARSE = "cusparse" # General sparse — intermediate cases
    AUTO     = "auto"     # Platform selects from domain + mesh_cells
```

Rules for Sim Bridge PRs:
- New solver adapters go in their own file (`ansys_fluent.py`, `eda.py`, etc). Never extend `base.py` directly.
- EDA (`eda.py`) and Collision (`ansys_lsdyna.py`) adapters are Phase 3+ stubs — they define the interface but raise `NotImplementedError` until that phase begins.
- `cuda_x_router.py` is the single source of truth for cuDSS vs AmgX selection. Solver adapters never choose the CUDA-X backend themselves.
- Every new adapter must include an integration test that mocks the solver API and verifies the request/response schema round-trip.

### NVIDIA CAE layer (`nvidia_cae/`)

The `nvidia_cae/` directory contains three sub-layers, each active from the phase indicated. Phase 0 code only touches `omniverse/usd_io/`. Do not activate Phase 2–3 code in Phase 0 PRs.

**`omniverse/` — OpenUSD I/O (Phase 0+)**
- Use `usd-core` Python API (`from pxr import Usd, UsdGeom, UsdPhysics`) for all USD operations.
- Every exported USD stage must pass `AssetValidator` before writing to disk or Nucleus.
- USD schema version compatibility must be documented in module docstrings.
- Never write to Omniverse Nucleus in Phase 0 — local `.usda` file output only.

**`physicsnemo/` — AI physics framework (Phase 2–3)**
- All surrogate model training and inference runs inside `PhysicsNeMo` — no bare PyTorch model files.
- cWGAN-GP configs live under `surrogate_configs/generative/`; PINN/AB-UPT configs under `surrogate_configs/surrogate/`.
- Hard physics constraints (divergence-free formulations, energy conservation) must be enforced by construction in the model, not as post-hoc validation.
- Every new model architecture requires a corresponding unit test verifying the physics constraint holds on a known analytical solution.

**`warp/` — GPU simulation kernels (Phase 3)**
- All kernels decorated with `@wp.kernel`. No raw CUDA C.
- Kernel functions must have docstrings stating: domain, physical quantity operated on, validity bounds, and GPU memory layout assumptions.
- Kernels must be benchmarked against CPU baseline before merge — include timing in the PR description.

**NIM inference client (`backend/app/ai_physics/`) — (Phase 1)**
- The NIM client uses the OpenAI-compatible endpoint. Never call a raw LLM API directly from application code — route through the NIM client wrapper.
- Engineering system prompt is versioned in `backend/app/core/prompts.py`. Changes to it require a PR with rationale; it is an architectural artefact, not a config file.
- Temperature for engineering inference is fixed at 0.1 unless a specific route requires otherwise, documented in the route handler.

---

## Phase-aware development

The platform is built in phases. The `requirements.txt` locks all NVIDIA CAE libraries from Phase 0 (`usd-core`, `warp-lang`, `physicsnemo`) so dependency resolution never surprises a later phase. But only Phase 0 code is activated in Phase 0 PRs.

A simple rule: **if the library is not yet active in the current phase, import it inside the function body, not at module level.** This means the import fails loudly at runtime if someone accidentally calls Phase 3 code in Phase 1 — rather than silently succeeding because the dependency is installed.

```python
# Correct — Phase 3 library, guarded import
def run_warp_validation(twin: DigitalTwin) -> ValidationResult:
    """GPU-accelerated twin validation. Active from Phase 3."""
    import warp as wp          # Late import — intentional phase guard
    wp.init()
    # ... kernel dispatch
```

```python
# Wrong — Phase 3 library at module level in a Phase 1 file
import warp as wp              # This runs at startup in Phase 1 — premature
```

**Active phases per directory:**

| Directory | Active from |
|---|---|
| `backend/app/` (core, API, models, auth) | Phase 0 |
| `nvidia_cae/omniverse/usd_io/` (twin exporter / importer) | Phase 0 |
| `backend/app/ai_physics/` (NIM client, DSR-CRAG) | Phase 1 |
| `backend/app/sim_bridge/base.py` (domain enum, CUDA-X enum) | Phase 0 (stubs only) |
| `backend/app/sim_bridge/comsol.py`, `lumerical.py` | Phase 2 |
| `backend/app/sim_bridge/cuda_x_router.py` | Phase 2 |
| `backend/app/sim_bridge/ansys_fluent.py`, `openfoam.py` | Phase 2–3 |
| `backend/app/sim_bridge/ansys_lsdyna.py`, `eda.py` | Phase 3 (stub → active) |
| `nvidia_cae/physicsnemo/` | Phase 2–3 |
| `nvidia_cae/warp/` | Phase 3 |
| `nvidia_cae/omniverse/physics/` (ovphysx) | Phase 3 |
| `nvidia_cae/omniverse/usd_io/simready_adapter.py` | Phase 3 |

---

## NVIDIA library version management

Three NVIDIA CAE libraries are locked into `requirements.txt` from Phase 0 — `usd-core`, `warp-lang`, and `physicsnemo` — so that dependency resolution is stable from the first commit and never surprises a contributor joining at a later phase. Only `usd-core` is actively used in Phase 0; the others are pinned but dormant until their phase begins.

**Rules for updating a pinned NVIDIA library version:**

1. Open an issue first. NVIDIA CAE libraries can have breaking API changes between minor versions — a version bump is an architectural event, not a routine maintenance task.
2. Run the full test suite against the new version in a dedicated branch before raising a PR.
3. Document any API changes in the PR description and update the affected module's docstrings.
4. If the update changes behaviour of an active phase (e.g. `usd-core` in Phase 0), the PR requires two reviewers and a CI pass on both backend and nvidia_cae test suites.
5. Never pin to an unpublished or pre-release version — NVIDIA NGC container tags must correspond to a stable release.

**Current pinned versions (update this table in the PR when bumping):**

| Library | Pinned version | Active from | PyPI / install |
|---|---|---|---|
| `usd-core` | 25.08 | Phase 0 | `pip install usd-core==25.08` |
| `warp-lang` | latest stable | Phase 3 | `pip install warp-lang` |
| `physicsnemo` | latest stable | Phase 2–3 | `pip install physicsnemo` |

NIM is API-only (no local install). Its model identifiers are configured via `.env` — treat a model identifier change like a dependency version bump: document it in the PR.

---

## Canonical domain references

When contributing to simulation domain logic — solver adapters, CUDA-X routing, PhysicsNeMo model configs, or Warp kernels — the primary technical reference is the **NVIDIA Computer-Aided Engineering glossary** (https://www.nvidia.com/en-us/glossary/computer-aided-engineering/). It defines the canonical five-step CAE workflow (preprocessing → solving → CUDA-X acceleration → AI physics → digital twins) and names the authoritative library stack for each step. If there is any ambiguity about which domain a solver or kernel belongs to, resolve it against that reference before opening a PR.

Domain coverage in EWC Compute follows the NVIDIA CAE taxonomy:

| Domain | `SimDomain` value | Primary solver(s) | CUDA-X solver | Phase |
|---|---|---|---|---|
| Computational fluid dynamics | `cfd` | COMSOL, Ansys Fluent, OpenFOAM | AmgX (large mesh) | 2 |
| Finite element method | `fem` | COMSOL, Ansys Mechanical | cuDSS | 2 |
| Thermal analysis | `thermal` | COMSOL | cuDSS | 2 |
| Electromagnetics | `electromagnetic` | COMSOL, Lumerical | AmgX | 2–3 |
| Electronic design automation | `eda` | Cadence/Synopsys (stub) | cuDSS | 3 |
| Collision / explicit dynamics | `collision` | Ansys LS-DYNA (stub) | cuDSS | 3 |
| Optical / photonic | `optical` | Lumerical FDTD/MODE | cuDSS | 2 |

EDA and Collision adapters (`eda.py`, `ansys_lsdyna.py`) are Phase 3 stubs: they import correctly, define the adapter interface, and raise `NotImplementedError` with a message stating the phase. Do not activate them before Phase 3 begins — a PR that does this without an ADR will be rejected.

---

## Questions

Open a GitHub Discussion or join the conversation on [engineeringworldcompany.substack.com](https://engineeringworldcompany.substack.com).
