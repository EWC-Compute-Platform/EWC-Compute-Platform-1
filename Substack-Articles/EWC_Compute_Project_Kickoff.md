# EWC Compute — The Kickoff: Architecture, Decisions, and What We Are Actually Building

**Engineering World Company · Platform Build Series, No. 2**

*This post follows the platform introduction published last week. If you have not read it, the short version is: we are building a general-purpose digital engineering platform for professional engineers who need serious computational capability without enterprise procurement overhead. This post is about the technical architecture, the decisions behind it, and the honest reasoning for each.*

---

## Starting with the constraint that matters most

Every engineering platform eventually fails its users in one of two ways. Either it is powerful but inaccessible — the kind of system where you spend two weeks configuring a solver environment before running your first job — or it is accessible but shallow, a UI wrapper around a single API that breaks the moment your problem leaves the expected shape.

The design constraint we set before writing a line of code was this: an engineer with a real problem should be able to get a meaningful result in under fifteen minutes on their first session, and that same engineer should not hit a capability ceiling at month three. Those two requirements are in tension. Resolving them is what the architecture is actually about.

---

## The architecture — two complementary views

EWC Compute has two views of its architecture that need to be read together. The first is the functional stack — five layers from user access down through DevSecOps — which describes what engineers interact with and how requests flow through the system. The second is the NVIDIA CAE integration stack, which maps the specific AI and GPU compute libraries that power each layer, phased across the build roadmap.

Most engineering platform documentation only publishes the first view, which is why their AI capabilities are difficult to evaluate honestly. We publish both. What follows is the functional view; the NVIDIA CAE integration stack is covered in the next section.

### The five functional layers

Most of what users see is Layer 2 — the four engineering pillars. The layers below it are what make those pillars trustworthy rather than just functional.

**Layer 1 — User access.** JWT-based authentication, role differentiation (individual engineer, team lead, admin), OAuth2 + PKCE flow. Not a complex decision — these are the current standards for web application security. The one deliberate choice here is that project data isolation is enforced at the database query level, not just at the API level. Multi-tenant isolation only at the API is a common shortcut that creates a category of data exposure risk we are not willing to accept in an engineering context.

**Layer 2 — The four pillars.** This is the platform surface — Digital Twin Engine, Sim Templates, KPI Dashboards, Physical AI Assistant. Each is described in the section below.

**Layer 3 — Platform core.** FastAPI (Python) for the backend gateway, Pydantic v2 for schema validation, a lightweight agentic orchestration layer for multi-step workflows, Redis-backed job queue for simulation dispatch. The choice of FastAPI over alternatives like Django REST or Flask is deliberate: it generates OpenAPI documentation automatically, handles async natively (important for long-running simulation jobs), and is already the de facto standard in the Python scientific computing and ML ecosystem — meaning our target developer contributors will be familiar with it.

**Layer 4 — Infrastructure and data.** MongoDB Atlas as the primary data store, chosen for schema flexibility (engineering objects have variable structure — a fluid dynamics twin and an electromagnetic twin do not share the same parameter set) and native vector search for retrieval-augmented generation. The Simulation Bridge is a separate adapter layer — not directly in the API handler — specifically so that adding a new solver backend does not require touching the upstream application code. This is the most important structural decision in the entire backend.

**Layer 5 — DevSecOps, cross-cutting.** GitHub Actions for CI/CD, security scanning on every pull request, Infrastructure as Code via Terraform, OpenTelemetry for observability. This layer is not beneath the infrastructure — it wraps everything. No code reaches production without a passing security scan and two reviewers. This is a standard we are setting from day one because retrofitting security discipline into a codebase built without it is significantly more expensive than building it in from the start.

---

## The NVIDIA CAE canonical workflow — and where EWC Compute sits in it

Before describing the pillars individually, it is worth establishing the reference framework. NVIDIA's Computer-Aided Engineering documentation describes a five-step canonical workflow that defines how AI and GPU acceleration interact in modern engineering simulation:

preprocessing → solving → CUDA-X acceleration → AI physics and agentic engineering → digital twins

