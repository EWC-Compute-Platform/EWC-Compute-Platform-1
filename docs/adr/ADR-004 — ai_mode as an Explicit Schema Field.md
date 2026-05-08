# ADR-004 — `ai_mode` as an Explicit Schema Field

**Status:** Accepted
**Date:** April 2026
**Deciders:** Engineering World Company
**Relates to:** ADR-001 (technology stack), ADR-003 (Sim Bridge adapter pattern),
               ADR-005 (PhysicsNeMo), ADR-006 (Flow360), ADR-007 (surrogate_compute_budget)

---

## Context

EWC Compute supports three fundamentally different approaches to simulation,
each making a different epistemological commitment about the relationship
between physics, accuracy, compute, and engineering intent:

- **`generative`** — a PhysicsNeMo generative model (cWGAN-GP architecture)
  explores a design space broadly, returning candidate configurations.
  It operates at the frontier of the unknown design space. The engineer
  does not yet know what they are looking for; the model explores.

- **`surrogate`** — a trained physics surrogate (PINNs / AB-UPT architecture)
  predicts simulation outputs in seconds from geometry and boundary
  conditions, bypassing the full numerical solver. The engineer knows
  the design space but needs fast, repeated evaluation. Physics constraints
  are enforced by construction, not post-hoc filtering.

- **`principled_solve`** — a full-fidelity numerical solver (Flow360, COMSOL,
  Ansys Fluent) runs the complete governing equations. The engineer needs
  a result they can submit to a regulator, certify to a standard, or
  commit to a fabrication process. Accuracy is non-negotiable.

These three modes are not interchangeable. Each has different accuracy
characteristics, different compute costs, different validity domains, and
different appropriate use cases. The accuracy-cost-validity trade-off
space between them is large:

| Attribute | `generative` | `surrogate` | `principled_solve` |
| --- | --- | --- | --- |
| Typical solve time | Seconds | Seconds–minutes | Minutes–hours |
| Accuracy vs full solver | Design-space exploration | 95–99% for in-distribution geometries | 100% by definition |
| Mesh required | No | No (CAD-native) | Yes |
| Valid for certification | No | No | Yes |
| Appropriate for | Early-stage design sweep | Rapid iteration, known design space | Pre-production validation |

The question this ADR answers is not which mode is best. The question is:
**who decides which mode runs, and is that decision visible?**

There are two possible answers:

**Option A — Implicit:** The platform decides internally based on heuristics
(query type, mesh size, previous run history). The engineer submits a
simulation and the platform selects a mode. The UI might say
"AI-optimised" or "smart dispatch" or "intelligent solver selection."
The engineer sees a result.

**Option B — Explicit:** The engineer declares `ai_mode` as a required
field on every `SimTemplate`. The platform cannot run a simulation without
a declared mode. The UI surfaces the choice. The engineer owns the decision.

The tension between these options is real. Option A is more convenient —
it reduces configuration burden. It is also the pattern that every major
engineering software vendor has adopted. Siemens Xcelerator, Dassault
3DEXPERIENCE, Ansys Discovery, and Autodesk Simulation all offer some
form of automatic solver selection or AI-assisted mode switching.

This ADR explains why we chose Option B.

---

## Decision

**`ai_mode` is a required, explicit field on every `SimTemplate`. It has
no default value. A simulation cannot be dispatched without a declared
`ai_mode`. The platform never selects a mode on behalf of the engineer.**

```python
class AiMode(str, Enum):
    GENERATIVE      = "generative"
    SURROGATE       = "surrogate"
    PRINCIPLED_SOLVE = "principled_solve"

class SimTemplate(BaseModel):
    # ... other fields ...

    ai_mode: AiMode
    # No default. Field is required. Pydantic raises ValidationError
    # if ai_mode is absent or not one of the three enum values.
    # The API returns HTTP 422 Unprocessable Entity if ai_mode is missing.
```

This is enforced at three independent layers:

1. **Pydantic schema** — `ai_mode` has no `default` parameter. Missing
   field raises `ValidationError` at model instantiation.
