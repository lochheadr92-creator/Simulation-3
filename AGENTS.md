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

