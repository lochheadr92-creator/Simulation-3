# Current architecture

## Scoped update — care by visible need, 2026-09-30

Checked against `e34decc` plus the local caregiving-priority change.
`WorldConfig.care_by_need_on` and CLI `--care-by-need` enable optional priority
for visibly starving children among visible empty-handed dependents. It
requires childhood and defaults off. `decide.someone_to_help` owns this
recipient ranking; it consumes the existing `SeenPerson.starving` flag and
does not gain exact hunger or distant knowledge. Own needs and the existing
nearby-handoff exception still arbitrate whether help happens. Saved decision
reasons explain priority through the existing viewer. No overlay or stream
schema changed, and off-mode descriptions remain unchanged.

## Scoped update — two birth parents, 2026-09-30

Checked at `fe940ef` plus preserved witnessed-death/configuration work and
the local shared-care addition. Optional `shared_care_on` (requires childhood,
default false) records the other birth adult in sparse `Overlay.second_parent`;
`parent` keeps the original birth-home link. `Overlay.children_of` unifies
the two relationships for observation and the existing dependent-child
relocation restriction. `process` preserves both across ticks and births.
Ordinary caregiving choice/settlement logic is unchanged; simultaneous offers
can each deliver one unit. The viewer reads both saved links and native outcomes.
Old states lack the new field and retain their digest; no second parent is
inferred. Off-mode configuration descriptions are unchanged. See the current
slice and latest WORLD_DIRECTIONS for verification and comparison limits.

## Scoped update — witnessed household death, 2026-09-30

Checked at `fe940ef` plus local changes. For an existing food expectation,
`observe` can record the speaker's death only at the just-completed boundary
and within the listener's sight, using both final positions. The sparse
`witnessed_deaths` observation feeds `storage.food_expectation`; existing
processing then drops the expectation. No new overlay field is required.
The saved observation and expectation-end event supply the viewer's inspector
and history. Later discovery of an old death and unseen death do not count.
The coordination rule description changes; older coordination-on headers
remain readable but do not reconstruct under the new rule.
See the current slice and WORLD_DIRECTIONS for verification and the absence
of activation in the sampled ordinary worlds. The original snapshot below
retains its original revision metadata.

## Source snapshot

- Source branch: `codex/kernel-first-slice`
- Source HEAD: `eda72d290bdb33aaaf620ad136149c6ef04e0a96`
- Constructed: 2026-09-28 from local source inspection and recorded documentation.
- Currency: snapshot only; not automatically current after this revision. Recheck relevant source and Git state before acting.
- Authority: [AGENTS.md](../../AGENTS.md) wins over this pack; [WORLD_DIRECTIONS.md](../../WORLD_DIRECTIONS.md) supplies current development direction.
- Evidence source: kernel/, stream/, world/ and viewer source; dependency tests.
- Refresh trigger: after architectural or state-ownership boundary changes.

## Product and layers

The product is a seeded Python civilisation aquarium: people live on a grid, observe locally, choose by authored rules and experience consequences. The viewer plays a saved world; there is no runtime AI choosing actions.

| Layer | Owner and entry points | Boundary |
| --- | --- | --- |
| Kernel | [engine.py](../../kernel/engine.py), [state.py](../../kernel/state.py), [settlement.py](../../kernel/settlement.py), [proposals.py](../../kernel/proposals.py) | Resource transactions, reservations, immutable ledger and outcomes. No world behaviour. |
| Stream | [run_file.py](../../stream/run_file.py), [replay.py](../../stream/replay.py), [recover.py](../../stream/recover.py) | File integrity and generic continuation support. Does not import world. |
| World | [run.py](../../world/run.py), [config.py](../../world/config.py), [overlay.py](../../world/overlay.py), [observe.py](../../world/observe.py), [decide.py](../../world/decide.py), [process.py](../../world/process.py) | People, geography, needs, behaviour and world-specific replay/recovery. Depends downward on stream/kernel. |
| Presentation | [world/viewer.py](../../world/viewer.py), [viewer_index.py](../../world/viewer_index.py), JS/CSS | Reads saved behaviour; animation does not resolve actions. |

The current [world/viewer.py](../../world/viewer.py) depends on [stream.run_file](../../stream/run_file.py) to read saved runs; it remains presentation-only and does not import the kernel or re-run world decisions. Changes to the stream schema or `Run` validation can therefore affect viewer behaviour, while the viewer does not participate in simulation decisions or settlement.

The older [viewer/world_view.py](../../viewer/world_view.py) is separate and imports none of kernel, stream or world. Its compatibility is narrower; use the current world viewer for the current aquarium. [Dependency tests](../../tests/test_dependency_direction.py) check package direction and kernel layering.

## Scoped update — firsthand reports, 2026-09-28

Checked against `22ffe27` plus local sharing/travel changes. `world/foraging.py`
owns retention and merging of firsthand food sightings and heard empty-source
reports. `observe` filters reports against personal sight and derives source
choices; `decide` records one firsthand report and adjacent housemate recipients.
`process.advance` delivers after choices. Sparse immutable `food_sightings`
and `source_reports` fields round-trip and survive births. Native observations
and reasons distinguish a report's effect from personal empty-source memory;
the viewer displays that record. See `tests/test_knowledge_sharing.py`.
The original snapshot below otherwise retains its original revision metadata.

## State ownership

`WorldConfig` defines seed, geometry, levers, feature switches and saved rule descriptions. `genesis` constructs a kernel ledger and world overlay. Seeded randomness is used to construct initial conditions; choices during ordinary ticks follow deterministic rules.

