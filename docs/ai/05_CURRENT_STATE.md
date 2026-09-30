# Current state — volatile snapshot

## Stone and the stone axe — 2026-09-30

Second slice on `codex/wood-yard-stone-axe`. `--stone on` / `--axe on`
(`--preset crafting` = wood + yard + stone + axe). One finite outcrop; an axe
is an overlay possession (`axes`) paid with 1 wood + 1 stone through staged
consumes over 3 craft ticks (`axe_work`), planned only after a recorded wood
delivery (`deliveries`) with demand still in sight; holders claim 5 wood
instead of 3. Details and the exploration table in WORLD_DIRECTIONS.

## Shared wood yards — 2026-09-30

On `codex/wood-yard-stone-axe`, branched from `codex/kernel-first-slice` at
`e34decc` (the shared-caregiving work below is committed there as
`e34decc`, superseding the "uncommitted" notes that follow). `--yard on` /
`--preset crafting` adds yards built where a shelter is seen short of wood,
supply tasks that fetch one pack to a yard, and withdrawals by shelter
builders. New overlay fields `yards`, `yard_work`, `supply_tasks`; new decision
fields `yard_site`, `supply`, `supply_end`; `source_created` production entries
may carry `resource`. Full suite **1,127 passed**; off-mode baselines from
`e34decc` match except seals/code identity. Details in WORLD_DIRECTIONS.

## Shared caregiving — 2026-09-30

Checked on `codex/kernel-first-slice`, HEAD `fe940ef`, with prior local work
preserved. The user authorized the next shared-caregiving slice with "Begin".
Optional `--shared-care on` records both birth parents and gives both the
existing local caregiving role and dependent-child relocation responsibility.
Saved family links, replay/recovery and the current viewer support the added
relationship; old saves retain only the parents they actually recorded.

Seed 11 now shows p06 feeding p08 while p03 travels for food, followed by the
child's meal. Three matched seeds show more child handoffs with mixed population
outcomes; no general survival benefit is established. Fresh full suite:
**1,105 passed**; six ordinary comparison runs verify/replay, recovery matches
around birth and delivery, and browser playback passed without errors.
Implementation remains uncommitted. Detailed verification and paths are in WORLD_DIRECTIONS and the
current slice; the repair's supplied independent PASS applies only to `fe940ef`.

## Household response and review closure — 2026-09-30

Checked on `codex/kernel-first-slice` at `fe940ef` plus local changes.
The supplied [reassessment](../reviews/2026-09-29-repair/README.md) clears
the repair blockers with PASS within its stated scope. Its 901-test result
is attributed to that independent execution. The reassessment files were
untracked at the start of this work and are preserved unchanged.

Current local work validates all boolean settings and malformed `yield_set`
collections. With coordination enabled, a listener who sees their speaker's
death at the just-completed boundary stops expecting food on their next
decision. The existing needs and provisioning rules choose what happens next.
See [current slice](06_CURRENT_SLICE.md) and the latest WORLD_DIRECTIONS entry
for verification and compatibility. Older snapshots below retain their dates.

## Review repair — 2026-09-29

The independent report on `81c10b7` is now supplied and signed FAIL,
with F1/F2 blocking acceptance as presented. The subsequent
[builder response](../reviews/2026-09-29-repair/RESPONSE.md) records the
viewer escaping repair, strict integer validation and wider timing-only
social-memory comparison. At 780 ticks the fixed 35-seed sample activates
memory in three current worlds and four old-estimate worlds; neither
activates by 400. The original FAIL remains historical; the later scoped
reassessment above clears its blockers for `fe940ef`.
See the response for fresh validation; historical counts below are
attributed to their original runs and are not current certification.

## Source snapshot

- Source branch: `codex/kernel-first-slice`
- Source HEAD: `eda72d290bdb33aaaf620ad136149c6ef04e0a96`
- Constructed: 2026-09-28 from local source inspection and recorded documentation.
- Currency: snapshot only; not automatically current after this revision. Recheck relevant source and Git state before acting.
- Authority: [AGENTS.md](../../AGENTS.md) wins over this pack; [WORLD_DIRECTIONS.md](../../WORLD_DIRECTIONS.md) supplies current development direction.
- Evidence source: local Git inspection; current source; WORLD_DIRECTIONS.md recorded results.
- Refresh trigger: after committed/accepted development work; recheck Git at task start.

