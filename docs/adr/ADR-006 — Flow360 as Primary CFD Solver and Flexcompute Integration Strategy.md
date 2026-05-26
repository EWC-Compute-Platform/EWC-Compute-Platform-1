# ADR-006 — Flow360 as Primary CFD Solver and Flexcompute Integration Strategy

**Status:** Accepted
**Date:** March 2026
**Deciders:** Engineering World Company
**Relates to:** ADR-001 (technology stack), ADR-003 (Sim Bridge adapter pattern),
               ADR-004 (ai_mode explicit field), ADR-005 (PhysicsNeMo)

---

## Context

ADR-003 established the Sim Bridge adapter pattern: a new solver requires
one file implementing the four-method `SolverAdapter` interface. The pattern
is solver-agnostic. The question this ADR answers is which solver is
implemented first, and why.

EWC Compute's Phase 2 deliverable is a working end-to-end simulation
workflow: engineer uploads a twin, selects a `SimTemplate` with
`ai_mode: principled_solve`, dispatches a job, receives results. This
requires at least one active solver adapter. The choice of first adapter
is not neutral — it determines what domain gets validated first, which
engineering audience the platform can demonstrate to earliest, and how
long it takes from Phase 2 start to first real simulation result.

The candidate solvers for Phase 2 first adapter are:

- **Flow360 (Flexcompute)** — GPU-native CFD, cloud-hosted, Python SDK,
  API key authentication
- **COMSOL Multiphysics** — multiphysics FEM/CFD, REST or LiveLink API,
  requires local licence server and installation
- **Ansys Fluent** — industry-dominant CFD, REST/gRPC API, requires
  local installation and licence
- **OpenFOAM** — open-source CFD, command-line, requires local
  installation and environment setup

The decision criteria:

1. Time from zero infrastructure to first simulation result
2. Physics capability and domain coverage
3. Engineering audience relevance
4. Strategic relationship potential
5. Alignment with EWC Compute's existing partner ecosystem (Tidy3D)

---

## Decision

**We adopt Flow360 (Flexcompute) as the primary CFD solver for EWC Compute
Phase 2, implemented as the first active Sim Bridge adapter. Flow360 is
also the strategic entry point for a broader Flexcompute partnership
covering the full simulation domain map.**

### Why Flow360 over the alternatives

**Time to first result — decisive factor**

Flow360 requires `pip install flow360` and one API key in `.env`.
Authentication is via `FLOW360_APIKEY`. There is no local installation,
no licence server, no hardware dependency, no environment setup.

COMSOL requires a local installation (multi-GB), a floating licence
server, and network licence configuration before a single API call can
be made. Ansys Fluent requires equivalent local setup plus platform-
specific batch submission configuration. OpenFOAM requires a Unix
environment, case directory structure, and subprocess management.

The practical consequence: the first working end-to-end CFD run through
EWC Compute — engineer uploads a geometry, selects a template, dispatches
to Flow360, results come back — can happen on day one of Phase 2, before
any other solver infrastructure is provisioned. For COMSOL or Ansys
Fluent, the equivalent milestone is several weeks into Phase 2 at the
earliest, gated on licence procurement and environment setup.

For a build-in-public project where demonstrating real capability at
each phase is part of the credibility argument, this timing difference
is significant.

**Physics capability**

Flow360 is the next-generation GPU-native Navier-Stokes solver, offered
on a cloud infrastructure, 100 times faster than industry-leading solvers
with the same high-fidelity and reduced cost.

The physics model set covers the full range of relevant engineering
workloads in EWC Compute's Phase 2 scope:

- Fully compressible Navier-Stokes: subsonic through hypersonic regimes
- Turbulence models: Spalart-Allmaras (SA), k-ω SST, scale-resolving
  DDES and ZDES for high-fidelity unsteady flows
- Conjugate heat transfer: coupled fluid-solid thermal analysis
- Rotor and propeller modelling: actuator disk and blade element methods
- Aeroacoustics: Ffowcs Williams-Hawkings far-field noise prediction
- A fully integrated, automated meshing pipeline designed to remove
  meshing as a workflow bottleneck, handling large complex geometries
  efficiently with minimal manual setup