Every serious engineering simulation follows this path. EWC Compute is the platform that orchestrates all five steps under a single interface. Preprocessing happens in the Digital Twin Engine (CAD upload, mesh specification, boundary conditions). Solving happens via the Simulation Bridge — a solver-agnostic adapter layer covering seven simulation domains: computational fluid dynamics (CFD), finite element method (FEM), thermal, electromagnetics, optical/photonic, electronic design automation (EDA), and collision/explicit dynamics. CUDA-X acceleration runs inside those solvers on GPU infrastructure: cuDSS (direct sparse) for FEM, EDA, and collision workloads; AmgX (algebraic multigrid) for large-scale CFD and electromagnetics. AI physics runs in the Sim Templates layer via PhysicsNeMo for generative and surrogate modes. Digital twins are produced, stored in OpenUSD, and monitored via the KPI Dashboard.

EDA and Collision are worth naming explicitly because they represent two domains that do not appear in most simulation platform descriptions but are central to the computational engineering ecosystem: EDA for GPU-accelerated semiconductor chip design and signal integrity verification, and Collision for explicit dynamics solvers assessing vehicle crashworthiness and structural deformation before physical prototypes are built. Both are Phase 3 integrations — the Simulation Bridge defines their interface from Phase 0, but the full solver adapters arrive when the platform is ready for them.

The architecture is also explicitly two views — a functional stack showing what engineers interact with, and an NVIDIA CAE integration stack showing the libraries that power each layer, phased across the build roadmap. Both views are documented in the repository README. The reason for making both explicit is that most engineering platforms describe only the first view — which is why their AI capabilities are difficult to evaluate honestly. Naming the library stack with phase labels makes it legible: what is running in Phase 0, what arrives in Phase 2, what is Phase 3. Engineers reading this can see exactly what the platform can and cannot do at any point in time.

---

## The four pillars — what they actually do

### Digital Twin Engine

The centrepiece. An engineer provides a CAD file (STEP, IGES, or DXF), a parametric specification, or a natural language description, and the engine produces a digital twin — geometry, physics parameterisation, material library association, and boundary condition set.

The critical format decision: twins in EWC Compute are stored in OpenUSD, NVIDIA's open 3D scene description standard. This is not an obvious choice — there are simpler formats we could have used for an initial implementation. We chose OpenUSD because Dassault Systèmes, Siemens, PTC, Microsoft, Cadence, and ABB have all committed to it as their interoperability standard at GTC 2026. An engineer who creates a twin in EWC Compute should be able to use that twin in Omniverse, Simcenter, or any other OpenUSD-native tool without a conversion step. Proprietary twin formats are a trap that vendors set and users fall into.

Twin fidelity operates at three levels. Geometric twins carry shape and dimensions — enough for interference checking and basic visualisation. Behavioural twins carry physics parameterisation — material properties, thermal boundary conditions, load cases — and connect to the Simulation Bridge for validation runs. Predictive twins incorporate a trained surrogate model that generates physics predictions in seconds without running the full solver on every query. Engineers choose the fidelity level appropriate to their current design stage; they are not forced to run a full CFD solve when a surrogate is accurate enough.

### Sim Templates

Software-defined computational workflow templates. The concept is simple: instead of configuring a solver from scratch every time, an engineer selects or customises a template that encodes the workflow decisions — solver type, mesh strategy, boundary conditions, convergence criteria, output targets — as a versioned, reproducible schema.

The schema is defined with Pydantic v2. Every template run validates against it before dispatch. If a boundary condition is missing or a mesh parameter is physically implausible, the validation catches it before any compute resources are consumed. Engineers who have configured COMSOL or ANSYS manually understand the cost of discovering a configuration error three hours into a solve.

The template's `ai_mode` field is the most important design decision in this pillar. It takes one of three values:

`generative` — **PhysicsNeMo** runs a cWGAN-GP architecture to explore the design space broadly, producing multiple candidate configurations for the engineer to evaluate. PhysicsNeMo enforces physics constraints by construction — candidate designs that violate fundamental conservation laws are eliminated in the generative loop, not by the engineer reviewing the output. Use this in early-stage design when you do not yet know which region of parameter space is worth investigating.

`surrogate` — **PhysicsNeMo** runs a physics-informed neural network (PINN or AB-UPT architecture) that generates predictions in near real-time without invoking the full solver. The AB-UPT architecture we covered on this Substack in October — trained on a single GPU in under a day, inference in seconds on 150 million mesh cell problems, hard physics constraints enforced by construction, no meshing required — is the reference implementation target for the CFD surrogate backend. **NVIDIA Warp** GPU kernels handle lightweight validation of the surrogate output before it reaches the engineer.

