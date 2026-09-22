# V3 — agent instructions

**ADOPTED 2026-09-19. These files are the active repository instructions. They
authorise only the scope recorded in the owner-direction register below; they do
not authorise implementation, runs, or acceptance beyond it.**

## Purpose and authority

Build a new engine in a separate repository for a small living world where
survival, experience, and relationships produce lasting consequences. Begin with
six people; design and benchmark for 50. Larger populations are a later objective.

Read three governing documents:

1. `AGENTS.md`: authority, scope, progression, and reporting.
2. [DOCTRINE.md](DOCTRINE.md): mandatory correctness and evidence principles.
3. [ROADMAP.md](ROADMAP.md): ordered objectives, deliverables, and exit conditions.

The roadmap cannot override doctrine. Evidence records implement these rules;
they cannot amend them. Explicit owner directions control changes to purpose,
scope, or the governing documents. Adopt the three files together in one commit.
Record later amendments in the dated owner-direction register below; amendment
commits cite the entry and retain the preceding version.

The old project is reference material only. Preserve its checkout, evidence, and
pins. Do not import its instruction hierarchy, target its trajectories, resume
its feature train, or copy domains without a current requirement and review.

## Session entry and working authority

Read the three governing files and the active stage record. Check the actual code
revision, outstanding findings, review status, and budget remaining. Briefly state
the active objective and next permitted action, then continue it. Do not infer a
pass from a stage name, a prior summary, or an implemented mechanism.

Stages 1–5 define the development scope. Work on one active stage and one concrete
objective. Routine design, implementation, focused tests, and declared exploration
within that scope need no repeated owner approval. Stage 6 requires a newly chosen
owner objective. No merge, publication, destructive operation, or alteration of
the reference project is implied by stage progression.

Use `evidence/stage-01/RECORD.md` through `evidence/stage-06/RECORD.md` for the
consolidated stage records. Track each record and its configuration from its first
commit. Link raw artifacts by immutable identity and accessible location; do not
silently ignore or discard evidence. Only create records for stages actually opened.

Create the short active-stage card when work starts. Complete its run-specific
definitions, limits, and criteria before any exploration, confirmation, or benchmark
run. Routine implementation and focused defect tests need no separate card or
approval. Append attempts and results beneath the card, preserving failed versions.

Adoption accepts the roadmap's proposed budget ceilings and coverage floors.
Agents declare exact values and allowed variations within that envelope before
use. Changing a candidate within the declared exploration levers consumes the same
budget. A confirmation attempt stays frozen through its recorded result. Changing
a counting predicate, required confirmation criterion, allowed levers, or budget
ceiling requires a recorded owner direction; it creates a new attempt, not a
retrospective pass or an automatic budget reset. Routine invariant repairs remain
authorised.

## Exit review

A stage advances only when its stated exit conditions are satisfied and a separate
reviewer using a different model has examined the evidence. Supply one packet:
stage record and original criteria; source/configuration identities; instrument
checks; raw evidence and reproduction commands; failed attempts; claimed conclusion.
Give the reviewer access to the pinned source and full supporting artifacts.

The reviewer runs the applicable reference test suite and independently reproduces
at least one central quantitative claim from the sealed evidence or a declared
rerun. Record reviewer/model identity, claims rerun versus read, discrepancies,
and a reasoned PASS, FAIL, or UNKNOWN verdict against each essential exit condition.
An inaccessible artifact or summary-only review cannot support PASS. Review work
uses reserved run capacity; it does not renew the budget.

If review is unavailable or inconclusive, mark progression pending. Evidence
packaging, focused tests, and defect repair within the active scope may continue;
next-stage implementation and runs may not. Do not substitute self-review or
presume a pass. The owner may supply the independent reviewer; an agent must not
invent one or silently waive the requirement.
Review does not replace tests or make a deficient measurement trustworthy.

Exhausted budgets or unresolved prerequisites stop the affected stage. Renaming
an attempt, changing versions, or moving it to another stage does not reset its
budget. Present the missing link and bounded alternatives to the owner.

Repair a later-found kernel defect within the active stage and budget. Mark affected
earlier claims invalid or pending revalidation, preserve the original results, and
rerun the relevant reference checks. Revalidate affected dependencies before using
them again; do not restart unaffected stages or preserve a bug behind a flag.
Expected-output changes require an explained, independently reviewed replacement,
with the old result retained. Invariant assertions are not weakened.

## Reporting

State what changed, what was measured, which checks passed, unresolved limitations,
review status, and rollback. Separate reported history from current measurements,
implementation from demonstrated behaviour, and demonstration from owner acceptance.

**Reproducibility alone does not establish correctness or causation.**

## Owner-direction register

This is the single location for dated direction entries: ID, exact owner direction,
affected scope or rule, reason, and linked revision. Evidence records cite entries
rather than creating another source of authority. A proposed entry is not an owner
decision.

### OD-001 - 2026-09-19 - Adoption and Stage 1a authorisation

