# V3 — development roadmap

**ADOPTED 2026-09-19; scope updated 2026-09-21 under OD-008 and OD-009. No
stage has passed. Stage 1 is open through slice 1b; slice 1c is re-scoped to a
record stream and viewer, slice 1d is deferred, and Stage 2 opens in checkpoint
order (position and movement, food source, hunger; then perception) once
checkpoint 1 exists. Confirmation floors, frozen baselines and independent
acceptance apply only to results the owner names for ratification. This
document by itself authorises no execution.**

The behavioural starter world has six people. The engineering target is 50 people.
The order below follows dependencies, not the old project's feature sequence.
Capacity workloads cannot supply behavioural counts for Stages 3–5.

## The active stage record

Keep a one-page working card at the top of the stage record, followed by definitions,
an attempt ledger, results, and review. Use the template at the end of this document.
The card is an index into evidence, not another governing document. Fill definitions
only for the active stage; later stages do not need invented values now.

No exploratory, confirmation, or benchmark run begins with an unspecified budget,
threshold, counting rule, or horizon. Positive exit claims and integrity rails must
pass; optional targets cannot excuse their absence.

### Adopted operating budgets

These are adopted ceilings, not measured capabilities or confidence estimates.
They bound exploration cost. Stage 2 has the largest search allowance because it
must establish viability and opportunity together.

| Work | Candidate limit | Whole-world execution limit | Maximum ticks per execution |
|---|---:|---:|---:|
| Stage 2 world design | 8 world configurations | 24 | 10,000 |
| Stage 3 request policy | 3 policy configurations | 12 | 10,000 |
| Stage 4 memory policy | 3 policy configurations | 18 | 10,000 |
| Stage 5 observation | 1 fixed model | 6 | 30,000 |
| Capacity checks, each of Stages 1–4 | 1 workload specification per stage | 8 | 10,000 |

Each execution, including confirmation, invalid runs, review reruns, and each arm
of a paired comparison, consumes a slot. Stage 4's extra slots accommodate the
intervention and no-op controls. A world/configuration combination counts
once as a candidate even if tested on several declared inputs. Reserve confirmation
and review capacity before exploration. Horizon extension consumes another execution;
never continue a confirmation until it happens to pass. Focused transaction tests
and analysis of existing sealed evidence do not consume whole-world slots.

Keep a shared ledger for questions spanning stages. Stage 3 does not inherit a fresh
world-design allowance: failure of its opportunities revalidates the Stage 2 world
within the remaining world budget. A bounded exploratory counterfactual continuation
counts as an execution arm; repeated focal-choice evaluations without ticking are
instrument tests. Version changes, retries, and session changes never renew budgets.

Adopted capacity ceilings on one named reference machine: 50 actors; mean tick
time at most 50 ms and 95th percentile at most 100 ms; peak process memory at most
512 MiB; complete uncompressed replay plus decision evidence averaging at most
64 KiB per tick and at most 1 GiB for 10,000 ticks. At fixed population and bounded
state, peak memory may grow by at most 64 MiB between 1,000 and 10,000 ticks.
These are operational targets, not predictions: the storage limit keeps a benchmark
under 1 GiB, and the memory limit rules out keeping its entire history in RAM.
Record machine, runtime, workload,
measurement method, and exact horizons before benchmarking. Include settlement
and evidence writes in cost; report final flush and both evidence streams separately.
Missing a ceiling cannot be fixed by dropping required evidence.

## 1. Kernel only

Build immutable state views, proposals, deterministic resolution, validated atomic
effects, action settlement, immutable evidence, and replay. A minimal actor has an
immutable ID, stock ownership or declared permission to claim a shared source,
and a proposal interface; it is not yet a person domain. No needs, movement,
perception behaviour, social systems, construction, graphical viewer, plugin
platform, or speculative general scheduler.

Declare units, numeric rules, canonical serialization, and code/schema versions
before implementation. Identity and replay must not depend on incidental object
order, wall-clock timing, or platform-specific number formatting.