`principled_solve` — full-fidelity solver run via the Simulation Bridge. CUDA-X acceleration is now delivered through COMSOL and Ansys (Fluent, LS-DYNA): **cuDSS** (direct sparse solver) for FEM, structural, and EDA workloads; **AmgX** (algebraic multigrid) for large-scale CFD and electromagnetics. The combined acceleration range is 20–500×, depending on domain and whether AI physics preconditioning is applied on top of the hardware acceleration. Use this when accuracy is the primary requirement and compute cost is acceptable. The engineer makes this choice explicitly; the platform does not make it for them.

The three modes are not a hierarchy — they are different tools for different design stages. The engineer selects `ai_mode` as a first-class field on every template run.

### KPI Dashboards

Monitoring is underbuilt in most simulation workflows. Engineers run a solve, inspect a result file, make a decision, and move on. The context — how that result compares to the previous iteration, where it sits relative to the design target, whether the convergence was clean or suspicious — is mostly in the engineer's head, not in a recoverable record.

The KPI Dashboard layer addresses this by treating simulation results as a time series, not as individual files. Every template run populates a MongoDB time-series collection. The dashboard builder lets engineers configure widgets — convergence history charts, parameter sweep Pareto fronts, fabrication readiness status, threshold alerts — using the accumulated run history as the data source.

The practical outcome is that an engineer can look at a dashboard six months into a project and see the full design iteration history, the key decision points, and the parameter trajectory that led to the current design. This is the kind of project continuity that currently exists only in expensive PLM systems.

### Physical AI Assistant

This pillar requires the most careful framing, because AI-assisted engineering reasoning is currently a space full of overpromising.

The Physical AI Assistant is a prompt-driven copilot that retrieves from a curated engineering corpus, cites its sources, and quantifies its confidence. It handles literature lookup, parameter estimation, design trade-off analysis, error diagnosis, materials guidance, and standards compliance checks. For queries that would trigger a platform action — running a simulation, querying a dashboard, adjusting template parameters — it proposes the action in plain language and waits for explicit engineer confirmation before executing.

Three design decisions that distinguish it from "chat with your CAD file" products:

The retrieval architecture is DSR-CRAG — Dual-State Corrective Retrieval-Augmented Generation. The corrective loop is not a post-processing check; it is part of the retrieval pipeline. Candidate responses are evaluated against retrieved source material for physical consistency before they reach the engineer. Physics-incorrect outputs — wrong material properties, implausible geometric constraints, fabricated standards references — are caught in the pipeline, not by the engineer reviewing the output.

Inference is served through **NVIDIA NIM microservices**. NIM gives us versioned, domain-tuned model endpoints behind an OpenAI-compatible API — meaning the underlying model can be updated, benchmarked against the previous version, and rolled back if its engineering accuracy regresses, all without touching application code. The assistant is not coupled to a single foundation model. It is coupled to a specification: cite sources, quantify uncertainty, enforce physics consistency, require confirmation before acting.

Every numeric claim carries an explicit provenance tag. "Retrieved from [source], confidence high" is a different signal from "Estimated by model, confidence moderate — verify before use." Engineers reading model outputs need to know which category they are in. The UI makes this distinction visible, not buried in metadata.

The assistant does not make autonomous design decisions. It has no write access to twins, templates, or dashboards without engineer-triggered confirmation. The human-in-the-loop constraint is enforced at the architecture level, not by a prompt instruction that can be rephrased around.

---

## The commercial logic

Three customer segments, ordered by which we build for first:

Individual engineers and consultants are the primary target for Phase 1. They are the users most directly constrained by the gap we are filling — professional-grade simulation capability exists, but the access layer requires enterprise procurement they cannot complete. A Free tier (one project, limited simulation runs) and a Professional tier at €49/month cover this segment. The pricing anchor is deliberate: a single ANSYS Mechanical standalone licence costs more per month than a year of EWC Compute Professional. The comparison is not approximate.

SME engineering firms of five to fifty engineers are the Phase 2 commercial target. They have shared project infrastructure needs — collaborative templates, team dashboards, client-reportable outputs — that point tools cannot provide and enterprise PLM is too expensive to deploy. A Team tier at €199/month for up to ten seats addresses this.

Research groups and universities are the third segment and the one that most directly feeds the engineering corpus. Academic teams producing applied engineering research generate exactly the kind of domain-specific simulation knowledge that makes the Physical AI Assistant more capable. The corpus improves with usage; the assistant improves with corpus quality; better assistant capability drives platform adoption. This is the flywheel.

