# Living World V3: roadmap

The plan, not a rulebook. Six people is the behavioural starter world; 50 is
the engineering target. The stages go in this order because each depends on
the one before. The older, fuller wording (budgets, confirmation floors, stage
cards) is in `archive/governance/ROADMAP.md` if it is ever useful again.

## Where it stands (2026-09-27)

- Stage 1 kernel: 1a (contention) and 1b (reservations) are built and passed
  independent review. 1c (sealed run files, replay, recovery, isolated
  instances) is built. Its review's two recovery bugs, F1 and F2 in
  `evidence/stage-01/review-2026-09-23-slice-1c/REVIEW.md`, were fixed on
  2026-09-25 (`tests/test_damaged_suffix.py`), and its test gaps F3 and F4
  are closed (`tests/test_seal_and_prefix.py`). 1d (the 50-actor cost check) is
  done: every target met with wide margins (`evidence/stage-01/slice-1d/`).
  All four kernel slices are built; Stage 2 (a viable world) is next.
- Ahead of Stage 2 proper, an exploratory world already runs on the kernel:
  movement, a renewable food source, hunger and death, a perception radius, a
  crowd-yield trait, scored actions and a world viewer.
- The 50-person world cost check passed on 2026-09-25, against the same
  targets as 1d (`evidence/stage-02/world-cost/`).
- Range fix (2026-09-25): people starved beyond about 8 steps from food. The
  survival window is now five times longer (hungry at 25, dead at 80, a unit
  feeds 30, renewal every 15 ticks so food per person is unchanged), a claim
  takes a pack of up to 3, and a person holding no food leaves in time to
  arrive as they get hungry. The old settings are `SHORT_RANGE_LEVERS` in
  `world/config.py`.
- Water (2026-09-25): the kernel has named resources beside the base one
  (per-resource accounts, holds and conservation), and the world has water
  and thirst as a second need. Pack carrying covers water too.
- Default world (2026-09-26): two food sources and two wells, water on. A
  person heads for the nearest source they can see with stock, else the
  nearest; a source out of sight never pulls anyone, so there is no walking
  back and forth. In 1,500-tick runs on four seeds all 6 lived, each ate about
  55 times after their starting food ran out, and a hungry person could see
  two others carrying spare food on 211 to 426 person-ticks (the one-source
  world, seed 7: 26). The old world is `ONE_SOURCE_FOOD_ONLY` in `world/config.py`,
  unchanged byte for byte, and the 50-person cost check still uses it.
- Warmth and shelter (2026-09-27), the last Stage 2 needs, opt in with
  `--warmth on`. Warmth is the only need with no resource behind it: shelter
  is a person's own home cell, cold rises by 1 on every tick that ends away
  from it and falls by 3 on every tick that ends on it, and death is at 80 as
  for the other two. Nothing is claimed, carried or consumed, so the kernel is
  not involved. When several needs call, the one nearest its lethal level is
  served, thirst then cold then hunger on ties; with warmth off that is the
  old two-need rule unchanged, and every earlier run file still replays.
  In 1,500-tick runs on four seeds, warmth on against warmth off: all 6 lived
  on three seeds and 5 on seed 3, eating was unchanged (about 53 times after
  starting food ran out), and the help moments that Stage 3 needs held up
  (196 to 433, against 204 to 411 with warmth off). Cold averaged 6 to 10 and
  peaked at 40 to 73, so the need bites without dominating.
  Open finding, not yet ruled on: the arbitration ranks needs by level over
  lethal level, which ignores how fast a need rises and how far away its
  remedy is. Thirst rises twice as fast as cold, and a well can be ten steps
  off while shelter is under your feet, so a need with plenty of time in hand
  can outrank one that is about to kill. Seed 3, p02, home at (11, 11): from
  tick 1338 to 1347 cold (50 to 61) outranked thirst (44 to 62) by level and
  sent p02 home, while the slack in each need - ticks to its lethal level at
  its own rate, less the steps to reach its remedy - was never below 18 for
  cold and fell from 15 to below zero for thirst. Walking home also took p02
  from 6 steps to 10 steps from the nearest well, so the trip destroyed the
  margin it needed. p02 died of thirst at 1356, one step short of the water,
  having been unsavable since 1347. Holding a person at shelter until they
  are warm (hysteresis) would have made this worse, not better: p02 had 9
  ticks of thirst left and warming would have taken about 20. Ranking by
  slack rather than by level is the candidate fix, and it is Ryan's call, as
  is whether warmth becomes a default like water. The levers are untouched:
  this is recorded, not tuned away.

