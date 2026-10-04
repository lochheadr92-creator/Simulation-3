"""World processes: the rules applied after settlement, in a fixed order.

  0. errands    a request made this tick waits for an answer; one that was
                already waiting has now been answered or has lapsed, so it is
                gone. Agreeing takes on an errand, which lasts until the unit
                is handed over or the person who asked dies
  1. movement   a person who decided to step is now on that cell, unless the
                rough cell under them still owes a tick: rough ground costs an
                extra tick, so stepping onto it holds the next step back
  2. hunger     hunger' = max(0, hunger + rate - satiation * units eaten);
                only units the kernel actually settled as consumed count
  2a. shelter   building adds a work tick; with wood on, a due material payment
                must have settled. Completed shelters remain on their home
                cell for good; a tick that ends on a shelter spot or on any
                built shelter adds shelter_relief less hunger and thirst
  2b. cold      warmth on: a tick that ends on the person's own home cell
                (their shelter) takes `warming` off their cold, and any other
                tick adds `cold_rate`, whatever they decided; floored at zero
  3. death      hunger' >= death_at ends the person at this tick, as does
                thirst or cold reaching its own lethal level; the needs and
                the position freeze, their held units stay in the ledger
  3a. housing   living grown children arrive at a chosen adult home; shared
                shelters have two resident places. New caches start empty.
  4. renewal    every `renewal_every` ticks each food source gains
                `renewal_amount` up to `source_cap`. Seasons adjust the amount
                before patch wear; with local regrowth on,
                worn food patches grow half that amount, rounded up.
                Harvests wear patches and quiet ticks restore them. With water on each
                water source does the same with the water levers (food
                sources first, then water). Optional wood groves renew on
                their own cadence, after water. This is the one
                production rule, and it is recorded on the tick line and
                re-checked by the reader

Needs never pause: a rejected claim or an empty source leaves hunger rising.
Production is the only way stock enters the world and it goes
through the kernel's own validated constructor, never a balance write.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Mapping

from kernel import Source, TickRecord, WorldState
from kernel.proposals import OP_CONSUME, OP_TRANSFER
from kernel.state import SINK_ACCOUNT, actor_account, sink_account
from world.observe import in_view

from world.config import WATER, WorldConfig, stone_sites, wood_sites, fishing_sites
from world.crafting import STONE_RENEWAL, STONE_RENEWAL_EVERY, STONE_STOCK, apply_crafting
from world.fishing import FISH, FISH_STOCK, FISH_RENEWAL_EVERY, FISH_RENEWAL
from world.foraging import remember_empty, update_reports
from world.materials import WOOD, WOOD_STOCK, WOOD_RENEWAL_EVERY, WOOD_RENEWAL, wood_cost
from world.decide import AGREE, ASK, BUILD, Decision
from world.overlay import Overlay
from world.social import remember_food
from world.storage import update_provisioning, update_food_expectations
from world.ecology import food_growth, recover_patches, season_at, seasonal_growth
from world.housing import apply_housing, update_experience
from world.belief import advance_beliefs
from world.persona import advance_persona, born as persona_born, remember_attempt
from world.pledges import advance_pledges, help_credit
from world.sky import exposure, sight, sky_at, storm_hold
from world.society import advance_society
from world.things import Things
from world.traits import build_goal
from world.wolves import HEALING_KINDS, advance_wolves, mend

if TYPE_CHECKING:
    from world.observe import Observation


@dataclass(frozen=True)
class Processed:
    overlay: Overlay
    ledger: WorldState                       # the kernel state the next tick starts from
    production: tuple[dict[str, Any], ...]   # empty when nothing was produced
    eaten: Mapping[str, int]
    died: tuple[str, ...]


def _consumed(record: TickRecord, sink: str) -> dict[str, int]:
    """Units each person consumed into `sink` this tick, from accepted consume outcomes only."""
    out: dict[str, int] = {}
    for outcome in record.outcomes:
        if outcome.accepted and outcome.operation == OP_CONSUME:
            amount = sum(e.delta for e in outcome.effects if e.account == sink and e.delta > 0)
            if amount:
                out[outcome.actor] = out.get(outcome.actor, 0) + amount
    return out


def units_eaten(record: TickRecord) -> dict[str, int]:
    """Food eaten: consumption into the base sink only (drinking is not eating)."""
    return _consumed(record, SINK_ACCOUNT)


def units_drunk(record: TickRecord) -> dict[str, int]:
    return _consumed(record, sink_account(WATER))


def settled_pairs(overlay: Overlay, config: WorldConfig) -> list[tuple[str, str]]:
    """Pairs standing on adjacent cells who are both doing well: a finished
    shelter of their own, and no need calling."""
    homes_built = set(overlay.shelters)

    def well(actor: str) -> bool:
        if config.birth_spacing and overlay.birth_ready.get(actor, 0) > overlay.tick:
            return False
        if config.childhood_on and overlay.age.get(actor, config.adult_at) < config.adult_at:
            return False                                   # a child is nobody's partner
        return (overlay.alive(actor) and overlay.homes[actor] in homes_built
                and overlay.hunger[actor] < config.hungry_at
                and (not config.water_on or overlay.thirst[actor] < config.thirsty_at)
                and (not config.warmth_on or overlay.cold[actor] < config.cold_at))

    living = [actor for actor in overlay.roster if well(actor)]
    out = []
    for i, a in enumerate(living):
        for b in living[i + 1:]:
            (ax, ay), (bx, by) = overlay.positions[a], overlay.positions[b]
            if abs(ax - bx) + abs(ay - by) == 1:
                out.append((a, b))
    return out


def free_cell_near(origin: tuple[int, int], taken: set[tuple[int, int]], config: WorldConfig):
    """The nearest cell nobody lives on and no source occupies, by distance then
    row then column, so a birth always lands in the same place for a given world."""
    rough, spots = config.terrain()
    unavailable = taken | set(rough) | set(spots)
    cells = [(x, y) for y in range(config.height) for x in range(config.width) if (x, y) not in unavailable]
    if not cells:
        return None
    return min(cells, key=lambda c: (abs(c[0] - origin[0]) + abs(c[1] - origin[1]), c[1], c[0]))


def eased(rate: int, relief: int) -> int:
    """A need's rate under shelter. Never below 1 while the rate itself is at
    least 1: shelter makes a need slower, not survivable without eating."""
    return max(1, rate - relief) if rate >= 1 else rate


def advance(overlay: Overlay, decisions: Mapping[str, Decision], record: TickRecord,
            settled: WorldState, config: WorldConfig,
            observations: Mapping[str, "Observation"] | None = None) -> Processed:
    if settled.tick != overlay.tick + 1:
        raise ValueError("settled ledger and overlay are not one tick apart")
    eaten = units_eaten(record)
    drunk = units_drunk(record)
    positions = dict(overlay.positions)
    hunger = dict(overlay.hunger)
    thirst = dict(overlay.thirst)
    cold = dict(overlay.cold)
    held = {actor: overlay.held.get(actor, 0) for actor in overlay.roster}   # full, or the overlay refuses it
    rough, shelter_spots = config.terrain()
    rough, shelter_spots = set(rough), set(shelter_spots)
    shelters = set(overlay.shelters)
    # a request is answered or lapses on the tick after it is made, so only
    # this tick's asking survives into the next one
    requests = {actor: d.target for actor, d in decisions.items() if d.kind == ASK and d.target}
    promises = dict(overlay.promises)
    promises.update({actor: d.target for actor, d in decisions.items() if d.kind == AGREE and d.target})
    for outcome in record.outcomes:
        recipient = promises.get(outcome.actor)
        if recipient and outcome.accepted and outcome.operation == OP_TRANSFER:
            if any(e.account == actor_account(recipient) and e.delta > 0 for e in outcome.effects):
                promises.pop(outcome.actor, None)
    built = {actor: overlay.built.get(actor, 0) for actor in overlay.roster}
    credited: dict[str, int] = {}                 # pledge -> ticks of work a helper added to somebody's shelter
    wood_spent = _consumed(record, sink_account(WOOD)) if config.wood_on else {}
    age = {actor: overlay.age.get(actor, 0) for actor in overlay.roster} if config.childhood_on else {}
    terrain_memory = {actor: set(overlay.terrain_memory.get(actor, ())) for actor in overlay.roster}
    if config.terrain_on and observations:
        for actor, view in observations.items():
            if actor in terrain_memory:
                terrain_memory[actor].update(view.rough_seen_now)
    died_at = dict(overlay.died_at)
    died: list[str] = []
    for actor in overlay.roster:
        if not overlay.alive(actor):
            continue
        decision = decisions.get(actor)
        owed = held.get(actor, 0)
        if owed > 0:
            # still climbing out of rough ground: the step waits a tick
            held[actor] = owed - 1
        elif decision is not None and decision.step is not None:
            positions[actor] = decision.step
            if decision.step in rough:
                held[actor] = 1 + storm_hold(overlay.sky)       # a storm makes the climb out cost an extra tick
            if config.on("wolves") and overlay.persona.hurt.get(actor, 0) >= config.lever("limp_at"):
                held[actor] = max(held[actor], 1)               # a limp: the next step waits a tick
        if (decision is not None and decision.kind == BUILD
                and (not config.wood_on or wood_spent.get(actor, 0) >= wood_cost(built[actor]))):
            axe = config.on("crafting") and settled.holdings.get("axe", {}).get(actor, 0) >= 1
            goal = build_goal(config.build_ticks, overlay.persona.skills.get(actor, ()),
                              config.lever("axe_saves") if axe else 0)
            helped = help_credit(overlay, decisions, actor, built[actor], goal, config) if config.on("pledges") else None
            built[actor] += 1                           # interrupted work is never lost
            if helped is not None:
                built[actor] += 1                       # somebody at the door lends a hand on the same tick
                credited[helped] = 1
            if built[actor] >= goal:
                shelters.add(overlay.homes[actor])      # permanent, and it shelters whoever stands there
        under = positions[actor]
        relief = config.shelter_relief if under in shelter_spots or under in shelters else 0
        # shelter slows a need, it never suspends one: a living person always gets
        # hungrier and thirstier, or a roof would be immortality.
        hunger[actor] = max(0, hunger[actor] + eased(config.hunger_rate, relief)
                            - config.satiation * eaten.get(actor, 0))
        if config.water_on:
            thirst[actor] = max(0, thirst[actor] + eased(config.thirst_rate, relief)
                                - config.quench * drunk.get(actor, 0))
        if config.childhood_on:
            age[actor] += 1
        if config.warmth_on:
            # Shelter is the person's own home cell, and this is where the tick left them.
            sheltered = positions[actor] == overlay.homes[actor]
            # out in the sky costs extra cold unless a finished shelter stands over the person
            extra = exposure(config, overlay.sky, positions[actor] in shelters) if config.on("sky") else 0
            if sheltered:
                cold[actor] = max(0, cold[actor] - max(1, config.warming - extra))
            else:
                cold[actor] = cold[actor] + config.cold_rate + extra
        if (hunger[actor] >= config.death_at
                or (config.water_on and thirst[actor] >= config.thirst_death_at)
                or (config.warmth_on and cold[actor] >= config.cold_death_at)):
            died_at[actor] = settled.tick
            died.append(actor)
    wolves, hurt = overlay.things.wolves, dict(overlay.persona.hurt)
    if config.on("wolves"):
        # after everybody has moved: wolves hunt those in the open, and the hurt are mended or finished
        living = {actor for actor in overlay.living if actor not in died_at}
        resting = {actor for actor in living if decisions.get(actor) is not None
                   and decisions[actor].kind in HEALING_KINDS and positions[actor] == overlay.homes[actor]}
        hurt = mend(hurt, living, resting, settled.tick, config)
        wolves, bites = advance_wolves(config, settled.tick, wolves, positions, living, shelters, overlay.sky,
                                       set(overlay.homes.values()) | set(config.all_source_positions()))
        for actor in sorted(bites):
            hurt[actor] = hurt.get(actor, 0) + bites[actor]
            if hurt[actor] >= config.lever("lethal_hurt"):
                died_at[actor] = settled.tick
                died.append(actor)
    condition = (recover_patches(overlay.patch_condition, config.food_source_ids(), record)
                 if config.regrowth_on else dict(overlay.patch_condition))
    season = season_at(settled.tick) if config.seasons_on else None
    empty_sources = {}
    if config.source_memory_on:
        for actor in overlay.living:
            view = (observations or {}).get(actor)
            entries = (view.empty_sources if view is not None
                       else remember_empty(overlay.empty_sources.get(actor, ()), (), overlay.tick))
            if entries and actor not in died_at:
                empty_sources[actor] = entries
    sightings, reports = update_reports(overlay, decisions, observations or {}, died_at, settled.tick) if config.knowledge_sharing_on else ({}, {})
    # Start from the previous overlay and replace only what this tick changes, so a
    # field that no rule here touches is carried over instead of being reset.
    next_overlay = replace(overlay, tick=settled.tick, positions=positions, hunger=hunger,
                           fishing_cast={p: positions[p] for p,d in decisions.items()
                                         if config.fishing_on and d.kind == FISH and p not in died_at
                                         and (d.target, positions[p]) in fishing_sites(config)},
                           empty_sources=empty_sources,
                           food_sightings=sightings, source_reports=reports,
                           patch_condition=condition,
                           season=season,
                           food_memory=remember_food(overlay, record) if config.social_memory_on else overlay.food_memory,
                           died_at=died_at, thirst=thirst, cold=cold, held=held, built=built,
                           shelters=tuple(sorted(shelters)),
                           age=age,
                           terrain_memory={actor: tuple(sorted(cells)) for actor, cells in terrain_memory.items()
                                           if cells},
                           requests={who: asked for who, asked in requests.items()
                                     if who not in died_at and asked not in died_at},
                           promises={who: owed for who, owed in promises.items()
                                     if who not in died_at and owed not in died_at
                                     and in_view(positions[who], positions[owed],
                                                 sight(config, overlay.sky, config.perception_radius))})

    if config.features:
        next_overlay = replace(next_overlay, persona=advance_persona(overlay, next_overlay, decisions, record, config))
    if config.on("wolves"):
        next_overlay = replace(next_overlay, things=Things(wolves=wolves),
                               persona=replace(next_overlay.persona, hurt=hurt))
    grievances: list[tuple[str, str, str]] = []
    if config.on("pledges"):
        pledges, asks, grievances = advance_pledges(overlay, decisions, observations or {}, record, positions,
                                                    set(died_at) - set(overlay.died_at), credited, shelters, config)
        tried = dict(next_overlay.persona.tried)
        for actor, kind, target, when, ok in asks:
            remember_attempt(tried, actor, (kind, target, when, ok))
        next_overlay = replace(next_overlay, pledges=pledges, persona=replace(next_overlay.persona, tried=tried))
    if config.on("bonds"):
        bonds, lonely, talking, failed = advance_society(overlay, next_overlay, decisions, observations or {}, record, config,
                                                         grievances)
        tried = dict(next_overlay.persona.tried)
        for actor, kind, target, when, ok in failed:
            remember_attempt(tried, actor, (kind, target, when, ok))
        next_overlay = replace(next_overlay, persona=replace(next_overlay.persona, bonds=bonds, lonely=lonely,
                                                              talking=talking, tried=tried))
    if config.on("beliefs"):
        next_overlay = replace(next_overlay, persona=replace(
            next_overlay.persona, beliefs=advance_beliefs(overlay, next_overlay, decisions, observations or {}, config)))
    if config.on("sky"):
        next_overlay = replace(next_overlay, sky=sky_at(config, settled.tick))
    production: list[dict[str, Any]] = []
    ledger = settled
    if config.relocation_on:
        next_overlay = update_experience(overlay, next_overlay, decisions, observations, config)
    if config.on("crafting"):
        ledger, made = apply_crafting(ledger, decisions, record, config)
        production.extend(made)
    if config.homes_on:
        next_overlay, ledger, created = apply_housing(next_overlay, ledger, decisions, config, record.rotated_roster, overlay)
        production.extend(created)
    if config.provisioning_on:
        next_overlay = replace(next_overlay, provision_trips=update_provisioning(overlay, next_overlay, decisions, record))
    if config.coordination_on:
        next_overlay = replace(next_overlay, food_expected=update_food_expectations(
            overlay, next_overlay, decisions, observations or {}))
    growth = seasonal_growth(config.renewal_amount, season) if season is not None else config.renewal_amount
    renewals = [(source_id, config.renewal_every,
                 food_growth(growth, condition[source_id]) if config.regrowth_on else growth,
                 config.source_cap)
                for source_id in config.food_source_ids()]
    renewals += [(source_id, config.water_renewal_every, config.water_renewal_amount, config.water_cap)
                  for source_id in config.water_source_ids()]
    renewals += [(sid, FISH_RENEWAL_EVERY, FISH_RENEWAL, FISH_STOCK) for sid,_ in fishing_sites(config)]
    renewals += [(sid, WOOD_RENEWAL_EVERY, WOOD_RENEWAL, WOOD_STOCK) for sid,_ in wood_sites(config)]
    renewals += [(sid, STONE_RENEWAL_EVERY, STONE_RENEWAL, STONE_STOCK) for sid, _ in stone_sites(config)]
    for source_id, every, per_renewal, cap in renewals:
        if per_renewal > 0 and settled.tick % every == 0:
            source = ledger.sources[source_id]
            amount = min(per_renewal, cap - source.stock)
            if amount > 0:
                production.append({"source": source_id, "amount": amount})
                sources = dict(ledger.sources)
                sources[source_id] = replace(source, stock=source.stock + amount)
                ledger = replace(ledger, sources=sources)
    if config.births_on:
        next_overlay, ledger, born = _births(next_overlay, ledger, config)
        production.extend({"born": actor} for actor in born)

    return Processed(overlay=next_overlay, ledger=ledger, production=tuple(production),
                     eaten=eaten, died=tuple(died))


def _births(overlay: Overlay, ledger: WorldState, config: WorldConfig) -> tuple[Overlay, WorldState, list[str]]:
    """Count the ticks each settled pair spends side by side, and when one
    reaches together_ticks, add a person. The newcomer holds nothing: a birth
    is a mouth, not a meal, and no unit of anything is created by it."""
    adjacent = {f"{a}|{b}" for a, b in settled_pairs(overlay, config)}
    counts = {pair: overlay.together.get(pair, 0) + 1 for pair in adjacent}
    taken = set(overlay.homes.values()) | set(config.all_source_positions())
    homes, positions = dict(overlay.homes), dict(overlay.positions)
    hunger, yield_at = dict(overlay.hunger), dict(overlay.yield_at)
    thirst, cold = dict(overlay.thirst), dict(overlay.cold)
    held, built = dict(overlay.held), dict(overlay.built)
    age, parent = dict(overlay.age), dict(overlay.parent)
    second_parent = dict(overlay.second_parent)
    ready = {actor: overlay.birth_ready.get(actor, 0) for actor in overlay.roster}
    born: list[str] = []
    parents: dict[str, tuple[str, str]] = {}
    roster_size = len(overlay.roster)
    for pair in sorted(counts):
        if counts[pair] < config.together_ticks:
            continue
        first, second = pair.split("|")
        if config.birth_spacing and any(ready[actor] > overlay.tick for actor in (first, second)):
            continue
        where = free_cell_near(overlay.homes[first], taken, config)
        if where is None:
            continue                                   # nowhere left to live
        counts[pair] = 0                               # they start counting again
        name = f"p{roster_size + len(born) + 1:02d}"
        born.append(name)
        parents[name] = (first, second)
        ready[name] = 0
        if config.birth_spacing:
            ready[first] = ready[second] = overlay.tick + config.birth_spacing
        taken.add(where)
        homes[name] = positions[name] = where
        hunger[name] = held[name] = built[name] = 0
        if config.childhood_on:
            age[name], parent[name] = 0, first
            if config.shared_care_on:
                second_parent[name] = second
        yield_at[name] = (config.yield_set[len(overlay.roster) % len(config.yield_set)]
                          if config.yield_on else config.actors + 1)
        if config.water_on:
            thirst[name] = 0
        if config.warmth_on:
            cold[name] = 0
    if not born:
        return replace(overlay, together=counts), ledger, []
    if config.birth_spacing:
        counts = {pair: count for pair, count in counts.items()
                  if all(ready[actor] <= overlay.tick for actor in pair.split("|"))}
    sources = {sid: replace(source, authorised=frozenset(source.authorised) | set(born))
               for sid, source in ledger.sources.items()}
    balances = dict(ledger.balances) | {name: 0 for name in born}
    holdings = {resource: dict(held_map) | {name: 0 for name in born}
                for resource, held_map in ledger.holdings.items()}
    grown = replace(ledger, balances=balances, sources=sources, holdings=holdings)
    # Only the maps a newcomer must appear in are replaced; everything else the
    # overlay carries (memories, casts, trips, structures) survives a birth as it is.
    persona = overlay.persona
    for name in born:
        persona = persona_born(persona, name, *parents[name], config)
    return (replace(overlay, homes=homes, positions=positions, hunger=hunger, yield_at=yield_at,
                    thirst=thirst, cold=cold, held=held, built=built, together=counts,
                    age=age, parent=parent, second_parent=second_parent, persona=persona,
                    birth_ready=ready if config.birth_spacing or overlay.birth_ready else {}),
            grown, born)
