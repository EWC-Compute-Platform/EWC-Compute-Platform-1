# ADR-005 — PhysicsNeMo as AI Physics Framework

**Status:** Accepted
**Date:** March 2026
**Deciders:** Engineering World Company
**Relates to:** ADR-001 (technology stack), ADR-003 (Sim Bridge adapter pattern),
               ADR-004 (ai_mode explicit field), ADR-007 (surrogate_compute_budget)

---

## Context

ADR-004 established that `ai_mode` is an explicit field with three values:
`generative`, `surrogate`, and `principled_solve`. The `principled_solve` mode
dispatches to solver adapters via the Sim Bridge (ADR-003). The `generative`
and `surrogate` modes require an AI physics framework — a library that can
train and serve physics-informed neural networks, generative models, and
surrogate architectures against engineering simulation domains.

This ADR decides which framework that is.

The requirements for the AI physics framework:

**Technical requirements**
- Support physics-informed neural networks (PINNs) for surrogate mode,
  where hard physics constraints are enforced by construction in the
  loss function — not post-hoc filtered from outputs
- Support generative architectures (cWGAN-GP or equivalent) for
  generative mode, where the model explores design spaces and returns
  candidate configurations
- Support CAD-native inference — the ability to make physics predictions
  directly from geometry without requiring a mesh as an intermediate step.
  This is the capability that eliminates the meshing bottleneck for
  surrogate paths (see ADR-002 consequences)
- Support multi-domain training: CFD, FEM, thermal, electromagnetic,
  optical domains must all be expressible in the same framework
- GPU-accelerated training and inference
- Python-native, installable via pip, compatible with the stack in ADR-001
- Active development and maintenance with a credible long-term trajectory

**Strategic requirements**
- Alignment with the NVIDIA CAE integration stack — the framework should
  be the accepted production path for physics AI in the NVIDIA ecosystem,
  not a research prototype requiring significant productionisation work
- MIT or Apache licensed — no runtime royalty, no commercial usage restriction
- Compatible with the Overtone-style flexible tokenisation approach
  described in ADR-007 — the framework should be extensible to support
  runtime accuracy-speed trade-offs without retraining

**Ecosystem requirements**
- Integration with the solvers in the Sim Bridge — the framework should
  be able to consume output from Flow360, COMSOL, and Ansys Fluent as
  training data, not require proprietary data formats
- Compatibility with NVIDIA Warp (Phase 3) for GPU kernel-level
  validation of surrogate outputs
- Compatibility with the Polymathic AI research trajectory (Walrus,
  Overtone) — the framework should be the natural production landing
  point for architectures that begin as Polymathic AI research papers

---

## Decision

**We adopt NVIDIA PhysicsNeMo as the AI physics framework for EWC Compute's
`generative` and `surrogate` ai_mode implementations.**

