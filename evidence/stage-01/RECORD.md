# Stage 1 record — kernel only

Authority: owner direction OD-001 of 2026-09-19, recorded in `AGENTS.md`.
Only slice 1a is open. Slices 1b, 1c and 1d are not authorised, and the Stage 1
exit gate is not claimed.

## Card

| Field | Contents |
|---|---|
| State | Stage 1, slice 1a. Objective: two authorised claimants contend for one shared resource unit, settled atomically and observed immutably. Consumer: the Stage 1b reservation slice, which needs a trustworthy availability boundary and settlement path before it can add two-tick actions. Prerequisites: none. Review status: no independent review requested or held; Stage 1 exit remains unclaimed. |
| Scope | In: immutable world state, per-actor read-only views, proposal validation, declared deterministic ordering, all-or-nothing settlement of balanced effects, immutable tick records with explicit outcome reasons, canonical serialization and digests, an inert diagnostics channel, focused deterministic tests. Owning modules: `kernel/`. Out: reservations, multi-tick or cancellable actions, replay and recovery, evidence streaming to disk, needs, movement, perception rules, memory, social behaviour, construction, viewers, plugins, a general scheduler, randomness, the six-person world and the 50-actor capacity workload. |
| Identity | Adoption revision `2bf08e9e4629022adb508b5c6db53a144bb355b4` on branch `codex/kernel-first-slice`, containing `AGENTS.md`, `DOCTRINE.md` and `ROADMAP.md` together. Declaration revision of this record, written before any kernel code existed: `bbbf142f1399c1642c567d3d9c78792610b2df0b`. Implementation revision: `b48542b3567bfba9f0fa7a831ab8ace0eb6ddc1f`. `ENGINE_VERSION = "0.1.0-stage1a"`; `SCHEMA_VERSION = "v3.kernel.1a.1"`. Owner-direction reference: OD-001. |
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

Two further files were added during implementation, for rules the declarations
above already state but the original nine assertions did not reach:

| # | Assertion | Test | Why it was added |
|---|---|---|---|
| A10 | Proposals sharing an identity are all rejected, and so are proposals sharing an actor sequence, whichever arrived first. | `tests/test_proposal_identity.py` | The declared identity rules are what let resolution order come from content alone, so A4 rests on them, and nothing was checking them. |
| A11 | The settlement integrity rails refuse to commit when their precondition holds. | `tests/test_integrity_rails.py` | The mutation check found that switching the negative-balance rail off broke no test. |

## Attempt ledger

| Attempt | Revision | What changed | Result |
|---|---|---|---|
| Declaration | `bbbf142f1399c1642c567d3d9c78792610b2df0b` | This record, written before any kernel code existed. | n/a |
| 1 | `b48542b3567bfba9f0fa7a831ab8ace0eb6ddc1f` | First kernel implementation against the declarations above, with the focused tests for A1 to A9, then A10 and A11 after the instrument check. | 107 passed, 0 failed. See Results. |

Failed versions are preserved here rather than overwritten. The corrections made
during attempt 1, including one defect in the instrument itself, are recorded
under Results.

## Results

Machine: Windows 11 Pro 10.0.26200, CPython 3.12.10, pytest 9.1.1.
Working directory: the repository root, `C:\dev\03-Living-World-V3`.

### Commands and results

| Command | Result |
|---|---|
| `py -3 -m pytest` | 107 passed, 0 failed, 0 skipped, 0.22s. Full per-test output: `evidence/stage-01/instrument/pytest_verbose_output.txt` |
| `py -3 -m pytest -q` repeated twice | 107 passed both times |
| `py -3 evidence/stage-01/instrument/mutation_check.py` | exit 0. 14 of 15 deliberate defects detected; 1 confirmed structurally unreachable. Output: `mutation_check_output.txt`, raw pytest output per run under `instrument/runs/` |
| `py -3 evidence/stage-01/instrument/fixture_digests.py` | Canonical results for the declared fixtures. Output: `fixture_digests_output.txt` |

Test counts by file, from the verbose run: `test_atomicity` 16,
`test_contention` 10, `test_credit_boundary` 8, `test_dependency_direction` 6,
`test_determinism` 10, `test_indivisibility` 11, `test_integrity_rails` 9,
`test_observation` 16, `test_order_independence` 5, `test_proposal_identity` 8,
`test_rotation` 8.

### The declared fixtures, as the engine produced them

A1, one unit and two authorised claimants, at tick 0:

```
rotated roster   ('A', 'B')
outcomes         [('pA', 'accepted'), ('pB', 'denied_insufficient_source')]
balances         {'A': 1, 'B': 0}
source S         0
total before 1   total after 1
record digest    b3846dbf23d06285dd190122aedda39d8253f718aa47d4bd33a5687e7a1a5aa9
state digest     9b5e304618d0711c0bbd5da7dbca8e6622b717e433b6cb3871a468ac529d4ee8
```

The same contention at tick 1 reverses the winner, with rotated roster
`('B', 'A')`, outcomes `[('pB', 'accepted'), ('pA', 'denied_insufficient_source')]`
and record digest `7d4bb4ad63480a7916d63cd32cce5aad28594e3b261fed9c29989517d0639ae5`.

A6, the roadmap's credit fixture, starting at tick 0:

```
tick 0 outcomes  [('a_gives', 'accepted'),
                  ('a_spends_again', 'denied_insufficient_balance'),
                  ('b_spends_early', 'denied_insufficient_balance')]
tick 0 balances  {'A': 0, 'B': 1}
tick 1 outcomes  [('b_spends_later', 'accepted')]
tick 1 balances  {'A': 0, 'B': 0}, consumed 1
total before 1   total after 1
tick 0 digest    09a4e2527e217674905ef5c3e91d0a8585f8df409cbb308cce1a7765c0d87339
```

Starting the same fixture at tick 1 puts B ahead of A in the rotation. B's early
consume is still denied, A's transfer is still accepted, and A's second spend is
still denied, which is the roadmap's "regardless of resolver order".

A8, the same A1 fixture run with and without a diagnostics sink, produced
identical record and state digests with one event captured by the sink.

### Instrument validation

The suite passed on its first complete run. That is not evidence that it checks
anything, so `evidence/stage-01/instrument/mutation_check.py` breaks one declared
rule in the kernel at a time and records which tests notice. Results:

| Mutation | Tests that noticed |
|---|---:|
| rotation always starts at the sorted roster | 8 |
| a unit credited this tick becomes spendable this tick | 4 |
| authority over a debited account is never checked | 6 |
| resolution follows proposal arrival order | 7 |
| the record lists outcomes in arrival order | 3 |
| canonical bytes follow mapping insertion order | 1 |
| state hands out a live mutable mapping | 3 |
| a view points at the state's own mapping | 2 |
| only the first leg is checked against availability | 1 |
| proposals sharing an identity are resolved | 3 |
| one actor may reuse a sequence | 2 |
| a transaction may create or destroy units | 1 |
| an amount need not be a whole unit | 3 |
| the negative-balance rail is off | 2 |
| the conservation rail is off | 0, unreachable |

The conservation rail cannot be reached by any input: a committed transaction
must already have balanced effects and touch only accounts inside the world, and
those two together conserve the total by construction. It is defence in depth
against a future slice, and the harness records it as declared-unreachable
rather than as a pass.

### Corrections made during attempt 1, preserved

1. **The instrument was wrong before the kernel was.** The first mutation harness
   reported the `authority-not-checked` failures again for `order-by-arrival`.
   Both mutations change `kernel/settlement.py` by exactly 38 bytes, and both
   runs fell inside one filesystem mtime second, so CPython accepted the previous
   mutation's cached bytecode as current and the second run tested the first
   mutation's code. The harness now disables bytecode writing, removes every
   `__pycache__` before each run, and checks the mutated text is the text on
   disk. Caught by running one mutation by hand and reading pytest's own output
   instead of the harness summary.

2. **The instrument altered the repository.** The same harness wrote files in
   text mode, which converts LF to CRLF on Windows, so its "restore" was not byte
   for byte and four kernel files were left with changed line endings. The
   harness now reads and writes bytes and verifies the restore. The affected
   files were normalised back to LF before the implementation commit.

3. **Two real blind spots in the suite**, both found by the corrected harness and
   both fixed by adding tests rather than by dropping the mutation:
   `view-shares-the-live-mapping` was noticed by nothing, because handing an
   observer the world's own mapping is unobservable while state is immutable;
   `negative-balance-rail-off` was noticed by nothing, because the ordinary
   validation path never reaches that rail. The first is now checked as a
   containment property, the second by calling the commit step directly with the
   staged effects that trip it.

4. **A missing declared rule.** The original nine assertions never checked the
   duplicate-identity and duplicate-sequence rules, although the declarations
   state them and the roadmap requires the first. Added as A10.

No assertion was weakened and no expected result was replaced at any point.

