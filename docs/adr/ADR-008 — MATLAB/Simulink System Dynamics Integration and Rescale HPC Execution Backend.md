# ADR-008 — MATLAB/Simulink System Dynamics Integration and Rescale HPC Execution Backend

**Status:** Accepted
**Date:** June 2026
**Deciders:** Engineering World Company
**Relates to:** ADR-001 (technology stack), ADR-003 (Sim Bridge adapter pattern),
               ADR-005 (PhysicsNeMo AI physics framework), ADR-006 (Flow360 integration)

---

## Context

ADR-003 established the Sim Bridge adapter pattern. ADR-005 noted that
MATLAB/Simulink and PhysicsNeMo serve complementary roles — PhysicsNeMo owns
field-level physics (CFD, FEM, EM), while MATLAB/Simulink owns system-level
dynamics, control, signal processing, and HIL testing — and flagged this ADR
for the formal integration decision.

Two separate but related integration decisions are addressed together here
because both are Phase 3 infrastructure concerns, both extend the Sim Bridge
beyond the core solver set established in Phase 2, and neither introduces a
new physics domain solver in the traditional sense.

**Decision 1: MATLAB/Simulink system dynamics integration**

The MathWorks MATLAB Expo UK 2025 (Silverstone) demonstrated three relevant
capability clusters:

- **Virtual vehicle development** using Simulink/Simscape for system-level
  modelling of vehicle dynamics, electric drivetrains, and control systems
- **Digital twin development** for automotive and aerospace applications using
  Simscape, covering hydraulic, pneumatic, electrical, and mechanical subsystems
- **Real-time HIL testing** via Simulink Real-Time and Speedgoat hardware,
  enabling hardware-in-the-loop validation against physical components

The AVL Copper Bird electric aircraft propulsion testing architecture (AVL
Webinar, April 2026) demonstrated exactly this workflow: a simulation layer
(aircraft RT model, emulator controls), an emulation layer (E-Motor emulators,
inverters), and real hardware under test (HV routers, DC/DC converters, battery
systems). AVL explicitly runs this on Simulink-based test system control. The
MATLAB Parallel Server enables HPC-scale parameter sweeps directly from the
MATLAB environment.

MATLAB/Simulink is absent from EWC Compute's Phase 2 Sim Bridge. This is a
gap that the professional engineering audience recognises immediately — MATLAB
is the dominant tool for system-level engineering in automotive, aerospace, and
industrial automation. Every firm using Flow360 for CFD also uses Simulink for
control system design and HIL testing. The gap creates a platform that
addresses one half of the engineering workflow and not the other.

**Decision 2: Rescale HPC execution backend**

The Rescale webinar (The Engineer UK, May 27 2026) revealed Rescale's current
platform structure: HPC Foundations, Advanced Modeling & Simulation, Agentic
Digital Engineering, and AI Physics OS. Their partner ecosystem includes AVL,
Ansys, Siemens, NVIDIA, and all major cloud providers (AWS, Azure, CoreWeave,
Google Cloud). They explicitly offer a "Powered by Rescale" channel partner
programme for domain-specific application layers.

Rescale uses Anthropic (Claude) in their AI & Agent Frameworks layer alongside
Amazon Bedrock, OpenAI, and NVIDIA — confirming alignment between EWC Compute's
DSR-CRAG architecture and Rescale's AI engineering philosophy.

Rescale's AI Physics OS describes exactly EWC Compute's surrogate model
architecture: data structuring and tagging, training on modular AI architectures,
model evaluation, publishing and inference, governance and controls, with a
solver-agnostic AI workflow toolkit. Their embedded AI Physics for Designers
use case — real-time surrogate inference integrated directly into CAD tools —
is EWC Compute's `surrogate` mode value proposition expressed at the CAD
plugin layer.

The critical architectural question: Rescale is not a physics solver. It is
a compute execution environment on which physics solvers run. Ansys Fluent runs
on Rescale. COMSOL runs on Rescale. OpenFOAM runs on Rescale. A naive
implementation as a `SolverAdapter` subclass would conflate two different
abstraction levels — the solver domain and the execution infrastructure. This
requires a distinct architectural treatment.

---

## Decision

### Decision 1: MATLAB/Simulink as a system dynamics Sim Bridge adapter

