# Simulation 3 — Development Directions

## Wolves, and a memory that keeps dates — 2026-10-04

The third piece of the rich world: two more optional features, `beliefs` and `wolves` (wolves
need the sky). [RICH_WORLD.md](RICH_WORLD.md) has the phase plan and the next step.

**What people believe.** A belief is one remembered fact: a kind of thing (so far a wolf), which
one, where it was, when it was seen, when this person learned it and who told them. What a
person sees, they believe first-hand. What they are told, they believe with the date of the
original sighting, so a rumour is never fresher for being repeated. Beliefs fade after 240 ticks
and only the ten freshest are kept. Nothing about a wolf reaches a person except through sight or
a telling: an unseen wolf changes nobody's plans, and a test moves one out of sight to show it.

**The wolves.** One wolf arrives at tick 40 and lives at a den on the map's edge where nobody
lives. It hunts only at dusk and night, bites anyone in the open beside it (under a finished
shelter nobody is touched), and goes back to its den to rest by day, or after a bite or a chase it
gave up. A bite is 25 hurt; hurt heals faster resting at home; past 40 each step costs a tick
more; at 100 the person dies. Everyone knows wolves hunt after dusk, so by day nowhere counts as
dangerous and a wolf seen lying by its den is nothing to run from.

**What people do.** They see a wolf only inside their sight (two cells at night). A wolf in view
within three steps makes them run, for a built home if they have one, else away, and the
need that runs out first still wins: somebody one drink from death drinks. Seeing a wolf they
did not see a moment ago they call out to everyone awake in view, who then believe it. A person
puts off a food or water errand to a place a wolf was lately near, whether they saw it or were
told, until the need cannot wait; then they go and the decision says they are taking the
risk. Routes go round believed danger when that is cheaper than the extra steps, and a hurt
person at home stays in while the need can wait.

**What watching found.** The first version put two wolves out all day and every sighting
sent people running; whole worlds died of thirst and cold while fleeing. A wolf's den
turned out to be a person's home, so one person was bitten at their own door every nine ticks.
A route search that judged only a window of the map sent somebody round the edge of the world
and made another step back and forth until they froze. Each is fixed by a rule above and pinned
by a test. Across eight seeds at 300 ticks the final rules cost 33 deaths of 77 people with one
wolf against 34 of 82 without, with 18 bites and about 25 ticks a world spent running; nobody
was killed by a wolf, they lost time. Two wolves cost 38 of 71. Switching the holds off made
it 48 of 77.

**What to watch.** A grey wolf by its den at dusk, a dashed ring on the map where the selected
person believes it was (fainter as it ages, labelled with who told them), "Knows about wolves"
in the inspector, and in the set-aside list a trip put off because of a wolf or a wound.

**Next.** Relationships and conversation (P4): people who pass on what they believe,
gifts, quarrels, apologies and avoidance.

## A sky: day, night, weather and what being out in it costs — 2026-10-04

The second piece of the rich world, two more optional features (`sky`, `steady`),
saved in the run header and off by default. [RICH_WORLD.md](RICH_WORLD.md) has the
phase plan and the exact next step.

**The sky.** A day is 120 ticks: dawn, day, dusk, then 36 ticks of night. Weather
changes in fronts every 30 ticks and follows a fixed table, so a storm builds through
rain and never arrives out of a clear sky. Temperature is the day's base plus the hour,
the weather and (when seasons are on) the season. Everything is fixed by the seed and
the tick, and every tick's world records the sky, so the viewer shows what was
recorded and replay checks it. A person out in the cold, the rain or a storm gains extra
cold each tick; under a finished shelter they gain none. Sight shrinks at night and in
storms, climbing onto rough ground costs a tick more in a storm, nobody starts building
or an optional outing in a storm, and (with sleep on) bedtime comes earlier at night.

**Planning with the weather.** The first version charged the cold but left every plan
using the nominal rate, and eight seeds of 300 ticks produced 27 cold deaths against
none without the sky. Three rules fixed that, and each is visible in the inspector:

* Cold's time-left and the "start for home" rule use the cold rate of the sky people
  are in, and away from home the walk back is taken off the time left, so somebody
  turns for home while they still can.
* Somebody at home does not set out on a food or water errand when the round trip would
  carry their cold past the emergency level, unless the need cannot wait any longer.
  They stay in and warm up, and the set-aside list says "waiting out bad weather".
* `steady`: whatever a person was serving last tick counts as 8 ticks more urgent when
  the next choice is made, so a need has to be clearly worse before they give up the
  errand. Without it people stepped out of their door and straight back in; in three
  seeds that happened 63, 52 and 125 times, and with it 4, 11 and 9. A later pass added three
  smaller rules to it: a need whose relief can be taken this tick counts for as much again,
  somebody who reaches the well a tick early takes the water rather than turning back, and
  somebody already out is not called home until the cold they would arrive with is a little past
  the usual line. Across five seeds that cut the remaining door reversals from 44 to 15.

Results of those eight seeds (7, 11, 14, 23, 31, 42, 57, 64) at 300 ticks, with
explain, personality, skills and sleep on: 34 dead of 93 people without the sky, 51 of
87 with the first sky, 38 of 75 after planning with the weather's rate, and 34 of 82
with steadiness and the walk-back rule, of which 2 died of cold. These are what those
runs did. The weather-wait rule had no measurable effect on survival in them (12 cold
deaths with it and 12 without, before steadiness). Later, with wolves in the same worlds,
switching it off (and the wolf holds) raised deaths from 33 to 48 of 77, so it does matter
once nights hold more than cold.

**What to watch.** The clock and weather in the corner of the map, the night tint, the
rain streaks, and in the inspector: a person at their hut in a rainy night, building
or resting, with the errand they did not make and why.

**Next.** A belief model and wildlife (P3): what people know about places and
dangers, how old it is, and who told them.

## People with temperaments, skills and sleep — 2026-10-04

The first piece of the rich world. Three optional features, each saved in the run
header and off by default (`--features explain,personality,skills,sleep`). With all
of them off a run is identical to before; `tests/test_disabled_mode_baseline.py`
checks 16 configurations against digests made from the untouched baseline commit.
[RICH_WORLD.md](RICH_WORLD.md) holds the full inventory, phase plan and next step.

**Temperament.** Everyone has five traits from 0 to 100: generosity, sociability,
caution, diligence, curiosity. They are drawn at genesis from their own generator
(so no home or terrain cell moves) and a newborn inherits its two birth adults'
average with a small deterministic offset. A trait only matters as a distance from
50. Stingy people (generosity under 35) keep their last unit from a stranger, though
never from their own child; generous people (75 and over) hand water to somebody
visibly parched. Cautious people set off a few ticks earlier for food, water and
home, and go to bed earlier. Diligent people work on through more tiredness and
keep the shared cache better stocked. Sociability and curiosity are stored but act
only through conversation and exploration, which come later.

**Skills.** Gathering, fishing, building, farming and crafting each collect practice
points from real work: an accepted claim, a casting, a finished work tick. Levels
begin at 0, 8, 24, 48, 80 and 120 points. Every two gathering levels add a unit to a
pack, every two fishing levels a unit to a catch, and each building level takes a
tick off a shelter.

**Sleep.** Fatigue is a fourth need that nobody dies of directly. It rises while
awake, faster on work ticks. A tired person goes home and sleeps for about fifteen
ticks, waking early only when another need cannot wait. "Cannot wait" means the
time left is no more than the time to reach the remedy and finish with it, plus a
small margin, so distance finally enters a choice. At the limit people collapse
where they stand and stay down. Sleepers see only their own cell; everybody else
can see they are asleep.

**Why a choice was not made.** Each decision now records the options it set aside
with a reason: less urgent, too late, unwilling. The inspector lists them, and a
person remembers their last four distinct attempts and whether each worked.

Watching ordinary worlds (10 seeds, 300 ticks) found four faults that tests alone
had not, each now fixed and pinned by a test:

1. Cautious people arrived at the source before they were hungry, could not claim,
   turned round, set off again, and repeated. Arriving within their own margin they
   now stock up.
2. A tired person turned back mid-trip to go to bed, then had to make the trip
   again. A food or water errand that fits before collapse is now finished first,
   and somebody already on an errand needs a few more ticks of reason to abandon it.
3. Waiting at an empty source counted as an errand and postponed sleep until
   collapse. Waiting is now costed as a full renewal period and gets no commitment.
4. Collapse was one tick long, so a starving, exhausted person collapsed every
   third tick. A collapsed person now stays down until ten points of fatigue have
   gone, except for one life-saving bite or sip of something already in hand.

What it did to the worlds: people sleep about 15-20% of the time in ordinary
runs. Famine worlds (seeds 11, 23, 57, 88) still collapse and starve, now with
exhaustion in the mix; no one dies of tiredness itself. Births fell in several
boom-and-bust seeds because sleepers cannot spend settled ticks side by side, and
rose in a few quiet ones; this is a trade-off to watch, not a tuned result.
Files grow by about a third (a persona block each tick, plus the set-aside lists).

## Baseline consolidation — 2026-10-03

The selected starting point is `019503c` on `codex/kernel-first-slice`.
Current work consolidates its existing household and stranger-helping behavior;
cultivation/live-viewer and other branches remain deferred. There are no new
behavioral rules or changed defaults. See the [consolidation report](docs/reviews/2026-10-03-consolidation/REVIEW.md)
for source scope, exact checks, saved scenes and limitations.

Canonical encoding was the measured hot path in repeated saved-world checks;
the encoder now avoids the old per-value Python formatting overhead while
preserving canonical bytes and unlimited integers. The full suite remains the
default; extended world checks can be selected separately. Final results:
**1149 passed in 237.08s (0:03:57)** full; **1127 passed, 22 deselected in 34.15s** fast. These are local results, not new performance
claims for every machine.

The family aquarium is explicitly defaults plus shared care and care-by-need.
Seeds 7/11/23/24 each produced real child handoffs over 400 ticks. Request worlds
with learned donor preference off delivered food in both request modes. In
ordinary seed 29, hiding p23's memory once at decision 588 switches a journey
to former donor p10 into an immediate gift to p19; their continuations remain
different at tick 780. The worlds already supply these opportunities without
new scarcity or weather. Keep causal consequences as the acceptance question;
counts and survival describe a configuration, not a score to maximize.

The early-warmth care handoff now retains why a starving child was selected.
Source review and tests found no further blocker in the three original additions.
Fresh Edge inspection on 2026-10-04 followed both family scenes, a fulfilled food
request, and the donor-memory choice and its labelled counterfactual. A fresh
critical check of the two production fixes passed 26 focused tests; 2,000 seeded
canonical comparisons matched the prior encoder byte for byte. The new repairs
still need a completed independent review before adding new social rules.
Existing dated entries below retain their original evidence and scope.

## Choosing between children when food is scarce — 2026-09-30

Built from `e34deccf11b59767aa7a256f5594e1bfbca6282c`, the committed and
pushed checkpoint containing shared care, witnessed household death, boolean
configuration checks and the supplied repair reassessment. The earlier dated
accounts below describe their implementation sessions before that publication.

`--care-by-need on` prefers visibly starving children among the parent's
visible, empty-handed dependents, then distance and actor ID. It requires
childhood, works with either one or both recorded parents, and is off by
default. It uses the existing visible emergency flag, never exact private
hunger. Personal needs, local sight, real transfers and separate parental
choices retain their rules. No new persistent state or viewer calculation
is needed; the saved decision reason explains the priority.