**Exact owner direction.** Recorded from the owner's message of 2026-09-19:

> Build the first slice of my new V3 simulation engine.
>
> I adopt the three founding documents below for the new project. This task
> authorises repository setup and Stage 1a only. Stop after delivering that
> slice; do not treat this as authorisation to implement every stage.
>
> Create a separate repository at `C:\dev\03-Living-World-V3`. Verify the
> destination is outside any existing repository. If it already contains work,
> stop and report rather than overwrite or clean it.
>
> Copy the three documents into its root. In those copies, replace draft-status
> notices with adopted-status notices and record this direction, dated with the
> actual date, in AGENTS.md's owner-direction register. Preserve their
> substantive rules and limits. Leave the source drafts unchanged.
>
> Create the initial local commit containing the three governing documents
> together. Use branch `codex/kernel-first-slice`. Do not create a remote, push,
> merge, or publish.
>
> The purpose is a small living world where survival, experience, and
> relationships produce lasting consequences. Six people is the eventual starter
> world; 50 is the initial capacity target. Neither world belongs in this first
> slice.
>
> Implement Stage 1a: two authorised claimants competing for one resource unit,
> with atomic settlement and immutable observation.
>
> Use Python and a minimal test setup. Before implementation, create
> `evidence/stage-01/RECORD.md` using the roadmap's card. Declare the concrete
> units, numeric rules, ownership, proposal identities, ordering, and assertions.
> Make routine engineering choices without seeking repeated approval.
>
> Prove through focused tests:
>
> - Two valid claims against one unit produce exactly one winner, no negative
>   balance, and conserved total stock.
> - An invalid or unauthorised transaction cannot partially commit.
> - Insufficient stock rejects an indivisible transaction without partial credit.
> - Reordering input maps or proposal collection leaves results unchanged.
> - The declared rotation avoids a permanent winner across equivalent contention
>   at successive tick values.
> - The roadmap's A to B transfer/consume fixture respects next-tick availability
>   and prevents double spending.
> - Observers cannot mutate live or previously observed state.
> - Diagnostics on/off and repeated identical execution produce identical
>   canonical results.
>
> Build only what those checks require. Do not add reservations, multi-tick
> action machinery, a replay platform, needs, movement, memory, social
> behaviour, construction, a viewer, plugins, or a general scheduler. Those
> belong to later slices or stages.
>
> The existing project at `C:\dev\02-Simulation-Sandbox` is reference material
> only. Do not modify or clean it, its worktrees, dirty work, frozen files,
> identities, or evidence. Its historical instruction hierarchy does not govern
> this new project.
>
> Preserve failed tests and explain corrections. Do not weaken assertions or
> replace expected results to manufacture a pass.
>
> Finish by reporting the repository and revision, files and responsibilities,
> exact test commands and results, demonstrated guarantees, limitations, and an
> explicit rollback list. Record actual results in the stage evidence.
>
> Stop after Stage 1a. Stage 1 remains incomplete; do not claim its exit gate or
> independent review has passed.

**Affected scope or rule.** Adopts `AGENTS.md`, `DOCTRINE.md` and `ROADMAP.md`
together as the governing documents of this repository, opening the register and
the adopted status of all three. Opens Stage 1, slice 1a only, with the roadmap's
Stage 1 scope, tick algorithm, credit fixture and budget envelope in force.
Authorises repository setup, the Stage 1a kernel, and focused deterministic tests.
Withholds authorisation for slices 1b, 1c and 1d, for Stages 2 to 6, and for any
remote, push, merge or publication. Confirms the old project at
`C:\dev\02-Simulation-Sandbox` as reference material whose instruction
hierarchy does not govern this repository.

**Reason.** The owner chose a new implementation as the starting point for a
small living world in which survival, experience and relationships produce
lasting consequences, and chose to prove the contested transaction and
observation kernel before any world, person or behaviour exists.

**Linked revision.** The adoption commit is the first commit on branch
`codex/kernel-first-slice`, which contains these three documents together. Its
exact hash cannot appear inside itself and is recorded in
`evidence/stage-01/RECORD.md` under Identity.

### OD-002 - 2026-09-20 - Resolve the Stage 1a review findings

**Exact owner direction:** "resolve findings", following the adversarial review
of `fa8be6083b31ead3c7e6aae844c0fd749927e6d0` identifying R1–R5.

**Scope:** repair reentrant ticks, rejected-outcome ordering, mutation-result
classification, unbounded-integer serialization, and engine ownership of proposal
sequences. Preserve the original evidence and assertions, add regression proof,
and record the repair outcome. This is Stage 1a defect repair only; it changes no
stage gate, budget, world, contention priority, or authority for later slices.

**Reason:** the review reproduced correctness and instrument failures despite the
original passing suite. Its recorded findings remain historical evidence.

**Linked revision:** the repair is identified by the changed-file hashes and source
base in `evidence/stage-01/RECORD.md`; no acceptance or Stage 1 exit is implied.