PhysicsNeMo is NVIDIA's open-source AI framework for physics-informed
machine learning. It is the production-grade implementation of physics AI
within the NVIDIA CAE ecosystem, positioned between the research layer
(Polymathic AI, academic PINN literature) and the application layer
(EWC Compute's Sim Templates, Digital Twin Engine).

### What PhysicsNeMo provides

**Physics-Informed Neural Networks (PINNs)**
PINNs embed the governing equations (Navier-Stokes, heat equation,
Maxwell's equations, elasticity equations) directly into the neural
network loss function. The model cannot produce outputs that violate
the physical laws it was trained to respect — not because outputs are
filtered post-hoc, but because violation of the governing equations
increases the training loss. This is what "hard constraint enforcement"
means and why it matters: a surrogate that can violate conservation of
mass, energy, or momentum on edge-case geometries is not a trustworthy
engineering tool.

**AB-UPT architecture for CAD-native surrogate inference**
The Attention-Based Universal Physics Transformer (AB-UPT) operates
directly on point clouds derived from CAD geometry — no mesh generation
required. This eliminates the preprocessing bottleneck that has
historically made high-fidelity simulation inaccessible for rapid
design iteration. For context on what this means in practice: the
DrivAerML dataset demonstrates training on 150M cell CFD cases on a
single GPU in under one day. The trained model then predicts aerodynamic
coefficients for new geometries in seconds.

The implication for EWC Compute's Digital Twin Engine (ADR-002) is
direct: a twin at `predictive` fidelity level does not require mesh
generation as part of the workflow. The USD stage geometry → PhysicsNeMo
AB-UPT inference → physics prediction in seconds path is entirely
mesh-free.

**cWGAN-GP for generative mode**
Conditional Wasserstein GAN with Gradient Penalty is PhysicsNeMo's
generative architecture for design space exploration. Where surrogate
mode predicts the physics of a given geometry, generative mode inverts
the relationship: given desired physics targets (target drag coefficient,
maximum stress below a threshold, thermal distribution within bounds),
the cWGAN-GP generates candidate geometries that are likely to meet
those targets. This is the computational basis of `ai_mode: generative`.

**Multi-domain architecture configs**
PhysicsNeMo's `surrogate_configs/` directory supports distinct model
architecture configurations per domain — CFD requires different network
depth and training strategy than electromagnetic or FEM. EWC Compute
maintains these configs in `nvidia_cae/physicsnemo/surrogate_configs/`,
one per domain, versioned alongside the trained model weights.

**Overtone-style flexible tokenisation**
As documented in ADR-007, PhysicsNeMo's adoption of Convolutional Stride
Modulation (CSM) and Convolutional Kernel Modulation (CKM) from the
Polymathic AI Overtone paper enables a single trained model to serve
multiple `surrogate_compute_budget` levels (`exploratory | standard |
high_fidelity`) at inference time. This was incorporated into Walrus
at 1.3B parameter scale before reaching PhysicsNeMo as a framework
feature. EWC Compute's `surrogate_router.py` passes the
`surrogate_compute_budget` value to the PhysicsNeMo inference call
as a tokenisation configuration parameter.

### How EWC Compute uses PhysicsNeMo

PhysicsNeMo operates in two distinct modes within the platform:

**Training mode (Phase 2–3, offline)**
Surrogate and generative models are trained per domain using simulation
output from the Sim Bridge solvers as ground truth. Flow360 CFD results
train the CFD surrogate. COMSOL results train the electromagnetic and
thermal surrogates. Training runs are not triggered by engineer queries —
they are scheduled infrastructure operations, producing versioned model
weights stored in `PHYSICSNEMO_MODEL_STORE`.

**Inference mode (Phase 2+, online)**
When an engineer dispatches a template with `ai_mode: surrogate` or
`ai_mode: generative`, `surrogate_router.py` loads the relevant domain
model from the model store and calls PhysicsNeMo inference. Results
are returned in seconds and stored as a `SimRun` record with
`ai_mode: surrogate` explicitly recorded in the run metadata.

```python
# surrogate_router.py — simplified inference dispatch
from physicsnemo.models import load_model
from app.models.template import SurrogateComputeBudget

async def dispatch_surrogate(
    domain: SimDomain,
    usd_stage_path: str,
    compute_budget: SurrogateComputeBudget,
) -> dict[str, Any]:
    model = load_model(
        model_store=settings.PHYSICSNEMO_MODEL_STORE,
        domain=domain,
    )
    patch_size = BUDGET_TO_PATCH_SIZE[compute_budget]
    result = await model.infer(
        geometry_path=usd_stage_path,
        patch_size=patch_size,
    )
    return result
```

### The research-to-production pipeline

The Polymathic AI → PhysicsNeMo → EWC Compute pipeline is the expected
trajectory for AI physics improvements throughout the platform's lifetime:

```
Polymathic AI (research)
  └─ Walrus: 1.3B param transformer, 19 domains, 63.6% error reduction
  └─ Overtone: CSM/CKM flexible tokenisation, 30-40% long-horizon error reduction
       │
       ▼ incorporated into
NVIDIA PhysicsNeMo (production framework)
  └─ Versioned model architectures
  └─ Domain-specific training scripts
  └─ Inference endpoint wrappers
       │
       ▼ exposed via
EWC Compute surrogate_router.py
  └─ surrogate_compute_budget → patch_size mapping
  └─ Domain model registry
  └─ SimRun result storage
```

Both Walrus and Overtone are MIT licensed. PhysicsNeMo is Apache 2.0
licensed. The path from research paper to production inference is
entirely open-licensed.

### MATLAB/Simulink relationship (Phase 2+)

The MathWorks MATLAB Expo UK 2025 presentation on virtual vehicle
development demonstrates a complementary workflow: MATLAB/Simulink
system-level models (Simscape, Simulink Real-Time) are used for
control system design, HIL testing, and multi-objective optimisation
sweeps — workflows where signal processing, control logic, and
system-level dynamics are the primary concern.

PhysicsNeMo and MATLAB/Simulink serve different but complementary
roles in the EWC Compute architecture:

| Capability | PhysicsNeMo | MATLAB/Simulink |
| --- | --- | --- |
| Field-level physics (CFD, FEM, EM) | ✓ Primary | — |
| System-level dynamics and control | — | ✓ Primary |
| Surrogate model inference | ✓ | Via Simulink AI Toolbox |
| Real-time HIL testing | — | ✓ Simulink Real-Time + Speedgoat |
| Signal processing | — | ✓ Signal Processing Toolbox |
| Multi-objective optimisation | Via training | ✓ Optimization Toolbox |
| Industrial automation | — | ✓ Simulink PLC Coder |

The MATLAB adapter for EWC Compute's Sim Bridge would expose Simulink
models as solver-equivalent outputs — feeding system-level dynamics
results into the same `SimRun` schema that field-physics solvers use.
This is an ADR-008 decision (MATLAB/Simulink integration strategy)
rather than a consequence of ADR-005. It is flagged here because
PhysicsNeMo and MATLAB/Simulink are complementary at the model level:
PhysicsNeMo surrogates can replace computationally expensive subsystem
models within a Simulink block diagram, and Simulink reduced-order
models (ROMs) can seed PhysicsNeMo training data for control-relevant
domains.

---

## Consequences

### Positive

**Hard physics constraints are not optional.** Because PhysicsNeMo
PINNs enforce governing equations in the loss function, EWC Compute's
`surrogate` mode cannot produce results that violate conservation laws.
This is the difference between a trustworthy engineering tool and an
ML model with engineering branding. The Physical AI Assistant's
provenance system surfaces which results came from surrogates — but
the surrogates themselves are physically constrained by construction.

**CAD-native inference eliminates the meshing bottleneck.** The
AB-UPT architecture takes point clouds from USD geometry directly.
The engineer uploads a CAD file, selects `ai_mode: surrogate`, and
receives physics predictions in seconds with no mesh generation step.
This is qualitatively different from traditional surrogate workflows
that still require meshing before inference.

**The NVIDIA ecosystem integration is tight.** PhysicsNeMo is
maintained by NVIDIA, integrated with NIM for inference serving,
compatible with Warp for GPU kernel validation, and is the expected
landing point for Polymathic AI research architectures. This means
EWC Compute benefits from NVIDIA's physics AI investment without
needing to maintain the framework itself.

**Training data comes from the Sim Bridge.** PhysicsNeMo models are
trained on outputs from Flow360, COMSOL, and Ansys Fluent — the same
solvers in EWC Compute's Sim Bridge. There is no dependency on
external datasets or proprietary data formats. Every `principled_solve`
run that accumulates in the `SimRun` collection is potential training
data for the next generation of surrogates.

**The Overtone path is ready.** As documented in ADR-007, the
`surrogate_compute_budget` schema field is defined now. When PhysicsNeMo
exposes Overtone-style tokenisation natively, the production path from
schema to inference requires one change in `surrogate_router.py` and
no schema migration.

### Negative / risks

**Phase 2–3 dependency on training infrastructure.** PhysicsNeMo
surrogate models must be trained before they can serve inference.
Training requires GPU compute infrastructure and significant simulation
data from the Sim Bridge. Until Phase 3 training is complete, the
`surrogate` and `generative` modes return a `503 Surrogate Not Yet
Available` response for domains where no model exists. The platform
is functional without trained surrogates — `principled_solve` mode
works from Phase 2 — but the AI physics capability requires the
training investment.

**PINN training is slow compared to standard neural networks.**
The physics constraint terms in the loss function increase training
time significantly compared to purely data-driven models. For complex
domains (turbulent CFD, nonlinear FEM), training a production-grade
PINN surrogate may take days on GPU clusters. This is a one-time cost
per domain per geometry class, amortised over all subsequent inference
calls.

**Out-of-distribution accuracy degrades without visible signal.**
PhysicsNeMo surrogates are accurate for geometries within the training
distribution. For geometries that differ significantly from training
data, accuracy may degrade. The `[Model estimate, confidence: moderate
— verify before use]` tag in the Physical AI Assistant's provenance
system addresses this for individual claims, but the `surrogate` run
itself does not currently surface an out-of-distribution warning.
This is a Phase 3 quality improvement: adding distribution distance
metrics to the `SimRun` result schema so engineers can assess whether
their geometry is within the trained distribution.

---

## Alternatives considered

### Custom PINN implementation (from scratch)

Building a bespoke physics-informed ML framework on top of PyTorch
or JAX. Rejected. The implementation cost is large, the maintenance
burden is permanent, and the result would be strictly inferior to
PhysicsNeMo for years. PhysicsNeMo represents years of NVIDIA
engineering investment in production-grade physics AI infrastructure.
The correct strategic position is to build on it, not to replicate it.

### DeepXDE

DeepXDE is an open-source PINN library from Brown University, widely
used in academic research. It has strong Python support and good
documentation. Rejected because it is an academic research tool
without production inference serving, without the NVIDIA CAE ecosystem
integration, and without the generative architecture support (cWGAN-GP)
needed for `generative` mode. DeepXDE is appropriate for research
exploration; PhysicsNeMo is appropriate for production deployment.

### PhysicsX

PhysicsX is a commercial physics AI platform offering multiphysics
inference at claimed 10,000× to 1,000,000× speedup over numerical
simulation. Rejected as a framework dependency for several reasons:
it is commercial (not open-licensed), it is an application rather than
a framework (EWC Compute would be calling PhysicsX's API rather than
training and owning its own models), and the strategic positioning
of EWC Compute as a platform requires owning the AI physics layer
rather than delegating it. PhysicsX is a potential partner for
specific domains where EWC Compute's trained surrogates do not yet
exist — not a replacement for the framework decision.

### Neural Concept

Neural Concept is a commercial AI engineering platform with strong
OEM traction (GM, Airbus, Eaton, Williams F1). Like PhysicsX, it
is a commercial application rather than an open framework. The
strategic relationship with Neural Concept is as a potential partner
for enterprise engineering deployments — not as the AI physics
framework layer. Neural Concept's commercial model and domain expertise
are complementary to EWC Compute; adopting it as a framework dependency
would make EWC Compute a reseller of Neural Concept's capability rather
than an independent platform.

---

## References

- PhysicsNeMo documentation: [developer.nvidia.com/physicsnemo](https://developer.nvidia.com/physicsnemo)
- PhysicsNeMo GitHub: [github.com/NVIDIA/physicsnemo](https://github.com/NVIDIA/physicsnemo)
- Polymathic AI Walrus: [github.com/PolymathicAI/walrus](https://github.com/PolymathicAI/walrus)
- Polymathic AI Overtone: [github.com/payelmuk150/patch-modulator](https://github.com/payelmuk150/patch-modulator)
- DrivAerML dataset: 150M cell CFD, single GPU, sub-day training
- ADR-004: `ai_mode` as explicit field — defines the modes PhysicsNeMo serves
- ADR-007: `surrogate_compute_budget` — extends surrogate mode with Overtone tokenisation
- EWC Compute Research Intelligence No. 1 (2026): Polymathic AI Walrus and Overtone
- MathWorks MATLAB Expo UK 2025: Virtual vehicle development, Simscape digital twins,
  real-time HIL testing — establishes MATLAB/Simulink as the complementary
  system-level dynamics layer (see flagged ADR-008)

---

*Engineering World Company · EWC Compute Platform*
*ADRs record the reasoning behind significant architectural decisions.
They are never deleted — superseded ADRs are marked as such.*