The first three shared-care worlds (seeds 7, 11 and 23) had no affected
helping choice through 780 ticks. A fixed scan of seeds 1–35 at 780 ticks,
with defaults plus shared care, found 14 decision opportunities where the
recipient ranking differed. Only one was an actual offer or delivery journey;
the parent's own needs took precedence in the others. This is a small fixed
sample, not an estimate of general frequency. The scene below was found by
that scan rather than constructed by adjusting needs or initial positions.

**Watch seed 24, p04, p19 and p23, world ticks 243–262.** At decision tick
244 (viewer frame 245), p04 carries one food. p23 is adjacent and has hunger
11; p19 is three steps away and visibly starving (private hunger 53). The
old rule feeds p23. The new rule sends p04 toward p19, transfers the food at
world tick 247, and p19 eats at 248: hunger falls from 56 to 27. p23 later
gathers independently and eats at 262. Removing only the new priority from
the same decision observation selects p23 again.

The later cost matters. In the old world p23 passes that first unit to p06
at world tick 248. In the changed world that handoff is absent and p06
starves at 252 instead of 282. p19 eventually starves at 301 instead of 271;
p23 dies of thirst at 274 in both. The parent p04 dies of thirst at 285 in
the changed world but survives to 400 in the comparison. A successful meal
is not a guaranteed rescue or a general improvement in survival.

Matched 400-tick worlds, defaults plus shared care, changing only care priority:

| Seed | Births off / on | Living off / on | Deaths off / on | Child handoffs off / on |
| --- | --- | --- | --- | --- |
| 7 | 6 / 6 | 11 / 11 | 1 / 1 | 6 / 6 |
| 11 | 13 / 13 | 5 / 5 | 14 / 14 | 16 / 16 |
| 23 | 14 / 14 | 7 / 7 | 13 / 13 | 14 / 14 |
| 24 | 22 / 17 | 8 / 4 | 20 / 19 | 14 / 12 |

The first three pairs have identical world states, ledger digests and decisions.
Seed 24 changes later encounters and births, so population totals compare
different populations. The feature stays optional. Another explicit tradeoff:
selecting a distant starving child can forgo an immediate handoff to a nearer
child before a warmth trip. The existing exception only applies when the
selected child is alongside; this rule does not grant extra walking time.

Verification: 450 affected subsystem tests passed, followed by **1,124 passing
tests in the full suite** (291.74 seconds). All eight comparison files
verify and replay; recovery before the choice, during the journey and after
delivery matches the uninterrupted scene, and a repeat run matches. Off-mode
headers and all saved tick fields except seals match 1,600 pre-edit ticks
across seeds 7, 11, 23 and 24. Seals change with the source identity in the
header. The actual pre-edit seed-24 file also replays identically. Old rule
descriptions remain reconstructible when this option is off. A final self-review
checked the diff, selection/need interaction, saved descriptions, legacy replay
and source ownership; `git diff --check` passed. No valid tests were weakened.

Edge playback and inspected screenshots show the changed target, native
reason, accepted transfer and later meal, plus the baseline handoff to p23.
No browser errors or console warnings. An initial browser script could not
select an unrendered person link; the final script selects a recorded event.
Its meal-text assertion was corrected from "hungry" to the observed
"emergency"; no simulation or viewer change was needed for either script fix.

Local saved viewers, comparison data, scan script/results and logs are under
`runs/child-priority-2026-09-30/` (ignored by Git). Open `seed24-careTrue.html`
and `seed24-careFalse.html`. Reproduce a new example with:

```powershell
py -3 -B -m world.run --seed 24 --ticks 400 --shared-care on --care-by-need on --out runs/child-priority-example.jsonl --html
```

No kernel, stream or observation source changed. This is builder validation;
the earlier independent repair PASS does not cover this addition.

## Both birth parents can care for their child — 2026-09-30

Local work on `codex/kernel-first-slice`, based on `fe940ef` plus the preserved
witnessed-death/configuration changes below. `--shared-care on` records both
adults involved in each new birth. Both use the existing caregiving rule:
help their visible, empty-handed dependent child when their own needs permit.
It requires childhood and is off by default for comparison. Homes, need
priorities, food transfers and birth eligibility keep their existing rules.

The existing `parent` field retains the adult whose home anchored the birth.
A sparse immutable `second_parent` field records the other adult. Both links
survive movement, later births, adulthood and death. Both parents receive the
existing restriction against relocation while they have a living dependent.
No relationship is guessed for old saves. A relationship does not reveal an
absent child's needs or position. The viewer draws both saved links, names
both parents in births/inspection, and counts either parent's actual handoff.

Parents decide separately. If both hand over food on the same tick, each
transfers one real unit; the child receives two and can spend them only from
the next tick. The focused test checks this accounting and the following meal.
There is no joint task assignment or automatic guarantee that somebody helps.

**Watch seed 11, p08 and p06, world ticks 40–49:** p08 was born to p03 and
p06 at tick 16. At 42, p06 hands p08 one of their two food units while p03 is
empty-handed and travelling to food. At 43 p08 eats. At 44 p06 gives another
unit, leaving themselves with none, then heads home for warmth. A same-state
comparison removing only p06's second-parent role changes the tick-42 choice.
This is generated genesis with default settings plus shared care, not a
constructed rescue. Open `runs/shared-care-2026-09-30/comparisons/seed11-sharedTrue-400.html`.

Matched 400-tick worlds (defaults, changing only shared care):

| Seed | Births off / on | Living off / on | Deaths off / on | Child handoffs off / on | Second-parent handoffs on |
| --- | --- | --- | --- | --- | --- |
| 7 | 6 / 6 | 11 / 11 | 1 / 1 | 5 / 6 | 1 |
| 11 | 23 / 13 | 7 / 5 | 22 / 14 | 10 / 16 | 5 |
| 23 | 17 / 14 | 8 / 7 | 15 / 13 | 6 / 14 | 7 |

These are three examples, not a survival result. Changing help changes later
encounters, births and the population being compared. Shared care stays optional.
Seed 7's second parent starts an errand by tick 215 but completes no handoff
within 240 ticks; its first second-parent delivery in the 400-tick run is at
386. In the first controlled arrangement the first parent delivered before
the second arrived. These exposed incorrect scene assumptions in two new
tests. The controlled initial state now makes the first parent empty-handed,
and the ordinary seed-7 test covers the inspected 400-tick trajectory. No
existing tests, simulation thresholds or old expected results were changed.

Verification: **502 affected subsystem tests passed**, followed by **1,105
passing tests in the full suite** (278.82 seconds), including the added
seed-11 causal check. All six ordinary comparison files verify and replay. Recovery at
four cuts, before/after a controlled birth and during later care, reproduces
the saved ticks; the ordinary seed-11 world also recovers identically from
cuts at completed ticks 15, 16 and 42 (before birth, after birth and after the
handoff). Controlled and ordinary repeat runs match. Default/off
configurations match the pre-edit description and every saved tick field
except seals for seeds 7, 11 and 23 over 240 ticks each (720 ticks). Seals
change because they chain from a header containing the changed code identity.

Browser playback in Edge checked both parent links, the delivery, the next
meal, scrubbing before birth, and an older single-parent run rendered with
the current viewer. No page errors or console warnings. One ad-hoc text
assertion was corrected to allow line breaks between the parent-link buttons;
the displayed parents were already correct. Screenshots were inspected.

Off-mode rule descriptions and sparse saved state remain unchanged. The
pre-edit seed-11 run replays identically with current code; its old file also
renders and plays. Recovery still requires matching code identity.
New shared-care headers describe the new rule explicitly. No kernel or stream
source changed. Logs, comparisons, source backups and saved viewers are under
`runs/shared-care-2026-09-30/` (ignored by Git). No commit, push or independent
review of this addition has been made. A final self-review checked state
preservation through both Overlay construction paths, legacy descriptions,
all parent-field consumers, viewer escaping and the final diff. JavaScript
syntax and `git diff --check` passed. This is builder validation, not an
independent review.

## A listener witnesses a food traveller's death — 2026-09-30

Local work on `codex/kernel-first-slice`, based on `fe940ef`. The user chose
to close out the review repair and explore this one household consequence.
The supplied [reassessment](docs/reviews/2026-09-29-repair/README.md) gives
the preceding repair PASS within its scope; it does not review this addition.

With coordination enabled, a person expecting food can witness the speaker's
death at the just-completed boundary. Both final positions must be within the
usual sight radius. The next decision ends that expectation with a recorded
reason; ordinary needs and provisioning determine what the listener does.
Unseen deaths and older deaths discovered later do not provide this information.
This is specific to the existing listener/speaker relationship, not general
death knowledge or inherited knowledge for a newborn. No new switch, persistent
overlay field, resource transfer, inheritance or forced outing was added.

The viewer reads the saved `witnessed_deaths` observation and expectation-end
reason. Its inspector names the witnessed person, and Happenings links the
ended expectation to the listener's later action.

**Controlled scene:** `runs/witnessed-death-2026-09-30/final/controlled.html`.
Follow p02 through world ticks 1–7. p01 announces at 1; p02 waits through 4;
p01 dies at 4; p02 witnesses that death and starts a cache outing at 5.
They reach the empty patch at 6 and wait there at 7. Knowing the promise
cannot be fulfilled changes a choice; it does not create food or rescue them.
This scene deliberately uses a shared built home, empty patches, p01 starting
at hunger 24, emergency/death thresholds 26/27 and meal satiation 1. No state
is edited after the start. `save_witnessed_death_scene` in
`tests/test_coordination.py` reproduces it. It is a controlled initial state,
not generated genesis and not an ordinary-world replay claim.

**Ordinary-world limit:** no expectation ended through witnessed death in
seeds 1–35 at 480 ticks with the existing full-feature coordination-test
configuration. Nor did it occur in seeds 7, 11 and 23 at 780 ticks using
defaults plus stores, homes, provisioning and coordination. These were scene
checks, not population statistics. The saved minimal seed-23 world is
`runs/witnessed-death-2026-09-30/final/ordinary-seed23.jsonl`; it verifies and replays
identically, and its viewer was played. This addition has not demonstrated
a new ordinary household scene in that sample. Do not expand it into a broader
death system on the strength of the controlled example.

Configuration cleanup rejects non-boolean values for every boolean field,
including inactive switches. `water_on="off"` now raises ValueError. Malformed
`yield_set` containers fail clearly; lists remain supported and are copied
to tuples as before. Valid defaults remain unchanged.

The saved coordination rule description now includes witnessed death. Old
coordination-on runs remain readable, but their previous rule descriptions
cannot be reconstructed for replay under this changed rule. Coordination-off
descriptions are unchanged. Recovery retains its matching-code requirement.

**Verification:** configuration and coordination checks passed 354 tests;
the broader affected subsystem run passed 464. After adding the saved-scene
check, the full suite passed 1,076 tests. The final narrowing of observation
to existing listeners and the viewer inspector change were checked afterward
with 369 passing configuration, coordination, map-viewer and browser-security
tests. An additional same-state uninformed comparison proves that p02 would
still wait without the witnessed information; the final eight focused death
checks passed. Saved cuts before death, before witnessing and after clearing
continue identically, and repeating the controlled scene gives the same trail.

The controlled scene and ordinary seed-23 page were played in Edge with no
page errors or console warnings. The controlled inspector shows p01's
witnessed death, the ended expectation and p02's outing; scrubbing backward
shows the earlier wait. The first ad-hoc browser assertion expected title
case where CSS renders uppercase; correcting that text assertion passed.
This did not require a viewer behaviour fix.

With coordination off, 220 ticks each for seeds 7, 11 and 23 matched the
pre-change observation implementation in every saved world field and kernel
record (660 ticks). Default headers and headers with stores/homes/provisioning
but coordination off also match the previous configuration description.
These are bounded preservation checks. No kernel or stream source changed.