## 1. Kernel

| Slice | Proof |
|---|---|
| 1a | Two claimants, one unit, one winner; invalid writes and observer mutation cannot commit. |
| 1b | Two-tick reserve, then complete or cancel, then release; settles exactly once. |
| 1c | Sealed run files, replay, recovery and isolated instances. |
| 1d | 50 synthetic actors within the cost targets below, against the 1a to 1c tests. |

Cost targets on the reference machine: 50 actors; mean tick at most 50 ms and
95th percentile at most 100 ms; peak memory at most 512 MiB; replay plus
decision evidence averaging at most 64 KiB per tick; memory growth at most
64 MiB between tick 1,000 and tick 10,000. State whether tick time includes
the evidence write.

### Tick algorithm

1. Freeze the tick-start state and declared boundary inputs. Build views and
   collect proposals against this boundary. People receive only their bounded
   view.
2. Validate proposal shape, unique identity, authority and preconditions.
   Reject all proposals sharing a duplicate ID, whichever arrived first.
3. Apply cancellations before completion of the same action. Cancellation
   releases its reservation exactly once. Rejecting an unrelated proposal does
   not cancel ongoing work.
4. Resolve surviving reserved completions, then new transactions. Within each
   phase, sort the tick-start actor roster by stable ID and rotate it left by
   `tick mod actor_count` (empty roster: no actor transactions). The key is
   phase, rotated actor rank, then the engine-assigned actor-local proposal
   sequence. Sequences never depend on collection order or map iteration.
5. Validate each whole transaction against remaining tick-start spendable
   balances, or its own reservation. Acceptance reduces availability at once;
   rejection leaves it unchanged. Each accepted transaction commits completely
   or not at all.
6. Commit the next state, seal the tick's evidence, publish immutable records.

New credits, production and released reservations become spendable at the next
tick start. A transaction cannot spend an incoming credit as if already held.
Reservation is neither consumption nor extra stock. Never repair an invalid
transition by clamping. Rotation is deterministic priority, not a fairness
guarantee.

Credit fixture: A owns one unit, B owns none. At tick T, A gives the unit to B
as A's first proposal and it is accepted. A's later claim on that unit is
denied, and B's consume at T is denied whatever the resolver order. At T+1, B
may consume it. Partial availability rejects an indivisible transaction.
Cancellation, completion, denial and transfer always carry explicit reasons.

### Evidence

Run files carry genesis and code, configuration and schema identities; ordered
inputs; proposal and action IDs; outcome reasons; balanced effects and
reservation changes; and a seal per complete tick. Decision records hold copies
of the inputs and alternatives actually used. Diagnostics cannot change
history. A partial file recovers only through the last good sealed tick, and
resuming must match an uninterrupted run. Replay from genesis and the recorded
inputs is the independent check.

## 2. Viable world

Six people with movement, bounded perception, food, water, warmth, shelter and
renewable resources. All of these are now built; warmth and shelter are opt
in. Levers: geometry, resource placement, renewal, starting supplies,
perception radius and consumption rates. Don't add social systems to
create need. The goal: repeated ordinary obtain-and-eat cycles after starting
food runs out, exact accounting, needs that keep rising when an action fails,
and enough moments where a hungry person can see at least two others with
spare food that asking for help becomes possible.

## 3. First social behaviour: request food

Ask, help or refuse, settled through the kernel, with memory off. Check consent
and stock at execution. Test refusal, competition, walking away, interruption
and death.

## 4. Experience changes outcomes

A small dated memory of food-request outcomes (about 32 records per person)
that changes partner choice. Show it matters by replaying a decision with that
memory hidden: the choice changes and the effect lasts in the world.

## 5. Longer-term patterns

Hold the rules fixed and watch for recurring partners, avoidance, reciprocity,
or no pattern. No pattern is a valid answer.

## 6. Next

Ryan picks the next extension.

## When something doesn't work

- No opportunity: look at the world and eligibility.
- The opportunity exists but the action loses: look at the competing scores.
- The action wins but execution fails: look at execution and accounting.
- The action completes but the consequence vanishes: trace the causal path.
- The measurement looks wrong: fix the instrument before trusting the numbers.