2. **FastAPI endpoint** — the HTTP layer returns `422 Unprocessable Entity`
   with a clear error message if `ai_mode` is absent from the request body.
3. **Database write** — the `sim_templates` service validates the template
   before writing to MongoDB. No template record can exist in the database
   without a valid `ai_mode` value.

The UI is required to surface the choice to the engineer. There is no
"auto" button that hides the decision behind a friendly label.

### The `surrogate_compute_budget` extension (ADR-007)

When `ai_mode` is `surrogate`, a second explicit field becomes active:
`surrogate_compute_budget` (`exploratory | standard | high_fidelity`).
This extends the same principle one level deeper: within surrogate mode,
the accuracy-speed trade-off is also made explicit rather than left to
platform heuristics. See ADR-007 for full reasoning.

---

## Consequences

### Why implicit mode selection is an engineering anti-pattern

The case for Option A (implicit) sounds reasonable: engineers should not
need to know the difference between a PINN surrogate and a direct sparse
solver. The platform should handle that complexity. This is the standard
argument for abstraction.

The argument fails in an engineering context for a specific, concrete
reason: **the validity domain of the result is different depending on
which mode ran.**

A `surrogate` result is accurate for in-distribution geometries — geometries
similar to what the model was trained on. For out-of-distribution
geometries, accuracy degrades, sometimes catastrophically, without any
visible signal in the output. A surrogate result and a `principled_solve`
result look identical as numbers. They are not identical as claims. One
is a physics-grounded prediction with known validity bounds; the other
is a certified numerical solution.

If the engineer does not know which mode produced their result, they
cannot assess what the result means. They cannot know whether the number
in front of them is appropriate to submit for certification, appropriate
to use for design iteration, or only appropriate as exploratory guidance.

An implicit mode selection therefore does not reduce the engineer's
cognitive burden — it transfers the burden from configuration to
interpretation, and makes it invisible rather than explicit. The engineer
still needs to know the difference between modes to use the result
correctly. The implicit UI just hides the information at the moment when
they are best positioned to engage with it.

This is precisely the failure pattern that produced the MCAS certification
crisis in commercial aviation, the fin whale collision incident in
autonomous shipping, and a long list of engineering failures where
automated system behaviour was not legible to the human operator. EWC
Compute is not an autonomous system, but the principle is the same:
**when an automated decision has consequences, the human must understand
what decision was made.**

### The anti-pattern in the market

Every major engineering software vendor that has introduced automatic
solver selection or "AI-optimised" dispatch has subsequently added
expert mode, advanced settings, or manual override paths because
professional engineers consistently require legibility. The sequence
is: ship the simple UI → professional users complain about not knowing
what ran → add an obscure expert setting that restores visibility →
most users never find it.

EWC Compute starts with the expert setting as the default. The UI
surfaces the choice clearly, with a plain-language explanation of
each mode's trade-offs. Engineers who want to run the same query in
multiple modes to compare results can do so explicitly. The platform
supports that workflow because the mode is a first-class schema field,
not an internal heuristic.

### The Dassault IPLM validation

Nicolas Cerisier (VP, 3DEXPERIENCE Platform R&D, Dassault Systèmes)
described IPLM — Intelligent Product Lifecycle Management — as their
mechanism for tracking every AI interaction in the engineering workflow
(NVIDIA AI Podcast Ep. 296, April 2026). The explicit `ai_mode` field
in EWC Compute is the implementation of the same principle at the
template level: every simulation run has a traceable, declared mode
that is stored in the `SimRun` record and the `AuditEvent` log.
Six months after a simulation ran, the engineer can answer the question
"which mode produced this result" by reading the database record.
With implicit mode selection, that question may be unanswerable.

### Positive

**Every result is interpretable.** An engineer looking at a simulation
result six months later can read `ai_mode: surrogate` and immediately
understand the result's accuracy claims and validity bounds.

**The audit trail is complete.** `SimRun` records, `AuditEvent` logs,
and the `AssistantResponse.prompt_version` field form a coherent audit
chain. `ai_mode` is one element of that chain. Regulators, quality
engineers, and project managers can reconstruct exactly what ran and why.