**STALE AS SOON AS RELEVANT WORK CHANGES. This is the source-revision snapshot, not a live status feed. Refresh after committed/accepted development work and recheck Git before acting.**

## Publication update — 2026-09-28

The implementation described below was committed as `81c10b7d25cc2e0f1b8de33bf547083eb0972c64` and pushed to `origin/codex/kernel-first-slice`; the remote branch was checked against that exact SHA. This supersedes the uncommitted/unpushed statements in the preserved implementation snapshots below. The recorded 729-test result was not rerun for this documentation update.

A [whole-project adversarial review packet](../reviews/2026-09-28-whole-project/README.md) pins that source and supplies an unsigned report. Preparing the packet is not independent review or user acceptance.

## Current local sharing work — 2026-09-28

Checked at `22ffe2748dc4c5ee14c71295ff33810c7f456a7c` plus the uncommitted
terrain-planning and knowledge-sharing changes. This section supersedes the
active-work and failure-status statements below; older source metadata stays
historical. Full suite: **729 passed**. The user chose to retain terrain-aware
departure and replace the two exact-scene assumptions with causal social-memory
coverage. Those original seeds still receive full-horizon replay checks.

Optional `--knowledge-sharing on` requires `--source-memory on`. Firsthand
empty-source reports pass only to adjacent visible housemates, affect later
food/provisioning choices, retain provenance and expire from the sighting date.
Reports cannot be relayed. Own newer/current sight wins. Two sparse overlay
fields preserve firsthand sightings and reports through births and recovery.

Six matched saved worlds verify/replay; seed 11's report-driven choice and
inspector were watched in the browser. See [current slice](06_CURRENT_SLICE.md)
and the newest [development account](../../WORLD_DIRECTIONS.md) for scope,
counts, artifacts and compatibility limits. Changes remain uncommitted and
unpushed. No independent review or user visual acceptance is claimed.

## Current local travel-planning work — 2026-09-28

Checked against `22ffe2748dc4c5ee14c71295ff33810c7f456a7c` plus the current local
travel-planning edits. This section supersedes the older active-work and
departure-estimate statements below; their source metadata remains historical.

Personal food departure timing now uses the existing route search over seen
and personally remembered rough ground, including any current movement delay,
when planned trips, terrain and routing are enabled. Unknown ground is still
open in the estimate. No new persistent state or knowledge transfer was added.
Nominal hunger rate, fishing casting cost, source selection and other needs'
planning keep their existing rules. This is planning from remembered sightings,
not learning elapsed journey durations.

Fresh verification: **70 focused tests passed; full suite 713 passed, 2 failed**.
The two unchanged fixed-scene social-memory tests pass at baseline HEAD but
diverge after the intentionally earlier departures. They remain unresolved,
not skipped or repinned. New tests establish the repeat-trip/control difference,
personal observation boundary, delay/cast handling, replay, recovery and viewer
text. Two saved worlds verify and replay, and the repeat-trip scene was inspected
in the browser. See [current slice](06_CURRENT_SLICE.md) and the latest account
in [WORLD_DIRECTIONS](../../WORLD_DIRECTIONS.md) for precise scope and failures.

All implementation, test and documentation changes are uncommitted and unpushed.
No independent review was performed. Old headers combining planned trips,
terrain and routing no longer reconstruct under the changed decision rule;
readability is preserved, exact-rule/replay and code-identity checks are intact.

## Fishing timing update — 2026-09-28

This focused update was checked against `12e34c98e794175b92640d48dc7f2caac578f828` plus the reviewed fishing-timing working-tree change. The source-snapshot metadata and repository/publication observations below describe the earlier pack baseline; they are not refreshed publication claims.

