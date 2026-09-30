# System retrieval map

## Source snapshot

- Source branch: `codex/kernel-first-slice`
- Source HEAD: `eda72d290bdb33aaaf620ad136149c6ef04e0a96`
- Constructed: 2026-09-28 from local source inspection and recorded documentation.
- Currency: snapshot only; not automatically current after this revision. Recheck relevant source and Git state before acting.
- Authority: [AGENTS.md](../../AGENTS.md) wins over this pack; [WORLD_DIRECTIONS.md](../../WORLD_DIRECTIONS.md) supplies current development direction.
- Evidence source: listed source entry points and test files.
- Refresh trigger: after significant module/file movement or subsystem changes.
- 2026-09-29 addition: remembered-contribution row, checked against local `codex/remembered-contribution` based on `fe940ef`. The rest of this map was not re-audited.

Use this after [current state](05_CURRENT_STATE.md). Paths are relative links to this checkout. Test links identify where to inspect verification, not executed results. Shared context: [architecture](01_ARCHITECTURE.md), [invariants](02_INVARIANTS.md), and [WORLD_DIRECTIONS](../../WORLD_DIRECTIONS.md).

| Concept / purpose | Primary files and entry points | Dependencies / affected systems | Tests to start with |
| --- | --- | --- | --- |
| Settle resource transactions | [engine](../../kernel/engine.py): Engine.tick; [settlement](../../kernel/settlement.py): settle; [proposals](../../kernel/proposals.py) | State, ordering, outcomes; every transactional resource action | [contention](../../tests/test_contention.py), [atomicity](../../tests/test_atomicity.py), [resources](../../tests/test_resources.py) |
| Reserved work | [state](../../kernel/state.py): Reservation, availability; settlement phases | Claims/holds/completion/cancellation, restoration | [reservations](../../tests/test_reservations.py), [credit boundary](../../tests/test_credit_boundary.py) |
| Configuration and genesis | [config](../../world/config.py): WorldConfig, describe/from_describe, genesis | Ledger/overlay, known landmarks, switches, replay | [world](../../tests/test_world.py), [sources](../../tests/test_sources.py) |
| Local sight and source choice | [observe](../../world/observe.py): observe, target_source | Ledger availability, overlay, food/water journeys | [perception](../../tests/test_perception.py), [sources](../../tests/test_sources.py) |
| Routes and terrain memory | [decide](../../world/decide.py): route_step; observe/process/overlay | Seen and remembered rough cells, child limits, travel | [review regressions](../../tests/test_review_regressions.py), [review followups](../../tests/test_review_followups.py) |
| Needs and action choice | decide: decide, _decide_needs, candidates; [run](../../world/run.py): proposals_for | Observation/config, resource proposals, movement | [warmth](../../tests/test_warmth.py), [water](../../tests/test_water.py), [scoring](../../tests/test_scoring.py), [yield](../../tests/test_yield.py) |
| Families, births, caregiving | [process](../../world/process.py): advance, _births; decide: someone_to_help | Overlay age/parent links, ledger roster, feeding, homes | [birth spacing](../../tests/test_birth_spacing.py), [nearby caregiving](../../tests/test_nearby_caregiving.py) |
| Requests, promises, received-food memory | decide: someone_to_ask/someone_to_help; process; [social](../../world/social.py): remember_food | Local encounters, accepted transfers, later helping | [adjacent handoff](../../tests/test_adjacent_handoff.py), [social memory](../../tests/test_social_memory.py), [review followups](../../tests/test_review_followups.py) |
| Patch wear and seasons | [ecology](../../world/ecology.py): recover_patches, season_at, food_growth | Accepted claims and renewal; source stock | [regrowth](../../tests/test_regrowth.py), [seasons](../../tests/test_seasons.py) |
| Fishing and empty-source memory | [fishing](../../world/fishing.py), [foraging](../../world/foraging.py): remember_empty; observe/decide/process | Cast state, source ranking, ordinary food claims | [fishing](../../tests/test_fishing.py), [source memory](../../tests/test_source_memory.py) |
| Wood and construction | [materials](../../world/materials.py): wood_cost; decide/process | Named-resource claims/consumes; shelter progress | [wood](../../tests/test_wood.py) |
| Home choice and relocation | [housing](../../world/housing.py): choose_site, choose_relocation, apply_housing, update_experience | Local/stale vacancy knowledge, arrival contention, homes/cache creation | [housing](../../tests/test_housing.py), [relocation](../../tests/test_relocation.py) |
| Shared caches and provisioning | [storage](../../world/storage.py): spare_for_store, start_provisioning, update_provisioning; decide: _provision_decision | Ledger deposits/claims, need interruptions, natural sources | [stores](../../tests/test_stores.py), [provisioning](../../tests/test_provisioning.py) |
| Firsthand source reports (local update 2026-09-28) | [foraging](../../world/foraging.py): remember_sightings, usable_reports, update_reports; observe/decide/process/overlay | Adjacent housemates, provenance, expiry, personal/provisioning destinations, saved viewer reasons | [knowledge sharing](../../tests/test_knowledge_sharing.py) |
| Household announcements | storage: food_expectation, update_food_expectations; observation/decision fields | Local hearing after choices, optional trip postponement | [coordination](../../tests/test_coordination.py) |
| Remembered contribution | storage: remember_contributions, prefer_contribution; overlay contribution_memory and contribution_selection | Tick-start sight of an accepted home-cache deposit; preference only among competing announcements | [remembered contribution](../../tests/test_remembered_contribution.py) |
| Run, read, replay, recover | run: world_step/run_world; [run_file](../../stream/run_file.py): RunWriter/read_run; [world replay](../../world/replay.py); [world recovery](../../world/recover.py) | Full causal record, canonical state, sealed prefixes | [replay](../../tests/test_replay.py), [recovery](../../tests/test_recovery.py), [damaged suffix](../../tests/test_damaged_suffix.py) |
| Watch and inspect | [world viewer](../../world/viewer.py), [index](../../world/viewer_index.py), [JS](../../world/viewer.js), [CSS](../../world/viewer.css) | Saved run only; people/events/history/inspector | [map viewer](../../tests/test_map_viewer.py), feature viewer assertions |
| Cost and isolation | [world bench](../../world/bench.py), [stream bench](../../stream/bench.py), kernel boundaries | Specific workload timing/memory and instance safety | [world bench tests](../../tests/test_world_bench.py), [bench tests](../../tests/test_bench.py), [dependency direction](../../tests/test_dependency_direction.py) |

For source changes, follow the affected row through state, configuration/header reconstruction, native saved fields and viewer consumers. Adding an overlay field requires particular attention to birth reconstruction and recovery: previous feature reports describe lost memories/casts through the birth path.

Relevant document routing: [testing](08_TESTING_AND_PROOFS.md) for commands and evidence scope; [decisions](04_DECISIONS.md) for rationale; [repo map](09_REPO_MAP.md) for historical fixtures and ignored artifacts. Feature sections in WORLD_DIRECTIONS are narrative examples, not automatic active-slice declarations.