`WorldState` owns actor holdings, shared sources, consumption sinks and reservations. Food is the base resource; water and optional wood are named resources. Consumption transfers units into a sink rather than silently deleting them.

`Overlay` owns homes, positions, hunger/thirst/cold, death records, shelter work, age, parent links, birth recovery, requests/promises, terrain and food memories, housing experience, fishing casts, provisioning trips and food expectations. Objects are replaced, not mutated in place. The person is an actor identity represented across these structures, not a separate autonomous engine.

## One world tick

`world.run.world_step` is shared by running and world replay:

1. Read the frozen ledger and overlay; compute tick-start availability.
2. `observe` constructs each living person's bounded observation.
3. `decide` selects actions. `proposals_for` translates resource actions into kernel proposals; movement and other world actions remain recorded decisions.
4. `Engine.tick` settles proposals and publishes the committed ledger and outcomes.
5. `process.advance` updates movement, needs, construction, memories and deaths, then applies the relevant housing, household, renewal and birth processing.
6. The next tick uses the processed overlay and ledger. The writer saves observations, decisions, submitted inputs, outcomes, committed state, production and world state.

Kernel resolution validates identity, authority and preconditions, handles cancellations before completions, and resolves new work against remaining tick-start availability. Actor priority rotates deterministically. Incoming credits are not spendable until the next tick. A person catching or collecting food still needs a later eating action.

## Settlement versus world production

**Transactional resource movements settle through the kernel. Settlement is not the only mechanism that produces a changed ledger.**

After settlement, world processes may renew source stock, add a newborn with zero holdings, or create an empty housing cache. These changes are explicitly recorded in the tick's `production` entries. Births also extend source authorization and the roster; cache creation introduces a source without creating food.

The scope is precise: kernel settlement is the write path for transactional effects against existing accounts and balances. After settlement, explicit world processing may construct the replacement post-settlement state for recorded production or structural changes, including supported source renewal, newborn creation and empty housing-cache creation. The stream records those production entries, and reconstruction applies them to the committed state.

The run records the committed ledger separately from the post-process state identity. [apply_production](../../stream/run_file.py) reconstructs recorded renewal, birth and source-creation effects; the reader checks the resulting digest and chain. Subsequent ticks start from this processed state. Conservation across settlement is exact; world totals can increase by explicitly recorded production. Do not confuse this with arbitrary domain writes to transactional balances.

## Information and action boundaries

Sight uses Chebyshev distance; movement uses four-neighbour steps. Declared natural source positions are known landmarks. Dynamic home-cache positions are only available through the world's local visibility rules; their stock is never globally revealed. Stock and other people are observed locally; out-of-view stock is unknown, not zero. Terrain memory retains seen rough cells. Source memory retains dated empty sightings; shelter memory can retain stale vacancies.

Need arbitration considers time remaining to lethal levels, with current caregiving exceptions. Optional scoring is a narrower food-action mode; configuration rejects combinations with water, warmth or requests. Selection does not guarantee execution: contention can deny a claim, a destination can be occupied on arrival, and another need can interrupt a trip.

## Implemented world behaviour

| System | Implemented behaviour at this revision |
| --- | --- |
| Families | Births after qualifying settled encounters; childhood, age, a recorded caregiving parent, child travel limits and feeding; optional birth recovery. Broader family life is partial: no ageing beyond childhood or coordinated dependent-family moves. |
| Social behaviour | Offers, optional walking/adjacent requests, promises and direct handoffs. Social memory remembers received food and influences helping among eligible visible people. It is not a general relationship model. |
| Ecology | Optional patch wear/recovery and plentiful/lean food seasons; explicit capped renewal. No general weather/ecosystem model. |
| Homes | Shelter building, optional adult home choice/joining, physical arrival and optional relocation after difficult supply outings. Housing contenders use the tick's rotated order. |
| Materials | Optional grove gathering and wood consumption for building work. |
| Fishing | Optional bank location with finite stock, a cast then a later catch; fish become ordinary food. |
| Source memory | Optional dated empty-source memory influences later food destinations; fresh local sightings and expiry update it. |
| Stores/provisioning | Optional shared food caches and trips to natural food sources, followed by return and ordinary deposit. Trips can be interrupted or return without surplus. |
| Coordination | Optional departure announcements to visible housemates. Listeners temporarily postpone optional trips; needs/helping retain priority. Speech is not a worker assignment or delivery guarantee. |

Defaults in WorldConfig enable water, warmth, terrain/routing, construction, offers, social memory, births and childhood. Requests, ecology switches, stores, adult homes, relocation, wood, fishing, source memory, provisioning and coordination are off; birth spacing is zero. Coordination requires provisioning, which requires stores; homes requires childhood, relocation requires homes, and wood requires building. Config validation is authoritative for combinations.

See [system map](03_SYSTEM_MAP.md) for code and tests, and [roadmap](07_ROADMAP.md) for suggestions that are not implemented commitments.

## Persistence and observation of a run

The writer uses sealed `v3.stream.3` JSONL. Header and ticks carry canonical content; timing is outside seals/digests. Code identity hashes Python sources in kernel, stream and world, independently of Git. A code digest is not a commit or publication receipt.

[World replay](../../world/replay.py) rebuilds configuration/genesis and recomputes each tick through `world_step`. [Recovery](../../world/recover.py) restores ledger plus overlay from a verified prefix and continues into a new file; it requires matching code identity. Readability of an old file does not imply replay compatibility with changed rules.

The current viewer indexes saved decisions and outcomes. View 0 is genesis; view k shows the result of simulation tick k-1. Interpolation is visual only. Diagnostics receive detached content and cannot feed settlement; diagnostic failures are counted. These are instrumentation boundaries, not proof that every future viewer change is correct.