### OD-003 - 2026-09-20 - Commit and publish the new V3 repository

**Exact owner direction:** "commit and push all eork", after identifying
`https://github.com/lochheadr92-creator/Simulation-3.git` as the new simulation
repository.

**Scope:** commit all current work in `C:/dev/03-Living-World-V3` and push the
existing `codex/kernel-first-slice` branch, including its preceding local history,
to that repository. This expressly supersedes OD-001's initial no-remote/no-push
restriction for this publication. It authorises no merge, force push, later slice,
new run, stage acceptance, or alteration of the old simulation project.

**Reason:** preserve and publish the new engine, repairs, governing documents and
complete evidence in the owner-created repository.

**Linked revision:** repair commit
`fb5a8959fb6a7a23d6e3107fe32be8248cc19901`; this entry is committed as
`docs(stage-1a): record publication authority (OD-003)`.

### OD-004 - 2026-09-20 - Freeze and commit Phase 1-3 automation

**Exact owner direction.** Recorded from the owner's message of 2026-09-20:

> Phase 4: audit, freeze, and commit the Phase 1–3 automation foundation
> without changing simulation behaviour or scientific acceptance state.
> Ensure generated automation-run evidence cannot contaminate the commit,
> run the complete verification stack from the final candidate tree, and
> report the exact commit contents and evidence. Do not begin Slice 1b and
> do not infer Stage 1a acceptance.

**Affected scope or rule.** Authorises committing the Phase 1–3 automation
tooling, its focused tests, `SIM3_STATE.md`, and ignore rules for generated
`evidence/automation-runs/` packages. Changes no Stage 1a scientific claim,
stage gate, budget, kernel behaviour, or authority for slice 1b or later
stages. Generated runner packages remain unaccepted local receipts.

**Reason.** Preserve a frozen, reviewable automation foundation without
treating a green suite or a packaged run as Stage 1a or Stage 1 acceptance.

**Linked revision.** The automation freeze commit on `codex/kernel-first-slice`.
Its exact hash cannot appear inside this entry and is reported after the
commit.

### OD-005 - 2026-09-20 - Verify and freeze orchestrator Phases 1-3

**Exact owner direction:**

> Finish verifying orchestrator Phases 1–3, fix any demonstrated defects,
> review the safety boundaries, and commit the result. Stop before
> implementing actual execution.

**Scope.** Verify and repair the read-only orchestrator, its focused tests,
and its verification record; commit the result. This does not authorise
orchestrator gate execution, Phase 4 implementation, scientific acceptance,
later slices, a merge, or publication.

**Reason.** Freeze the inspected and tested control plane before execution
capability. Newer uncommitted Phase 4 work found in the original checkout is
preserved there. This bounded freeze uses a separate worktree and branch,
`codex/orchestrator-phases-1-3-freeze`, based on `b915aa0`.

**Linked revision.** The commit containing this entry and
`evidence/stage-01/orchestrator-review/REVIEW.md`; its resulting identity is
reported on completion. This is tooling review, not the separate different-model
Stage 1a exit review, which remains pending.

### OD-006 - 2026-09-20 - Repair the reviewed Phase 4 orchestrator defects

**Exact owner direction:** "Fix issues", following the Phase 4 readiness review
that returned NEEDS FIXES and identified F1-F9.

**Scope.** Repair those tooling defects in an isolated checkout and run focused
tests with harmless commands in disposable repositories. This supersedes
OD-005's implementation restriction only for this bounded Phase 4 repair.
Preserve both original checkouts, local receipts and failed review evidence.
No real registered project gate, pilot, implementation commit, merge, push,
scientific acceptance or later engine slice is authorised by this sitting.

**Reason.** Restore the verified inspection boundaries and make execution
ownership, cleanup, identity, receipts and audit provenance testable.

**Linked work.** Branch codex/orchestrator-phase4-repair, based on
6591629029ac5cfedbb16279e2c62888894fb44b. The uncommitted candidate and focused
verification are identified in evidence/stage-01/orchestrator-phase4-repair/REVIEW.md.
Stage 1a independent acceptance remains pending; Slice 1b remains unauthorised.

### OD-007 - 2026-09-21 - Commit and publish the verified orchestrator

**Exact owner direction:** "Commit and push", following confirmation of the
completed Phase 4 repair 2, its 191 focused / 365 whole-tree tests and one
successful controlled fixture pilot.

**Scope.** Commit and publish the verified automation snapshot and its bounded
publication record to Simulation-3 on codex/kernel-first-slice. This supersedes
the earlier no-commit/no-push restrictions for this publication only. Preserve
existing checkouts, local receipts and failed evidence. No new project gate,
merge, force push, scientific acceptance or later slice is authorised.

**Linked work.** evidence/stage-01/orchestrator-publication/RECORD.md identifies
the source, retained tests, local pilot and publication method. The published
commit incorporates previously unpublished automation based on local revisions
b915aa0 and 6591629 as one snapshot atop the existing GitHub branch. Those local
source revisions and their checkouts remain preserved.
### OD-008 - 2026-09-21 - Resume simulation development at Stage 1b