Flow360 delivers simulation results up to 100× faster than traditional
CFD tools, enabling rapid design iteration. Aerospace engineers can run
full aircraft or component-level analyses in minutes instead of days,
accelerating concept evaluation, optimisation, and certification
readiness.

**Engineering audience alignment**

Flow360's customer base — Joby Aviation, Beta Technologies, Electra Aero,
REGENT, Northrop Grumman, NIO, Robinson Helicopter — maps precisely onto
the engineering verticals where EWC Compute's platform has the most
immediate relevance: aerospace and advanced air mobility (eVTOL, UAM),
automotive aerodynamics, and defence. These are also the verticals where
the Substack series has built its initial audience.

The Electra use case is particularly concrete: Electra cut 9 months off
its aircraft design timeline using Flow360's ultra-fast CFD simulations.
With rapid iteration and deep flow insights, startups like Electra bring
breakthrough innovations to market faster and more cost-effectively.
This is precisely the engineering efficiency argument EWC Compute makes
for its `principled_solve` mode in the CFD domain.

### The Flexcompute product map — a strategic relationship

Flow360 is not an isolated integration. Flexcompute's full product
portfolio maps directly across EWC Compute's simulation domain coverage:

| Flexcompute product | EWC Compute domain | Phase |
| --- | --- | --- |
| Flow360 | CFD, thermal (conjugate HT) | 2 — primary CFD |
| Tidy3D | Optical, photonic, EM | 2 — optical domain |
| AutoInsight | CFD generative mode | 3 — `ai_mode: generative` |
| GeometryAI | Digital Twin Engine CAD preprocessing | 3 — twin upload pipeline |

This is the key strategic point: **Flexcompute is not one adapter among
many — it is the primary simulation partner across multiple domains.**

Tidy3D is already the Precision with Light platform's simulation engine
for photonic and optoelectronic simulation. It uses the same Flexcompute
account and API key as Flow360. For EWC Compute users who also run
photonic simulation workflows — which is directly relevant given the
platform's photonics domain depth — a single Flexcompute account covers
both CFD (Flow360) and optical (Tidy3D) domains. No separate procurement.

AutoInsight — Flexcompute's AI-driven aerodynamic optimisation product —
is the natural Phase 3 backend for `ai_mode: generative` in the CFD
domain. It sits alongside PhysicsNeMo's cWGAN-GP generative architecture
as a solver-side complement: where PhysicsNeMo trains generative models
from EWC Compute's own simulation data, AutoInsight brings Flexcompute's
pre-trained aerodynamic optimisation capability.

GeometryAI — Flexcompute's automated geometry preprocessing product —
is directly relevant to the Digital Twin Engine's CAD upload pipeline
(ADR-002). Automated geometry cleanup and meshing preparation is a
friction point in the twin creation workflow that GeometryAI addresses.

**The commercial positioning is complementary, not competitive.** Flexcompute
builds best-in-class physics solvers. EWC Compute builds the orchestration
layer, AI assistant, twin management, and KPI monitoring above those
solvers. The relationship is analogous to a database engine and the
application built on it: both are necessary, neither replaces the other,
and the value to engineers comes from having both integrated.

### What the adapter implements

The `flow360.py` adapter in `backend/app/sim_bridge/` implements the
four-method `SolverAdapter` interface established in ADR-003:

```python
class Flow360Adapter(SolverAdapter):

    @property
    def domain(self) -> SimDomain:
        return SimDomain.CFD

    @property
    def solver_name(self) -> str:
        return "flow360"

    async def dispatch(
        self,
        parameters: dict[str, Any],
        usd_stage_path: str,
    ) -> str:
        """
        Submit a Flow360 CFD case. Returns the Flow360 case ID.

        The Flow360 Python SDK is synchronous; calls are wrapped in
        asyncio.get_event_loop().run_in_executor() to preserve the
        FastAPI async event loop. This adds negligible latency relative
        to CFD job durations of minutes to hours.

        Parameters handled: turbulence model selection (SA through iLES),
        freestream conditions (Mach, Reynolds, AoA), conjugate heat
        transfer config, rotor geometry, output field selection.
        """
        ...

    async def poll_status(self, job_id: str) -> SimRunStatus:
        """
        Map Flow360 case status strings to SimRunStatus enum.
        Flow360 statuses: running → SimRunStatus.RUNNING
                          completed → SimRunStatus.COMPLETED
                          diverged → SimRunStatus.FAILED
                          cancelled → SimRunStatus.CANCELLED
        """
        ...

    async def fetch_results(self, job_id: str) -> dict[str, Any]:
        """
        Return normalised result dict:
        - Scalar aerodynamic coefficients (CL, CD, CM, CY, CMx, CMz)
        - Convergence history (residuals per iteration)
        - Download URLs for surface and volumetric field data
        - Solver metadata (wall time, mesh cell count, GPU hours)
        """
        ...

    async def cancel(self, job_id: str) -> bool:
        """Call flow360.Case.cancel(job_id). Returns True if successful."""
        ...
```

### Phase 2+ solver roadmap

Flow360 is the first active adapter. The roadmap beyond it:

| Phase | Adapter | Domain | Notes |
| --- | --- | --- | --- |
| 2 | `flow360.py` | CFD, thermal | Active — primary CFD |
| 2 | `lumerical.py` | Optical | Active — Lumerical FDTD/MODE |
| 2 | `comsol.py` | FEM, EM, thermal, multiphysics | Active — requires local licence |
| 2+ | `openfoam.py` | CFD | Open-source alternative CFD |
| 2+ | `ansys_fluent.py` | CFD | On-premise / Enterprise tier |
| 3+ | `ansys_lsdyna.py` | Collision | Explicit dynamics |
| 3+ | `eda.py` | EDA | Cadence/Synopsys — Phase 3 |
| 3+ | `matlab_simulink.py` | System dynamics | See flagged ADR-008 |

The ordering reflects both technical readiness and strategic priority.
Lumerical is Phase 2 alongside Flow360 because of the direct connection
to the Precision with Light photonics platform. COMSOL is Phase 2 because
it covers the broadest domain set (multiphysics FEM, electromagnetics,
thermal) and has a Python LiveLink API that maps cleanly to the adapter
interface.

---

## Consequences

### Positive

**Day-one working simulation.** The absence of local installation
requirements means the first end-to-end simulation test can run
immediately when `FLOW360_APIKEY` is set in `.env`. No infrastructure
procurement, no environment setup, no licence negotiation blocks the
Phase 2 milestone.

**100× performance is real and citable.** Flow360 is 100 times faster
than industry-leading CFD solvers while remaining high-fidelity.
This number is independently validated, not a marketing claim specific
to favourable conditions. EWC Compute's `principled_solve` mode
inherits this performance for CFD domain runs. It is a concrete,
quotable capability that distinguishes the platform from workflows
built on CPU-based solvers.

**Single account, two domains.** The same Flexcompute account covers
Flow360 (CFD/thermal) and Tidy3D (optical/photonic). For the engineering
audience EWC Compute is building — practitioners who work across
mechanical and optical domains, which is especially relevant given the
platform's photonics depth — this is a meaningful operational simplification.

**Clear Phase 3 extension path.** AutoInsight as the `generative` mode
backend for CFD and GeometryAI as the twin preprocessing tool are
natural Phase 3 extensions that require no new vendor relationships.
The Flexcompute partnership deepens incrementally.

**Reference implementation for the Sim Bridge pattern.** The `flow360.py`
adapter is the canonical example that all future adapters follow. Its
patterns — synchronous SDK wrapped in thread executor, status string
mapping, normalised result dict structure — are documented in the adapter
and serve as the implementation reference for `comsol.py`, `lumerical.py`,
and all subsequent adapters.

### Negative / risks