### Four internal slices, one stage exit

| Slice | Proof object |
|---|---|
| 1a | Two authorised claimants, one unit, one winner; invalid writes and observer mutation cannot commit. |
| 1b | Two-tick reserve → complete or cancel → release; exactly-once settlement. |
| 1c | Sealed evidence, replay, recovery, and private instance isolation. |
| 1d | The declared 50-actor cost envelope against the frozen 1a–1c reference suite. |

Complete them in order. They are implementation slices, not extra roadmap stages
or approval gates. The first code is the contested transaction and isolation checks.

### Tick algorithm

1. Freeze the tick-start state and declared boundary inputs. Build views and collect
   proposals against this boundary. Later people receive only their bounded view.
2. Validate proposal shape, unique identity, authority, and operation preconditions.
   Reject all proposals sharing a duplicate ID, regardless of which arrived first.
3. Apply authorised cancellation causes before completion of the same action.
   Cancellation releases its reservation exactly once. Rejecting an unrelated
   proposal does not cancel ongoing work.
4. Resolve surviving reserved completions, then new transactions. Within each phase,
   sort the tick-start actor roster by stable ID and rotate it left by
   `tick mod actor_count` (empty roster: no actor transactions). The total key is
   phase, rotated actor rank, then engine-assigned actor-local proposal sequence.
   Use one global order for multi-resource transactions. Proposal sequences must
   not depend on collection order or incidental input-map iteration.
5. Validate each entire transaction against remaining tick-start spendable balances
   or its own reservation. Acceptance reduces that availability immediately;
   rejection leaves it unchanged. Stage balanced effects and lifecycle changes,
   committing each accepted transaction completely or not at all.
6. Commit the next state and seal the tick's evidence. Publish immutable records.

New credits, production, and released prior reservations become spendable at the
next tick-start. Existing reservations may settle through their owning action.
An atomic transaction may have several balanced effects, but cannot spend an
incoming credit as if already held. Reservation is neither consumption nor extra
stock; count held or escrowed units once. Validate source balances and conservation
before commit; never repair an invalid transition with clamping.

Stage 2 declares how mandatory need changes and death generate boundary outcomes
and cancellation causes; rejected voluntary actions cannot suppress those changes.
Equivalent partner ties use tick-based rotation of the sorted eligible partner
list. Rotation is deterministic priority, not a fairness guarantee.

**Required credit fixture:** A owns one unit, B owns none. At T, A→B is A's first
proposal and is accepted. A's subsequent claim on that unit is denied. B's consume
proposal at T is denied regardless of resolver order. At T+1, B may consume if the
unit remains held. Production and reservation release obey the same availability
boundary. Partial availability rejects an indivisible transaction; it cannot create
an implicit partial credit. Also test repeated completion and cancellation versus
completion at the same boundary. Cancellation, completion, denial, and transfer
must carry explicit outcome reasons rather than disappear from the record.

### Evidence and foundation checks

Specify the small evidence schema before implementing its writer: genesis and
code/configuration/schema identities; ordered inputs and tick IDs; proposal/action
IDs; resolution reasons; balanced effects and reservation transitions; state/event
identities; and a complete-tick seal. Native decision records contain or reference
immutable copies of the actual inputs and alternatives used, linked to outcomes.
They are not later reconstructions from live state.

Stream required evidence. Optional diagnostic capture cannot change canonical
simulation history, state, or identity allocation. A partial write recovers only
through the last verified sealed tick; resume with pending reservations must agree
with uninterrupted execution. Replay independently from genesis and declared inputs;
snapshots accelerate recovery without replacing that check.

Verify input-map permutation, repeated execution, replay and resume; unauthorised
writes; observer attempts to mutate live or prior state; and isolation of two
instances restored from the same state. Changing one instance cannot affect the
other. This enables Stage 4's small intervention harness without building a generic
branching platform now. Add dependency-direction checks and the reference suite.
Old accounting/observer failures are adversarial examples, not a queue of old domains.

