# The Physics Foundation Model Layer Is Forming — And It Changes How EWC Compute Thinks About Surrogates

**Engineering World Company · Research Intelligence, No. 1**

*This is a research intelligence post — a shorter piece outside the main build series, covering developments from the research frontier that directly inform how EWC Compute is being built. The main series continues with Post 6 on Sim Templates.*

---

## Two papers you should know about if you run simulations for a living

In the past six months, a research group called Polymathic AI — a multi-institution collaboration funded by the Simons Foundation and Schmidt Sciences, with a scientific advisory board that includes Yann LeCun and Stéphane Mallat — has published two results that I think mark a genuine inflection point in physics simulation.

The first is **Walrus**: a 1.3 billion parameter transformer that predicts the next state of a fluid system from a sequence of previous states. It covers 19 physical domains — from turbulent flows to astrophysical plasmas to non-Newtonian fluids — from a single architecture, trained once. Against the best previous specialised models, it reduced one-step prediction error by an average of 63.6 percent. MIT licensed, freely available.

The second, published in March 2026, is **Overtone**: a framework that makes transformer-based physics surrogates flexible at inference time. Where Walrus established that a single model could match or beat domain-specific models across a wide range of physics, Overtone establishes that the same model can serve multiple compute budgets at inference time — without retraining. One trained model, many deployment configurations, on demand.

Both papers are from the same core team. McCabe, Ohana, Cranmer are on both. Walrus incorporated the Overtone approach at scale. They are building a coherent research programme, not isolated results.

This post explains what these papers actually do, why they matter for working engineers, and how they change the architecture of EWC Compute's surrogate mode.

---

## The problem Walrus solves — and the one it does not

Traditional simulation surrogates are trained for a specific physical system. A model trained on turbulent pipe flow can tell you about turbulent pipe flow. A model trained on airfoil aerodynamics can tell you about airfoil aerodynamics. The accuracy is high, but the specialisation is total. To cover a new physical domain, you train a new model.

Walrus breaks that pattern. It is trained across 19 physical domains simultaneously, learning shared representations of physical dynamics — density, pressure, velocity, temperature — that transfer across systems. The result is a single model with broad coverage rather than a portfolio of narrow specialists.

This follows the trajectory Andrew Ng described in The Batch: just as large language models learned to read and predict across tasks and languages, physics transformers trained on diverse data appear to be learning to predict the behaviour of diverse materials across domains. The specialised-to-general shift that took NLP a decade is happening in physics simulation over a much shorter timescale.

What Walrus does not yet solve is the deployment problem. It is a remarkable research result, but it is trained and deployed at a fixed tokenisation scale. That means it runs at one accuracy-compute operating point. If you want a faster, coarser prediction for exploratory work, you cannot just tell it to run faster. If you want to push fidelity higher for a critical validation, you cannot just tell it to be more precise. Changing the operating point means training a different model.

That is the problem Overtone addresses.

---

## What Overtone actually does

Patch-based transformer surrogates work by dividing the spatial domain into patches — groups of grid cells or pixels — and treating each patch as a token. Smaller patches mean more tokens, finer resolution, higher accuracy, higher compute cost. Larger patches mean fewer tokens, coarser resolution, faster inference, lower cost.

In conventional architectures, the patch size is fixed at training time. A model trained at patch size 4 runs at patch size 4. If you want patch size 8, you train again.

Overtone introduces two mechanisms — Convolutional Stride Modulation (CSM) and Convolutional Kernel Modulation (CKM) — that make the patch size a runtime parameter rather than a training constant. CSM changes the stride of the convolutional encoder dynamically. CKM resizes the kernel itself. Both are architecture-agnostic: they can be applied to existing transformer designs without restructuring them.

The practical result: a single Overtone-trained model can run at patch sizes 4, 8, and 16 at inference time. In their experiments, one Overtone model trained on the same compute budget as three separate fixed-patch models matches or exceeds all three across their respective operating points. You spend the training budget once, you get the full accuracy-speed trade-off on demand.

The second result is less obvious but arguably more important for long simulations. When the same patch grid is used at every autoregressive step, discretisation errors accumulate at the same spatial frequencies repeatedly. Over 20, 40, 60 steps, this produces checkerboard-like artefacts in the predicted fields — structured errors that compound rather than averaging out.

Overtone's cyclic rollout schedules — alternating through patch sizes like 4→8→16→4→8→16 — break that coherence. Different patch sizes introduce errors at different frequencies, so no single frequency accumulates. The result is up to 30–40% reduction in long-horizon rollout error, and visibly cleaner predicted fields across 10-step and longer predictions. Across 2D and 3D benchmarks spanning shear flow, Rayleigh-Bénard convection, active matter, and supernova explosion dynamics, the pattern holds consistently.