**Exact owner direction:** "stage 1b", immediately after directing that
orchestrator work stop because it had drifted away from the simulation.

**Scope.** Implement and test Stage 1, slice 1b: reserve stock, then complete or
cancel and release, with exactly-once settlement. Record the declarations and
results in evidence/stage-01/RECORD.md. This supersedes the earlier slice-1b
restriction for this bounded simulation work. Preserve the existing tooling,
uncommitted files and historical evidence; do not resume orchestrator work.
No Stage 1c, capacity/world runs, scientific acceptance, commit or publication
is implied. Stage 1's independent exit review remains pending.

**Reason.** Return to the simulation's next kernel slice. The roadmap defines
1a–1d as internal slices with one Stage 1 exit, not separate stage exit gates.
The earlier publication direction is OD-007 in published revision 810ab25;
this checkout's existing automation work is deliberately left untouched.

**Linked work.** The dated Stage 1b card and evidence/stage-01/slice-1b/ identify
the source, tests and rollback. Local source base: b915aa0.

### OD-009 - 2026-09-21 - Checkpoint cadence: visible world before acceptance machinery

**Exact owner direction:** "Prove the engine can create a varied, repeated,
readable living world before building acceptance machinery. Work in declared
exploration: determinism and reproducibility stay; frozen baselines,
provenance packages and adversarial acceptance return only when something is
worth preserving. Backend work never gets more than two legs ahead of
something I can see and inspect." Recorded from the owner's messages of
2026-09-21 ("ok", "can u implement") accepting the drafted direction.

**Scope.** Amends the Stage 1 slice plan and Stage 2 entry, nothing in
DOCTRINE.md.
1. Slice 1b is committed first, after resolving the evidence-verifier
   manifest mismatch and removing the stale untracked orchestrator files.
2. Slice 1c is re-scoped to a record stream: tick records written to an
   append-only file per run, plus a plain text or HTML viewer that renders
   from that file, never from live state. Sealing, replay and recovery are
   deferred. This is checkpoint 1.
3. Slice 1d (capacity envelope) is deferred; a per-tick timing line stays in
   the run output so drift is visible.
4. Stage 2 opens after checkpoint 1 in this order: position and movement, one
   renewable food source, hunger (checkpoint 2, a map over time); then
   perception radius and bounded views (checkpoint 3). The Stage 2
   opportunity-counting instrument and confirmation floors are not opened by
   this direction.
5. Every leg keeps: seeded run-twice-same-digest, the existing rails and
   reference tests, one record file per run. No frozen hashes, no evidence
   contracts, no independent acceptance until the owner names a result worth
   ratifying.
6. No orchestrator work. The Phase 4 repair branches remain parked.

**Reason.** Five tooling sittings advanced the kernel by zero slices; 1a and
1b are reviewed and correct, and the next risk is building a world nobody can
look at. Readable records are the one piece of 1c the checkpoints depend on,
so they stay; the rest of 1c and 1d cost more than they prove right now.
Checkpoint output is exploration, not evidence: anything worth keeping is
re-run under the ratification rules before it is cited as a result.

**Linked revision.** Slice 1b landed in `9d1542d` on `codex/kernel-first-slice`
after `1858e96`; checkpoint legs are recorded beneath the Stage 1 and Stage 2
cards as they run.

**Supersession.** Remaining sequencing under this entry is superseded by
OD-009 Revision 3 below. Work already delivered under this entry (slice 1b,
checkpoints 1–3) stands.

### OD-009 Revision 3 - 2026-09-21 - Exploration lane

**Exact owner direction.** Recorded from the owner's message of 2026-09-21:

> OD-009 — 2026-09-21 — Revision 3: exploration lane
>
> Objective
> Prove the engine can produce a varied, repeated, readable living world
> before any scientific acceptance machinery is built.
>
> Lane definition
> This direction opens the exploration lane on Living World V3.
> Kept in the exploration lane: determinism, reproducibility, replay equality
> within a run, tests, one active leg at a time, declared stop conditions.
> Deferred to the ratification lane: frozen baseline hashes, provenance
> packages, adversarial acceptance reviews, Stage exit claims.
> Nothing built in the exploration lane may claim a Stage exit.
>
> Cadence
> Foundation leg, behaviour leg, visual checkpoint, further behaviour,
> visual checkpoint.
> The backend must not advance more than two legs ahead of something
> visible or inspectable. A leg that would breach this waits until a
> checkpoint lands.
>
> Leg order
> 1. Close slice 1b (manifest regeneration against the 1b kernel, stale
>    orchestrator files removed, commit).
> 2. Canonical agents and entities, world presence.
> 3. Position and locality. Visual checkpoint A: people exist and occupy
>    space over a run.
> 4. Perception. Decision time observations, native, inert by construction.
> 5. Inter agent and population state. Visual checkpoint B: people notice
>    each other, differentiated by declared trait.
> 6. Contested scoring. Ties resolve by the adopted rotation rule
>    (tick mod actor_count). Visual checkpoint C: a contested choice
>    resolves deterministically and readably.
> 7. Slices 1c and 1d and the Stage 1 exit gate, under the ratification
>    lane.
>
> Leg opening
> Each leg from 2 onward is opened by its own owner direction. Before
> code, the leg declares: behaviour targeted, canonical state it changes,
> what becomes visible afterward, control or ON/OFF comparison, tests,
> stop condition.
>
> Standing constraints
> DOCTRINE.md is unchanged by this direction.
> Stage 3 re entry is parked. Stage 4 is blocked.
> No orchestrator or pilot tooling work under this direction.
> Halt and report on drift toward infrastructure first, test first,
> abstraction first, or diagnostic only work.
>
> Relationship to prior directions
> OD-001 through OD-008 stand. Where ROADMAP.md stage sequencing conflicts
> with the leg order above, this direction governs until it is closed.
>
> Closure
> This direction closes when the owner accepts visual checkpoint C or
> withdraws the direction. Closure returns sequencing authority to
> ROADMAP.md.

**Affected scope or rule.** Opens the exploration lane and replaces remaining
sequencing from the original OD-009 with the leg order above. Does not open
legs 2–6 for implementation; each still needs its own owner direction and a
pre-code declaration. Parks Stage 3 re-entry and blocks Stage 4. Moves slices
1c and 1d and the Stage 1 exit gate to the ratification lane (leg 7). Does
not amend DOCTRINE.md. Does not undo work already delivered under the original
OD-009. No orchestrator or pilot tooling. No Stage exit may be claimed from
exploration-lane work.

**Reason.** Keep proving a readable living world, with a stricter cadence
(visible checkpoints A–C, one opened leg at a time) and a hard split between
exploration and ratification, before any scientific acceptance machinery.

**Linked revision.** Recorded on `codex/kernel-first-slice` after checkpoint 3
(`9d354414`). The amendment commit's hash cannot appear inside this entry and
is reported after the commit.

### OD-010 - 2026-09-21 - Open exploration leg 5: inter-agent state, visual checkpoint B

**Exact owner direction.** Recorded from the owner's message of 2026-09-21
("ok") accepting the drafted declaration below in full.

**Behaviour targeted.** A hungry person walking to the source who can see it
crowded holds back instead of stepping on, unless in emergency. Whether they
hold back depends on a trait, so people with the same view act differently.
No social action: nobody requests, gives, follows or avoids a particular
person. The trait is a model assumption (DOCTRINE 8), declared and recorded,
not a finding.

**Canonical state it changes.** The overlay gains one immutable per-person
trait assigned at genesis: `yield_at`, an integer drawn by the seeded genesis
generator from a declared set (default {1, 2, 3}), written to the run header.
Nothing else in canonical state changes. The kernel is untouched. No new
stored population state: crowd counts are derived from positions already
recorded.

**Rule (exact).** At tick start, a person who is hungry, not in emergency,
not on the source, and who can see the source cell, counts the living people
standing on it. If that count is >= their `yield_at` and the observed source
stock is < that count, the person's decision is `yield`: stay where they are
this tick. Otherwise the existing rule applies unchanged. Emergency (hunger
>= emergency_at) never yields. Hunger keeps rising while yielding (DOCTRINE
1). Dead people are not counted and, as already implemented, not seen; that
becomes a declared line in the config description.

**What becomes visible (checkpoint B).** On the map: people holding position
at the rim of the source with their trait shown; a `yield` decision with its
reason (for example "saw 3 on source, stock 2, yield_at 2"). Over time: crowd
on the source cell per tick, yield events, and deaths and emergency
person-ticks broken down by trait value.

**Control.** `--yield off` sets every `yield_at` beyond the actor count so no
one ever yields; that run must match `9d354414` decisions byte-for-byte
(extending the existing fixture test). The checkpoint reports seed 7 and two
more seeds ON and OFF side by side: survivors, deaths, emergency
person-ticks, denied claims. This is a picture of a difference, not a claim
about it.

**Tests.** OFF byte-identity against the HEAD fixture; yield occurs only when
the recorded observation satisfies the rule, checked from the run file;
emergency never yields; trait assignment is seeded, identity-neutral, from
the declared set, and present in the header; determinism; tamper on the trait
block fails verification; ownership unchanged (kernel imports nothing from
world).

**Stop condition.** The leg closes when checkpoint B renders from the run
file and the seed-7 ON run contains at least one yield event with its ON/OFF
comparison recorded in evidence/stage-01/RECORD.md. It halts and reports if
implementing it would need a social action, a retained fact or observation
age, or any kernel change.

**Held constant.** The claim-then-eat latency rule (two deaths at the source
holding food, checkpoint 2) stays as it is for this leg so the ON/OFF
comparison is not confounded; it is a separate owner decision after
checkpoint B.