**Cloud-only, no on-premise option.** Flow360 runs on Flexcompute's GPU
cloud infrastructure. It cannot be deployed on-premise. For Enterprise
tier clients with strict data sovereignty requirements — defence
contractors, regulated industries, government research labs — cloud
execution may not be acceptable. Mitigation: the Sim Bridge adapter
pattern means on-premise CFD (Ansys Fluent, OpenFOAM) can be added
in Phase 2+ for Enterprise tier without changing the template schema
or the dispatch logic. The cloud solver and on-premise adapter coexist
in the registry.

**Cost per simulation.** Flow360 bills by compute unit (CU). At scale,
simulation cost must be factored into EWC Compute's pricing model —
particularly for high-mesh-cell-count jobs or large parameter sweeps.
Mitigation: the `SimRun` result schema includes `gpu_hours` and solver
metadata; cost tracking is implementable against this data. Phase 3
Enterprise tier pricing will need to account for pass-through simulation
costs.

**Dependency on Flexcompute's API stability.** If Flexcompute changes
the Flow360 Python SDK interface, `flow360.py` requires updating. The
Sim Bridge pattern contains this risk — only `flow360.py` changes, not
the rest of the platform. Given Flexcompute's engineering culture
(over 75% of staff hold PhDs, founded by MIT professors including the
original Spalart-Allmaras turbulence model author) and NVIDIA partnership,
API stability is reasonably expected.

---

## Alternatives considered

### COMSOL Multiphysics as first adapter

COMSOL covers more domains (FEM, electromagnetics, thermal, acoustics,
multiphysics) than Flow360's CFD focus, which could make it the better
first adapter by breadth. Rejected as first because of the local
installation and licence server requirement. The multi-week procurement
and setup timeline delays the Phase 2 milestone and creates an
infrastructure dependency that is not appropriate for the first
working demonstration. COMSOL is the correct second adapter precisely
because its breadth complements Flow360's depth.

### Ansys Fluent as first adapter

Ansys Fluent is the industry-dominant CFD solver, with the largest
installed base in engineering firms. Being the "Ansys adapter platform"
would have clear market resonance. Rejected as first because: local
installation required, licence procurement is complex and expensive,
the API is less developer-friendly than Flow360's Python SDK, and
Ansys-dependent workflows create the solver lock-in pattern that EWC
Compute's architecture is explicitly designed to avoid for its own users.
Ansys Fluent is a Phase 2+ adapter for Enterprise tier on-premise
deployments.

### OpenFOAM as first adapter

OpenFOAM is open-source and free. No licence cost. Rejected as first
because: it requires local installation and Unix environment setup,
it is command-line driven requiring subprocess management rather than
a Python API, and its user base — primarily academic and open-source
oriented — does not align with the professional engineering firm audience
that Phase 2 is targeting. OpenFOAM is the correct open-source CFD
option for Phase 2+ users who need on-premise execution without licence
cost.

---

## References

- Flow360 documentation: [docs.flexcompute.com/projects/flow360](https://docs.flexcompute.com/projects/flow360)
- Tidy3D documentation: [docs.flexcompute.com/projects/tidy3d](https://docs.flexcompute.com/projects/tidy3d)
- Flexcompute AutoInsight: [flexcompute.com/autoinsight](https://www.flexcompute.com/autoinsight/)
- Flow360 Python SDK: `pip install flow360`
- `backend/app/sim_bridge/flow360.py` — adapter implementation
- `backend/app/sim_bridge/cuda_x_router.py` — CUDA-X routing for CFD domain
- ADR-003: Sim Bridge adapter pattern — the interface `flow360.py` implements
- ADR-005: PhysicsNeMo — training data for CFD surrogates comes from Flow360 runs
- EWC Compute Post 3 (2026): *EWC Compute Adds Flow360: GPU-Native CFD via Flexcompute*
- Electra Aero case study: 9 months off aircraft design timeline using Flow360

---

*Engineering World Company · EWC Compute Platform*
*ADRs record the reasoning behind significant architectural decisions.
They are never deleted — superseded ADRs are marked as such.*