Local logs, compatibility results, screenshots and final examples live under
`runs/witnessed-death-2026-09-30/`; runs are ignored and are not supplied by a
clean clone. No commit, push or independent review of this addition was made.

## Review repair — 2026-09-29

The independent whole-project review returned a bounded FAIL. The
[repair response](docs/reviews/2026-09-29-repair/RESPONSE.md) preserves
that signed report and records the fixes and remaining limits. The viewer
now escapes actor names in death totals; malformed integer settings fail
at configuration construction; world/decision tick labels are distinct.

Social memory is rare in the measured default worlds, not absent. With
routing unchanged, seeds 1-35 show zero activations under either departure
estimate by 400 ticks. At 780, current timing produces 12 remembered-helper
decision ticks in seeds 29/30/32; the old estimate produces 16 in
14/26/28/29. These are decision ticks, not unique gifts or a general
survival measure. Terrain-aware departure stays. Seed 29 supplies a real
gift at world tick 560 and return gift at 714, both settled by the kernel.

See [existing rules clarified](docs/reviews/2026-09-29-repair/MODELLING_NOTES.md)
for shared-home listeners, capped waiting after death, retained holdings,
valid edge settings and movement-delay terminology. No witnessed-death
rule, inheritance or forced social encounter was added.

Viewer visual direction: [Field atlas](VIEWER_DIRECTION.md).

## Sharing firsthand food sightings — 2026-09-28

Implemented on `codex/kernel-first-slice`, based on `22ffe27` plus
the existing terrain-planning work. Committed and pushed as `81c10b7` on
2026-09-28; the remote SHA was checked. The verification below records the
implementation run, not a new test execution for publication. A
[whole-project review packet](docs/reviews/2026-09-28-whole-project/README.md)
is prepared; its reviewer report is unsigned.

`--source-memory on --knowledge-sharing on` lets a person tell visible
housemates on the same or an adjacent cell about their most recent firsthand
empty berry-patch or fishing-spot sighting. Speech accompanies the ordinary
action. Listeners can use the report from the following tick. Personal food
trips and optional home-cache trips use it in the existing source ranking.
The new sharing switch is off by default.

Reports keep the source, original witness, sighting tick and hearing tick.
They expire twenty ticks after the sighting; repeated speech does not extend
that date. Recipients cannot relay reports. Current sight overrides them,
as does an equally recent or newer personal sighting. Recent firsthand
stocked sightings are retained too, preventing an older empty report from
undoing what a listener already saw. No distant refill or death supplies
new information. Existing need priorities, child limits, fallback when all
sources are remembered empty, gathering and resource accounting remain.

**Watch seed 11, p05, viewer ticks 133–150.** p09 saw `food` empty at
simulation tick 128 and told p05 at completed tick 133. p05 feeds a child at
134 and starts a household outing at 135. At 137, personally seen empty fish
plus p09's report send p05 toward `food2`. Removing only reports from that
same decision state sends p05 toward `food`. Thirst interrupts at 140;
p05 later takes three food from `store-p04` at 147, eats at 148, returns
home at 149 and deposits one at 150. The report changes a choice, not a
guaranteed destination or successful rescue. The browser inspector shows
the native reason and dated report; playback was inspected without browser
warnings or errors.

Three matched 360-tick runs use source memory, stores, adult homes,
provisioning, coordination, fishing, regrowth and seasons, with birth
spacing 30. The exact configuration is in each saved header.

| Seed | Accepted report updates | Changed food decision ticks | Living off / on |
| --- | --- | --- | --- |
| 7 | 8 | 0 | 18 / 18 |
| 11 | 43 | 26 | 12 / 13 |
| 23 | 12 | 1 | 19 / 21 |

Changed decisions compare the native on-run choice with the same state and
personal memories but reports disabled. Counts include consecutive ticks
and report-induced early departures, not unique journeys or meals.
Population totals do not establish a general survival benefit.

**Verification:** 729 tests passed in the full suite. The 13 sharing tests
cover local hearing, next-tick effects, an actual sighting-to-meal chain,
no relaying, original-date expiry, fresh/personal sight, unseen changes,
deterministic competing reports, child limits, fallback, immutable validated
state, birth preservation, death cleanup, configuration, saved replay,
repeat runs, recovery with a report present, and viewer output. The affected
subsystem run passed 96 tests before an additional attribution test was
added; the final full suite includes that test. All six final comparison
files verify and replay. The correction to report attribution changed no
world states in these examples; disabled-mode tick content was unchanged
(both seal chains verified independently; code-identity changes alter seals).

The user explicitly chose to retain terrain-aware departure. The earlier
fixed-scene test conflict was resolved at the rule-test level; that did not
establish activation in ordinary worlds. Both original failures were
reproduced. Their fixed gift/choice dates were replaced with a controlled
real-transfer -> memory -> changed recipient -> real return-transfer test,
including viewer events, exact accounting and deterministic continuation.
The two original seeds still run through their full original horizons and
replay, but their old scenes are not claimed to recur. No substitute lucky
seed, skipped test or relaxed replay check was used.

The feature uses `world/foraging.py`, the existing observation/decision and
processing paths, two sparse overlay fields (`food_sightings`,
`source_reports`), config/CLI and the existing viewer. No kernel or stream
code changed. With sharing off, no new header/state/observation fields are
written. The older terrain-planning compatibility limit remains: headers
from the previous departure rule cannot replay under the new rule when
planned trips, terrain and routing were all enabled. Recovery still requires
matching code identity. No independent reviewer was used.

Local artifacts are in
`C:/Users/RJLoc/OneDrive/Desktop/Documents/ChatGPT/Simulation 3 - Living World Engineer/work/knowledge-sharing/final/`.
Open `seed11-on.html`; `summary.json` contains the bounded comparisons.
These files are local and are not guaranteed in a clean clone.

## Planning food trips from remembered ground — 2026-09-28

Local implementation on top of `22ffe27`; not committed or pushed. With
planned trips, terrain and routing enabled, a person now uses the existing
route search's cost when deciding when to leave for their selected food source.
Known rough ground costs two ticks, other ground one. Their current movement
delay is included. Unseen ground still counts as open. This reuses personal
terrain memory; it does not record elapsed journey durations or share knowledge.

The selected source, route choices and tie-breaking, fishing cast, water and
shelter planning, need priority, resource accounting and storage rules are
unchanged. The nominal hunger rate still ignores shelter relief, interruptions
and competition. Disabling terrain or routing retains Manhattan departure
timing. No new switch or persistent state field was added.

**Watch p01 in `runs/travel-planning/repeat-trip-seed1.html`.** On the first
outing they depart at simulation tick 21 with hunger 21, learn rough ground,
and claim food at tick 27 with hunger 27. On the repeat outing they depart at
48 with hunger 19, allow six travel ticks instead of four, claim at 54 with
hunger 25, and eat at 55. The viewer shows the result of a simulation tick one
frame later: inspect frame 49 for the departure reason and frame 56 for the meal.
The configuration is in `repeat_trip_config()` in `tests/test_travel_planning.py`.

The matched test control starts at the second departure with identical needs,
position and supplies but without the earlier terrain sightings. It still
learns normally after that point. It waits two more ticks and claims at hunger
27. This is a controlled comparison, not a claim of improved population survival.

**Fresh checks:** 70 focused tests passed, including all 24 new travel checks.
Recovery before the repeat departure and during a rough-ground delay matches
the uninterrupted run; repeating the run gives the same trail digest. The
80-tick example and an ordinary 180-tick seed-7 world verify and replay
identically. The browser showed the departure reason, map and later meal.
An additional comparison against HEAD found identical first steps in 800
sampled routing cases and header differences only in `decision` for the
planned-trips/terrain/routing combination, across 16 combinations including
fishing on/off. These are bounded checks, not exhaustive equivalence claims.

**Historical result before the sharing work: 713 passed, 2 failed.** The
regression-contract conflict is resolved in the newer note above. Both failures were cases of
`test_remembered_gift_changes_choice_and_is_visible` in `tests/test_social_memory.py`.
Their fixed scenes are seed 14 (gift 534, choice 643) and seed 26 (gift 588,
choice 774). Both pass on unchanged HEAD in an isolated checkout snapshot.
The first actual action differences are the intended earlier departures:
seed 14, tick 28, p06 rests before and goes now (hunger 22, cost 2 -> 3);
seed 26, tick 334, p12 builds before and goes now (hunger 21, cost 3 -> 4).
The expected social scenes do not recur in those horizons. These failures are
preserved in this historical account. The newer note above records the explicit
behaviour choice and revised causal coverage; no independent review is claimed.

The saved decision rule now describes terrain-informed food planning. Old
headers with all three switches enabled fail exact reconstruction/replay;
recovery also retains its code-identity check. Old files remain readable.
Other switch combinations keep their previous descriptions. No compatibility
or replay check was relaxed. Saved example files are local ignored artifacts.

## Telling housemates about a food trip

`--stores on --provisioning on --coordination on` lets someone starting a
home-cache outing tell the housemates they can currently see: "I'm getting
food for us." Use `--homes on` to let grown children join shared homes.
The announcement accompanies their normal action. Housemates hear it after
making that tick's choices, so two people can still set out together.
Coordination is off by default.

A listener remembers one speaker for twelve ticks and postpones a new
optional cache trip. Eating, drinking, warming, helping and outings already
underway keep their priorities. Seeing at least two meals in the home cache,
or seeing the speaker back at home without spare food, ends the expectation
early. A returning person carrying spare food gets time to deposit it.
Unseen refills, deaths and changes of plan supply no information. The timer
still runs; moving home or dying clears the listener's expectation, and
births preserve everyone else's memories.

**Watch seed 23, ticks 92–108.** p05 announces an outing at 92. p07 stays
home at 94 instead of following. p05 collects three food at 97, returns at
102 and deposits two at 103. At 104 p07 sees the stocked cache and feeds
their own new child. They take food from that cache at 107 and eat at 108.
An early version let p07 leave on the deposit tick; waiting for the actual
deposit when a returning housemate has spare food removes that wasted trip.

**Keep watching through 121.** p05 announces another outing at 108. p07
postpones their trip, but still drinks and feeds a child. p05 collects food
at 114 and is diverted by childcare. At 121 the expectation expires before
another deposit, so p07 sets out and announces their own trip. A spoken
intention can help a household without guaranteeing a delivery.

Three 480-tick runs add only coordination to the provisioning worlds:

| Seed | Announcements | Waiting events | Deposits, off / on | Living, off / on | Deaths, off / on |
| --- | --- | --- | --- | --- | --- |
| 7 | 41 | 19 | 49 / 52 | 9 / 13 | 28 / 24 |
| 11 | 24 | 8 | 23 / 25 | 14 / 10 | 22 / 27 |
| 23 | 33 | 8 | 30 / 28 | 19 / 6 | 17 / 27 |

Announcements are counted per listener. Waiting events include resuming
after another need interrupts the wait. Neither counts successful deliveries.
The population results are mixed: this changes household routines and later
meetings, births and resource pressure, without showing a general survival
improvement. Twelve ticks is a first waiting rule to watch, not a tuned value.

Saved runs and viewers are in `runs/coordination/final/`, with fresh `-off`
baselines beside them. The seed-23 viewer was played in a browser, including
the stocked-cache and expiry scenes. The inspector shows the speaker and
remaining expectation time; the history records announcements, postponed
trips and the observed reason for ending a wait.