### Guarantees demonstrated

- One contested unit produces exactly one winner and exactly one credit; the
  loser carries an explicit reason; balances stay at or above zero; the declared
  total is conserved.
- A transaction with an unauthorised, unknown or unaffordable leg commits none of
  its legs, including the legs that would have succeeded alone.
- An indivisible transaction against insufficient stock is denied outright. Zero,
  negative, fractional and boolean amounts are denied rather than rounded,
  reversed or treated as no-ops.
- Every permutation of the genesis balance map, source map, authorised set,
  claim source map and proposal collection gives one canonical result: 576
  orderings, one digest.
- The rotation gives no permanent winner over equivalent contention at
  successive ticks, for two and for three claimants, and a high-sorting identity
  wins as often as a low-sorting one.
- The roadmap's credit fixture holds at both resolver orders, and a unit credited
  this tick, whether transferred or claimed, is only spendable at the next tick.
- Views, states, sources, records, outcomes and effects all refuse mutation; a
  view or record taken earlier is unchanged after later ticks; the maps handed to
  the constructor and to a proposal can be edited afterwards with no effect.
- Diagnostics on and off give identical canonical results, a hostile sink that
  corrupts its payload and raises changes nothing and is counted, and settlement
  cannot import the diagnostics channel at all.

### Limitations

- **Stage 1 is not complete and its exit gate is not claimed.** Slices 1b, 1c and
  1d are not built: no reservations, no two-tick actions, no cancellation, no
  sealed evidence stream, no replay, no recovery, no instance isolation, no
  capacity benchmark.
- **No independent review has been requested, supplied or held.**
- The roadmap's clause that optional capture must not perturb identity allocation
  is only partly exercised, because this slice allocates no identity of its own:
  proposal identities are supplied by the caller. Slice 1c must satisfy it
  properly.
- The tick record is in memory only. It is not the sealed evidence schema, and it
  does not yet carry immutable copies of the inputs and alternatives a decision
  used. It records identity, reason and committed effects. Slice 1c specifies the
  schema and writes it.
- Contention over successive ticks is shown by sweeping the genesis tick, because
  nothing in this slice produces resources, so a depleted source cannot be
  refilled to contend over again inside one run. The engine's own tick-over-tick
  rotation is checked separately across four consecutive ticks.
- Rotation is deterministic priority. It is not a fairness result, and it says
  nothing about claimants whose opportunity or eligibility differ.
- `WorldView` gives every actor the whole boundary. Bounded perception is Stage 2.
- The conservation rail is unreachable by any current input, as recorded above.
- Amounts are unbounded Python integers. No overflow behaviour is defined,
  because none exists at this size.
- Nothing here is a world, a person or a behaviour. No claim is made about six
  people, fifty actors, performance, or any social or emergent property.

## Review

No independent review has been requested, supplied or held. Stage 1 has three
further slices and its exit gate is not claimed. Under `AGENTS.md`, progression
past Stage 1 additionally requires a separate reviewer using a different model,
which has not happened.

## Rollback

The work sits in four commits on `codex/kernel-first-slice` in a repository with
no remote. Nothing outside `C:\dev\03-Living-World-V3` was changed.

To undo the slice but keep the adopted documents, revert or reset to
`bbbf142f1399c1642c567d3d9c78792610b2df0b`. To undo everything including the
adoption, reset to before `2bf08e9e4629022adb508b5c6db53a144bb355b4`, or delete
the repository directory.

Exact files introduced by the slice, all of which may be deleted to remove it:

- `kernel/__init__.py`, `canonical.py`, `diagnostics.py`, `engine.py`,
  `ordering.py`, `outcomes.py`, `proposals.py`, `reasons.py`, `settlement.py`,
  `state.py`, `units.py`, `version.py`
- `tests/__init__.py`, `support.py`, `test_atomicity.py`, `test_contention.py`,
  `test_credit_boundary.py`, `test_dependency_direction.py`,
  `test_determinism.py`, `test_indivisibility.py`, `test_integrity_rails.py`,
  `test_observation.py`, `test_order_independence.py`,
  `test_proposal_identity.py`, `test_rotation.py`
- `evidence/stage-01/RECORD.md` and `evidence/stage-01/instrument/`
- `pyproject.toml`, `.gitignore`, `.gitattributes`

Configuration to revert: `pyproject.toml` holds the only configuration, the
pytest `pythonpath` and `testpaths` settings. There is no other configuration
file, no environment variable and no installed package.