**Versioning is unambiguous.** A `SimTemplate` with `ai_mode: surrogate`
and one with `ai_mode: principled_solve` are different templates, even
if all other parameters are identical. They represent different
engineering commitments. Versioning them separately is correct.

**The Physical AI Assistant can give useful guidance.** The assistant
is grounded in the corpus and can explain the trade-offs of each mode
for a given domain and geometry. Because `ai_mode` is explicit, the
assistant can surface the decision at the moment the engineer is
creating a template — "for this geometry type, surrogate accuracy is
typically within 2% for this domain; here is the reference." That
guidance is only useful if the engineer is about to make an explicit
choice. It is useless if the platform is about to make the choice
silently.

**The platform is honest.** EWC Compute is positioning itself as a
trustworthy engineering tool, not a black box. Making `ai_mode` explicit
is the schema-level expression of that commitment.

### Negative / risks

**Higher initial configuration burden.** The engineer must declare
`ai_mode` for every template. Engineers unfamiliar with the three modes
face a steeper learning curve on first use. Mitigation: the UI provides
plain-language descriptions of each mode with concrete accuracy and
timing guidance for each domain. The Physical AI Assistant can answer
mode selection questions directly. Template libraries with pre-configured
modes for common workflows reduce the burden to copy-and-modify.

**Risk of cargo-cult selection.** Engineers who do not understand the
modes may select `principled_solve` for everything as the "safe" choice,
paying compute costs they do not need. This is a training and UX problem,
not an architectural problem. It is preferable to engineers unknowingly
using `surrogate` results for certification-relevant decisions.

**Friction in automated workflows.** Automated pipeline integrations
(CI/CD systems calling the EWC Compute API for repeated design iteration)
must include `ai_mode` in every request. This is intentional — even
automated pipelines must declare what they are running. The `ai_mode`
field in a pipeline configuration is a documented engineering decision,
not configuration boilerplate.

---

## Alternatives considered

### Default `ai_mode` to `surrogate`

Provide a default value so the field is technically optional while
still being queryable. Rejected. A default creates a class of runs
where the engineer did not actively choose the mode. The audit trail
becomes ambiguous: did the engineer choose `surrogate`, or did they
not set the field and get the default? The discipline of no-default
is the discipline of no-ambiguity.

### Separate endpoints per mode (`/simulate/surrogate`, `/simulate/solve`)

Three endpoints instead of one field. Rejected. This fragments the
`SimTemplate` schema. A template that starts in `generative` mode
and transitions to `principled_solve` for final validation is a single
engineering artefact with a documented progression. Separate endpoints
would require separate template records with no structural link between
them. The mode is a property of the template, not a routing decision.

### Implicit with audit logging

Run implicit mode selection but log which mode was chosen. Rejected.
Logging after the fact does not give the engineer the information at
the moment of decision. The point of explicitness is not just
auditability — it is engineer engagement at the right moment.

### `ai_mode` as a free-text field

Allow arbitrary strings so engineers can define custom modes. Rejected.
The three modes are architecturally grounded in fundamentally different
computational approaches. Custom modes would not map to any dispatch
logic. An enum with three values is the correct type for a closed set
of mutually exclusive, architecturally distinct options.

---

## References

- `backend/app/models/template.py` — `AiMode` enum and `SimTemplate` model
- `backend/app/services/sim_templates.py` — `ai_mode` dispatch routing
- ADR-003: Sim Bridge adapter pattern — adapters receive `ai_mode` as
  a dispatch parameter
- ADR-005: PhysicsNeMo — implements `generative` and `surrogate` modes
- ADR-007: `surrogate_compute_budget` — extends the explicit field
  principle into surrogate mode resolution
- NVIDIA AI Podcast Ep. 296 (2026): Dassault Systèmes IPLM — AI
  interaction traceability as an engineering discipline
- EWC Compute Post 4 (2026): *Sim Templates: Three Ways to Solve the
  Same Engineering Problem* — `ai_mode` trade-offs in prose

---

*Engineering World Company · EWC Compute Platform*
*ADRs record the reasoning behind significant architectural decisions.
They are never deleted — superseded ADRs are marked as such.*