**Standing.** Exploration lane only under OD-009 Revision 3; no ratification,
no Stage exit; one active leg. Local commit, no push. Alternatives set aside
at drafting: a trait that does not use perception (speed, appetite)
differentiates people but does not make them notice each other; moving
toward a seen food-holder makes them notice each other but is a request-food
precursor, which is Stage 3 and parked.

**Reason.** Leg 5 is the next undelivered item in the Revision 3 order and
requires an owner direction with a pre-code declaration. Crowd-yielding uses
the perception delivered at checkpoint 3 without opening a social action, a
memory, or a kernel change.

**Linked revision.** Recorded on `codex/kernel-first-slice` after
`aef393fd`. The recording commit's hash cannot appear inside this entry.

### OD-011 - 2026-09-21 - Open exploration leg 6: scored actions, checkpoint C

**Exact owner direction.** "next stage", followed by "your best decision"
when asked whether to score a person's actions or competing food claimants.
This opens the next exploration leg, not a roadmap Stage exit. The concrete
choice and modelling declarations below are the agent's implementation design
under that delegation, not a quotation or independent owner acceptance.

**Behaviour targeted.** Score existing eligible actions using the person's
tick-start observation. When yielding is eligible, increasing hunger can
outweigh crowd pressure before emergency. Food allocation still uses the
existing kernel rotation; action scores confer no priority over other people.

**Pre-code declaration.** In opt-in `--scoring on`, compare integer pairs
`(tier, pressure)` lexicographically, greatest first: EAT `(2,0)`;
CLAIM/WAIT `(1,0)`; GO `(0,2*(hunger-hungry_at)+1)`;
YIELD `(0,2*(seen_crowd-yield_at+1))`; HOME/REST `(0,0)`.
Eligibility is unchanged, including emergency exclusion of YIELD. EAT always
wins when eligible. GO/YIELD pressures have opposite parity, so these
competing actions cannot tie; CLAIM/WAIT and HOME/REST are mutually exclusive.
No new action tie policy is needed. Equivalent food claims continue to resolve
by the sorted tick-start kernel roster rotated by `tick mod actor_count`,
including ledger actors who have died; dead people make no decisions or claims.
Do not substitute claimant-count or living-count rotation. These scores are
authored assumptions, not findings or a new allocation policy.

**Canonical state.** No new retained state, trait or kernel schema. Changed
choices may change ordinary positions, hunger, food and deaths. Scored decisions
record their actual eligible score pairs at selection time in the existing
decision block. `process.py` and the kernel are unchanged. The header declares
the scoring mode and formula. Default/OFF retains the leg-5 decisions exactly.

**Visible checkpoint.** Show each eligible action's native score and selected
action; show the kernel's recorded rotation, claim requests, accepted/denied
outcomes and effects. Provide a jump to a contested claim and a scored
GO-versus-YIELD choice. Render HTML and text from saved run files only.

**Control and budget.** Fixed leg-5 seed-7 world, 300 ticks, yield ON: scoring
ON twice and OFF once, at most three whole-world executions for this leg.
No tuning, seed search, horizon extension or capacity runs. OFF decisions and
physical trajectory must match the existing leg-5 run. Keep prior artifacts.
Focused tests are not whole-world exploration slots; no stage budget is reset.

**Tests and stop.** Existing reference suite unchanged; focused checks for
score crossover, EAT/emergency safety, observation bounds, input-order
independence, native score tampering, unchanged atomic settlement, and exact
rotation including inactive actors. Stop when the saved seed-7 ON file shows
a GO/YIELD scored choice, contains contested food claims resolved by recorded
rotation, renders checkpoint C, and the fixed comparison/determinism result
is recorded. A missing demonstration is reported, not tuned into a pass.

**Standing.** Local only, exploration only. Claim-then-eat latency and world
levers stay fixed. No social action, memory, orchestrator, ratification or
Stage exit. Checkpoint C acceptance remains the owner's; leg 7 is not opened.
Base revision: `768a454951bb2ec82ceb224a9065ecb785b31516`.

#### OD-011 revised implementation direction — 2026-09-22, before code

The owner's detailed leg-6 instruction revises the declaration above. The
preceding declaration remains history; its local-only standing is superseded
only by the conditional push authority below. The formula remains the previous
agent's delegated design, not a verbatim owner specification or accepted finding.

**Scale and crossover.** One additional hunger point and one additional observed
person each add two pressure units. This equal weighting is a modelling
assumption, not an empirically established scale. For simultaneously eligible
GO and YIELD, GO wins exactly when
`hunger >= hungry_at + seen_crowd - yield_at + 1`; at `hungry_at = 5`,
`hunger >= seen_crowd - yield_at + 6`. Record both forms in the run header and
stage record. Test immediately below and at the boundary, and directly assert
GO odd, YIELD even and never equal across the eligible domain. This establishes
a possible crossover, not occurrence in the fixed run, better survival or fewer
whole-run yields. A yield episode can shorten under fixed conditions; trajectory
feedback may change total yields in either direction.

