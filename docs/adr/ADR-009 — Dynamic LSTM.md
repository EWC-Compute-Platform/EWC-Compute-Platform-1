# ADR-009 — Dynamic LSTM Configuration-Conditioned Surrogates for RF and Vibro-Acoustic Domains

**Status:** Accepted
**Date:** June 2026
**Deciders:** Engineering World Company
**Relates to:** ADR-003 (Sim Bridge adapter pattern), ADR-004 (ai_mode explicit field),
               ADR-005 (PhysicsNeMo AI physics framework), ADR-007 (surrogate_compute_budget),
               ADR-008 (MATLAB/Simulink system_dynamics)

---

## Context

ADR-005 established PhysicsNeMo as the AI physics framework for `generative`
and `surrogate` ai_mode, centred on PINNs and the AB-UPT architecture for
CAD-native, spatial-field surrogate inference (CFD, FEM, electromagnetic
field solves). That architecture family answers one specific question well:
*what is the physical field, everywhere, given this geometry?*

A distinct paper — Sun et al., "Digital twin optical computing system"
(DT-OCS), *Opto-Electronic Advances* 9, 250254 (2026), Tsinghua University
and National University of Defense Technology, DOI 10.29026/oea.2026.250254 —
proposes a different architecture answering a different question: *what is
the next moment of this time-domain signal, given the device's current
scalar configuration?* This is the correct question for a materially
different class of physical systems: those whose defining behaviour is
causal, time-domain, finite-memory, and governed by a small number of
continuously adjustable configuration parameters rather than by spatial
geometry.

### The DT-OCS mechanism, precisely

DT-OCS models a physical optical computing system as an operator
`O(t) = F(i(ξ ∈ [t−τ, t]); V)` — the output at time `t` depends on the
input over a finite receptive field `[t−τ, t]` and on a configuration
vector `V` (in their validation case, three phase-shifter bias voltages).

The system is measurement-driven, not derived from governing equations:
DT-OCS is trained by supervised learning directly on experimentally
measured input-output pairs from the physical device, across randomly
sampled configurations. This is the correct choice precisely because the
target systems have significant non-ideal, fabrication-specific, and
component-level behaviour (thermal crosstalk, phase-to-intensity
nonlinearity, bandwidth-limited electronics) that is impractical to derive
analytically but is fully captured by direct measurement.

The core architectural device is the **Dynamic LSTM cell**. In a standard
LSTM, the gate weight matrices and biases are fixed parameters learned once
during training. In DT-OCS, those same internal parameters are *generated*
by a small trainable function block (a linear/affine mapping in the primary
configuration, tested against a two-layer nonlinear variant) that takes the
configuration vector `V` as input. The recurrent cell's dynamics are
therefore continuously reconfigured by device state — a single trained
network spans the entire configuration space, rather than requiring one
model per operating point.

Three results from the paper matter architecturally, independent of the
specific optical hardware validated:

1. **Differentiability enables gradient-based configuration optimisation.**
   Because the Dynamic LSTM supports backpropagation, optimal configuration
   search that previously required online hardware evaluation (particle
   swarm optimisation directly on the physical device) can be replaced by
   offline gradient descent on the trained surrogate. In their gold-trading
   temporal strategy validation task, this reduced total optimisation time
   from 1.74 days (15,000 hardware evaluation rounds, ~10s each due to
   thermal settling) to 10.7 minutes — under 0.4% of the original time.

2. **Joint time-frequency similarity loss.** Training and validation use
   `SF = 0.5·MSE(Ô,O) + 0.5·MSE(|FFT(Ô)|,|FFT(O)|)` — equal weighting of
   time-domain and frequency-domain error — explicitly to avoid degenerate
   fits that match local waveform shape while missing global spectral
   structure, or vice versa.