**We implement `matlab_simulink.py` as a `SolverAdapter` for the
`system_dynamics` domain, extending the `SimDomain` enum with a new value.**

MATLAB/Simulink occupies a genuinely different computational role from the
field-physics solvers. A new domain value is architecturally correct rather
than forcing system-level dynamics into the existing `fem` or `thermal` domains.

```python
# Extension to SimDomain enum in sim_bridge/base.py
class SimDomain(str, Enum):
    CFD             = "cfd"
    FEM             = "fem"
    THERMAL         = "thermal"
    ELECTROMAGNETIC = "electromagnetic"
    EDA             = "eda"
    COLLISION       = "collision"
    OPTICAL         = "optical"
    SYSTEM_DYNAMICS = "system_dynamics"  # ADR-008: MATLAB/Simulink
```

The `system_dynamics` domain covers:
- Control system design and simulation (Simulink)
- Physical system modelling (Simscape: hydraulic, pneumatic, electrical,
  mechanical, thermal)
- Model-in-the-loop (MIL), software-in-the-loop (SIL), and hardware-in-the-loop
  (HIL) testing workflows via Simulink Real-Time
- Signal processing (MATLAB Signal Processing Toolbox)
- Multi-objective parameter optimisation sweeps via MATLAB Parallel Server
- FMU (Functional Mock-up Unit) export for co-simulation with other adapters

#### Adapter interface

```python
# sim_bridge/matlab_simulink.py

class MatlabSimulinkAdapter(SolverAdapter):
    """
    Sim Bridge adapter for MATLAB/Simulink system-level dynamics.

    Execution modes:
      local:   MATLAB Engine API for Python — requires local MATLAB installation
      engine:  MATLAB Production Server — remote execution via REST API
      parallel: MATLAB Parallel Server — HPC/cloud parameter sweeps
      hil:     Simulink Real-Time — real-time HIL via Speedgoat hardware

    The execution mode is set via MATLAB_EXECUTION_MODE in .env.
    Default: local (development), engine (production).

    FMU export: Simulink models can be exported as FMUs (Modelica standard),
    enabling co-simulation with COMSOL, OpenFOAM, and other adapters that
    accept FMU plant models. This is the primary co-simulation integration
    path with the existing solver adapters.
    """

    @property
    def domain(self) -> SimDomain:
        return SimDomain.SYSTEM_DYNAMICS

    @property
    def solver_name(self) -> str:
        return "matlab_simulink"

    async def dispatch(
        self,
        parameters: dict[str, Any],
        usd_stage_path: str,
    ) -> str:
        """
        Submit a Simulink model execution job.

        parameters must include:
          model_path: str        — path to .slx or .mdl Simulink model
          sim_mode: str          — MIL | SIL | HIL | sweep
          stop_time: float       — simulation stop time in seconds
          solver: str            — ode45 | ode23 | ode4 | discrete
          param_sweep: dict      — optional parameter sweep config

        Returns a job_id (local: process PID, engine: session_id,
        parallel: batch_job_id).
        """
        ...

    async def poll_status(self, job_id: str) -> SimRunStatus: ...
    async def fetch_results(self, job_id: str) -> dict[str, Any]:
        """
        Returns normalised result dict:
          - time_series: dict[signal_name, list[float]]
          - final_values: dict[param_name, float]
          - fmu_path: str | None  — if FMU was exported
          - performance_metrics: dict  — rise time, settling time, overshoot, etc.
          - pareto_front: list | None  — if multi-objective sweep was run
        """
        ...

    async def cancel(self, job_id: str) -> bool: ...
```

#### MATLAB ↔ PhysicsNeMo co-simulation path

Simulink Reduced Order Models (ROMs) can seed PhysicsNeMo surrogate training
data for control-relevant domains. Conversely, PhysicsNeMo surrogates can
replace computationally expensive Simscape subsystem models within a Simulink
block diagram — a PhysicsNeMo PINN predicting thermal distribution can be
called from a Simulink S-function, replacing a high-fidelity thermal model
that would slow real-time HIL execution.

This bi-directional relationship is the key technical integration between
ADR-005 and ADR-008.

#### CUDA-X routing for system_dynamics

The `system_dynamics` domain does not use cuDSS or AmgX — MATLAB's ODE
solvers and Simulink's fixed-step discrete solvers are not sparse linear
algebra problems in the CUDA-X sense. The `cuda_x_router` returns
`CudaXSolver.AUTO` for this domain (a no-op signal, consistent with the
optical domain treatment). MATLAB Parallel Server handles its own parallel
execution.

