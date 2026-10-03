# Consolidation of the existing world — 2026-10-03

Source: `codex/kernel-first-slice`, clean starting HEAD
`019503cfdeacee0674ca44a05ec1267b4e0cf902`, followed by the local changes described here.
At the 2026-10-03 report cutoff, nothing had been committed, pushed or merged.
Check Git for current publication status. Cultivation/live-viewer and the other
worktrees are deferred; none of their work was incorporated.

## What changed

Profiling found repeated canonical JSON encoding to be a substantial cost in
saved-world checks. `kernel/canonical.py` now uses the compiled standard JSON
encoder after the same validation, with the existing encoder as a fallback for
integers beyond Python's decimal conversion limit. Canonical byte syntax,
invalid-value rejection and the process-wide conversion limit are preserved.
This is a demonstrated saving, not proof of the entire historical 22-to-292-second
increase: that comparison involved different suites and configurations.

The care-by-need early-warmth handoff selected the right child but replaced the
reason with a generic handoff description. `world/decide.py` now retains the
priority reason before explaining the warmth tradeoff. Off-mode wording is exact;
targets, settlement, defaults and schemas are unchanged. Older care-by-need-on
files that exercise this path remain readable but can differ on their recorded
reason during replay. Recovery already requires matching code identity.

Eighteen existing extended saved-world test functions (19 cases) have an explicit
`long_run` marker. Their assertions and horizons are unchanged. The new saved
asking checks and memory continuation check also use it. Plain pytest still runs
everything; short replay, accounting, configuration and browser-security checks
remain in the fast selection. No automatic CI or test exclusion was installed.

## Measured checks

Windows, Intel Core Ultra 9 285K, CPython 3.12.14, pytest 9.1.1, Node 24.19.0,
locked Playwright 1.63.0 and installed Edge. Measurements were sequential on this
machine, with pytest cache disabled and fresh temporary directories.

| Check | Fresh result |
| --- | --- |
| Original complete suite, before edits | 1124 passed in 228.07s |
| Focused encoding, care, coordination, configuration and regression checks | 453 passed in 22.32s |
| Request contracts after correcting the ineligible diagonal contention fixture | 11 passed in 9.18s |
| Ordinary memory counterfactual and continuation | 1 passed in 24.84s |
| Final complete suite, including new tests | 1149 passed in 237.08s (0:03:57) |
| Final fast selection | 1127 passed, 22 deselected in 34.15s |

The fast target is approximately 30 seconds on this machine. A duration over 30
does not meet a strict 30-second budget; do not hide more tests to claim it does.
The full suite has more checks than the original timing. The new memory check
includes an ordinary run, replay, 192-tick paired continuation and deliberate
replay divergence, so its cost is explicit.

The original slowest housing integration took 20.23s without profiling. Its
profile took 74.88s (profiling overhead): canonical_bytes accumulated 50.388s,
including 34.603s in the old encoder, across repeated save/read/replay/recovery.
There was no evidence in this bounded investigation that wall-clock sleeps or
unbounded donor-memory scans caused the slowdown. Logs and the profile summary
are beside this report; the larger raw profile and saved worlds are in the local
artifact directory listed below. A direct five-repeat timing of 256 canonical encodes
on each of three saved tick records measured 114–180 ms with the old encoder
and 42–69 ms with the new one (37–39% of the old time). All 12 byte comparisons
between saved tick payloads and the old encoder matched. This small encoding
microbenchmark establishes a local hot-path saving, not whole-suite throughput.

## Asking without learned donor preference

`tests/test_requests_without_social_memory.py` sets `social_memory_on=False`
from genesis. It leaves request/promise lifecycle state intact. Controlled cases
isolate the encounter; ordinary seed-23 worlds keep default terrain and other
default ecology, with requests enabled in walking or adjacent mode. Optional
source memory, reports and coordination are off. This is not a claim that all
navigation or short-lived interaction state is removed.

Both modes deliver real food. Checks cover agreement where appropriate, delivery,
next-tick eating, unanswered requests, two eligible requesters for one unit,
current sight/stock rechecks, personal-need interruption, and death of either
party before the answer. Both ordinary 220-tick saves replay and recover exactly
from an actual pending-request boundary. Memory remains empty throughout. In
ordinary seed 23, the 220-tick walking run records 15 deliveries and 13
immediate recipient meals; adjacent mode records 3 and 3. The local asking
summary preserves each giver, recipient and completed tick.

## Ordinary donor-memory counterfactual

`tests/test_memory_counterfactual.py` uses default seed 29 for 780 ticks. It finds
the first recorded memory-influenced decision whose physical choice changes
when that actor's donor-memory observation is hidden. No memory is invented.

At decision 588, p23 remembers food received from p10 at completed tick 428.
With memory, p23 walks toward p10 and transfers at completed tick 591. From the
same ledger and overlay, hiding p23's donor-memory input for decision 588 alone
makes p23 transfer immediately to adjacent p19 at completed tick 589. Other
observations and the initial persistent state are equal. Normal observation and
memory writes resume after that one decision. Both branches use world_step,
settlement and world processing for 192 ticks. Physical differences persist
through decision 779. Final living counts are 11 and 10, with different people;
this single scene is not a survival-benefit estimate.