3. **Residual decomposition via Voigt profile.** The discrepancy between
   surrogate and physical hardware output is fit as a Voigt profile (the
   convolution of a Gaussian and a Lorentzian), physically motivated as the
   combination of two distinct error sources: model approximation error
   (Gaussian-like, from the function block's limited expressiveness) and
   hardware-induced physical noise — timing jitter, thermal noise, phase
   noise, gain noise (Lorentzian-like, long-tailed). This is a materially
   more rigorous uncertainty characterisation than a single confidence
   score.

### Why RF and vibro-acoustic are correct extensions and CFD is not

The Dynamic LSTM pattern is architecturally appropriate exactly when a
physical system has: (a) time-domain, causal, finite-memory input-output
behaviour, and (b) a small number of continuously adjustable scalar
configuration parameters governing that behaviour. It is architecturally
inappropriate when the primary output is a spatially distributed field
rather than a time-domain signal.

**RF domain fits precisely.** RF power amplifier behavioural modelling —
capturing memory effects, gain compression, and nonlinear distortion as a
function of bias and gain configuration — is a long-established subfield
currently dominated by memory-polynomial and Volterra-series models. Those
are themselves configuration-conditioned time-domain models with known
limitations in capturing complex nonlinear memory interactions. A Dynamic
LSTM is a legitimate, plausibly superior, drop-in architectural alternative
for the same modelling problem: causal, time-domain, low-dimensional
configuration space.

**Vibro-acoustic domain fits precisely.** A structural system's vibrational
or acoustic response — driven by stiffness, damping, and thermal
configuration — is causal, exhibits finite memory (settling/decay time
analogous to DT-OCS's receptive field `τ`), and is governed by a small
number of adjustable physical parameters. The measurement-driven approach
is additionally well-suited here because vibro-acoustic behaviour is
notoriously difficult to derive purely analytically once real damping,
material variance, and boundary conditions are involved — exactly the
situation DT-OCS was designed to address for optical hardware.

**CFD does not fit, and should not be forced.** CFD's defining output is a
spatially distributed field (pressure, velocity, temperature across a mesh
or point cloud) resulting from geometry, not a time-domain signal resulting
from a handful of scalar configuration values. This is precisely the
problem ADR-005's AB-UPT architecture already solves correctly — CAD-native,
point-cloud attention over spatial geometry. Forcing CFD into a Dynamic LSTM
formulation would require either discarding spatial field structure (a real
accuracy loss) or prepending a spatial encoder to a fundamentally
sequence-oriented architecture — in which case the result is simply an
inferior, ad hoc version of what AB-UPT already does. **This ADR explicitly
excludes CFD from the Dynamic LSTM surrogate family.** Any future proposal
to apply this architecture to CFD should be evaluated against this
reasoning before proceeding.

---

## Decision

**We adopt the Dynamic LSTM configuration-conditioned surrogate architecture,
following Sun et al. (2026), as a second AI physics surrogate family within
EWC Compute's `surrogate` ai_mode — distinct from and complementary to the
PhysicsNeMo AB-UPT/PINN family established in ADR-005. This architecture is
scoped explicitly to two new simulation domains: `rf` and `vibro_acoustic`.
It is explicitly not applied to CFD, FEM, thermal, electromagnetic
(field-solve), or optical (spatial) domains, which remain served by
PhysicsNeMo per ADR-005.**

### SimDomain extension

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
    SYSTEM_DYNAMICS = "system_dynamics"   # ADR-008: MATLAB/Simulink
    RF              = "rf"                # ADR-009: Dynamic LSTM
    VIBRO_ACOUSTIC  = "vibro_acoustic"    # ADR-009: Dynamic LSTM
```

Note the distinction from `ELECTROMAGNETIC`: that domain remains reserved
for field-solve problems (Maxwell's equations via COMSOL/HFSS, routed
through AmgX per ADR-003). `RF` is reserved for circuit/component-level,
time-domain behavioural modelling — a different computational problem
sharing the same underlying electromagnetic phenomena but requiring the
Dynamic LSTM family, not a field solver.

### The `dynamic_lstm` surrogate module

```
ai_physics/
├── __init__.py
├── physicsnemo_client.py       # ADR-005 — spatial-field surrogates
├── warp_kernels.py
├── surrogate_router.py         # Extended to route by architecture family
└── dynamic_lstm/                # NEW — ADR-009
    ├── __init__.py
    ├── dynamic_lstm_cell.py     # Configuration-conditioned LSTM cell
    ├── function_block.py        # V → gate parameters mapping (linear/nonlinear)
    ├── similarity_loss.py       # Joint time-frequency SF loss
    ├── residual_analysis.py     # Voigt-profile decomposition, noise injection
    └── training/
        ├── rf_training.py
        └── vibro_acoustic_training.py
```

#### Dynamic LSTM cell

```python
# ai_physics/dynamic_lstm/dynamic_lstm_cell.py

class DynamicLSTMCell(nn.Module):
    """
    LSTM cell whose gate weight matrices and biases are generated by a
    trainable function block conditioned on device/system configuration,
    rather than fixed at training time.

    Follows Sun et al., "Digital twin optical computing system",
    Opto-Electron Adv 9, 250254 (2026).

    A single trained DynamicLSTMCell spans the entire configuration space
    of the physical system — one network, not one model per operating point.
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        config_dim: int,           # dimension of V (e.g. bias voltages,
                                    # amplifier gain settings, damping coeffs)
        function_block: Literal["linear", "nonlinear"] = "linear",
    ):
        """
        function_block: "linear" — single affine mapping V → gate params.
                         Matches the primary DT-OCS configuration: high
                         computational efficiency, stable training.
                         "nonlinear" — two linear layers with an intermediate
                         nonlinear activation. Captures nonlinear parameter
                         coupling (e.g. thermal crosstalk between configuration
                         channels) at increased computational cost. Use when
                         the linear block's residual distribution shows
                         significant Lorentzian (long-tail) component,
                         indicating uncaptured coupling — see ADR-009
                         residual_analysis.py.
        """
        ...

    def forward(
        self,
        input_sequence: torch.Tensor,   # [batch, receptive_field, input_size]
        config: torch.Tensor,           # [batch, config_dim]
    ) -> torch.Tensor:
        """
        Returns predicted output sequence. Internal gate parameters are
        generated from `config` via the function block before the standard
        LSTM recurrence is applied.
        """
        ...
```

#### Similarity loss

```python
# ai_physics/dynamic_lstm/similarity_loss.py

def joint_time_frequency_loss(
    predicted: torch.Tensor,
    target: torch.Tensor,
) -> torch.Tensor:
    """
    SF(pred, target) = 0.5 * MSE(pred, target)
                      + 0.5 * MSE(|FFT(pred)|, |FFT(target)|)

    Equal weighting of time-domain and frequency-domain error prevents
    degenerate fits that capture local waveform shape while missing
    global spectral structure, or vice versa. Following Sun et al. (2026).
    """
    ...
```

#### Residual analysis

```python
# ai_physics/dynamic_lstm/residual_analysis.py

def fit_voigt_residual(
    predicted: np.ndarray,
    measured: np.ndarray,
) -> VoigtFitResult:
    """
    Fits the residual distribution (predicted - measured) as a Voigt
    profile — the convolution of a Gaussian and a Lorentzian component.

    Gaussian component σ: attributed to model approximation error
      (function block expressiveness limits).
    Lorentzian component σ: attributed to hardware-induced physical
      noise (timing jitter, thermal noise, phase noise, gain noise).

    This decomposition feeds the confidence tier assigned to
    dynamic_lstm surrogate results in the Physical AI Assistant's
    provenance system — a materially more rigorous basis than the
    single similarity-score confidence mapping used for PhysicsNeMo
    surrogates (see ADR-005 _tier_to_confidence). A large Lorentzian
    component relative to Gaussian indicates the residual is dominated
    by hardware noise the model cannot and should not try to fit —
    informing engineers that the surrogate is at its practical accuracy
    ceiling for this device, not under-trained.
    """
    ...
```

### Measurement-driven training requirement

Unlike PhysicsNeMo surrogates (ADR-005), which can be trained on synthetic
or solver-generated data, the Dynamic LSTM family is **measurement-driven
by design** — it is trained on real device input-output data because its
entire purpose is capturing device-specific, fabrication-specific,
non-ideal behaviour that a governing-equation model would not represent.
This has a direct operational consequence: `rf` and `vibro_acoustic`
domain surrogates require a physical device or component measurement
campaign before training is possible. `seed_corpus.py`-style synthetic
seeding does not apply here. This is documented explicitly so the Phase 3
roadmap does not silently assume the same training data pipeline as the
CFD/FEM/EM domains.

### Twin revalidation taxonomy (informing ADR-002)

Sun et al. give a clean three-tier taxonomy for when a trained
measurement-driven surrogate remains valid after the underlying hardware
changes, directly applicable to any EWC Compute digital twin at
`predictive` fidelity (ADR-002):

| Hardware change | Surrogate validity |
| --- | --- |
| Component replaced with identical-spec part | Remains valid, no retraining |
| Component replaced with different characteristic parameters (bandwidth, noise, gain) | Retraining required; same architecture/framework |
| Underlying computational/physical architecture redesigned | New surrogate required; methodology unchanged |

This taxonomy should be adopted as the formal revalidation policy for any
`predictive`-fidelity twin in the Digital Twin Engine, not only for
`dynamic_lstm`-family surrogates. It is recorded here because this is
where it was identified; ADR-002 should reference it.

### `ai_mode` and `surrogate_compute_budget` interaction

The Dynamic LSTM family operates under `ai_mode: surrogate`, consistent
with ADR-004. `surrogate_compute_budget` (ADR-007) does not apply in the
same sense — there is no equivalent to Overtone's patch-size tokenisation
for a recurrent, configuration-conditioned architecture. For `rf` and
`vibro_acoustic` domains, `surrogate_compute_budget` is accepted but
mapped only to a choice between the `linear` and `nonlinear` function
block (`exploratory`/`standard` → linear; `high_fidelity` → nonlinear),
which is a genuine accuracy-compute trade-off analogous in spirit, though
not mechanism, to the PhysicsNeMo case.

---

## Consequences

### Positive

**A real architectural gap is closed.** RF and vibro-acoustic domains had
no home in EWC Compute's Sim Bridge or surrogate architecture prior to
this ADR. Both are common engineering workloads (power amplifier
characterisation, structural resonance and NVH analysis) that the platform
could not previously address in `surrogate` mode at all.

**The measurement-driven approach is intellectually honest for these
domains.** Unlike CFD or FEM, where governing equations are well
established and PINNs are the correct tool, RF component behaviour and
real structural damping are dominated by exactly the kind of
fabrication-specific, hard-to-derive-analytically effects DT-OCS was built
to capture. Choosing measurement-driven modelling here is not a compromise
— it is the more rigorous choice for this class of problem.

**Differentiability gives a concrete, citable performance argument.** The
1.74 days → 10.7 minutes figure is a strong, source-verified number for
EWC Compute's `surrogate` mode value proposition in these domains,
consistent in register with the Flow360 100× and AB-UPT sub-day figures
already in the corpus.

**The Voigt residual decomposition upgrades EWC Compute's confidence
model.** This is a better foundation for future refinement of the Physical
AI Assistant's `_tier_to_confidence` mapping (ADR-005) than what currently
exists — worth extending to PhysicsNeMo-family surrogates in a later phase,
not only the new Dynamic LSTM family.

**CFD exclusion is explicit and reasoned, preventing future architectural
drift.** By stating clearly why CFD does not fit this pattern, a future
proposal to extend Dynamic LSTM to CFD is forced to engage with this
reasoning rather than reopening the question from scratch.

### Negative / risks

**Requires physical measurement infrastructure EWC Compute does not
currently have.** Unlike PhysicsNeMo surrogates trained on Sim Bridge
solver output, `rf` and `vibro_acoustic` Dynamic LSTM surrogates require
real hardware measurement campaigns — signal generators, oscilloscopes,
vibration shakers, or equivalent, plus the device or component under
test. This is a materially different resource requirement than any other
domain in the platform. Mitigation: this is scoped as a Phase 3+
capability, dependent on either EWC Compute or a partner (potentially the
Tsinghua/NUDT group itself, or an Enterprise tier client with existing
lab infrastructure) providing the measurement data. It is not a Phase 2
blocker.

**Two distinct surrogate architecture families increase system
complexity.** `surrogate_router.py` must now route not only by domain but
by architecture family (PhysicsNeMo spatial-field vs. Dynamic LSTM
configuration-conditioned). Mitigation: the routing key is simply
`SimDomain` — `cfd/fem/thermal/electromagnetic/optical` → PhysicsNeMo;
`rf/vibro_acoustic` → Dynamic LSTM. No per-request ambiguity.

**No existing solver adapter produces training data for these domains.**
The Sim Bridge currently has no RF or vibro-acoustic solver adapter
(SPICE-family for RF, or an FEA modal/harmonic solver for vibro-acoustic
are the natural candidates, not yet built). Measurement-driven training
does not strictly require one — real hardware measurement is the
DT-OCS-following path — but a solver adapter would allow synthetic
pre-training before a measurement campaign, as a Phase 4 refinement.

---

## Alternatives considered

### Extend PhysicsNeMo/AB-UPT to RF and vibro-acoustic instead

Rejected for the reasons stated in Context: these are time-domain,
low-dimensional-configuration problems, not spatial-field problems.
AB-UPT's point-cloud attention mechanism has no natural role here — there
is no CAD geometry driving the prediction, only a scalar configuration
vector and a time-domain signal history.

### Apply Dynamic LSTM to CFD as originally proposed

Rejected and documented explicitly above. CFD's output is a spatial
field, not a time-domain signal; forcing the architecture would discard
information AB-UPT already handles correctly.

### Wait for a solver adapter before building the surrogate architecture

Rejected as the required first step. DT-OCS's central contribution is
precisely that measurement-driven training does not require a solver
adapter — it requires real hardware data. Waiting for a synthetic-data
solver adapter would delay this capability without technical necessity,
given the reference methodology is explicitly measurement-driven.

---

## References

- Sun R, Li YM, Fu TZ, Liu WC, Yang SG, Chen HW. Digital twin optical
  computing system. *Opto-Electronic Advances* 9, 250254 (2026).
  DOI: 10.29026/oea.2026.250254. Open access, CC BY 4.0.
  Code: https://cloud.tsinghua.edu.cn/d/146f72dd4f2b46f394bd/
- ADR-002: OpenUSD twin format — twin revalidation taxonomy to be
  incorporated from this ADR's findings
- ADR-003: Sim Bridge adapter pattern — `SimDomain` enum extension pattern
  (consistent with ADR-008's `system_dynamics` addition)
- ADR-004: `ai_mode` explicit field — Dynamic LSTM operates under `surrogate`
- ADR-005: PhysicsNeMo AI physics framework — the complementary spatial-field
  surrogate family; CFD/FEM/thermal/EM/optical remain PhysicsNeMo's domain
- ADR-007: `surrogate_compute_budget` — partial applicability noted above
- ADR-008: MATLAB/Simulink `system_dynamics` domain — precedent for
  extending `SimDomain` for non-spatial-field physics
- `ai_physics/dynamic_lstm/` — implementation location

---

*Engineering World Company · EWC Compute Platform*
*ADRs record the reasoning behind significant architectural decisions.
They are never deleted — superseded ADRs are marked as such.*