After 1a–1c, benchmark 50 synthetic actors with fixed contention/action mixes at
1,000 and 10,000 ticks, twice at each length. Use the declared cost ceilings, stream
complete evidence, and retain no ever-growing history in working memory.

## 2. Viable world with reachable social opportunities

Build a compact six-person world with movement, bounded perception, food, water,
warmth, shelter, and renewable resources. Shelters may be placed; construction is
not required. Observation is a text display of sealed native records, not a product.

Declare the world-design budget first. Allowed levers are geometry, distribution,
renewal, initial supplies, perception radius, and consumption rates. Do not add a
social system to create need. Separate an accounting defect from a world-design miss.

Declare the initial placement and stock-generation rules before exploration; they
must not assign successful pairs or advantages by actor identity. Designed maps and
hand-built diagnostic fixtures are allowed, but fixtures cannot supply ordinary-world
confirmation counts. Freeze geometry, ranges, initialisation rules, and confirmation
inputs before confirmation. Do not nudge individual coordinates after seeing a miss.
Changing an allowed world lever creates a recorded candidate within the same budget.

Exit evidence must show repeated ordinary obtain/consume cycles after starting
reserves cease to explain survival, exact accounting, and the declared survival
rail. A deprived fixture must still suffer or die under the declared need rules.
Define explicit safety rails and measure emergencies as well as deaths; merely
keeping everyone barely alive does not establish the intended viable baseline.
Need progression and world processes continue when a voluntary action is rejected;
losing contention cannot freeze a person's hunger or grant a free pause.

The ordinary world must produce prospective help opportunities in at least six
distinct shortfall episodes across three people, using Stage 3's episode definition.
Count only frames where the person can make a decision, meets the proposed request
eligibility, and observes at least two potential partners with spare food inside
the declared interaction range. Define spare-stock and knowledge-freshness rules
before counting. Mid-action frames and unusable alternatives do not qualify.
These are prospective opportunities, not completed requests. Use engine accessors
and the actual tick-start observations; do not infer opportunities from later stock
or locations. The counting instrument must pass known-positive, known-negative,
busy-actor, stale-knowledge, and boundary cases before its totals are used.

Before advancing, write explicit score inequalities for a region where the proposed
request can beat ordinary competing actions without overriding an emergency. Back
the argument with constructed inputs evaluated through the shared selection rule.
Include exclusions and tie-breaking, not just raw scores. Do not build a second
scorer in the probe. The probe may implement the proposed request candidate's
eligibility and score for read-only evaluation; Stage 3 reuses that exact logic.
It enables no social execution in Stage 2. This establishes possibility; Stage 3
must demonstrate actual selection and completion after social actions alter the world.

### Definitions to freeze before the first counting run

Keep these in the stage record with exact values in its configuration. Freeze
counting predicates before exploration; declare which physical parameters may vary.

| Term | Required definition |
|---|---|
| Spare food | Unreserved stock exceeding the giver's declared retained amount, in named units; observed estimates and execution-time availability remain distinct. |
| Range and freshness | Distance metric, perception radius, interaction/contact range, maximum observation age, and boundary inclusivity. |
| Shortfall episode | Exact start and recovery predicates, hysteresis if used, and handling of death, run-end censoring, and initially hungry actors. A dead actor does not recover. |
| Emergency | Exact condition giving mandatory survival precedence; ordinary competitors are the other genuinely eligible engine candidates. |
| Viability | Observation horizon, renewal/need-cycle duration, minimum survival and emergency rails, and the check that starting buffers are insufficient to explain the result. |
| Opportunity | Decision-ready actor, request eligibility, and two observed usable partners; count actor/tick and episode separately. |

Later, Stage 4 adds the exact separation duration, contact predicate, memory access
scope, material outcome, and persistence window before its exploration. These are
stage-specific modelling declarations, not missing prerequisites for kernel work.

Repeat the 50-person engineering workload with movement and perception active.
A synthetic kernel benchmark alone does not establish full-world capacity.