---

### Decision 2: Rescale as an execution backend, not a solver adapter

**We implement a `RescaleExecutionBackend` class in a new
`sim_bridge/execution_backends/` module. This is not a `SolverAdapter`
subclass. It is an infrastructure layer that existing domain adapters can
optionally route through for Enterprise tier HPC execution.**

The architectural distinction is essential: Rescale does not define the
physics domain or return domain-specific results. It executes whatever
solver the adapter has already selected, on HPC infrastructure the
client already has access to through their Rescale account.

```
sim_bridge/
├── base.py                          # SolverAdapter interface (unchanged)
├── cuda_x_router.py                 # CUDA-X routing (unchanged)
├── execution_backends/              # NEW — Phase 3
│   ├── __init__.py
│   ├── rescale_backend.py           # Rescale HPC job submission
│   └── local_backend.py            # Local/on-premise execution (default)
├── flow360.py                       # Cloud-direct, no execution backend needed
├── comsol.py                        # Can route via local or rescale backend
├── ansys_fluent.py                  # Can route via local or rescale backend
├── matlab_simulink.py               # Can route via local, engine, or parallel
└── ...
```

#### RescaleExecutionBackend

```python
# sim_bridge/execution_backends/rescale_backend.py

class RescaleExecutionBackend:
    """
    Execution backend that submits solver jobs to Rescale's HPC infrastructure.

    Used by solver adapters that support both direct/on-premise and
    Rescale-hosted execution modes. Enables Enterprise tier clients who
    already have Rescale accounts to route EWC Compute simulation jobs
    through their existing Rescale infrastructure without duplicating
    licence or compute costs.

    Rescale partner context:
      Rescale offers a "Powered by Rescale" channel partner programme.
      EWC Compute's domain specialisation in photonics and optical simulation
      is a potential vertical within this programme — bringing domain-specific
      AI assistant, provenance, and open architecture that Rescale's platform
      does not currently provide for the photonics domain.

    Configuration (.env):
      RESCALE_API_KEY:       Rescale API key
      RESCALE_BASE_URL:      https://platform.rescale.com/api/v2
      RESCALE_DEFAULT_HW:    default hardware config (e.g. "marble_towhee")
    """

    async def submit(
        self,
        software_code: str,         # Rescale software catalog code
        software_version: str,      # e.g. "2025r1"
        input_files: list[str],     # Local file paths to upload
        command: str,               # Execution command on the HPC node
        hardware_config: dict,      # Cores, RAM, GPU, etc.
    ) -> str:
        """Submit job to Rescale. Returns Rescale job_id."""
        ...

    async def poll(self, job_id: str) -> SimRunStatus:
        """Map Rescale job status → SimRunStatus."""
        # Rescale statuses: Queued → PENDING
        #                   Executing → RUNNING
        #                   Completed → COMPLETED
        #                   Failed → FAILED
        #                   Stopped → CANCELLED
        ...

    async def fetch_results(
        self,
        job_id: str,
        output_files: list[str],    # File patterns to download
    ) -> dict[str, Any]:
        """Download job outputs from Rescale storage. Returns file paths."""
        ...

    async def cancel(self, job_id: str) -> bool: ...
```

#### Adapter integration pattern

Adapters that support Rescale execution accept an optional backend parameter:

```python
class AnsysFluentAdapter(SolverAdapter):
    def __init__(
        self,
        execution_backend: Literal["on_premise", "rescale"] = "on_premise",
    ):
        self._backend = (
            RescaleExecutionBackend() if execution_backend == "rescale"
            else LocalExecutionBackend()
        )

    async def dispatch(self, parameters: dict, usd_stage_path: str) -> str:
        # Prepare Fluent input deck from USD stage and parameters
        input_files = self._prepare_fluent_case(parameters, usd_stage_path)

        if isinstance(self._backend, RescaleExecutionBackend):
            return await self._backend.submit(
                software_code="ansys_fluent",
                software_version=parameters.get("version", "2025r1"),
                input_files=input_files,
                command="fluent 3ddp -g -i case.jou",
                hardware_config=self._hardware_for_mesh_size(parameters),
            )
        else:
            return await self._backend.submit_local(input_files)
```

