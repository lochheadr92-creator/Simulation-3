# Current slice — recurring work made visible (Slice 3, final of wood yard → stone → stone axe)

## Current work — corrections, re-evaluation and the work view, 2026-09-30

See the top WORLD_DIRECTIONS entry. Crafting scope is closed after this slice.
Known limits carried forward: the housing site predicate does not exclude yard
cells (seed 23 (ii) 600: p12's home sits on `yard-5-8`); re-evaluation judges
demand from where the person stands when resuming; no one reached two
deliveries in any exploration run; the one finished axe (seed 42 (ii) 600, p02
at t593) was never used.

## Previous work — stone and the basic stone axe, 2026-09-30

`--stone on`, `--axe on`; see the top WORLD_DIRECTIONS entry. Carried forward
to Slice 3 (recurring-work visibility and re-evaluation): the axe fired once in
seven exploration worlds and never paid back; the worthwhile rule (a delivery
first) and grove scarcity are the two levers to look at, and the `deliveries`
counter is now recorded truth for that work.

## Previous work — shared wood yards and supply trips, 2026-09-30

Branch `codex/wood-yard-stone-axe` from `e34decc`. `--yard on` is described in
WORLD_DIRECTIONS (top entry). Next slices: stone as a second named resource,
a stone axe possession affecting gathering, viewer integration for both. Open
questions carried forward: no item/tool concept exists (holdings are integer
counts per named resource); `source_created` now accepts `resource`; supply
tasks are wood/yard specific by design (no general job framework).

## Previous work — shared caregiving, 2026-09-30 (committed as `e34decc`)

Authorized by "Begin" following the proposed two-parent caregiving slice.
Baseline: `codex/kernel-first-slice` at `fe940ef` plus existing uncommitted
witnessed-death/configuration work. That work and supplied reassessment are
preserved. No commit or push is authorized or performed.

`--shared-care on` adds a sparse immutable second-parent link at birth;
childhood is required and the default remains off. Both parents see their
own family relationship and can help visible empty-handed dependents through
the existing rule. Both retain personal needs and the existing restriction
against relocation with living dependents. No additional transfer algorithm,
remote knowledge, family move, inheritance or shared scheduling is introduced.

The viewer displays both parents and labels handoffs from either using native
records. Simultaneous handoffs are two accounted transfers; the child cannot
spend those incoming units on the same tick. Tests cover this, one unavailable
parent, local visibility, personal needs, adulthood/death, immutable state,
later births, descriptions/CLI, recovery around birth and deterministic replay.

Fresh validation: 502 affected subsystem tests, then **1,105 full-suite tests
passed**. Six ordinary comparison runs verify/replay; controlled and ordinary
cuts recover identically around birth and handoffs. Browser playback checks
the new family links, delivery/meal and an old single-parent run. Off-mode
comparison matches 720 pre-edit simulation ticks; the earlier seed-11 file
also replays identically. This is builder validation, with no independent
review of the shared-care addition.

The ordinary scene is seed 11, world ticks 40–49, p06 and p08. Their other
parent p03 seeks food while p06 supplies a meal. Three matched 400-tick seeds
show mixed population consequences. See the latest WORLD_DIRECTIONS entry
for the exact comparisons, verification results and local artifact paths.
The dated accounts below retain the earlier work and its boundaries.

## Current work — 2026-09-30

The user authorized review closure, configuration type corrections and one
household consequence after `fe940ef`. The supplied independent reassessment
is [filed here](../reviews/2026-09-29-repair/README.md); its PASS applies to
that repair only.

`observe` exposes locally visible deaths from the just-completed boundary
when coordination is enabled, using final positions and the usual sight
radius. `storage.food_expectation` ends a listener's existing expectation
when its speaker is among those witnessed deaths. Existing processing clears
the memory; existing saved observations and viewer events show the cause.
There is no new overlay field, death rumour, inheritance or forced outing.
Older deaths discovered later do not count; unseen deaths still wait for
the ordinary evidence or timeout. Needs keep priority.

The coordination rule description changes, so previous coordination-on
headers cannot be reconstructed under the new rule. Old runs remain readable;
coordination-off descriptions are unchanged. Recovery keeps its code-identity
requirement. Latest results and the watchable example are recorded at the top
of [WORLD_DIRECTIONS](../../WORLD_DIRECTIONS.md).

The dated sharing and repair accounts below describe earlier work.

## Review repair — 2026-09-29

The current work is the [bounded repair response](../reviews/2026-09-29-repair/RESPONSE.md)
to Claude's supplied signed FAIL. F2 viewer escaping and F4 configuration
types are repaired; the birth-text assertion and presentation labels are
strengthened. F1 is investigated across matched seeds without reverting
terrain-aware departure or forcing a social event. The original report
is preserved as history; the supplied reassessment subsequently cleared the
blockers for `fe940ef`.

- Checked: 2026-09-28 against `22ffe2748dc4c5ee14c71295ff33810c7f456a7c` plus local changes.
- Authorized: user said "proceed" to bounded sharing and chose to keep terrain-aware departures with causal social-memory tests.
- State: implemented, tested and watched locally; committed and pushed as `81c10b7d25cc2e0f1b8de33bf547083eb0972c64` on 2026-09-28. Remote SHA checked. The test result below is recorded implementation evidence, not a rerun for publication.
- Full suite: **729 passed**. No independent reviewer was used.

Share one recent firsthand empty natural-food sighting with adjacent visible
housemates alongside the ordinary action. Use it only from the following tick.
Keep original dates and witness; no relaying, no hidden refill knowledge, and
no extension through repeated speech. Current/newer firsthand evidence wins.
Reuse food-source ranking for personal and household trips. The new switch
is optional and requires source memory. No kernel or stream changes.

The actual sighting -> hearing -> changed destination -> collection -> meal
chain has focused coverage. Seed 11's ordinary saved world shows a report
changing p05's choice at frame 137, followed by thirst, collection from a cache,
a meal and a later home deposit. The browser inspector and playback were
checked; six final comparison runs verify and replay. Recovery with a report
present and deterministic repeat runs pass in the suite.

The earlier two fixed-scene failures were reproduced. The selected contract
change retained replay of seeds 14/26 and a controlled causal rule test, but
did not establish ordinary-world frequency. The controlled test uses an
artificial movement delay. The later matched 1-35 sweep found no activation
by tick 400 under either departure estimate; by 780 it found three current
worlds and four old-estimate worlds. Their particular former scenes are not
required under changed timing. See the repair response linked above.

See the latest [WORLD_DIRECTIONS](../../WORLD_DIRECTIONS.md) account for exact
scope, results and local artifact paths. Older terrain-rule replay compatibility
limits still apply; checks were not relaxed. No next feature is assigned here.

---

## Historical travel-planning record

The following is the preserved pre-sharing record. Its remaining-conflict and
test-count statements are superseded by the current account above.

# Current slice — personal terrain knowledge in food planning

## Source and scope

- Checked: 2026-09-28.
- Baseline branch: `codex/kernel-first-slice`.
- Baseline HEAD: `22ffe2748dc4c5ee14c71295ff33810c7f456a7c`.
- State: local implementation and tests, uncommitted and unpushed.
- Task: the user authorized the proposed bounded slice with “proceed”.
- Authority: [AGENTS.md](../../AGENTS.md); live source outranks this snapshot.

Use a person's existing seen/remembered terrain to estimate their selected food
trip and leave earlier when needed. Unknown ground stays unknown. Reuse route
search, tie-breaking and memory; include the current personal movement delay.
Do not change food-source ranking, water/shelter planning, household rules,
resource accounting or unrelated behaviour to make the example work. This
slice does not learn elapsed journey durations or add a knowledge-sharing rule.

## Implemented and checked

`world/decide.py` shares next-step and route-cost calculation and uses the cost
for personal food departures. `world/observe.py` supplies the person's existing
movement delay. `world/config.py` describes the changed deterministic rule.
`tests/test_travel_planning.py` covers the contract and saved-run continuation.
The viewer displays the native decision reason without a presentation change.

The seed-1 repeat-trip test demonstrates personally acquired terrain memory,
six estimated travel ticks instead of four, departure at hunger 19 instead of
21, and collection at hunger 25 instead of 27. Its matched control has identical
starting needs/location/supplies without earlier sightings; it learns normally
afterwards. The repeat run, recovery before departure and during a terrain
delay, and replay checks pass. The saved viewer shows the chain. An ordinary
180-tick seed-7 run also verifies and replays.

## Remaining conflict

**70 focused tests passed. Full suite: 713 passed, 2 failed.** Both unchanged
failures are `tests/test_social_memory.py::test_remembered_gift_changes_choice_and_is_visible`:
seed 14's gift/choice at 534/643 and seed 26's at 588/774 no longer occur in the
changed worlds. The same two tests pass on isolated, unchanged baseline HEAD.
The first actual divergences are earlier food departures at ticks 28 and 334,
respectively. No test was skipped, weakened or repinned, and there has been no
independent review. Resolve the conflict between intentional trajectory change
and the fixed-scene regression contract before calling this a clean handoff.

Old saved headers with planned trips, terrain and routing enabled fail exact
rule reconstruction under the changed code. Other combinations retain their
descriptions. Replay/recovery validation was not weakened.

See [the latest development note](../../WORLD_DIRECTIONS.md) for exact evidence,
local saved examples, viewer frame numbering and limitations. Historical stages
and this document do not automatically assign another feature.
