# Current slice — sharing firsthand food sightings

- Checked: 2026-09-28 against `22ffe2748dc4c5ee14c71295ff33810c7f456a7c` plus local changes.
- Authorized: user said "proceed" to bounded sharing and chose to keep terrain-aware departures with causal social-memory tests.
- State: implemented, tested and watched locally; uncommitted and unpushed.
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

The earlier two fixed-scene failures were reproduced and resolved by the
explicitly selected test-contract change. A controlled actual gift and return
gift establish causation; seeds 14 and 26 retain full-horizon replay checks.
Their former scenes are no longer expected under changed departure timing.

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