The `SolverAdapter` interface (defined in ADR-003) is never modified. The
execution backend is an internal implementation detail of each adapter.

#### Rescale MCP Server Framework

The webinar slide showed Rescale's MCP (Model Context Protocol) Server
Framework integration. EWC Compute's Physical AI Assistant already uses
Anthropic's Claude with MCP-compatible patterns in its DSR-CRAG pipeline.
The Rescale MCP integration means that in a "Powered by Rescale" deployment,
the Physical AI Assistant could query Rescale's job history, software catalog,
and hardware configurations directly — enabling the assistant to surface
cost estimates, hardware recommendations, and job troubleshooting guidance
grounded in the client's actual Rescale account data. This is a Phase 4
enhancement, not a Phase 3 requirement.

---

## Phase roadmap

| Phase | Integration | Location | Notes |
| --- | --- | --- | --- |
| 3 | `matlab_simulink.py` | `sim_bridge/` | MIL/SIL/HIL, Simscape, Parallel Server |
| 3 | `execution_backends/rescale_backend.py` | `sim_bridge/execution_backends/` | Enterprise tier HPC |
| 3 | `execution_backends/local_backend.py` | `sim_bridge/execution_backends/` | Default on-premise |
| 3 | Rescale backend option in `comsol.py` | Adapter modification | Enterprise routing |
| 3 | Rescale backend option in `ansys_fluent.py` | Adapter modification | Enterprise routing |
| 3 | Rescale backend option in `matlab_simulink.py` | Adapter modification | HPC sweeps |
| 4 | Rescale MCP Server integration with Physical AI Assistant | `assistant_service.py` | Job history, cost, HW recommendations |

---

## Consequences

### Positive — MATLAB/Simulink

**Closes the system dynamics gap.** Every engineering firm doing CFD
and FEM also does system-level control design and HIL validation in
Simulink. The absence of MATLAB/Simulink from EWC Compute's Sim Bridge
is immediately visible to professional engineers evaluating the platform.

**Direct AVL/aerospace integration path.** The AVL Copper Bird architecture
— simulation layer, emulation layer, real hardware — maps exactly onto
Simulink's MIL/SIL/HIL framework. The MATLAB/Simulink adapter makes EWC
Compute architecturally coherent with the test workflows used by
aerospace and automotive engineering firms that are EWC Compute's target
Enterprise tier clients.

**FMU co-simulation enables multi-solver workflows.** A Simulink model
exported as an FMU can be passed to the COMSOL or OpenFOAM adapter as
a plant model, enabling true multi-domain co-simulation — the control
system and the fluid dynamics evolving together. This is a capability
no single-domain platform provides cleanly.

**MATLAB Parallel Server bridges to HPC.** For parameter sweeps that
need HPC scale, MATLAB Parallel Server provides the execution backbone.
In a "Powered by Rescale" deployment, MATLAB Parallel Server can be
configured to submit workers to Rescale's HPC infrastructure — a direct
integration between Decision 1 and Decision 2 of this ADR.

### Positive — Rescale execution backend

**HPC infrastructure without owning it.** The single most significant
gap in EWC Compute's architecture is the absence of HPC compute
infrastructure. The `RescaleExecutionBackend` fills this gap for
Enterprise tier clients without requiring EWC Compute to own, operate,
or fund cloud compute infrastructure.

**"Powered by Rescale" partnership path.** The execution backend
implementation is the technical prerequisite for a formal Rescale
channel partner conversation. EWC Compute contributes domain
specialisation (photonics, optical simulation, provenance-tagged AI
assistant, open ADR architecture) that Rescale does not provide.
Rescale contributes compute, software catalog, security, and compliance
infrastructure that EWC Compute does not need to build.

**No SolverAdapter interface changes.** The execution backend sits
below the existing adapter interface. All Phase 2 adapters continue to
work exactly as built. Enterprise tier routing is additive.

**Governance and compliance alignment.** Rescale provides 1,000+
independently tested and audited security controls. Enterprise tier
clients with data sovereignty, IP protection, or regulatory compliance
requirements (defence, regulated industries) can route EWC Compute jobs
through their existing Rescale infrastructure that already meets their
compliance requirements — without EWC Compute needing to independently
certify against those standards.

### Negative / risks