The full suite passed 677 tests. Coordination checks cover the delivery-to-meal
chain, local hearing, simultaneous departures, needs and helping, expiry,
unseen events, return with and without spare food, births, moves, deaths,
immutable memories, old headers, saved events, repeat runs and recovery while
an expectation is active. All six 480-tick files verify and replay identically.
Repeating seed 23 gives identical tick records and seals. With coordination
off, all three worlds retain the preceding provisioning runs' simulation
records. JavaScript syntax and diff checks pass.

## Gathering food for home

`--stores on --provisioning on` lets a low shared cache prompt a food trip.
An adult at a finished home who would otherwise rest, carries at most one
meal and sees fewer than two meals stored can set out. With warmth on they
warm fully first. The first runs exposed people leaving while still cold
and turning back almost immediately; finishing their warming removes that
repeated start. The switch is off by default.

These outings use berry patches and the fishing spot, following the existing
local stock observations and empty-source memories. They do not fetch from
other home caches. One successful collection starts the return home, even
if the catch is small. A refused claim leaves the person still gathering.
Fishing still needs a cast and a later catch, and gathering does not eat.

Own needs, helping, construction and choosing a home keep their priorities.
A food outing survives interruptions, including eating or giving away the
catch. Reaching home ends it; the existing deposit rule then puts away any
spare food while keeping one carried meal. Arriving empty-handed is possible.
Moving home or dying ends an outing too. Births keep other people's outings,
and newborns start without one. People cannot remotely see a cache refill.
With coordination off, two adults sharing a home can both respond to its
shortage independently.

**Watch seed 7, ticks 21–45.** p01 sees an empty cache and heads for fish at
21. Water interrupts the journey at 23. After drinking, p01 returns to the
bank, catches three food at 37, arrives home at 38 and stores two at 39.
p04 takes those two meals at 44 and eats at 45. p01 notices the emptied
cache and sets out again at 45, this time avoiding the remembered empty
fishing spot and heading towards berries. A neighbour's meal has become
another person's work trip.

Three 480-tick runs add only provisioning to the source-memory worlds:

| Seed | Food outings started | Deposits, off / on | Living, off / on | Births, off / on | Deaths, off / on |
| --- | --- | --- | --- | --- | --- |
| 7 | 60 | 31 / 49 | 8 / 9 | 2 / 31 | 0 / 28 |
| 11 | 54 | 4 / 23 | 11 / 14 | 25 / 30 | 20 / 22 |
| 23 | 73 | 13 / 30 | 9 / 19 | 46 / 30 | 43 / 17 |

Deposits include ordinary leftovers as well as food from the new outings;
starting an outing does not mean it returns with a surplus. The changed
journeys also change meetings, births and pressure on supplies. Seed 7 has
many more births and deaths, so its extra living person at the end says
little about how comfortable life became. These are new routines with real
costs, and the two-meal trigger is a first rule to watch.

Saved runs and HTML viewers are in `runs/provisioning/checked/`, with fresh
`-off` baselines beside them. The viewer records departures, interruptions
and returns, and the inspector shows whether someone is gathering for home
or returning. The seed-7 HTML viewer was opened through a local HTTP server;
playback, the catch, the deposit and the saved reasons were inspected.

The final full test suite passed 668 tests. Provisioning checks cover the
complete collection/deposit/meal chain, need and helping priorities, warming
before departure, local knowledge, source memory, fishing contention, shared
homes, births, deaths, moves and immutable saved outings. Recovery works
during both gathering and return journeys. All six 480-tick files verify and
replay identically; repeating seed 7 gives the same trail digest. With
provisioning off, all three runs retain the preceding source-memory worlds'
simulation records. JavaScript syntax and diff checks pass.

## Remembering empty food sources

`--source-memory on` lets each person remember when they saw a berry patch
or fishing spot with no available food. The memory lasts twenty ticks after
the latest empty sighting. Seeing stock there again clears it immediately.
Only local sight supplies those facts; an unseen refill cannot change a
person's memory.

Food choices first favour visible stocked sources, then sources not remembered
empty. Within a group, the existing distance and fishing-effort ranking applies.
If every source is remembered empty, people still use the nearest fallback.
Old memories expire, so an exhausted patch is not avoided forever. Home caches
still attract people only while visibly stocked; water choices are unchanged.

In the corrected seed 11 run, p01 sees the first berry patch empty at decision
tick 191. At viewer tick 196 they are outside its sight and choose the other
patch instead. At 198 that patch is also observed empty, so p01 heads toward
the fishing spot. They cast at 210, catch two food at 211 and eat at 212.
The source choices and reasons are recorded, and the viewer shows dated empty
memories and events when memory changes a food destination.

Tracing this exposed a birth-state omission: births were clearing the new
memories, and the earlier fishing work also lost casts through that path.
Both now survive other people's births; newborns start with neither. This can
change older fishing runs when replayed, so the comparisons below use fresh
memory-off baselines with the birth fix too. Earlier fishing examples remain
historical examples of the preceding code.

Three matched 480-tick runs:

| Seed | Viewer reroute events | Living, memory off / on | Births, on | Deaths, on |
| --- | --- | --- | --- | --- |
| 7 | 2 | 9 / 8 | 2 | 0 |
| 11 | 167 | 11 / 11 | 25 | 20 |
| 23 | 215 | 17 / 9 | 46 | 43 |

These are changed journeys, not a general survival improvement. Remembered
shortages can send people on longer searches, and every known source can be
empty. Twenty ticks is a first memory duration, not a tuned optimum. A viewer
reroute event can also mark resuming a food journey after another need; it is
not a count of unique trips or successful meals.

Runs and viewers are in `runs/source-memory/final/`, alongside fresh `-off`
baselines. The `seed11-memory-story.png` picture shows actual saved observations
and positions. Live HTML playback remains unverified here because the local-file
browser restriction is still in place.

The final full suite passed 657 tests. Focused cases cover local observations,
unseen refills, fresh-stock overrides, expiry, all-empty fallback, fishing,
child travel limits, immutable memory, births, old headers, deterministic
repeat runs and recovery with memories present. All six fresh on/off runs
verify and replay identically. JavaScript syntax and diff checks pass, and
the static saved-run picture has been visually checked.

## Fishing through the lean season

`--fishing on` adds one bank fishing spot on clear ground near the west edge.
It leaves the existing homes, berry patches, wells, groves and terrain in place.
The spot starts with six food and gains two every twelve ticks, up to six,
in both plentiful and lean seasons. Berry wear does not reduce fish renewal.
This is a small seasonal alternative, not a full river or fish ecology model.

People know where the spot is, but only see its stock within sight. Their
existing food-source choice includes it, with one extra tick of gathering
effort. A hungry person casts from the bank for one tick, then can catch on
the next consecutive tick. Another action interrupts the cast. Catches use
the normal claim size and settlement rules: two people cannot take the same
last fish. Catching does not also eat. Fish become ordinary carried food and
can be eaten, stored or given away through the existing rules.

The viewer draws a blue fishing spot with visible stock, a rod while casting,
and catch events. Its inspector explains the steady replenishment. A depleted
spot can leave people waiting or choosing another source. Optional empty-source
memory now guides those choices, as described above. Home-location
ranking still uses the existing berry and water landmarks.

In seed 23, p06 casts at tick 89 and catches three food at 90. One is eaten
at 91, one deposited in the home cache at 98, and the remaining unit given to
their child p18 at 112. No other food reaches p06 between that catch and gift.

Three 480-tick runs add only fishing to the preceding wood worlds:

| Seed | Catches | Food caught | Catches in lean seasons | Living, fishing off / on |
| --- | --- | --- | --- | --- |
| 7 | 25 | 68 | 14 | 7 / 9 |
| 11 | 37 | 78 | 20 | 2 / 13 |
| 23 | 33 | 70 | 21 | 4 / 22 |

These runs show fishing being used in both seasons and a substantial change
in population. They do not establish a balanced food supply: fishing adds
food to the map, and births also change. This first version has no boats,
equipment requirements, skills, freezing water or separate fish inventory.

Final saved runs and HTML viewers are in `runs/fishing/final/`. Focused checks
cover cast/catch/eat timing, interrupted casts, contention for the last fish,
local stock visibility, the child leash, seasonal renewal and stock caps,
scored choices, immutable saved state, deterministic repeat runs, replay and
recovery from the middle of a cast.

The full regression run passed 647 tests. After making casting an explicit
candidate action in the saved decisions, all 26 focused fishing and scoring
tests passed. The three final runs replay identically. JavaScript syntax and
diff checks pass. The static saved-run picture `seed23-fishing-story.png`
has been visually checked; live HTML playback remains unverified here because
the browser's local-file restriction is still in place.

## Review repairs

Claude's independent review of `c1d13cb` found that early food departures and
walking while asking could bypass the child leash. Local regression checks
also found that a terrain detour could step outside it. These paths now obey
the documented distance limit. Children may still ask while staying home or
returning home, and can travel to reachable food and water. The saved rule
text changed: old childhood runs remain readable, but are a different rule
set and are not replayed as the corrected world.

The routing switch now round-trips through run headers, including when
terrain is off. New `--routing off` runs replay and recover after truncation.

All quantitative results below this correction are historical unless stated
otherwise. The earlier childhood and spacing comparisons used the leaky
leash. The review also reports route tie flips affecting memory comparisons
and adult offspring included in child-feeding totals. Both are now fixed,
but those earlier measurements have not been redone. Do not use those
numbers to judge the corrected childhood or learning rules.

Food promises now end only on delivery to the promised recipient, either
person's death, or loss of sight. Dead askers cannot receive new agreements.
Child-first handoffs apply only below adulthood, and new homes avoid rough
ground and shelter spots. Equal-cost routes keep the straight first step.
Saved rule descriptions now reflect these changes.

The map viewer closes ended errands, identifies stale promises in older
files, counts water crowds at the water source, and can show the verified
prefix of a damaged sealed run with a visible warning. Text output handles
births. The older fixed-roster viewer explicitly refuses changing populations
instead of silently omitting newborns.

After the first leash repair, before the remaining repairs, 400-tick runs
with requests off ended as follows:

| Seed | Spacing | Births | Alive | Deaths |
| --- | --- | --- | --- | --- |
| 7 | 0 | 7 | 12 | 1 |
| 7 | 30 | 3 | 9 | 0 |
| 11 | 0 | 24 | 11 | 19 |
| 11 | 30 | 9 | 7 | 8 |
| 23 | 0 | 18 | 12 | 12 |
| 23 | 30 | 7 | 5 | 8 |

Every recorded child move in those six runs stayed within the leash. The
later promise, terrain-placement and route repairs can change these results
again. Fresh 400-tick requests-on runs for seeds 7, 11 and 23 replayed
identically and retained no promises involving dead or out-of-sight people.
The original review packet remains an unchanged snapshot of `c1d13cb`, not
of these repairs.

## Families after the review repairs

These are fresh 400-tick runs at `81cbd39`, with requests off and all other
settings at their defaults except birth spacing. All six files verified and
replayed identically. Child feedings count recipients below adulthood at
the start of the transfer tick; peak dependents counts living children
assigned to the same recorded parent.

| Seed | Spacing | Births | Alive at 400 | Deaths | Peak dependents | Child feedings |
| --- | --- | --- | --- | --- | --- | --- |
| 7 | 0 | 5 | 11 | 0 | 4 | 2 |
| 7 | 30 | 3 | 9 | 0 | 1 | 3 |
| 11 | 0 | 23 | 7 | 22 | 7 | 10 |
| 11 | 30 | 10 | 6 | 10 | 2 | 11 |
| 23 | 0 | 15 | 5 | 16 | 11 | 6 |
| 23 | 30 | 8 | 8 | 6 | 2 | 8 |