**Preserved boundaries.** Scores use only bounded tick-start observations and
declared configuration. The one live selector records actual eligible pairs in
the existing decision block. Default/OFF keeps exact leg-5 decision shape and
values. Personal scores never rank food claims. The unchanged kernel rotates
the sorted full tick-start roster, including inactive ledger actors, by
`tick mod actor_count`. Observation rules, overlay, process.py, claim-then-eat
latency and every world lever remain unchanged. No retained population state,
memory, social action or new trait. Viewer HTML and text read saved native
scores, decisions, rotation, requests and settlement effects without rescoring.

**Fixed comparison and stop.** Three whole-world executions maximum: seed 7,
300 ticks, yield ON, scoring ON, identical ON repetition, then scoring OFF.
Declare commands/configuration/remaining budget before execution; fresh names,
all attempts retained, no tuning, extra seeds, horizon extension or capacity
runs. Compare OFF decisions and physical trajectory to saved leg 5, repeated ON
canonical content excluding timing, and ON/OFF survivors, identified/timed deaths,
denied claims, tick-start emergency person-ticks and yields. Report native
GO/YIELD scores and consequences and explicitly whether GO actually wins while
YIELD is eligible. Timings stand separately; changed digests are not behavioural
evidence. Missing demonstrations must be reported without another run or a
completion claim. Keep old reference assertions; focused fixtures are distinct
from whole-world exploration executions.

**Revised commit/push authority.** Commit on `codex/kernel-first-slice` and push
only to the existing verified private origin. Verify both destination and private
visibility before pushing. No remote creation, visibility change, merge or public
release. If privacy cannot be verified, keep the local commit and report the
blocker. This supersedes earlier no-push directions for this bounded work only.

**Immediate next decision after C.** Present the recorded consequences of
claim-then-eat latency and a bounded owner decision before ratification. Do not
silently defer it into another behaviour leg or alter it during leg 6. C remains
exploration output, not owner acceptance. No leg 7, orchestrator, social/memory
work, ratification or Stage exit is opened.

### OD-012 - 2026-09-22 - Presentation track: world view, isometric smooth playback

**Exact owner direction.** "Checkpoint C is much more technical than I wanted
to look at. I want a 2.5D view of the world, much more polished than the
previous sim's viewer, and it has to run smoothly, not jump tick to tick."
Recorded from the owner's messages of 2026-09-22 accepting the drafted entry
and brief ("you implement").

**Amendment to OD-009.** "Readable living world" in OD-009 and Revision 3
means two things from this entry on: instrument views (records, scores,
rotation, settlement, as delivered at checkpoints A to C) and a world view a
person can watch tick by tick. Checkpoints A to C stand as delivered on their
declared instrument content. This entry neither accepts nor rejects
checkpoint C; that remains a separate owner ruling, as does the claim-then-eat
latency decision named in OD-011. Acceptance of any future checkpoint may
cite the world view for readability; it may never cite the world view for a
behavioural or accounting claim.

**Scope.** Opens a presentation track alongside the exploration lane. It is
not a leg, has no behavioural objective, and does not touch the exploration
or ratification lanes' sequencing; leg 7 is not opened by it. It lives in a
new top-level `viewer/` package. It proceeds on `codex/kernel-first-slice` in
file-disjoint commits; no branch is created for it. For this track only, it
amends ROADMAP.md's Stage 1 "no graphical viewer" and Stage 2 "observation is
a text display of sealed native records, not a product" lines: the world view
is a way to look, and the instrument views remain the record of observation.

**Rules.**
1. Reads saved run files only. Never live state, never a running engine.
2. Imports nothing from `kernel/`, `world/` or `stream/` (`stream/` imports
   the kernel). The dependency-direction check is extended to assert this.
3. One self-contained HTML file per rendered run, generated by a small Python
   script that inlines the run data, following the existing `world/viewer.py`
   pattern. No framework, no build step, no package install, no external
   resources.
4. Interpolation is presentation. Positions and colours may be tweened
   between recorded ticks for smooth playback; nothing derived from an
   interpolated value is written, exported, counted, or shown in any
   instrument view. Events (claim, eat, yield, denial, death) snap to their
   recorded tick boundary. There are no half-tick states. When paused,
   stepped, or landed by the scrubber, the frame shows exactly the recorded
   tick state with no interpolation; the inspect panel shows recorded values
   and recorded band labels only, never a colour or a fraction.
5. Not an acceptance instrument. Behavioural and accounting claims cite
   records and instrument views only. The world view does not verify a run
   file's digests; that is the reader's job (`stream.run_file.read_run`).