**MATLAB licence requirement.** The `matlab_simulink.py` adapter requires
a MATLAB licence for every client that uses `system_dynamics` domain
simulations. MATLAB licences are expensive. Mitigation: the adapter
degrades gracefully — if no MATLAB licence is configured, `system_dynamics`
templates return `503 Solver Not Available`, consistent with the established
graceful degradation pattern. MATLAB/Simulink is an Enterprise tier feature,
not a Free or Professional tier feature.

**Rescale API dependency.** If Rescale changes their REST API, the execution
backend requires updating. Mitigation: the backend is isolated in
`execution_backends/rescale_backend.py`. No other file is affected. The
`SolverAdapter` interface and all Phase 2 adapters are entirely unaffected
by a Rescale API change.

**Execution backend increases test surface.** The `dispatch()` method on
adapters that support the Rescale backend now has two code paths. Both must
be covered by integration tests. The local backend tests remain fast and
dependency-free; the Rescale backend tests require either a real Rescale
account or a mock of the Rescale API. A mock is appropriate for CI;
real Rescale integration tests belong in a separate `tests/enterprise/`
directory that runs on demand rather than on every PR.

---

## Alternatives considered

### MATLAB as a separate platform, not a Sim Bridge adapter

Given that MATLAB is an entire engineering environment rather than a
physics solver, it could be argued that the integration should be at
the platform level (EWC Compute provides a "launch in MATLAB" button or
API export) rather than as a SolverAdapter. Rejected because the
`SimRun` record schema, the `ai_mode` dispatch routing, the KPI Dashboard
time-series collection, and the audit log all depend on solver results
flowing through the Sim Bridge. A MATLAB integration that bypasses the
Sim Bridge produces orphaned results with no provenance trail — exactly
the problem the architecture is designed to prevent. The adapter pattern,
with `system_dynamics` as a proper domain, keeps MATLAB results in the
same auditable pipeline as all other simulation results.

### Rescale as a SolverAdapter with a synthetic domain

Implementing Rescale as a `SolverAdapter` with a `domain: hpc_cloud`
enum value. Rejected because it would conflate infrastructure with physics
domain. The `SimDomain` enum represents physics domains, not execution
environments. A `domain: hpc_cloud` value would break the conceptual
integrity of the Sim Bridge and mislead any engineer reading the codebase.
The execution backend pattern correctly separates the two concerns.

### Build EWC Compute's own HPC infrastructure

Provision cloud compute (AWS, GCP, Azure) directly, manage solver
installations, handle licence orchestration. Rejected. This is Rescale's
core business, built over a decade with hundreds of millions in capital.
Replicating it would be the most expensive, time-consuming, and
strategically weakest use of EWC Compute's development effort. The
execution backend pattern makes Rescale's infrastructure available
without owning or replicating it.

---

## References

- MathWorks MATLAB Expo UK 2025 (Silverstone): virtual vehicle development,
  Simscape digital twins, Simulink Real-Time + Speedgoat HIL, MATLAB
  Parallel Server HPC execution
- AVL Webinar (April 2026): Copper Bird electric aircraft HIL testing —
  demonstrates Simulink-based MIL/SIL/HIL workflow for electric propulsion
- Rescale Webinar, The Engineer UK (May 27, 2026): AI Physics OS,
  Agentic Digital Engineering, "Powered by Rescale" partner programme,
  MCP Server Framework integration, Anthropic in AI & Agent Frameworks layer
- rescale.com: 1,250+ software catalog, 180+ hardware architectures,
  AVL/ANSYS/Siemens/NVIDIA as partner products
- ADR-003: Sim Bridge adapter pattern — `SolverAdapter` interface unchanged
- ADR-005: PhysicsNeMo — MATLAB/Simulink as the complementary system dynamics
  layer; surrogate ↔ Simscape ROM co-simulation path
- ADR-006: Flow360 as primary CFD solver — Rescale backend complements rather
  than replaces cloud-direct Flexcompute execution
- `sim_bridge/base.py` — `SimDomain` enum extension with `system_dynamics`
- `sim_bridge/execution_backends/rescale_backend.py` — Rescale HPC backend
- `sim_bridge/matlab_simulink.py` — MATLAB/Simulink adapter implementation

---



*Engineering World Company · EWC Compute Platform*
*ADRs record the reasoning behind significant architectural decisions.
They are never deleted — superseded ADRs are marked as such.*
