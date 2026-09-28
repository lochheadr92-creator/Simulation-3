# Terminology

## Source snapshot

- Source branch: `codex/kernel-first-slice`
- Source HEAD: `eda72d290bdb33aaaf620ad136149c6ef04e0a96`
- Constructed: 2026-09-28 from local source inspection and recorded documentation.
- Currency: snapshot only; not automatically current after this revision. Recheck relevant source and Git state before acting.
- Authority: [AGENTS.md](../../AGENTS.md) wins over this pack; [WORLD_DIRECTIONS.md](../../WORLD_DIRECTIONS.md) supplies current development direction.
- Evidence source: source types/functions and current feature descriptions.
- Refresh trigger: when project terminology changes.

Definitions describe this revision. Follow [system map](03_SYSTEM_MAP.md) for implementation; [architecture](01_ARCHITECTURE.md) explains relationships.

| Term | Meaning here |
| --- | --- |
| Civilisation aquarium | The watchable rule-based living world; not a runtime LLM agent society. |
| Actor / person | Stable identity used by kernel accounts and world records. World people also have overlay state; the kernel need not know their needs. |
| Ledger / WorldState | Immutable resource accounts, sources, sinks and reservations. |
| Overlay | Immutable non-resource world state: position, needs, homes, family links, memories and ongoing activities. |
| Genesis | Initial ledger/overlay generated from saved configuration and seed. |
| Tick-start boundary | State against which observations and transactional availability are determined. |
| Observation | A person's permitted current information plus relevant retained memory and known landmarks. |
| Availability | Spendable stock at the boundary after holds, reduced by accepted debits during resolution. It differs from total account holdings. |
| Proposal | Identified request to the kernel for a resource operation; selection is not acceptance. |
| Effect | Signed change to one account within a transaction's balanced effects. |
| Settlement | Kernel validation, ordered resolution and atomic transaction commit. |
| Reservation | Hold against existing units for future completion or cancellation; neither extra stock nor consumption. |
| Consumption sink | Account retaining consumed units for accounting while removing them from circulation. |
| Production | Run-record category for explicit post-settlement renewal and structural ledger changes, including births/empty source creation. Not every production entry creates units. |
| Committed / processed state | Settlement output versus the ledger after recorded world production/structural processing. |
| Request | Person-to-person food ask awaiting the next response opportunity; distinct from already delivered food. |
| Promise / errand | Helper's short-lived commitment to a recipient; can end without successful delivery. Not long-term social memory. |
| Food memory | Retained received-food donor encounters used in later helping choices. |
| Terrain memory | Rough cells previously seen and used for routing; not global terrain knowledge. |
| Empty-source memory | Dated local empty sightings affecting food-source selection. |
| Shelter memory | Retained potential housing locations; unseen vacancies can be stale. |
| Provisioning | Gathering for a low home cache, followed by a return phase. A started outing does not guarantee surplus. |
| Food expectation | Listener's remembered household announcement, temporarily delaying an optional trip. Not a reservation, assigned job or guaranteed delivery. |
| Cast / catch | Separate fishing steps; a catch claims ordinary food, which can be eaten later. |
| Shared cache | Kernel food source representing stored food at a home. No automatic growth. |
| Need slack | Remaining ticks to a lethal level at the configured rise rate, used in need arbitration. |
| Decision record | Selected action, reason and applicable candidates/scores emitted by the live choice path. |
| Canonical content | Stable serialized simulation data used for digests/comparison; wall-clock timing is separate. |
| Seal / sealed prefix | Chained integrity value / contiguous verified beginning of a run. A seal is not proof of external authenticity. |
| Reconstruction | Building ledger/overlay from their saved canonical forms, including recorded post-settlement changes. |
| Replay | Re-execution compared with a saved run. World replay recomputes choices; scenario replay resubmits inputs. |
| Recovery | Continue a damaged/incomplete run from its verified prefix into a new file with matching code identity. |
| Code identity | Digest of source-file content in kernel, stream and world; not a Git commit or push receipt. |
| View k | Saved world after k ticks; view 0 is genesis, view k displays actions/outcomes of tick k-1. |
| Recorded / fresh result | Previously reported execution / execution performed in the present task. Neither implies broader acceptance. |
| Invariant / modelling rule | Integrity contract / changeable authored behaviour or parameter. See [invariants](02_INVARIANTS.md). |
| Active slice | Explicitly established current work boundary. None was established for this snapshot. |