---

## Why this matters for engineers, not just researchers

The research framing focuses on benchmark scores. The engineering framing focuses on a different question: what does this change about how you actually run simulations in a design workflow?

The current situation: if you want a fast surrogate for exploratory design sweeps, you train a coarse model. If you want a high-accuracy surrogate for pre-validation, you train a fine model. Maintaining both means double the training compute, double the versioning overhead, double the validation effort. For a research group with GPU clusters, this is manageable. For a small engineering team that wants surrogate inference without a dedicated ML engineer, it is a significant barrier.

What Overtone changes: one trained model handles both workflows. The engineer sets a compute budget parameter — exploratory, standard, high-fidelity — and the model adjusts its tokenisation accordingly. The accuracy-speed trade-off that previously required two separate models becomes a runtime dial.

For eVTOL aerodynamics specifically — the domain most relevant to the aerospace engineering audience this series is building — this matters concretely. A rotor design sweep across 200 collective pitch configurations wants fast, approximate results. Narrowing to five candidates before committing to a full CFD solve wants accuracy close to the solver. With fixed-patch surrogates, these are sequential workflows requiring two models. With an Overtone-style approach, they are two settings on one model invocation.

---

## How this changes EWC Compute's architecture

EWC Compute's `ai_mode` field already distinguishes between `generative` (PhysicsNeMo cWGAN-GP, broad design exploration), `surrogate` (fast physics prediction, skip the full solver), and `principled_solve` (full-fidelity Flow360 or COMSOL run). That three-mode structure remains correct and important — it reflects three genuinely different epistemological positions on how much you know about a design problem.

What Overtone adds is resolution within the `surrogate` mode. Currently, surrogate mode is a single operating point: one model, one accuracy level, one compute cost. With Overtone-style flexible surrogates, the surrogate mode gains a `compute_budget` parameter — the accuracy-speed dial that Overtone makes available. The engineer who knows their design space but wants to manage compute cost gains a control they currently lack.

In EWC Compute's implementation, this maps to an extension of the `SimTemplate` schema: a `surrogate_compute_budget` field with values `exploratory`, `standard`, `high_fidelity`, each corresponding to a different Overtone tokenisation setting. The surrogate router — `surrogate_router.py` — passes this through to the inference call. The engineer does not need to understand patch sizes or CSM mechanics; they choose how much compute to spend, and the platform translates that into the appropriate model configuration.

There is also an important implication for training cost. Phase 3 of EWC Compute involves training PhysicsNeMo surrogate models for each simulation domain. If those models incorporate Overtone-style flexible tokenisation, the training budget covers multiple deployment regimes rather than one. The operational maintenance overhead — tracking, validating, and versioning multiple fixed-patch models per domain — is reduced to one flexible model per domain.

---

## The ecosystem is forming

Walrus and Overtone are research outputs from a university-adjacent lab. They are not yet production infrastructure — there is no managed API, no enterprise support, no SLA. But that will change, and the MIT licensing means it will not require a commercial relationship to use them.

The trajectory is: Polymathic AI publishes research → NVIDIA PhysicsNeMo incorporates the architectures → EWC Compute's surrogate mode benefits. The Overtone authors already note that CSM has been incorporated into Walrus at scale. The path from research paper to production framework is shortening.

The positioning that follows from this is simple. Polymathic AI is building the research layer. NVIDIA is building the production framework layer. EWC Compute is building the application layer — the platform that translates research-grade physics AI into a tool a mechanical engineer or aerodynamicist can use without a PhD in machine learning. Each layer depends on the others. None of them are in competition.

For working engineers, the message is this: the accuracy of surrogate simulation is improving rapidly, the compute cost of running it is falling, and the range of physical domains it covers is expanding. The gap between what a physics AI surrogate can predict and what a full numerical solver can predict is narrowing in both directions at once. EWC Compute's job is to make that gap visible, honest about when it matters, and accessible to the engineers who need to make decisions on both sides of it.

---

*EWC Compute — Engineering World Company*
*GitHub: [github.com/EWC-Compute-Platform](https://github.com/EWC-Compute-Platform)*
*Polymathic AI: [polymathic-ai.org](https://polymathic-ai.org)*
*Walrus: [github.com/PolymathicAI/walrus](https://github.com/PolymathicAI/walrus)*
*Overtone: [github.com/payelmuk150/patch-modulator](https://github.com/payelmuk150/patch-modulator)*

---

*Engineering World Company covers the methods, tools, and decisions behind modern computational engineering — and builds the platform to make them accessible.*