Spacing reduces overlapping dependents in these three seeds. It does not
uniformly increase the final living population, and fewer births also mean
fewer people can die. Keep spacing optional; these runs do not pick a best
setting. Local files and viewer pages are in
`runs/post-review-families-81cbd39/` and are not tracked in Git.

**The encounter behind nearby caregiving.** In
seed 7 with spacing zero, p01 sets off to feed their child p07 at tick 217.
At tick 218 the parent still holds one food. At tick 219 a handoff is eligible,
but the parent heads home instead: cold is 23 at the decision point and home
is two steps away. Playback and the inspector show the interruption directly.

**Nearby caregiving now finishes before an early warmth trip.** A parent
below their own hunger, thirst and cold thresholds can hand one food to an
empty-handed dependent on the same or an adjacent cell before heading home
early. A water trip still comes first. This gives no extra time to a walking
errand and changes neither the child leash nor the kernel transfer. The
inspector explains the handoff; ordinary child-feeding descriptions now say
the child has no food instead of incorrectly calling every child starving.

Fresh 400-tick runs with requests off and spacing zero show:

| Seed | Births | Alive at 400 | Deaths | Child feedings before / after |
| --- | --- | --- | --- | --- |
| 7 | 6 | 11 | 1 | 2 / 5 |
| 11 | 23 | 7 | 22 | 10 / 10 |
| 23 | 15 | 5 | 16 | 6 / 6 |

In seed 7, p01 hands food to p07 at viewer tick 219. The child is not hungry
yet: they carry it home and eat at tick 226. The parent gives away their last
food just before becoming hungry, gathers more, eats at tick 228 and reaches
home at tick 234. Over viewer ticks 219–240 the parent's peak hunger rises
from 25 to 33 and peak cold from 25 to 38 compared with the earlier run.
One additional birth and a later death leave the final population unchanged.
This is help with a cost, not an overall survival improvement.

Only seed 7 used the new priority in these runs. Seeds 11 and 23 have exactly
the same recorded world states and settlement records as before. All three
new files verify and replay identically; a second seed-7 run has the same
trail digest. The full test suite passed (519 tests).

Files and viewer pages are in `runs/nearby-caregiving-final/`. The generated
viewer includes the child-feeding event at tick 219 and its recorded reason.
Browser automation blocked the local HTML URL, so the new playback has not
been visually inspected. Older childhood files remain readable in the
viewer; their different saved rule description prevents replay as this rule.

**Next: watch the price of giving away the last food.** Follow p01 and p07
through viewer ticks 217–240 in the new seed-7 page, alongside the earlier
run. The child gets fed, but the parent gives away tomorrow's meal. Watch
that choice before adding another caregiving rule.

## Remembering who helped

People now remember the four most recent distinct people whose food actually
arrived through a successful transfer. Each memory carries the completed
tick of the gift. Another gift from the same person refreshes that entry;
a fifth distinct donor replaces the oldest, with donor ID breaking ties.
Memories do not expire with time or reveal where someone is. A dead donor
can remain in the person's history but cannot be chosen as a recipient.

When choosing unsolicited help for someone visibly starving, a person
prefers a remembered donor, then distance and ID. Own needs, dependent
children, direct answers and existing promises keep their priorities.
This is on by default; `--social-memory off` restores the previous choice.
Asking stays off by default. Food and water collection amounts are unchanged:
people already collect up to three of each per visit, with no separate
carrying-capacity limit.

The inspector has a **People who fed me** section with links to the original
gift ticks. When memory changes the chosen recipient, the decision records
the earlier gift and the event list calls out the choice. The viewer reads
these records; it does not calculate a relationship or choose a recipient.

Two ordinary seeded runs show different consequences:

- Seed 14: p03 feeds p10 at tick 534. At tick 643, p10 chooses p03 instead
  of p01 because of that gift. Both choices initially lead along the same
  route, and both versions eventually feed p03 at tick 649. The intended
  recipient changes, but this example does not show a different delivery.
- Seed 26: p02 feeds p22 at tick 588. At tick 774, p22 walks west toward
  p02; without memory, p22 walks east toward nearer p06. This is the first
  physical difference between the paired runs. Cold repeatedly interrupts
  the remembered errand. With memory off, p22 feeds p06 at tick 781. With
  memory on, p22 eventually feeds p21 at tick 785 instead. Remembering help
  changes movement and who gets food, but does not guarantee repayment.

At tick 850, seed 26 has 7 living people and 21 deaths with memory, compared
with 11 living and 22 deaths without it. Births also differ, so these totals
are not a simple survival benefit or penalty. Seed 14 ends tick 800 with
9 living and 9 deaths in both versions. Seeds 7, 11 and 23 at 400 ticks
remember gifts but do not change their helping choices.

Saved runs and viewer pages are in `runs/social-memory/`. The seven runs
verify and replay identically, and a repeat of seed 26 with memory has the
same trail digest. Tests cover accepted versus rejected transfers, food
versus water, personal observation, bounded immutable memory, newborns,
old files, recovery, and the changed choices in seeds 14 and 26.
The full suite passes (536 tests), and the viewer JavaScript passes its syntax
check. `seed26-choice.png` is a visually checked static map of the recorded
opposite steps at tick 774.

Browser automation still cannot open the local HTML pages, so the new
playback and inspector have not been visually checked. **Next: follow p22
in seed 26 through ticks 774–785, then jump back to the gift at tick 588.**
Watch whether favouring an old helper is an interesting cost before adding
more relationship rules. Refusals, trust and friendship are not built yet.

## Food patches wear and recover

Local regrowth is available with `--regrowth on`. The existing default remains
off. Each food patch starts at condition 100. Every unit actually harvested
costs 10 condition, floored at zero; a tick with no successful harvest restores
one, up to 100. Rejected claims, drinking and eating carried food do not wear
a patch. Standing at an empty patch does not prevent recovery.

Below condition 50, a patch grows half its usual renewal amount, rounded up.
With the normal settings that means one food instead of two every 15 ticks.
Quiet recovery to 50 restores the full amount. The update happens after
harvesting and before renewal, so a harvest on a renewal tick counts. Stock
caps still apply; zero renewal stays zero; water and carrying amounts are
unchanged. Food production still has an explicit recorded source and amount.

This first rule changes how much grows at each renewal, not the renewal
schedule. People continue to choose from visible stock; they do not know the
hidden condition or predict when a patch will recover. The viewer shows the
recorded condition in the source inspector and summary. Worn bushes have
smaller, browner foliage, while berries still represent actual food stock.
The event list marks patches becoming worn and recovering.

Seed 7 shows the local cycle clearly: the first patch is picked empty at
tick 44. At tick 45 it grows one food, while the healthier second patch grows
two. The first patch reaches condition 50 at tick 75 and grows two again.
The next harvest wears it down again. At tick 52, p01 changes destination
from the empty first patch to the stocked second patch using the existing
source-choice rule. This is a recorded journey, not a new migration rule.

Fresh 400-tick runs, with all other settings at their current defaults:

| Seed | Food grown, off / on | Births, off / on | Living, off / on | Deaths, off / on |
| --- | --- | --- | --- | --- |
| 7 | 89 / 74 | 6 / 0 | 11 / 6 | 1 / 0 |
| 11 | 103 / 69 | 23 / 11 | 7 / 2 | 22 / 15 |
| 23 | 102 / 72 | 15 / 14 | 5 / 7 | 16 / 13 |

The rule reduces food supply in all three runs, but the population effects
differ. It prevents births in seed 7, leaves very few people in seed 11,
and leaves more alive in seed 23. These outcomes are a reason to keep it
optional while watching the effect, not to tune the seeds into success.

Files are in `runs/local-regrowth/`. All six files verify and replay
identically. The focused checks cover harvest accounting, independent
patches, caps, recovery, births, saving, replay and truncation recovery.
The full suite passed with 556 tests. The static chart `seed7-recovery.png`
has been visually inspected. Browser automation still blocks local HTML,
so the new foliage and inspector have not been checked in live playback.

The early patch cycle is visible in seed 7 through ticks 40–76, selecting
the first food patch. Larger supplies and seasons have since been tried
below. Remembering an empty patch is still not implemented.

## Larger supplies and food seasons

Larger supplies use the existing settings: `--source-stock 8 --source-cap 16
--renewal-amount 3`. In the previous 400-tick comparison, increasing just
starting food and storage had mixed results. Increasing renewal too left
10, 5 and 10 people alive in seeds 7, 11 and 23, compared with 6, 2 and 7
under the smaller supplies with local regrowth on. These are optional run
settings; the default remains 4 starting food, capacity 8 and renewal 2.

Seasons are available with `--seasons on`. The world starts plentiful, turns
lean at completed tick 120, plentiful at 240, and continues alternating
every 120 ticks. Plentiful growth is 150% of the base amount rounded up;
lean growth is 50% rounded down. With base renewal 3, that is 5 and 1.
Local patch wear applies afterwards, so a worn patch produces 3 and 1.
Zero growth stays zero. The existing renewal cadence and storage cap still
apply, and each produced unit is recorded. Water, cold and the rate at
which patches recover are unchanged.

The completed tick's season applies to renewal on a boundary tick. Season
state is saved in the world, survives births, and is restored during replay
and recovery. Older runs omit it. People do not receive knowledge of unseen
food or a forecast: they respond to available stock through their existing
decisions. Seasons remain off by default and can run with or without patch
wear. The viewer shows the recorded season above the map, its growth
allowance in the source panel, and an event at each change.

Fresh 480-tick runs use the larger supplies and local regrowth in both
versions. Everything except seasons is held the same:

| Seed | Births, steady / seasonal | Living, steady / seasonal | Deaths, steady / seasonal |
| --- | --- | --- | --- |
| 7 | 5 / 0 | 11 / 6 | 0 / 0 |
| 11 | 26 / 20 | 14 / 4 | 18 / 22 |
| 23 | 22 / 22 | 6 / 5 | 22 / 23 |

The supply cycle matters, but is harsh. In seed 11 both patches are empty
at tick 239. At 240 the plentiful season begins and each grows three food;
eight people have chosen to wait at food sources on that tick. Population
continues falling after growth returns. By tick 359 the second patch is
full again, with only four living people in the world. More food later
does not automatically restore the previous population.

Files and viewers are in `runs/seasons/`. All six files verify and replay
identically; the earlier seed-7 larger-supply file still replays unchanged.
The full suite passes with 578 tests, including season boundaries, rounding,
patch wear, caps, zero growth, births, old files, replay and recovery across
a season change. Viewer JavaScript passes its syntax check. The static
`seed11-seasons.png` chart has been visually inspected; live HTML playback
is still unverified because local browser access is blocked.

Watch seed 11 through ticks 119–150 and 239–260 to see the season changes. Select a patch
and follow the waiting people as lean growth arrives and plentiful growth
returns. Shared home caches have since been added below; people still do not
plan for the next season.

## Shared food caches at homes

`--stores on` gives each founding home an initially empty food cache. After
building the shelter, its adult resident can put spare carried food there
instead of resting. They keep one meal and fill towards six food. Their
own needs and existing helping choices come first. With provisioning off,
this rule stores leftovers from ordinary food trips. Optional provisioning
adds trips prompted by a low cache, as described above.

Anyone who sees a stocked cache at a completed shelter can choose it alongside
the food patches, by distance then source ID. They must walk to it and spend
a tick collecting, then spend another tick eating. Children still obey their
leash. Empty and unseen caches never attract a trip. These are shared caches,
not private family property. With adult homes off, only the founding resident
deposits; with adult homes on, anyone living there can deposit. Neighbours and
children can collect. Caches persist after the resident dies. Newborns do
not create caches until they choose an adult home. Water storage, spoilage and carrying
limits are not added.

