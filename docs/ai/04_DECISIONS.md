# Design decisions and rationale

## Source snapshot

- Source branch: `codex/kernel-first-slice`
- Source HEAD: `eda72d290bdb33aaaf620ad136149c6ef04e0a96`
- Constructed: 2026-09-28 from local source inspection and recorded documentation.
- Currency: snapshot only; not automatically current after this revision. Recheck relevant source and Git state before acting.
- Authority: [AGENTS.md](../../AGENTS.md) wins over this pack; [WORLD_DIRECTIONS.md](../../WORLD_DIRECTIONS.md) supplies current development direction.
- Evidence source: AGENTS.md; WORLD_DIRECTIONS.md; archived OD-014; listed implementation.
- Refresh trigger: after a supported architectural decision or supersession.

These entries compress supported decisions. They do not authorize new work. Pack-local D-* labels are navigation labels, not invented historical records. Historical OD identifiers retain their original meaning; their surrounding governance is inactive under current AGENTS.md.

## OD-014 — Obtain, possess and eat remain separate

- **Decision:** keep claim/obtain and eating as separate actions.
- **Reason:** possession is useful intermediate world state; later transfer, storage, interruption and competition can act on held food before consumption. Visual convenience is insufficient reason to collapse the actions.
- **Evidence:** [archived OD-014](../../archive/governance/AGENTS.md), heading “OD-014”; [credit-boundary tests](../../tests/test_credit_boundary.py); current [proposals_for](../../world/run.py).
- **Affected systems:** action selection, settlement, food stores, helping, fishing and playback.
- **Relevant invariants:** K3, W5 in [invariants](02_INVARIANTS.md).
- **Status:** HISTORICAL ARCHITECTURAL DECISION, still reflected in implementation. The same entry explicitly records checkpoint C acceptance; this does not establish acceptance of later features.
- **Supersession:** supplements OD-013 with the owner's rationale. The later AGENTS.md retires the stage/ratification process; it does not make same-tick eating implemented.

## D-01 — A watchable rule-based world

- **Decision:** build a civilisation aquarium with authored runtime choices and make additions visible in the viewer.
- **Reason:** a world worth watching, with consequences understandable as behaviour.
- **Evidence:** [AGENTS.md](../../AGENTS.md); [WORLD_DIRECTIONS](../../WORLD_DIRECTIONS.md), “Working direction” and “Making each addition visible and trustworthy.”
- **Affected systems:** world behaviour and presentation; relevant invariants W2, W5.
- **Status:** CURRENT DOCUMENTED DIRECTION.
- **Supersession:** current AGENTS.md explicitly displaces historical governance as instructions. No successor was established at the source revision.

## D-02 — Ledger and overlay have different ownership

- **Decision:** kernel state owns resource holdings/reservations; overlay owns world/person state. World processing records explicit post-settlement production and structural changes.
- **Original rationale:** UNKNOWN as a historical decision. Current module documentation explains the implemented boundary.
- **Evidence:** [state](../../kernel/state.py), [overlay](../../world/overlay.py), [process](../../world/process.py), [run_file](../../stream/run_file.py).
- **Affected systems:** all world ticks and persistence; relevant invariants K1, W1, W3.
- **Status:** IMPLEMENTED DESIGN.
- **Supersedes / superseded by:** UNKNOWN; no historical decision chain established for this entry.

## D-03 — Separate deterministic content from measurement

- **Decision:** canonical header/tick content and seals exclude wall-clock timing; code identity is derived from source bytes.
- **Reason:** the run-file module explicitly separates nondeterministic timing from repeatable content.
- **Evidence:** [run_file](../../stream/run_file.py), [determinism tests](../../tests/test_determinism.py), [sealed stream tests](../../tests/test_sealed_stream.py).
- **Affected systems:** recording, replay, diagnostics and benchmarks; relevant invariants K5, W4, W5.
- **Status:** IMPLEMENTED DESIGN WITH DOCUMENTED TECHNICAL REASON.
- **Supersession:** v3.stream.3 adds seals/inputs to earlier readable formats; see module format notes, not a new approval record.

## D-04 — Local evidence guides household expectations

- **Decision:** announcements are heard after tick choices and temporarily postpone optional cache trips. They do not assign workers or guarantee delivery.
- **Reason:** communicate an intended food outing while preserving simultaneous decisions, urgent needs and the possibility of interruption.
- **Evidence:** [WORLD_DIRECTIONS](../../WORLD_DIRECTIONS.md), “Telling housemates about a food trip”; [storage](../../world/storage.py); [coordination tests](../../tests/test_coordination.py).
- **Affected systems:** provisioning, observation, memory and viewer; relevant invariants W2, W3, W5.
- **Status:** IMPLEMENTED DESIGN, optional and off by default.
- **Supersession:** extends independent provisioning; no formal predecessor/successor decision ID established. Original rationale for choosing exactly twelve ticks: UNKNOWN; the direction notes call it a first rule to watch, not a tuned value.

Further design history should be retrieved from the source relevant to the task, not copied wholesale from the archived owner-direction register.