## 3. First social behaviour: request food

Implement observation, eligible partners, selection, help/refusal, and settlement.
Memory influence is disabled. Counterpart consent and available stock are checked
at the declared execution boundary; an observed spare is not a guaranteed delivery.
Test refusal, competition, movement away, interruption, and death boundaries as
applicable. Outstanding obligations cannot duplicate or disappear silently.

### Adopted confirmation floors

| Measure | Minimum |
|---|---:|
| Actual scored food-request frames | 12 |
| Distinct shortfall episodes | 6 across at least 3 people |
| Request selections with at least 2 eligible partners | 6, from distinct episodes across at least 3 people |
| Completed transfers | 3 across at least 2 recipients |

Count at most one request frame per actor per tick. An episode begins when the
declared hunger-shortfall predicate becomes true and ends when the triggering need
reaches its declared recovery condition. Repeated asks, waiting, changing partners,
or receipt of food before recovery do not create another episode. Record the exact
start/recovery predicates before exploration; do not change them to improve counts.

Every counted selection must be the actual engine winner. Report the five-link
funnel, refusals and interruptions, with actors, episodes, and denominators explicit.
Include per-person counts and episode duration, candidate count, request delay,
and transferred-quantity distributions; retain zeroes and censored episodes.
Do not pool successful exploration into confirmation. Transfers conserve stock;
survival and integrity rails pass. Check the capacity workload with requests active.

These are engineering coverage floors, not statistical confidence thresholds.
Freeze the horizon and counting rules before confirmation. More selected asks alone
do not demonstrate memory, relationships, or emergent cooperation.

## 4. Experience changes material outcomes

Use earned interaction memory to change partner choice on the demonstrated world.
The first model stores dated food-request outcomes with counterpart, observation
time, and source event ID: at most 32 records per person and four per counterpart.
Evict oldest first, breaking same-tick ties by stable event ID; enforce both caps.
Declare expiry and the bounded scoring rule before exploration. Query work is
bounded by those 32 records. No embeddings, inferred friendship store, or general
belief engine. These caps are design proposals, not evidence of adequate memory.
Social-memory eviction cannot erase transaction obligations held by the kernel.

Require three complete causal chains across at least two people: ordinary accepted
interaction creates memory; declared separation follows; removing access only to
the specified memory at the same later decision changes the choice; ordinary
execution accepts the changed action; and a declared material consequence persists
in canonical state over the specified window.
Count distinct later need episodes, not repeated attempts inside one episode.
Record the originating interaction and retained information supporting each chain.

Replay to just before the focal choice and restore private instances from identical
state. Declare whether the intervention masks one source event or one counterpart's
buffer, and how focal choices are selected before confirmation. Mask only that
actor's access at that decision; do not delete physical state, transaction records,
or other people's memories. Restore ordinary access for later decisions.
Prove both an unmodified fork and an empty-mask intervention reproduce the original
choice and continuation. Keep physical state and all other decision inputs fixed
at the focal choice; divergence after a changed action is then part of the outcome.
Do not attribute a whole-run difference to memory without tracing that choice's
downstream effects. Pure memory fields, identifiers, and diagnostic counters are
not material consequences.

Declare separation, relevant expiry conditions, consequence dimensions, and the
persistence window before confirmation, justified by Stage 2's action/need timescales.
Separation uses the declared contact range and minimum duration, not merely different
coordinates or an arbitrary age counter. State whether post-expiry influence is
required; an in-window effect cannot satisfy a post-expiry claim.
Use confirmation inputs not selected for success during exploration. A seed-label
change counts as variation only when it changes a real input or random sequence.

Check capacity/eviction boundaries and repeat the 50-person workload with memory
active. Report demonstrated mechanism, observed occurrence, and robustness separately.

## 5. Observe longer-term patterns

Hold local rules fixed over declared need and encounter cycles. Measure recurring
partner preference, avoidance, reciprocity, association, or no durable pattern.
Repeated measurements of one encounter are not independent relationship episodes.