Food remains in the kernel ledger. A new immediate `deposit` proposal debits
the person's holding and credits the cache; ordinary `claim` takes it back
out. Deposits cannot be reserved, and credited food becomes available on the
next tick. Caches never receive production and never count as growing patches.
They start empty, so enabling them adds no food. The filling target is a world
decision rule, like the existing patch renewal cap; it is not a new kernel
account capacity.

The viewer draws a small food box beside each completed founding shelter,
shows its stored food, and lists deposits and collections. Its inspector
explains that food must be carried there. Stores are off by default; older
run headers and behavior remain unchanged when they are off.

**A neighbour's food reaches a child.** In seed 11, p06 puts one food in their
cache at tick 44. Child p08 drinks first at tick 45, walks from (2, 9) to
(3, 11) over ticks 46–48, collects the food at 49 and eats at 50. Hunger falls
from 33 to 4. The child's recorded parent is p03, so this is a neighbour's
stored meal reaching a child without a request or direct handoff. In the same
run, p09 collects from p05's cache at tick 49 and p12 does so at tick 105.

Fresh 480-tick runs use source stock 8, source capacity 16, renewal 3, patch
wear and seasons. Each baseline is the earlier matching seasonal run:

| Seed | Food deposited | Food collected | Collections by others | Collections by children | Living, off / on | Births, on | Deaths, on |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | 24 | 24 | 15 | 0 | 6 / 10 | 4 | 0 |
| 11 | 9 | 8 | 3 | 3 | 4 / 3 | 19 | 22 |
| 23 | 9 | 7 | 2 | 1 | 5 / 4 | 18 | 20 |

Collection columns count events, not distinct people. Child age is checked
before collection. This is useful local sharing with mixed population
effects, not a general cure for lean seasons. In seed 7, p05 collects from
p02's cache at tick 89 and p02 later collects from p05's at tick 109; neither
exchange was prescribed as repayment.

The three new runs and all three older baselines verify and replay identically.
The full suite passes with 596 tests. Checks cover deposit conservation and
refusals, delayed credit, competing claims, local sight, needs and helping,
children, births, no cache production, single-patch worlds, old headers,
deterministic repeat runs and recovery after a deposit. JavaScript syntax and
diff checks pass. A fresh code review found no remaining accounting issue in
this change; this was a review by the builder, not an independent review.

Files and viewers are in `runs/home-stores/`. The static picture
`seed11-child-cache.png` has been visually checked. Automated live HTML
playback remains blocked by the browser's local-file restriction.

**Next: watch seed 11 through ticks 44–52, following p08 and store-p06.**
Then follow the two-way use of neighbours' caches in seed 7 at ticks 89 and
109. Purposeful supply trips are now available with provisioning on, as
described above. Residents respond to a low cache; they do not forecast the
next lean season or stock up to a seasonal plan.

## Grown children choose an adult home

`--homes on` lets grown children make one housing choice after their immediate
needs and helping errands are satisfied. They look at visible finished
shelters with room and clear sites. Finished shelters come first, then short
routes to the known food and water landmarks. There are two resident places
in a finished shelter. Arrivals competing for the last place use the same
rotating order as the rest of the tick.

People walk to their chosen site and keep their old home until they arrive.
They remember the destination through interrupted journeys, but choose again
if they see that it is no longer available. They can join an occupied home,
reuse an empty shelter, or establish a home on clear ground, including their
own childhood plot. Joining a finished shelter makes it usable immediately;
a bare site still needs the usual building work.

With `--stores on`, a newly established home gets an empty cache and residents
can refill the same cache. Food at the old home stays there. Cache creation
is recorded separately from food production and adds no resources. Six food
is a refill target: two residents depositing together can go above it.
The viewer follows the current home and housemates and lists journeys,
successful moves, and unsuccessful arrivals.

**A full home changes p08's destination.** In seed 11, p08 grows up at tick 76
and walks to a spare place at (3, 10). At tick 78, p07 takes that last place
first. p08 then walks to (3, 11) and joins p06 at tick 80. At tick 124, p08
stores one spare meal in the shared cache there.

**An adult home becomes a place to find food.** In the same run, p10 chooses
their childhood plot at (3, 8) as their adult home at tick 144, finishes the
shelter at 178, and stores food at 289. Another adult, p24, collects it at 299
and eats at 300. New storage is now useful beyond the founding households.

Fresh 480-tick runs use the earlier store worlds, changing only adult homes:

| Seed | People settling into adult homes | New caches | Living, homes off / on | Births, on | Deaths, on |
| --- | --- | --- | --- | --- | --- |
| 7 | 1 | 0 | 10 / 7 | 1 | 0 |
| 11 | 9 | 4 | 3 / 3 | 20 | 23 |
| 23 | 12 | 3 | 4 / 14 | 27 | 19 |

These runs show different household and population patterns, not a general
survival improvement. All three new runs and all three earlier comparisons
replay exactly. The full suite passed 611 tests; the final housing and viewer
checks passed 30 tests, including two additional cache edge cases. Those
checks cover local choices, physical arrival, competing arrivals, death,
cache accounting, old headers, deterministic repeat runs and recovery.

Saved runs and HTML viewers are in `runs/adult-homes/`. The saved-data picture
`seed11-adult-homes.png` has been visually checked. Live HTML playback remains
unverified because of the browser's local-file restriction.

Adult homes are off by default. The first housing choice now has an optional
follow-up: relocation after difficult supply outings, described below. Water
storage and purposeful supply trips remain separate possible additions.

## Relocation after difficult supply outings

`--homes on --relocation on` lets adults consider moving after repeated
difficult outings. They count their actual ticks walking, waiting, asking or
collecting food and water while away. Returning home ends the outing. Eight
or more supply ticks raise home strain by one, up to three; a shorter supply
outing lowers it by one. Ordinary return travel and helping someone else do
not count as supply effort.

At strain three, an adult can choose a finished shelter they remember seeing
with room. Its combined distance to the nearest food and water landmarks must
be at least three steps shorter than the current home's. Shelter vacancies
are refreshed only in sight; people do not know whether a distant remembered
place has filled. They recheck room as they approach and when they arrive,
and drop a destination they see is full. Arrivals still compete for two
resident places in the existing rotating order.

Needs and helping interrupt moves. At home, a person preparing to relocate
warms fully before taking a relocation step. A food or water need can still
call them away first. During the journey, a chosen finished shelter can
replace the old home as the warmth destination once it is no farther away.
Without that connection to warmth, the first runs showed people repeatedly
starting a move and retreating to their old home, with no completed moves.

A move changes home only after physical arrival. The old shelter, cached food
and family links stay in place. Effort and strain reset, and another move must
wait at least 120 ticks. The same wait applies from genesis and from a grown
child's first home choice. Adults with living dependent children stay put;
moving whole families is not included in this rule.

**p06 leaves a costly location.** In seed 7, p06 returns from outings with 16,
9 and 21 supply ticks at ticks 42, 73 and 145. Shorter outings later ease the
strain, but another costly outing brings it back up. At tick 209, p06 chooses
the remembered shelter at (2, 3). Needs interrupt the journey, including a
return to the old home, before p06 arrives and joins p02 at tick 235.
The old home at (9, 11) and its shelter remain.

After the move, p06's first four completed supply outings take 7, 2, 16 and 1
supply ticks. The new location changes daily travel, but does not eliminate
costly trips. These are recorded actions, not an estimate of travel time or
a claim that moving improves everybody's survival.

Fresh 480-tick runs change only relocation from the earlier adult-home worlds:

| Seed | Completed moves | Move | Living, relocation off / on | Births, on | Deaths, on |
| --- | --- | --- | --- | --- | --- |
| 7 | 1 | p06, tick 235 | 7 / 6 | 0 | 0 |
| 11 | 1 | p03, tick 217 | 3 / 4 | 20 | 22 |
| 23 | 1 | p02, tick 363 | 14 / 14 | 26 | 18 |

The viewer shows the chosen home, a line to it for the selected person,
remembered shelters, effort on the current outing, strain, and completed
moves. All three final runs and their three earlier comparisons replay
exactly. The full suite passes with 626 tests; JavaScript syntax and diff
checks also pass. Focused checks cover real effort, local and stale knowledge,
dependent children, warmth, competing arrivals, resource preservation,
deterministic repeat runs and recovery during a relocation journey.

Final runs and viewers are in `runs/relocation/final/`. The saved-data picture
`seed7-relocation.png` has been visually checked. Live HTML playback remains
unverified because of the browser's local-file restriction. Relocation is
off by default. The thresholds are starting rules, not tuned settings.

## Wood gathering and construction costs

`--wood on` adds a material chain to shelter building. Adults without a finished
home walk to a wood grove, gather up to three wood, carry it home and spend it
as they build. Needs, helping and housing choices still take priority.
Children do not gather wood or build.

One wood pays for each group of four work ticks: a normal twelve-tick shelter
costs three wood, paid before work ticks 1, 5 and 9. The payment uses the
existing named-resource ledger. If settlement refuses it, construction makes
no progress. Paid work stays completed when hunger, thirst or cold calls the
builder away. Used wood remains accounted for in its consumption sink.

There are up to two groves on clear cells outside existing homes, food sources,
wells and shelter spots. Enabling wood does not change founding homes, traits
or terrain. Each grove begins with twelve wood and regrows one every forty
ticks, up to twelve. Grove locations are known landmarks, but only nearby
stocks are visible. People prefer a visible stocked grove; otherwise they try
the nearest. Wood growth is independent of food seasons and patch wear.

**p05 carries a project through interruptions.** In seed 7, p05 gathers three
wood at tick 11. At tick 28, back home, the first wood pays for the first group
of work. Food calls p05 away after three work ticks; that progress and the two
carried wood remain. Further payments occur at ticks 45 and 49, with a drink
interrupting work at 50. The shelter is finished at tick 53.

Fresh 480-tick runs change only wood from the earlier relocation worlds:

| Seed | Wood gathered | Wood used | Shelters completed | Living, wood off / on | Births, on | Deaths, on |
| --- | --- | --- | --- | --- | --- | --- |
| 7 | 18 | 18 | 6 | 6 / 7 | 2 | 1 |
| 11 | 18 | 18 | 6 | 4 / 2 | 18 | 22 |
| 23 | 24 | 24 | 8 | 14 / 4 | 14 | 16 |

Building now competes for time and resources, with consequences for household
formation and survival. These three seeds show mixed population effects;
they do not establish a balanced construction cost.

The viewer draws groves and carried wood, shows grove stock and total wood
used, and lists gathering and construction payments. All three new runs and
their three earlier comparisons replay exactly. Focused checks cover resource
conservation, competition, refused payments, interrupted work, growth caps,
children, unchanged starting layouts, old headers, deterministic repetition
and recovery after gathering. The full suite passes with 638 tests; JavaScript
syntax and diff checks also pass.

Runs, viewers and the visually checked `seed7-wood-construction.png` are in
`runs/wood/`. Live HTML playback remains unverified because of the browser's
local-file restriction. Wood is off by default and requires building to be on.
Wood storage, trading, salvage, repair and practical skills are not included.
Building progress remains personal as before; abandoned unfinished work is
not a transferable project, and spent materials are not recovered.

## Working direction

This is the current working list of things to try. The order reflects our
present priorities and can change when watching the world reveals a better
direction. AGENTS.md remains the project brief. This document introduces no
approval requirements, stage gates, fixed run budgets or extra paperwork.

"Civilisation aquarium" describes the kind of world we are building. The
project is called Simulation 3.

## 1. What already exists

The foundation below was checked against the code as this was written.

