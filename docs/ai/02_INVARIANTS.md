# Integrity contracts and modelling rules

## Source snapshot

- Source branch: `codex/kernel-first-slice`
- Source HEAD: `eda72d290bdb33aaaf620ad136149c6ef04e0a96`
- Constructed: 2026-09-28 from local source inspection and recorded documentation.
- Currency: snapshot only; not automatically current after this revision. Recheck relevant source and Git state before acting.
- Authority: [AGENTS.md](../../AGENTS.md) wins over this pack; [WORLD_DIRECTIONS.md](../../WORLD_DIRECTIONS.md) supplies current development direction.
- Evidence source: listed implementation and contract tests; AGENTS.md guarantees.
- Refresh trigger: after integrity-contract or enforcement changes.

## Classification

The IDs below are pack-local retrieval labels, not historical decision IDs. Enforcement describes source at the snapshot; tests are verification routes, not fresh PASS claims.

- **KERNEL INVARIANT:** validity of ledger transactions, ordering or immutable kernel state.
- **WORLD INVARIANT:** consistency of world state, permitted information or saved execution.
- **MODELLING RULE / CURRENT PARAMETER:** an authored choice that can change intentionally. Its implementation must match its declared rules, but the chosen value is not a universal integrity requirement.

## Kernel invariants

| ID / name | Rule and reason | Systems / enforcement | Verification method | Failure consequence |
| --- | --- | --- | --- | --- |
| K1 Resource accounting | Transactions balance independently for each resource; balances stay non-negative integers. Consumption remains in a sink. This separates real use from leakage. | [units](../../kernel/units.py), [state](../../kernel/state.py), [settlement](../../kernel/settlement.py): authority, balance, shortfall and commit rails. | [integrity rails](../../tests/test_integrity_rails.py), [resources](../../tests/test_resources.py), [atomicity](../../tests/test_atomicity.py). | Created, lost or cross-converted resources invalidate behaviour. |
| K2 Atomic authority | Commit the whole authorized transaction or deny it. Reject duplicate proposal identities/order conflicts rather than favor arrival order. | [proposals](../../kernel/proposals.py), settlement validation and explicit outcomes. | [indivisibility](../../tests/test_indivisibility.py), [proposal identity](../../tests/test_proposal_identity.py), [contention](../../tests/test_contention.py). | Partial effects, unauthorized debit or arrival-dependent winners. |
| K3 Availability boundary | Accepted debits reduce remaining tick-start availability; incoming credits and released reservations become spendable at the next boundary. | Settlement's staged effects and availability; state reservation accounting. | [credit boundary](../../tests/test_credit_boundary.py), [reservations](../../tests/test_reservations.py). | Reuse of the same units within a tick. |
| K4 Reservation lifecycle | Holds are existing stock, not production or consumption. Complete/cancel consistently and release once; cancellation precedes completion. | State reservations; settlement phase order and reserved plans. | Reservation lifecycle, competing completion/cancellation and recovery fixtures in [reservations](../../tests/test_reservations.py) and [recovery](../../tests/test_recovery.py). | Double settlement, stranded holds or excess spendable stock. |
| K5 Deterministic ordering | Given the same boundary and proposals, canonical outcomes do not depend on collection/map iteration. | [ordering](../../kernel/ordering.py): sorted rotating roster; settlement phases and assigned sequences; [canonical](../../kernel/canonical.py). | [rotation](../../tests/test_rotation.py), [order independence](../../tests/test_order_independence.py), [determinism](../../tests/test_determinism.py). | Irreproducible conflicts and replay divergence. Rotation alone does not prove fairness. |
| K6 Inert observation and isolation | Old state/views remain unchanged; detached diagnostics cannot affect settlement; ticks cannot re-enter the same engine. | Frozen state/outcomes, copied maps, [engine](../../kernel/engine.py) guard, [diagnostics](../../kernel/diagnostics.py). | [observation](../../tests/test_observation.py), determinism, recovery and [dependency direction](../../tests/test_dependency_direction.py). | Inspection changes the world or engine instances interfere. |

## World invariants

| ID / name | Rule and reason | Systems / enforcement | Verification method | Failure consequence |
| --- | --- | --- | --- | --- |
| W1 Explicit post-settlement changes | Record source renewal and structural ledger changes. Births/cache creation introduce zero holdings/stock. Transaction conservation does not prohibit recorded production. | [process](../../world/process.py), [housing](../../world/housing.py), [apply_production](../../stream/run_file.py). Separate committed and processed state identities. | [world](../../tests/test_world.py), [housing](../../tests/test_housing.py), [fishing](../../tests/test_fishing.py), [replay](../../tests/test_replay.py). | Hidden gains or a saved state that cannot be reconstructed. |
| W2 Permitted information | Choices use bounded observations and retained information. Unseen current stock, deaths or trip progress cannot silently update a person's knowledge. Known landmark locations are allowed. | [observe](../../world/observe.py), [foraging](../../world/foraging.py), [storage](../../world/storage.py), housing observation. | [perception](../../tests/test_perception.py), [source memory](../../tests/test_source_memory.py), [coordination](../../tests/test_coordination.py). | Omniscient behaviour mistaken for learning or cooperation. |
| W3 Consistent continuation | Saved configuration, ledger and overlay reconstruct the same execution. World replay uses the live world-step path. | [overlay](../../world/overlay.py), config round-trips, [world replay](../../world/replay.py), [world recovery](../../world/recover.py). | Replay/recovery plus feature tests with active memories, casts, trips and expectations. | State disappears on birth/load or continuation changes decisions. |
| W4 Verified prefix | Recovery trusts only the first verified header and contiguous sealed prefix, and refuses incompatible code identity. | [reader](../../stream/run_file.py), [sealed_prefix](../../stream/recover.py). | [damaged suffix](../../tests/test_damaged_suffix.py), [seal and prefix](../../tests/test_seal_and_prefix.py). | Corrupt suffix/header content changes resumed history. |
| W5 Native observable causes | Saved choices/outcomes explain actual execution; viewers do not independently choose actions. Timing and diagnostics are excluded from canonical simulation history. | Run writer, [viewer index](../../world/viewer_index.py), viewer; stream timing separation. | [map viewer](../../tests/test_map_viewer.py), [sealed stream](../../tests/test_sealed_stream.py), dependency/determinism tests. | Presentation or measurement fabricates a causal story. |

## Modelling rules are changeable

Current examples: four-neighbour movement; child leash 5; adulthood at 60 ticks; social memory of four distinct donors; empty-source memory 20 ticks; household expectation 12 ticks; low-cache trigger below two meals; store target six; plentiful/lean periods of 120 ticks.

These are **MODELLING RULE / CURRENT PARAMETER**, supported by [config](../../world/config.py), [social](../../world/social.py), [foraging](../../world/foraging.py), [storage](../../world/storage.py) and [ecology](../../world/ecology.py). They are not permanent integrity invariants. Intentional changes require corresponding rule descriptions, persistence/replay consideration and focused behaviour checks. “A different duration” is distinct from “memory cleared accidentally by a birth.”

Likewise, a refusal is a valid outcome. A selected claim need not succeed, a promised delivery need not arrive, and a population increase does not establish a general survival benefit.