Introduce no friendship object merely to produce the desired finding. One leftover
unit of food is not evidence of a durable relationship.
Distinguish association explained by geography from experience-dependent association.
Attribute a recurring pattern to memory only when an appropriate control supports it.

A valid negative observation may complete this observation stage. It does not
establish the desired pattern or mean the project's full purpose has been achieved.
The population/horizon of behavioural evidence limits its claim; a 50-person
performance benchmark is not a 50-person social demonstration.

## 6. Choose one extension

The owner chooses the next objective from the recorded limitations and desired
experience. Name the consumer, ordinary opportunity, consequence, and check before
implementation. No automatic feature train resumes.

## Misses, stop conditions, and progression

- No opportunity: examine the world and eligibility.
- Opportunity exists, action loses: examine the competing reasons.
- Action wins, execution fails: examine execution and accounting.
- Action completes, consequence disappears: examine the claimed causal path.
- Measurement is unreliable: make one bounded instrument-repair attempt within the
  remaining budget. If validation still fails, the affected claim is UNKNOWN.

An unresolved prerequisite blocks dependent work. Stages 3 and 4 require positive
demonstrations; a well-measured absence cannot pass them. Stage 5 permits a negative
observation because observation is its declared objective.

Two confirmation misses at the same causal link halt the stage for a bounded owner
revision even if execution slots remain. Exploratory misses consume the search
budget without becoming extra approval gates. No downstream work bypasses a failed
or unknown prerequisite.

At budget exhaustion, report the missing link and bounded alternatives: revise
world assumptions, revise the local policy, choose another first behaviour, or
suspend the objective. No silent budget extension or new prerequisite programme.

Progression also requires the independent evidence review specified in AGENTS.md.
Keep one stage record with the design, versions, original criteria, raw evidence,
instrument checks, failed attempts, review, outcome, and rollback.

## Stage-card template

Use these eight rows; link details rather than expanding the card into another plan.
Keep one configuration file per attempt and an artifact index beneath the card.

| Field | Contents |
|---|---|
| State | Stage/slice, active objective and consumer, prerequisite/review status. |
| Scope | In/out, owning modules, permitted changes. |
| Identity | Source, configuration and schema versions; owner-direction reference. |
| Claim | Essential exit conditions and integrity rails; optional targets separately. |
| Definitions | Linked predicates, units, tie rules, counting boundaries and input selection. |
| Instrument | Known cases, null controls, accessors, native inputs and validation result. |
| Budget and attempt | Limits/used/remaining; exact runs, horizons, reserved confirmation/review slots. |
| Evidence and rollback | Commands, artifacts, result/review links; exact files/configuration to revert. |

### Filled example: illustrative card, not execution evidence

The table below is a worked illustration of the template written before any
repository existed. It is not the Stage 1a record. The live Stage 1a record is
`evidence/stage-01/RECORD.md`.

| Field | Stage 1a example |
|---|---|
| State | Draft; contested shared-stock transaction consumed by two synthetic actors. Nothing implemented or passed. |
| Scope | Minimal state, proposal validation, deterministic settlement, immutable observation and focused tests. No person domain, reservations, replay platform, or world runs. |
| Identity | These three draft documents; no repository/code revision exists yet. Builder records the actual initial revision before tests. |
| Claim | One source unit yields exactly one credited unit; balances remain nonnegative; invalid/unauthorised transactions and observer mutation cannot alter canonical state. |
| Definitions | Integer resource units; tick starts at zero; authorised shared-source claims; roadmap rotation; all-or-nothing transactions. |
| Instrument | Inspect actual pre/post state and accepted/denied outcomes; reverse map/proposal collection order; attempt observer mutation; compare diagnostics on/off. Not run. |
| Budget and attempt | Focused deterministic fixtures only; zero whole-world or capacity runs authorised for this slice. |
| Evidence and rollback | Planned record: evidence/stage-01/RECORD.md. Builder records exact changed files, commands/results and rollback; Stage 1 exit review remains pending. |