**A deterministic grid world.** People occupy a 12x12 grid. Each tick every
living person observes what is near them, decides from that observation
alone, the kernel settles whatever moves resources, and world processes
apply movement, needs, death, renewal and births. The same seed always
produces the same world, and a saved run replays to the same result.

**Three needs.** Hunger, thirst and cold. Each rises on its own schedule and
kills at its own level. Cold falls again while a person is on their home
cell. When more than one need is calling, a person serves whichever will
kill them soonest at the rate it is rising.

**Food and water sources.** Two food sources and two wells at fixed places,
each renewing on its own cadence up to a cap. Optional local regrowth makes
harvested food patches produce less until they recover. People walk to a source, claim
a pack of units, carry them, and eat or drink later. Claims are settled by
the kernel, so two people wanting the last unit cannot both have it.

**Rough ground and shelter spots.** Roughly a fifth of the grid is rough
ground, which costs an extra tick to cross. A few cells are shelter spots,
where hunger and thirst rise more slowly. Sources and homes are always open
ground. Terrain is drawn from its own generator, so changing a terrain
setting never moves anybody's home.

**People build shelters.** With no need calling and standing at home on bare
ground, a person works on a shelter. It takes several ticks of work, and
work already done is kept when a need calls them away, so shelters go up in
snatches between trips. Optional wood construction adds gathering and material
payments. A finished shelter is permanent and slows hunger and thirst for
whoever stands on it.

**People carry food to someone visibly starving.** Distress is visible: you
can see that somebody nearby is in a hunger or thirst emergency, though not
how bad it is. Someone with nothing of their own calling and a spare unit in
hand will walk to the nearest visibly starving person and hand over one
unit. The handover is a kernel transfer and can be refused.

**Births and a changing population.** When two people whose homes have finished
shelters, and who are neither hungry nor thirsty nor cold, stand on
adjacent cells for a few ticks running, a new person arrives with a home on
the nearest free cell. They hold nothing: a birth creates no food and no
water. A run whose roster changes still seals, verifies and replays.

**Childhood.** Somebody born into the world is a child until they have lived
adult_at ticks. A child will not go more than child_leash steps from home for
food or water, builds nothing, and is nobody's partner, so the newly born
cannot immediately have children of their own. A parent who is free and
holding food takes a unit to their own child — in view and carrying none —
before anybody else. Everybody at genesis starts grown.

It steadied the world more than anything else so far. Because a child cannot
breed for sixty ticks, the population stops overshooting its food and then
collapsing: over 400 ticks, seed 11 went from 5 alive of 41 to 10 of 22, and
seed 23 from 28 of 75 to 20 of 33 — fewer people, but the share of them alive
at the end rose from about a third to two thirds, and on seed 7 to nine tenths.
About four children in ten still die before growing up, most of them born too
far from a source for the leash to reach and dependent on somebody
remembering them.

**Walking round remembered rough ground.** A person heading anywhere picks
their way round the rough ground they can see or remember, counting a known
rough cell as two ticks and everything else as one. Ground nobody has seen is
still treated as open. Only the edge of sight is judged for brand-new ground:
measuring a cell in the middle of what they can see would pretend the rough
beyond it was not there, and a cell just short of a wall would look like the
best place on the map. Going round one rough cell costs more than crossing
it, so nobody bothers; a run of three is worth avoiding, and that is the case
this exists for. `--routing off` restores straight-line walking.

It made a large difference. Over 400 ticks the time people spend bogged in
rough ground fell by about nine tenths — 321 stuck ticks to 17 on seed 7, 739
to 116 on seed 23 — and three seeds of four ended much better off, seed 7
going from 5 alive of 6 to 14 of 18 and seed 23 from 12 of 53 to 28 of 75.
Seed 11 went the other way, 24 of 62 down to 5 of 41: a more efficient world
breeds faster and can overshoot its food. The 50-person cost check still meets
every target.

**Asking for food, built but switched off.** `--requests on` gives a hungry
person holding nothing the ability to ask somebody they can see carrying food
for it. Asking is speech: they call out and walk on, so it costs no tick. The
person asked answers next tick, and agrees only if nothing of their own is
calling, they hold a unit, and they are not already carrying one for somebody
else. An agreement is held in the world state until the unit is handed over
or they lose sight of the asker, so an errand once taken on is not dropped
for a nearer stranger. The handover is a kernel transfer. The whole exchange
is in the viewer: who asked, who agreed, who went unanswered, who delivered.

It is off by default because it costs the world more than it gives, and three
separate attempts to make it pay have failed.

The first version charged the asker a tick, which was fatal: they stopped to
ask, almost nobody was ever free to answer, and populations died of the delay.
Making asking free, and then refusing free as well, did not rescue it — seed 11
still went from 24 alive of 62 to 3 of 25.

That looked like a brittle birth rule, so we tried letting time together decay
by a tick on separation rather than resetting to nothing. It did not recover
the lost births, and it made the world worse without asking at all: seed 11
fell from 24 survivors to 6, because pairs barely together accumulated enough
credit to breed anyway. Reverted.

The third attempt came after routing and childhood had made the world much
steadier, on the theory that it could now afford the cost. It cannot. Over 400
ticks seed 23 went from 20 alive of 33 to 9 of 21, seed 11 from 10 of 22 to 6
of 23, and on seed 11 the number of children dying before they grew up rose
from 7 to 13. That last number named the mechanism: an adult away on a
stranger's errand is an adult not feeding their own child. A kin-first rule —
nobody with a dependent child takes a stranger's errand — saved some of those
children, 10 deaths down to 8 on seed 23, but not the world: 20 of 33 became
7 of 18.

So this is settled rather than open. Carrying food to somebody takes many ticks
away from home, and those are the same ticks that feed children and make new
ones; a dozen delivered units does not pay for them. The kin-first rule was
kept, because it is right on its own terms and costs nothing while asking is
off. What might yet make asking worth it is a cheaper kind of help: handing a
unit to somebody already beside you, with no journey at all.

**A map viewer.** `world/viewer.py` renders a saved run as a self-contained
HTML page: an isometric diorama of the world you can play, step and scrub
through. Terrain, bushes whose berries are their stock, wells whose water
level is theirs, homes and the shelters going up on them, and people who
show what they are doing, what they carry and which needs are pressing.
Asking, answering, errands and handovers are drawn between the people
involved. A list of what happened jumps to any moment, and an inspector
follows one person through time. `world/viewer_index.py` reads the saved
file once into those events, and `viewer.js` and `viewer.css` draw them. It
never runs the world, and the older table-and-chart record is still there
under "Under the hood".

### Where these systems stop

**In the default world, help only happens when distress is seen.** With
asking switched off, a person in trouble cannot signal and nobody looks for
them. Help depends entirely on a well-supplied person happening to have
someone starving inside their perception radius while nothing of their own is
calling. Offers are consequently rare. Comparing runs with offers on and off across a handful of
seeds showed no overall gain in the number of survivors — slightly fewer, in
fact, within the noise of a few runs. That says the practice does not lift
survival overall; it does not say individual outcomes are unchanged. A unit
carried to a neighbour plainly helps whoever receives it and costs whoever
gave it.

**Memory covers terrain, received food and optional empty-source sightings.** A person remembers rough cells
for later routes and up to four people who gave them food. Former helpers
can take priority over other visibly starving neighbours. Optional source memory
retains dated empty-patch and fishing-spot sightings. People do not yet
remember refusals or unsuccessful attempts to help, and they
do not seek out a remembered person who is outside sight.

**Childhood exists, but family life is still thin.** Newborns have a parent,
an age and a period of dependency. They stay near home, do not build, do not
become parents and can be fed by their parent. Optional adult homes now let
grown children join a household or establish one. Optional relocation lets
adults move after costly supply outings. Ageing beyond childhood, moving
dependent families together, and richer family relationships are still absent.

**Other present limits.** Scored action selection cannot run alongside water
or warmth, because the scorer has no cases for their actions. The older
isometric viewer in `viewer/` predates water, warmth, terrain, shelters and
births, and shows only one food source. Shared home food caches are optional;
wood for shelter construction is optional too. There is no exchange, no other
building material, no weather and no shared rules.

## 2. How we develop: explore the primitives

A primitive is a small rule or capability with a concrete consequence:
seeing something nearby, moving, carrying, consuming, asking, refusing,
transferring, remembering an encounter, sharing shelter, or learning a
route.

Primitives can also describe the environment: travel costs, limited space,
resource depletion, regrowth and exposure to cold.

The larger domains in the next section grow through combinations of these
rules. A single useful primitive may contribute to several domains.

### The way of working

**Start with the world we can watch.** Look for an interesting event, a
repeated frustration, an unused capability, or a situation where people have
too few meaningful choices.

**Explore the rules behind it.** What can people perceive? What can they do?
What does it cost? What changes afterwards? Does that change affect a later
decision?

**Deepen or combine existing primitives where useful.** A small change to
carrying, requests, travel, shelter or memory may enrich several behaviours
at once. Add a new primitive when it provides a useful choice or consequence
that existing rules cannot express.

**Complete the interaction.** Follow it the whole way:

    need or opportunity -> local observation -> decision -> action or refusal
    -> world change -> later decision

A new field, animation or event label is only useful when something in the
world acts on it or experiences its consequences.

**Run the world and watch.** See whether people actually use the capability,
what competes with it, where it fails, and whether anything unexpected
becomes interesting.

**Explore a few meaningful conditions when useful.** Geography, resource
distribution, carrying limits, travel costs, shelter capacity and population
pressure can expose different interactions. Use reproducible runs and
describe which conditions produced what. Avoid adjusting settings solely to
manufacture a desired scene.

**Keep, deepen, simplify or drop the idea.** An interesting surprise may
become the next piece of work. A dull idea may need a better opportunity, a
stronger consequence, or removal. Use judgement rather than mechanically
completing a domain.

### Examples of combinations worth exploring

- Asking, limited supplies and the helper's own hunger can produce selective
  help, refusal or an interrupted rescue.
- A completed transfer, memory and a later partner choice can produce
  recurring cooperation.
- Travel costs, home relocation and shared storage can encourage settlement
  clusters.
- Local depletion, regrowth and remembered routes can change where people
  travel over time.

These are possibilities to explore, not outcomes to arrange. Participants and
outcomes must follow from local rules and actual circumstances.

Implement the small rules explicitly and let larger patterns develop through
their interactions. Do not hardcode particular friendships, successful
rescues, villages, occupations or population collapses.

### Keeping it practical

- No separate primitive registry or new process documents are needed.
- No generic primitive engine or speculative abstraction is required.
- Put behaviour in the subsystem that owns it.
- Use focused tests and relevant checks to protect correctness.
- Judge whether the world became more interesting by watching it.

## 3. Ten development domains

These are connected areas to explore, in our current priority order. We do
not need to finish an entire domain before following a useful interaction
into another one.

### 1. Communication and asking for help

**First behaviour.** A hungry person asks someone nearby for food. The
person asked answers from their own needs and supplies: they help or they
refuse. Follow the request through to delivery, refusal or interruption.
Water requests can follow the same shape once food requests work.

**Primitives.** Asking, answering, refusing, and a reason for the answer.
These join existing perception, distance, carrying, transfer and the
competing needs that already pull people away mid-journey. The existing
offer behaviour is the delivery half of this already: what is missing is
the request that starts it and the answer that may decline it.

**In the viewer.** A request in flight between two people, who was asked and
what they answered, a delivery arriving, and a helper turning back when
their own hunger or thirst becomes the more urgent thing.

### 2. Navigation and exploration

**First behaviour.** A person choosing a route that accounts for the extra
tick rough ground costs, rather than stepping blindly along the longer axis.
Later, exploring for a new source when the ones they know keep failing.