**Definitions.** Tick index `t` in the page is the recorded state after `t`
ticks (`t = 0` is genesis, `t = n` is the final state). During playback from
`t` toward `t + 1` the counter shows `t`, positions and hunger colour tween
from state `t` to state `t + 1`, and the decision, claims and settlement shown
are those of tick `t` (the ones that produce state `t + 1`). A person whose
recorded `died_at` is `k` moves during the interval ending at `k`, stops at
the `k` boundary, and their death marker begins there and fades over the next
three ticks.

**First deliverable (v1).** An isometric (2:1 diamond tile) canvas render of
the grid: cells, the source with its stock, shelters, and people as simple
sprites; hunger band as colour (fed, hungry, emergency) using the run's
declared thresholds; trait shown on the sprite; a hollow ring while yielding;
a death marker that fades over three ticks; crowd count on the source cell.
Playback: play, pause, speed from 1 to 20 ticks per second, scrubber that
lands on integer ticks, single step forward and back, tick counter.
Smoothness: requestAnimationFrame, each person tweened between the recorded
cell at tick `t` and tick `t + 1` across the playback interval with an ease,
camera pan and zoom, fit-to-grid. Inspect: click a person for their recorded
decision line, hunger, stock and trait at the current tick; click the source
for stock and this tick's accepted and denied claims. A legend and a footer
line stating that motion between ticks is interpolated presentation. Must
play the 300-tick seed-7 files without visible jank and must be built so that
50 people over 2,000 ticks would still play at full frame rate.

**Deferred polish.** Sprite animation frames, terrain art, lighting, weather,
sound, paths and trails, night and day. These are reopened by owner direction
once a Stage 2 world is viable, so polish is spent on a world people live in.

**Budget.** No new whole-world executions; render the existing leg-6 seed-7
ON and OFF files (`runs/leg6-20260922-seed7-300-on.jsonl`,
`runs/leg6-20260922-seed7-300-off.jsonl`). One sitting. Existing stage
budgets unchanged. A synthetic 50-person, 2,000-tick fixture written by the
test suite in the run-file shape is a test input, not a world execution, and
is never saved under `runs/` or cited as a run.

**Tests.** Embedded run data digest equals the source file digest; the
generated HTML references no external resource; dependency-direction check
passes with `viewer/` included; JavaScript syntax check; the generator
refuses a run file whose header it does not recognise rather than guessing;
the synthetic 50 x 2,000 fixture renders and the page stays under a declared
size bound; the per-frame interpolation step is timed headlessly on that
fixture. Layout and motion are inspected by the owner; the report lists that
as unverified by the agent if the browser tool cannot open local files.

**Stop.** v1 renders both seed-7 files, plays smoothly at 10 ticks per second
on the owner's machine, and the report is delivered. Anything beyond v1
waits for a further direction.

**Standing.** Does not block leg 7. Does not amend DOCTRINE.md. Commit and
push under the revised push authority (OD-011) once the origin's visibility
is settled; until then, local commit and report.

**Reason.** The exploration lane's purpose is a world the owner can see.
Checkpoints A to C delivered records the reviewer can read; the owner needs
the picture as well, and the 02 line showed that watching the world is what
drives good direction. The rules keep the viewer from becoming what the
previous frontend became.

**Linked revision.** Recorded on `codex/kernel-first-slice` after
`94523ae06957a549ffd2b98aacb3b12120f6b0f3`. The recording commit's hash
cannot appear inside this entry and is reported after the commit.

### OD-013 - 2026-09-23 - Retain claim-then-eat latency; open the ratification lane

**Exact owner direction.** "Keep claim and eat as separate actions. Do not
authorise a same-tick obtain/eat revision. Proceed to ratification."
Recorded from the owner's acceptance of the drafted entry on 2026-09-23
("yes"), following the decision named in OD-011 and restated in SIM3_STATE.md.

**Scope.** Claim-then-eat latency is retained as built: an obtain settles
within its tick and consumption is possible no earlier than the next tick
start, per the slice 1a availability boundary and slice 1b's exactly-once
reservation semantics. No kernel or world change is authorised by this
entry. The ratification lane is opened: slice 1c (sealed evidence stream and
replay), then slice 1d (50-actor cost envelope), then a Stage 1 exit review
requested from an independent reviewer. This entry does not accept
checkpoint C, does not authorise exploration leg 7, does not reopen parked
work, and does not claim the Stage 1 exit gate.

**Reason.** The leg-6 hypothesis was validated under the existing latency;
a same-tick revision would supersede the checkpoint comparisons and require
new comparison authority without a demonstrated benefit. Hunger pressure
already discriminates GO from eligible YIELD before emergency under the
current rules. Ratification is the cheapest path to an independently
reviewed Stage 1, and the decision was the only blocker the state file
recorded for that lane.

**Linked work.** SIM3_STATE.md records 1c as the active ratification slice;
ratification cards for 1c and 1d are opened in evidence/stage-01/RECORD.md;
the Stage 1 exit review is requested only once the 1c and 1d records are
complete. Recorded on `codex/kernel-first-slice`; the recording commit's
hash is reported after the commit.