The ordinary run and the unmasked continuation reproduce recorded tick payloads.
The masked file is clearly named and labelled CONTROLLED COUNTERFACTUAL; ordinary
replay correctly reports its first divergence at decision 588. It is not a
corrupted ordinary run or a claim that replay should reproduce an intervention.
Repeating the masked first step is deterministic and leaves the source state
unchanged. A 32-record unified memory store is unnecessary for this result.

## Family opportunities and outcomes

The named family aquarium means current WorldConfig defaults plus
`shared_care_on=True, care_by_need_on=True`, 400 ticks, seeds 7, 11, 23, 24.
The reference defaults themselves were not changed. No weather, seasons,
scarcity, source-memory or coordination option was added.

| Seed | Visible empty dependent while carrying food | Selected care ticks | Accepted child handoffs | Immediate next-tick meals | Living at 400 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 7 | 60 | 18 | 6 | 1 | 11 |
| 11 | 91 | 45 | 16 | 2 | 5 |
| 23 | 120 | 39 | 14 | 2 | 7 |
| 24 | 60 | 32 | 12 | 2 | 4 |

The first column is an opportunity screen, not an assertion that care outranks
the parent's own needs. Selected ticks include walking and handoffs; repeated
walking is not counted as several deliveries. The meal column counts only the
immediately following tick, so it is not a total of all later meals. All four
runs replay identically. Seed 11 and 24 recover identically at the recorded cuts;
seed 24 repeats with the same trail. Births and deaths occur in these worlds, so
historical claims that the original six survived a different 1500-tick setup
must not be used as their present survival floor.

Watch seed 11 p06's accepted handoffs to p08 at completed ticks 42 and 44
(with the first meal the next tick), and seed 24 p04's choice at viewer tick 245,
delivery at 247 and p19's meal at 248. The saved records and existing viewer expose
family links, the chosen target, reason, native transfer and subsequent need.

## Bounded review and remaining limits

The source review covered `fe940ef..019503c`: configuration validation, shared
parent links through birth/observation/care/movement/persistence, witnessed
speaker death through local observation/expectation clearing, care-by-need
ordering, and saved viewer consumers. The consolidation agent did not author
those original additions. Baseline tests were freshly executed before edits.
One concrete P2 explanation defect was reproduced and repaired as described
above; no additional settlement or persistence blocker was found in this scope.

A separately delegated reviewer returned partial static notes, then stopped at
the account usage limit before executing checks. That is not a completed
independent review. The consolidation agent's new encoder and explanation changes
have been tested and critically checked here, but not independently reviewed.
The supplied older independent PASS still applies only to `fe940ef`.

On 2026-10-04, Edge opened the locally served saved viewers. Seed 11 shows p06
feeding their child p08 at tick 42 and p08 eating at 43, with p03 and p06 both
shown as parents. Seed 24 shows p04 choosing visibly starving p19 at tick 245,
an accepted handoff at 247, and p19 eating at 248. In the walking-request world,
p04 delivers food p01 requested at 56 and p01 eats at 57. The ordinary seed-29
viewer shows p23 walking toward remembered donor p10 at 589 and handing over food
at 591; the clearly labelled one-tick memory-hidden comparison instead hands p19
food at 589. These are visual checks of saved reasons and outcomes, not independent
code review. The earlier in-app-browser attempt was blocked; no security setting
was changed. A fresh critical check of the encoder and explanation changes found
no blocker in scope: 26 focused tests passed and 2,000 seeded canonical comparisons
matched the previous encoder byte for byte. The new changes still lack a completed
independent review.

## Feature disposition and next work

- Shared care and care-by-need: ordinary saved-world examples, replay/recovery
  and contract checks pass. Fresh Edge inspection shows both handoff-to-meal scenes.
- Asking: ordinary deliveries with donor memory off plus controlled lifecycle
  coverage. Keep the optional flag; no ecological change was needed to observe it.
- Donor memory: ordinary changed choice with an actual persistent counterfactual
  consequence. This is received-food memory, not a memory of refusals or all
  request outcomes described by the old Stage 4 proposal.
- Witnessed speaker death: controlled capability demonstrated by the existing
  saved/recovery tests. Coordination is off in the family sample, so that sample
  has no eligible opportunity; it cannot estimate ordinary frequency. Keep it
  conditional on coordination. No cull or default enablement is justified.
- Existing memory stays separate: four donor identities per recipient;
  source records keyed by the finite natural-source set and aged out after
  20 ticks; one short-lived food expectation per listener, 12 ticks. Dead-person
  history still contributes to total world size as births grow the roster; no
  claim of a fixed world-wide memory bound is made.

Finish independent review of the two narrow production changes before resuming
new social rules. Preserve cultivation/live-viewer work for its own review. Reciprocity, economy, weather, memory unification and broad
parameter sweeps remain deferred. Consider static scarcity only if a specific
question lacks eligible opportunities under a separately fixed configuration.

Local artifact directory: `C:\Users\RJLoc\OneDrive\Desktop\Documents\ChatGPT\Simulation 3 - Living World Engineer\work\consolidation-019503c`. It contains `family/`, `asking/`, `memory/`,
the raw profile, original failure logs and the scripts used for the saved scenes.
These paths are local artifacts, not published files or a new run-management
system. The test files reproduce their own contract evidence in fresh temp dirs.
