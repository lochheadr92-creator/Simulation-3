# Stage 1 record — kernel only

Authority: owner direction OD-001 of 2026-09-19, recorded in `AGENTS.md`.
Only slice 1a is open. Slices 1b, 1c and 1d are not authorised, and the Stage 1
exit gate is not claimed.

## Card

| Field | Contents |
|---|---|
| State | Stage 1, slice 1a. Objective: two authorised claimants contend for one shared resource unit, settled atomically and observed immutably. Consumer: the Stage 1b reservation slice, which needs a trustworthy availability boundary and settlement path before it can add two-tick actions. Prerequisites: none. Review status: no independent review requested or held; Stage 1 exit remains unclaimed. |
| Scope | In: immutable world state, per-actor read-only views, proposal validation, declared deterministic ordering, all-or-nothing settlement of balanced effects, immutable tick records with explicit outcome reasons, canonical serialization and digests, an inert diagnostics channel, focused deterministic tests. Owning modules: `kernel/`. Out: reservations, multi-tick or cancellable actions, replay and recovery, evidence streaming to disk, needs, movement, perception rules, memory, social behaviour, construction, viewers, plugins, a general scheduler, randomness, the six-person world and the 50-actor capacity workload. |
| Identity | Adoption revision `2bf08e9e4629022adb508b5c6db53a144bb355b4` on branch `codex/kernel-first-slice`, containing `AGENTS.md`, `DOCTRINE.md` and `ROADMAP.md` together. This record's declaration revision and the implementation revision are listed under Attempt ledger. `ENGINE_VERSION = "0.1.0-stage1a"`; `SCHEMA_VERSION = "v3.kernel.1a.1"`. Owner-direction reference: OD-001. |
| Claim | Essential: one contested source unit yields exactly one credited unit and exactly one winner; an invalid or unauthorised transaction commits no part of itself; an indivisible transaction against insufficient stock is rejected without partial credit; results are independent of input-map and proposal-collection order; the declared rotation gives no permanent winner over equivalent contention at successive ticks; the roadmap's A to B transfer/consume fixture honours the next-tick availability boundary and prevents double spending; observers cannot mutate live or previously observed state; diagnostics on and off, and repeated identical execution, give identical canonical results. Integrity rails on every tick: no negative balance, conserved declared total, every committed transaction's effects sum to zero, every submitted proposal carries exactly one explicit outcome reason. Optional targets: none in this slice. |
| Definitions | See "Declarations" below: units and numeric rules, accounts and ownership, operations and balanced effects, proposal identity and the actor-local sequence, ordering and rotation, the availability boundary, outcome reasons, canonical form. |
| Instrument | The tests read the engine's own state objects and tick records through its public accessors; there is no second scorer or reconstructed ledger. Ordering is exercised by generating every permutation of the declared input maps and proposal collections, not by sampling. Null controls: an empty proposal collection, and an empty roster for the rotation rule. Known-negative controls: unauthorised claimant, insufficient source, insufficient balance, duplicate proposal identity, duplicate actor sequence, unbalanced effects, non-integer and non-positive amounts. Deliberate failure case: a diagnostics sink that attempts to mutate what it is handed. Validation result recorded under Results. |
| Budget and attempt | Focused deterministic fixtures only. Whole-world executions authorised: 0. Used: 0. Remaining: 0. Capacity runs authorised: 0. No exploration levers are declared, because this slice answers a correctness question, not a design question. |
| Evidence and rollback | Commands, results and rollback list recorded under Results and Rollback below. |

## Declarations

These are fixed before implementation. Changing any of them after a recorded
result creates a new attempt; it does not revise an existing one.

### Units and numeric rules

- One resource kind exists in this slice, named `unit`. It is abstract; it
  acquires meaning in Stage 2, not here.
- All quantities are Python integers. No floating-point value may enter state,
  a proposal, a tick record, or the canonical form; canonical serialization
  rejects them rather than formatting them.
- `bool` is rejected as a quantity even though Python treats it as an integer.
- Balances and source stocks are integers greater than or equal to zero, with no
  upper bound.
- A transaction amount is an integer greater than or equal to one. Zero and
  negative amounts are malformed, not no-ops.
- Units are indivisible: a transaction moves its exact declared amounts or
  nothing. There is no fractional or partial credit.
- Conserved total, asserted after every tick:
  `sum(source stocks) + sum(actor balances) + consumption sink`.

### Accounts and ownership

Three account kinds, addressed as `source:<id>`, `actor:<id>` and `sink:consumed`.

- `source:<id>` is a shared source holding a stock, with a fixed set of
  authorised claimant actor identities.
- `actor:<id>` is an actor's exclusive holding.
- `sink:consumed` is the single declared consumption sink. It is the explicit
  rule for loss: consumed units leave circulation but stay in the conserved
  total, so consumption can never be confused with leakage.

Authority is checked per debited account, for the whole transaction:

- debiting `actor:X` requires the proposing actor to be `X`;
- debiting `source:S` requires the proposing actor to be in `S`'s authorised set;
- debiting `sink:consumed` is never permitted;
- crediting requires no authority; an actor may be given units unasked.

No module outside `kernel/settlement.py` writes a balance. There is no public
mutator on any state object.

### Operations and balanced effects

A transaction is a list of balanced effects whose signed amounts sum to zero.
An operation is a named constructor for such a list. Three exist in this slice:

| Operation | Parameters | Effects |
|---|---|---|
| `claim` | `sources`: a mapping of one or more source identities to positive integer amounts | debit each named source by its amount; credit the proposing actor the total |
| `transfer` | `to`: an actor identity other than the proposer; `amount` | debit the proposer; credit `to` |
| `consume` | `amount` | debit the proposer; credit `sink:consumed` |

`claim` accepts several sources because a single-debit transaction cannot
demonstrate that a rejected transaction commits none of its parts. A two-source
claim is the smallest transaction that can prove all-or-nothing settlement, and
the roadmap already requires one global order for multi-resource transactions.
No other multi-effect operation is built.

An effect list is rejected before commit if its amounts do not sum to zero, so a
malformed operation cannot create or destroy units even if it passes every other
check.

### Proposal identity and the actor-local sequence

A proposal is `(proposal_id, actor, sequence, operation, params)`.

- `proposal_id` is a non-empty string, unique across the tick. If two or more
  proposals share an identity, all of them are rejected with
  `denied_duplicate_proposal_id`, regardless of which arrived first.
- `actor` must be present in the tick-start roster.
- `sequence` is the actor-local proposal sequence: a non-negative integer by
  which the actor declares the order of its own proposals within the tick. It is
  carried on the proposal rather than assigned from arrival order, because the
  roadmap's fixture depends on "A to B is A's first proposal" and ordering may
  not depend on collection order. The engine validates it: if one actor submits
  two proposals with the same sequence, all proposals sharing that `(actor,
  sequence)` are rejected with `denied_duplicate_actor_sequence`.

### Ordering and rotation

Resolution order is derived only from tick-start state and proposal content.

1. `roster` is the tick-start actor identities sorted by Unicode code point.
2. `k = tick mod len(roster)`; `rotated = roster[k:] + roster[:k]`. An empty
   roster resolves no actor transactions.
3. `actor_rank` is the actor's index in `rotated`.
4. The total order key is `(actor_rank, sequence)`.

The roadmap's key is `(phase, rotated actor rank, actor-local sequence)`. The
phase term is constant in this slice because reserved completions do not exist
until slice 1b; the key is therefore implemented without it, and 1b restores it.

Rotation is deterministic priority, not a fairness guarantee. It only removes a
permanent winner among claimants that are otherwise equivalent.

### The availability boundary

- At tick start, each account's available amount equals its tick-start balance.
- A transaction is validated against remaining availability for every account it
  debits, as one unit of work.
- Acceptance reduces that availability immediately. Rejection leaves it
  unchanged.
- Credits never raise availability within the tick. A unit credited at tick `T`
  becomes spendable at tick `T+1`.
- Accepted effects are staged and applied together at the end of the tick.

### Outcome reasons

Every submitted proposal appears in the tick record with exactly one reason.
Nothing disappears from the record.

`accepted`, `denied_unknown_actor`, `denied_unknown_source`,
`denied_unknown_operation`, `denied_malformed_params`,
`denied_non_integer_amount`, `denied_non_positive_amount`,
`denied_duplicate_proposal_id`, `denied_duplicate_actor_sequence`,
`denied_unauthorised`, `denied_insufficient_source`,
`denied_insufficient_balance`, `denied_unbalanced_effects`,
`denied_self_transfer`.

### Canonical form

Canonical bytes are UTF-8 JSON with sorted keys, `(",", ":")` separators and
escaped non-ASCII. Integers only; floats and booleans are refused at
serialization rather than formatted, so no platform number formatting can reach
an identity. A digest is the SHA-256 hexadecimal of those bytes. State identity
and tick-record identity are digests of the canonical form, so no incidental
object order, insertion order or wall-clock value can enter them.

### Diagnostics

The diagnostics channel receives already-canonical copies after each decision is
fixed. It returns nothing the engine reads and allocates no identity. This slice
allocates no identities at all, so the roadmap's stronger clause about
diagnostics never perturbing identity allocation is only partly exercised here;
that is recorded as a limitation, not a pass.

## Assertions

The eight owner-required checks, plus one check required by doctrine 9.

| # | Assertion | Test |
|---|---|---|
| A1 | Two valid claims on one unit produce exactly one winner, no negative balance and a conserved total. | `tests/test_contention.py` |
| A2 | An invalid or unauthorised transaction commits no part of itself. | `tests/test_atomicity.py` |
| A3 | Insufficient stock rejects an indivisible transaction without partial credit. | `tests/test_indivisibility.py` |
| A4 | Reordering input maps or the proposal collection leaves canonical results unchanged. | `tests/test_order_independence.py` |
| A5 | The declared rotation produces no permanent winner over equivalent contention at successive ticks. | `tests/test_rotation.py` |
| A6 | The A to B transfer/consume fixture honours next-tick availability and prevents double spending. | `tests/test_credit_boundary.py` |
| A7 | Observers cannot mutate live or previously observed state. | `tests/test_observation.py` |
| A8 | Diagnostics on and off, and repeated identical execution, give identical canonical results. | `tests/test_determinism.py` |
| A9 | Module dependency direction holds; lower layers do not import higher ones. | `tests/test_dependency_direction.py` |

## Attempt ledger

| Attempt | Revision | What changed | Result |
|---|---|---|---|
| Declaration | recorded under Results | This record, written before any kernel code existed. | n/a |
| 1 | recorded under Results | First kernel implementation against the declarations above. | recorded under Results |

Failed versions are preserved here rather than overwritten.

## Results

NOT YET RUN. No implementation exists at the time this record is committed.
Actual commands, output and digests are appended below after execution.

## Review

No independent review has been requested, supplied or held. Stage 1 has three
further slices and its exit gate is not claimed.

## Rollback

Recorded under Results after implementation.