Six business moats — not listed to impress, but because investors eventually ask and the honest answer matters: engineering corpus quality and RAG retrieval precision; template library network effects (templates shared between engineers compound in value); twin history and project data gravity; solver integration depth (each validated Simulation Bridge adapter is months of engineering work); fabrication export accuracy (GDSII generation that passes real DRC checks is non-trivial); and ethical AI differentiation (in a market where hallucinated physics causes fabrication errors and design failures, a platform with explicit uncertainty quantification is meaningfully different from one without it).

---

## The build sequence — and the reasoning behind it

Phase 0 is infrastructure: authenticated platform skeleton, base Pydantic schemas, CI/CD pipeline, local development environment, GitHub monorepo structure, first Architecture Decision Records. The deliverable is a running but empty platform — an authenticated shell that proves the stack works end to end before any engineering logic is added. Five ADRs are written in Phase 0: technology stack (ADR-001), OpenUSD as native twin format (ADR-002), Sim Bridge adapter pattern (ADR-003), `ai_mode` as an explicit schema field (ADR-004), and PhysicsNeMo as the AI physics framework replacing a generic model architecture description (ADR-005).

One Phase 0 decision deserves naming explicitly: `usd-core`, `warp-lang`, and `physicsnemo` are all locked into `requirements.txt` from the first commit, even though only `usd-core` is actively used in Phase 0. Locking them now means dependency resolution is stable and tested before those libraries become load-bearing in Phases 2 and 3. Discovering a version conflict between PhysicsNeMo and a transitive dependency at the start of Phase 2 — when you are trying to build a surrogate training pipeline — is a much more expensive problem than pinning it correctly from the beginning.

Phase 1 is the Physical AI Assistant. This sequencing needs justification because the Digital Twin Engine might seem like the natural starting point — it is the visual centrepiece of the platform. The reason for building the AI Assistant first is that it has the lowest infrastructure dependency of the four pillars (no solver integration required), the highest immediate value signal for early users, and it seeds the engineering corpus that improves every other pillar downstream. Concretely: Phase 1 connects the DSR-CRAG retrieval pipeline to the engineering corpus, builds the NVIDIA NIM inference client with the Nemotron domain model, and ships the citation display and engineer-confirmation UI. An engineer who can ask a well-grounded engineering question and receive a cited, uncertainty-quantified answer in Phase 1 is an engineer who understands what the platform is for. A digital twin with no physics-grounded copilot is a prettier version of a CAD viewer.

Phase 2 is Sim Templates and the first Simulation Bridge connection. Phase 3 is the Digital Twin Engine with full OpenUSD support and fabrication export. Phase 4 is KPI Dashboards, platform polish, and the controlled beta launch.

The full sequence is thirty-six weeks from Phase 0 start to beta. That is the realistic timeline for a platform built properly — with security discipline, test coverage, and architecture decisions documented in ADRs — not the timeline for a demo built to impress investors.

---

## What the Substack is to the platform

Every deep-dive published here is a potential entry in the engineering corpus that powers the Physical AI Assistant. The AB-UPT analysis covers neural CFD surrogates. The space data centre analysis covers thermal management constraints for orbital infrastructure. Each post in this series covers one platform pillar in depth — the methods behind it, the specific NVIDIA library that powers it, the architectural decisions made, and the honest limits of what the current implementation can do.

The series plan from here: the Digital Twin Engine and OpenUSD (Post 3); Sim Templates, CUDA-X solver routing, and the three AI modes (Post 4); the Physical AI Assistant, NIM inference, and what DSR-CRAG actually means in practice (Post 5); KPI Dashboards and a build-in-public progress update (Post 6).

The connection between the writing and the building is not incidental. Understanding an engineering method clearly enough to explain it rigorously to practitioners is the same standard required to build a system that reasons about it honestly. The publication is the record of the reasoning. The platform is the reasoning made useful.

---

*EWC Compute — Engineering World Company*
*GitHub: [github.com/EWC-Compute-Platform](https://github.com/EWC-Compute-Platform)*
*Post 3 — The Digital Twin Engine: OpenUSD, physics parameterisation, and why CAD-native surrogate inference changes the meshing problem*

---

*Engineering World Company covers the methods, tools, and decisions behind modern computational engineering — and builds the platform to make them accessible.*