**Primitives.** Route cost, a comparison between routes, and remembered
terrain. Personal food departure timing now uses seen and remembered rough
ground when terrain and routing are enabled; unknown ground remains open in
that estimate. Water and shelter departure timing still use straight-line
steps. See the current travel-planning note above for its limits and tests.

**In the viewer.** Trails that bend around rough ground, two people taking
different routes to the same place, worn familiar paths, and a journey into
a part of the map nobody had used.

### 3. Life stages, families and caregiving

**First behaviour.** A newborn recorded with its parents, dependent for a
period, unable to make long trips, and fed by an adult who brings supplies
to it. Maturation into independence, and spacing between births. Ageing can
follow.

**Primitives.** Age, a parent link, dependency, and carrying food to a
specific person rather than to whoever is visibly starving. The last of
those is the same transfer primitive the request work will already have
deepened.

**In the viewer.** A household's workload changing when a child arrives, an
adult making trips on someone else's behalf, a child growing up, and a grown
child leaving to establish a home of its own.

### 4. Social memory and relationships

**First behaviour.** Remembering a small number of actual encounters — who
asked, who helped, who refused — and letting those memories influence whom a
person asks or helps next.

**Primitives.** A short dated memory of encounters, and a partner choice
that reads it. Asking would give memory far more to record — a refusal is a
sharper thing to remember than a gift — which is why asking is the earlier
priority. But memory does not wait on it: the unsolicited gifts that already
happen are real encounters, and could shape who a person walks to next.

**In the viewer.** The same pairs helping each other repeatedly,
reciprocity, someone avoided after a refusal, and a relationship visibly
changing after a particular event.

### 5. Ecology, weather and seasons

**First behaviour.** Food depleting locally where it is taken from and
recovering over time, rather than renewing at a fixed cadence regardless.
Then a simple seasonal effect on growth or on cold.

**Primitives.** Depletion, regrowth and a world-wide condition that changes
over time. These interact with the existing renewal rule and with the
leave-in-time rules, which assume a source will be there when you arrive.

**In the viewer.** A patch worked out and left bare, the same patch
recovering, journeys shifting to wherever is productive now, and a routine
that stops working when the season turns.

### 6. Households and settlement growth

**First behaviour.** Shelters that hold more than one person, with a limit
on capacity, and a real choice about moving home to a better place.

**Primitives.** Shared occupancy, capacity, and relocation. Home is
currently fixed for life and private to one person, so both are new; they
interact with building, warmth and the birth rule, which already places a
newcomer at the nearest free cell.

**In the viewer.** Clusters forming, a shelter at capacity turning someone
away, people moving toward useful places or toward company, and homes left
empty behind them.

### 7. Work, materials and practical skills

**First behaviour.** One complete material chain: gather wood, carry it,
and spend it constructing or repairing something useful. Practice at that
particular task making a person better at it.

**Primitives.** A material with a source and a use, and a per-person skill
that improves with practice. These extend the existing claim, carry and
build primitives. Optional wood construction now supplies the material chain;
building without that switch still costs only time. Practice and skills can
follow once the work itself is worth watching.

**In the viewer.** Work trips out and back, a project standing half-finished
while its builder deals with hunger, someone who is visibly the one who
repairs things, and a landscape that shows the work done on it.

### 8. Storage, exchange and specialisation

**First behaviour.** A household store that people physically carry things
into and take things out of. Then carrying limits and spoilage, so a store
is worth having. Then simple barter once different people can produce
different useful things.

**Primitives.** A place that holds resources, carrying limits, decay, and an
exchange between two people. Stores must move resources through the kernel
exactly as claims and transfers already do.

**In the viewer.** A surplus building up, a store running short, hauling
trips, an exchange between two people, and someone visibly dependent on
another person's work.

### 9. Disputes and shared rules

**First behaviour.** Once shared stores and valuable places exist, a small
local agreement about access — taking turns at a source, or contributing to
a shared store — and what people do when it is broken.

**Primitives.** An agreement, a breach, and a response to a breach. These
need the existing crowd-yield behaviour and shared stores to have something
to be about.

**In the viewer.** Turn-taking at a crowded source, an agreement breaking
down, somebody withdrawing from a group, and a different arrangement forming
in its place.

### 10. Culture and knowledge passed between generations

**First behaviour.** One useful thing — a route, a technique, a preference —
that a person can learn by watching someone else do it, and pass on in turn.

**Primitives.** Learning by observation and transmission between people.
This needs memory, and something worth knowing, so it sits last.

**In the viewer.** Different habits in different parts of the map, knowledge
travelling when its holder does, a practice outliving the person who started
it, and a practice disappearing because nobody learned it.

## 4. What to try next

Asking for food is built. It is switched off, and whether the cost it
carries is one we want is an open question rather than a settled no — a world
where people are less often at the edge might pay it easily.

Terrain-aware movement is built and on by default.

Childhood is built and on by default.

Asking was retried in the steadier world and still does not pay; see above.

Remembered terrain now changes repeat journeys. In 220-tick runs of seeds
7, 11 and 23, keeping previously seen rough cells changed the next route step
6, 1 and 11 times compared with using current sight alone. These are local
route comparisons in the same run, not claims about survival improvements.

**Direct answers beside the helper are now built.** With asking on, an
empty-handed asker alongside a free helper can receive one unit on the answer
tick. The helper still spends that tick giving, and their own needs take
priority. Feeding an empty-handed child comes first. A parent may answer
locally without taking on a journey; an existing delivery promise is kept.
The kernel settles the transfer, and the viewer records the answer and the
delivery on the same tick.

In 220-tick runs with asking on, seeds 7, 11 and 23 produced zero, one and five
direct handoffs. Seed 23's first is p07 feeding p06 at tick 87 after a request
at tick 86. This does not establish a survival benefit: walking errands still
run alongside these handoffs. Asking stays off by default.

**Nearby-only requests are available with `--requests adjacent`.** People
ask only on the same or an adjacent cell, keep walking while asking, and can
receive a direct answer next tick if still alongside. This mode creates no
requested walking errands. Unsolicited offers and feeding children retain
their existing rules. `--requests on` still permits walking errands, and
the default remains off.

Over 220 ticks, seeds 7, 11 and 23 ended with 7, 6 and 12 survivors in nearby
mode, compared with 6, 7 and 9 with walking requests. Nearby mode produced
zero, two and two direct handoffs. It is a mixed result, not a reason to
change the default. The rules also change who asks, so this comparison does
not isolate the cost of travel alone.

The most interesting nearby exchange was in seed 23 at tick 93: p10 and p11
had both asked their parent p05, who had one unit. p10 received it and p11's
request went unanswered. Cheap help still has a scarce supply to divide.

**Next: follow competing children and caregiving.** Seed 23 with asking off shows p01 setting off toward
starving p12 at tick 127, then turning home for warmth at tick 128. Both food
patches are empty. This interrupted help is the clearest next interaction to
explore. Nearby answers avoid that journey, but they do not solve a parent's
limited food or time. Watch whether spacing births gives families more room
to care for children before adding more kinds of help.

**Birth spacing is built as an optional rule.** `--birth-spacing 30` gives
both adults involved in a birth a 30-tick recovery period. Neither can
accumulate time together during recovery, even with another partner. At the
deadline they can start the usual consecutive-tick countdown again. The
deadline is saved per person and the viewer inspector shows the remaining
ticks. Zero spacing is the default and preserves the previous birth rule.
This applies to both adults, although the existing child record still names
only one caregiving parent.

With asking off, 400-tick runs gave these results. Dependents means living
children below adulthood assigned to the same recorded parent; the peak is
the largest such family at any tick in the run.

| Seed | Spacing | Births | Alive at 400 | Deaths | Peak dependents | Child feedings |
| --- | --- | --- | --- | --- | --- | --- |
| 7 | 0 | 5 | 11 | 0 | 4 | 3 |
| 7 | 30 | 4 | 9 | 1 | 1 | 3 |
| 11 | 0 | 11 | 4 | 13 | 4 | 7 |
| 11 | 30 | 8 | 6 | 8 | 2 | 10 |
| 23 | 0 | 24 | 18 | 12 | 11 | 6 |
| 23 | 30 | 8 | 6 | 8 | 2 | 10 |

Spacing reduces overlapping dependents in these runs and changes caregiving,
but it also produces fewer people. These three seeds do not establish that
spacing improves survival, and 30 ticks is an experimental setting, not a
chosen optimum. Keep it optional while exploring families. Ageing and grown
children leaving to establish their own homes can follow.

### What asking looked like, and what it cost

A complete food request, from need to consequence:

1. **Need.** A person is hungry, holds nothing, and either the source is far
   or what they can see of it is empty.
2. **Local observation.** They look at who is within their perception radius
   and identify a possible helper — somebody visibly carrying food. Distance
   matters, because a request they cannot reach is worth less than one they
   can.
3. **Request.** They call out while continuing toward food. Asking itself
   costs no tick; their needs keep rising during the journey.
4. **Answer.** The person asked decides from their own state. They may help,
   or refuse because they are hungry themselves, because they hold too
   little, or because something of their own is more urgent. A refusal is a
   real outcome with a reason, not a failure.
5. **Delivery or interruption.** If they agree, they close the distance and
   hand over a unit through the kernel, exactly as the existing offer does.
   Their own needs keep rising on the way, so they may turn back before they
   arrive.
6. **Later decision.** A unit that arrives is a chance to eat, not a
   reprieve: the asker still has to spend a tick eating it, and thirst and
   cold have gone on rising throughout. It may also arrive too late to
   matter. Whoever gave is a unit poorer and may need it themselves later.

### How it meets what already exists

The offer behaviour supplies the mechanics of delivery: finding somebody,
walking to them, and transferring a unit through the kernel's settlement
path. It does not supply an agreement. The target is worked out afresh from
the current observation on every tick, and nothing in the world state
records who a helper is on their way to. A helper part-way through a
journey will silently re-pick the nearest visibly starving person, and will
switch recipients if a nearer one appears or drop the errand entirely if the
first one leaves their view.

So a requested delivery needs a little state the offer behaviour has never
needed: an outstanding request, and the agreement it turns into, held long
enough to be completed, refused or interrupted. That is a short-lived record
of one piece of business in progress. It is not the same thing as the social
memory in domain 4, which is about remembering encounters after they have
finished in order to choose differently later.

What asking adds on top of that is the other direction of the exchange: a
person in need choosing a particular helper, and that helper giving an answer
that can be no.

Things worth exploring as it is built: perception radius decides who can be
asked at all; distance decides whether help can arrive in time; carrying
decides whether the helper has anything to give; the helper's own hunger,
thirst and cold compete with the errand and can abandon it mid-way; and the
transfer itself is already governed by the kernel, which can refuse it.

Keep resource transfers in the kernel's settlement path. A helper must
actually possess what they give, and must go on experiencing their own needs
while giving it.

The first addition should be small enough to understand by watching an
ordinary run. Depth should follow from what that run reveals rather than
being designed in advance.

## 5. Making each addition visible and trustworthy

Every addition should show up in the map viewer: requests and the answers to
them, chosen routes, family links, shared stores, changing patches, or
whatever the new behaviour actually is.

The viewer should make it possible to follow one person and understand how
earlier events shaped what they do next. It must show real world behaviour
read from the saved run, never a second calculation of what the world
decided.

These guarantees stay:

- Resource gains and losses have explicit causes.
- Settlement owns balance changes.
- Observation cannot mutate world state.
- Runs remain deterministic from a seed.
- People decide by rules, with no AI-generated choices at runtime.

Keep the emphasis on watching the world and following what is interesting.
No orchestrators, evidence pipelines, verification frameworks or
run-management systems.