Personal food trips with fishing and planned trips enabled now include one casting tick in departure timing. An empty-handed person at the selected, visibly stocked bank may cast before hungry when hunger plus one nominal hunger increment reaches the threshold. Personal claiming and later eating retain their hunger requirements. Source selection, provisioning rules, accounting and renewal are unchanged. See [decision code](../../world/decide.py) and [focused tests](../../tests/test_fishing.py).

The saved rule description changes for this switch combination. Old fishing-plus-planned-trips headers are therefore rejected by exact configuration reconstruction, replay and recovery; this follows the existing contract in [WorldConfig.from_describe](../../world/config.py), [replay tests](../../tests/test_replay.py) and [testing guidance](08_TESTING_AND_PROOFS.md). The other three fishing/planning switch combinations retain their descriptions. Recovery separately requires matching code identity. No validation check was relaxed, and old files remain historical records rather than runs to continue under changed rules.

The implementation passed the full 691-test suite. Final compatibility checks passed 93 fishing/replay/recovery/damaged-suffix tests and verified all four switch combinations using valid sealed synthetic fixtures with the previous descriptions. These fixtures isolate rule compatibility from code identity; they are not historical run reproductions. The earlier seed-23 viewer check showed early casting followed by a separate catch and meal. At that revision, departure remained a Manhattan-distance and nominal-rate estimate, without predicting terrain delays, shelter effects, competition or interruptions.

## Repository and publication

Repository: `C:\dev\03-Living-World-V3`. Branch: `codex/kernel-first-slice`. HEAD is the source hash above, commit “feat: add fishing, source memory and coordinated home provisioning.”

The working tree was clean during reconnaissance and immediately before pack creation: no tracked modifications, staged changes or non-ignored untracked files. HEAD matched the locally stored `origin/codex/kernel-first-slice` reference, with zero commits ahead and zero behind. No committed local-only work was found relative to that reference.

Live remote publication status is **UNKNOWN**. `git ls-remote` failed with `SEC_E_NO_CREDENTIALS`; GitHub synchronization was not independently confirmed. This pack is newly authored documentation after that baseline. Creation does not imply staging, commitment or publication.

## Latest functionality

The current product is the civilisation aquarium described in AGENTS.md. Recent committed work includes family/caregiving changes, social memory, patch ecology and seasons, shared stores, adult housing and relocation, wood construction, fishing, empty-source memory, household provisioning and coordination.

Coordination is the latest top-level feature report: a departing provisioner tells visible housemates; listeners temporarily postpone optional cache trips while retaining their own needs and helping priorities. Announcements can expire without delivery. Most recent extensions are optional; see [architecture](01_ARCHITECTURE.md) and [system map](03_SYSTEM_MAP.md) before selecting a configuration.

## Verification status

**RECORDED TEST RESULT:** WORLD_DIRECTIONS reports 677 passing tests for the coordination work. It also reports six 480-tick comparison files verifying/replaying identically, repeated seed-23 tick records/seals, and browser inspection of the seed-23 example.

**FRESHLY EXECUTED TEST RESULT:** none during reconnaissance or this documentation task. Source/test inspection and documentation checks are not a new simulation-suite PASS.

Referenced coordination JSONL and HTML artifacts existed locally under `runs/coordination/final/`. That directory is ignored by Git and is not guaranteed in a clean clone. Their presence was checked; no fresh replay or browser acceptance is claimed.

## Limits and active work

**NO ACTIVE SLICE ESTABLISHED FROM REPOSITORY EVIDENCE.** The latest feature report is not an active-slice declaration. [Current slice](06_CURRENT_SLICE.md) preserves that boundary; no next authorized implementation or current milestone was established.

General survival benefit from coordination/source memory is not established by the mixed example results. Scoring cannot be combined with water, warmth or requests. The older viewer has narrower compatibility. Earlier childhood/memory measurements carry correction notices, and historical benchmarks do not establish current all-feature performance.

No current implementation blocker was established by this inspection; that is not a claim that none exists. The known verification limitation is live-origin access. Root ROADMAP stage language is historical under AGENTS.md; consult [roadmap](07_ROADMAP.md) for direction distinctions.
