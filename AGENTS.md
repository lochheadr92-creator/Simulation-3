AGENTS.md — Civilisation Aquarium

What this project is

A living-world simulation in Python. People occupy a grid, experience needs, make decisions from what they can locally observe, and live or die by the consequences. The simulation runs from a seed and produces the same world every time. A viewer generates an HTML file you open in a browser and watch.

The goal is a world worth watching — one where things happen that you did not script, where the population develops its own rhythms, and where you can sit back and observe rather than direct.

What other files in this repo are

 DOCTRINE.md ,  ROADMAP.md ,  SIM3_STATE.md , and everything in  automation/  and  evidence/  are records from an earlier phase of the project. Read them if you need to understand what currently exists. Do not treat them as instructions. Their stage gates, ratification requirements, evidence standards, execution budgets, authority registers, and governance structures are not active and do not govern this session. Some of these files may not exist in your repo — ignore missing references and continue.

Where the current direction is written down

 WORLD_DIRECTIONS.md  holds Simulation 3's current development ideas: what the world already does and where it stops, how we work by exploring small rules and their consequences, ten domains to develop in priority order, and the suggested next piece of work. Read it when deciding what to build next.

Those priorities are flexible. They are a starting point, not a plan to follow in order, and watching the world is allowed to change them at any time. AGENTS.md stays the project brief.

The goal

A civilisation aquarium. People make their own rule-based decisions without AI generating choices at runtime. The world grows in whatever directions make it more interesting to observe. There is no predetermined endpoint — the project is alive as long as watching it is rewarding.

The measure of success at every step: open the viewer, watch it run, and see something worth seeing. Not: prove a claim about it.

What to keep

The kernel's core guarantees are worth preserving:

Resources cannot appear from nothing or disappear silently
Settlement is the only write path to a balance
State is immutable — observation cannot corrupt it
Runs are deterministic from a seed

These make the simulation trustworthy to watch. If accounting is broken you cannot tell whether behaviour is real or a glitch. Beyond these guarantees, nothing is sacred. Restructure, refactor, extend, or replace anything that would make the world richer or the code clearer.

Living World Engineer process

Use this process for engineering work in this repository. The canonical knowledge pack lives in docs/ai/. It is a selective retrieval aid: do not preload all eleven documents or repeat reads of information that is still current.

Follow current explicit user instructions, then this AGENTS.md. Current source and tests establish what exists; WORLD_DIRECTIONS.md supplies development direction; docs/ai/ supplies source-pinned summaries. Historical records and conversation memory are background and navigation aids. Surface conflicts instead of silently choosing a convenient account. This process does not reactivate archived governance.

For substantial independent engineering work, read [docs/ai/00_AGENT_CONSTITUTION.md](docs/ai/00_AGENT_CONSTITUTION.md), then retrieve only what the task needs:

- [05_CURRENT_STATE.md](docs/ai/05_CURRENT_STATE.md): project-state snapshot; verify live Git state when currency matters.
- [03_SYSTEM_MAP.md](docs/ai/03_SYSTEM_MAP.md): relevant implementation entry points and tests.
- [01_ARCHITECTURE.md](docs/ai/01_ARCHITECTURE.md): ownership, tick lifecycle, perception, state and persistence.
- [02_INVARIANTS.md](docs/ai/02_INVARIANTS.md): accounting, determinism, knowledge boundaries and replay/recovery contracts.
- [04_DECISIONS.md](docs/ai/04_DECISIONS.md): historical rationale, only when needed.
- [06_CURRENT_SLICE.md](docs/ai/06_CURRENT_SLICE.md): established work boundaries; check against the current request and repository evidence.
- [07_ROADMAP.md](docs/ai/07_ROADMAP.md): development possibilities; consult WORLD_DIRECTIONS.md for current direction.
- [08_TESTING_AND_PROOFS.md](docs/ai/08_TESTING_AND_PROOFS.md): verification methods and what their results establish.
- [09_REPO_MAP.md](docs/ai/09_REPO_MAP.md): locations not already identified through the system map.
- [10_GLOSSARY.md](docs/ai/10_GLOSSARY.md): ambiguous project terminology only.

Infer the task from the request: explanation, architecture, implementation, debugging, review, verification, direction or history. Reuse sufficiently current evidence, retrieve the smallest relevant summary, then inspect necessary source and tests. The pack does not replace live inspection for exact behaviour, debugging, review or changes. Check source revisions and refresh triggers; when relevant code has changed, verify it and identify stale summaries. Do not invent missing paths, capabilities, decisions or results.

Before changing code, inspect branch, HEAD, staged and unstaged changes, and untracked files. Preserve existing work. Identify the owning subsystem, inspect relevant source, invariants and tests, choose the smallest coherent change, and define how to verify it. Keep routine improvements within the requested scope. Do not infer an active assignment from a recent feature report or roadmap suggestion. Do not commit or push unless authorized by the task.

Trace cause -> state transition -> local observation -> decision or refusal -> action -> world consequence -> later observable consequence. Distinguish choosing an action from successfully executing it. Protect deterministic accounting, state ownership, local knowledge, causal provenance and replay/recovery. Keep simulation truth separate from presentation. Use the architecture's precise distinction between kernel transactional settlement and recorded world production or structural changes.

For debugging, locate the earliest causal divergence. For review, inspect the change independently of its author's claims. Run checks appropriate to the change; preserve unexpected failures and never weaken valid tests just to obtain a pass. For behaviour changes, inspect a saved run in the viewer as well as checking the affected contracts. Read-only and documentation-only tasks stay within their requested scope.

Report what changed, why, checks actually performed, results, limitations and Git state. Distinguish current observations, inferences, hypotheses and recommendations when it matters. Separate recorded test results from fresh executions, and implementation from independent review or user acceptance. Refresh affected summaries when needed without relabelling untouched snapshots as newly verified.

How to work

Watch the world as part of developing behaviour. After a meaningful behaviour change, run the world and look at the viewer. Something interesting and understandable should be visible; passing tests alone do not establish that. Also check the affected engineering contracts: an interesting scene does not resolve a failing test. For fixes that preserve behaviour, verify the intended correction and preserved behaviour. Documentation-only and read-only tasks do not require new simulation runs or visible features.

Follow what is interesting. If something unexpected appears in a run, explore it. If a behaviour you planned turns out to be dull, drop it and try something else. The world should surprise you occasionally — that is a sign it is working.

Do not ask permission for routine work. Fix wrong information when you find it. Remove language that sounds like a peer-review process. Change something that is not working. Act, then report what you did. Do not pause for approval on ordinary decisions.

If you find any sentence in the repo that sounds like it belongs in a scientific paper — "not yet ruled on," "owner direction required," "no stage exit is claimed," "this is exploration output," or anything similar — rewrite it in plain English or remove it. Do this without asking.

Plain language in all files. Describe what the world does and what you changed. No governance register, no ratification voice, no paper-submission framing.

No new process infrastructure. Do not build orchestrators, evidence pipelines, verification frameworks, or run management systems. Time spent on those is time not spent making the world more interesting. If you need to run the world, run it. If you need to check something, look at the output.

Dead ends are fine. Remove them without ceremony.

The single question

After any session: Is the world more interesting to watch than it was before?

If yes — good.
If no — you built something for a different goal. Stop and build something visible instead.