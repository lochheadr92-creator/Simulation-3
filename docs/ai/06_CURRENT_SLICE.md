# Current slice — remembered household contributions

Checked 2026-09-29 on branch `codex/remembered-contribution`, based on `fe940ef`. Local implementation, not committed in this note. The switch `remembered_contribution_on` is off unless set. It requires coordination.

A resident remembers the latest food deposit they saw a housemate make into their shared home cache. Witnessing is the tick-start observation plus an accepted positive food deposit. The memory is one contributor and one world tick. It is used only when several eligible food-trip announcements arrive in the same tick, and only to prefer that contributor over the lowest actor id. One speaker, an ineligible person, and the case where the lowest id is already the remembered person do not claim a changed choice. Moving home clears the observer's memory. Newborns have none. The wait length and need priorities are unchanged.

The controlled scene and seeds 1–5 at 800 ticks are recorded in [WORLD_DIRECTIONS](../../WORLD_DIRECTIONS.md). The five ordinary runs recorded witnessed deposits and no competing announcements, so they did not show a changed speaker. The controlled scene does. This is implementation verification, not an independent review.

The sections below are the previous sharing and travel notes.

# Previous slice — sharing firsthand food sightings

## Review repair — 2026-09-29

The current work is the [bounded repair response](../reviews/2026-09-29-repair/RESPONSE.md)
to Claude's supplied signed FAIL. F2 viewer escaping and F4 configuration
types are repaired; the birth-text assertion and presentation labels are
strengthened. F1 is investigated across matched seeds without reverting
terrain-aware departure or forcing a social event. The original report
is preserved for independent reassessment of the new commit.

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
