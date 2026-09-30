"""Home choices, experienced supply effort, and physical arrival."""

from dataclasses import replace
from typing import TYPE_CHECKING

from kernel import Source

if TYPE_CHECKING:
    from world.config import WorldConfig
    from world.overlay import Overlay

HOME_CAPACITY = 2
GO_SETTLE = "go_settle"
SETTLE = "settle_home"
GO_RELOCATE = "go_relocate"
RELOCATE = "relocate"
LONG_OUTING = 8
DIFFICULT_OUTINGS = 3
MOVE_COOLDOWN = 120
ROUTE_IMPROVEMENT = 3


def supply_distance(site, config):
    """Distance to known landmarks, never a look at hidden stocks."""
    def distance(p):
        return abs(site[0]-p[0]) + abs(site[1]-p[1])
    return min(map(distance, config.food_positions())) + (
        min(map(distance, config.water_positions())) if config.water_on else 0)


def remembered_shelters(actor, overlay, config):
    """Refresh only the shelters in sight; distant remembered vacancies may be stale."""
    origin = overlay.positions[actor]
    def seen(site):
        return max(abs(site[0]-origin[0]), abs(site[1]-origin[1])) <= config.perception_radius
    known = {site for site in overlay.shelter_memory.get(actor, ()) if not seen(site)}
    known.update(site for site in overlay.shelters if seen(site)
                 and site_available(actor, site, overlay.homes, overlay.living, overlay.shelters, config))
    return tuple(sorted(known - {overlay.homes[actor]}))


def can_relocate(actor, overlay, config):
    return (config.relocation_on and overlay.alive(actor)
            and overlay.age.get(actor, 0) >= config.adult_at
            and (actor not in overlay.parent or actor in overlay.home_settled)
            and overlay.tick - overlay.home_settled.get(actor, 0) >= MOVE_COOLDOWN
            and (overlay.home_strain.get(actor, 0) >= DIFFICULT_OUTINGS or actor in overlay.home_targets)
            and not any(overlay.alive(child)
                        and overlay.age.get(child, 0) < config.adult_at
                        for child in overlay.children_of(actor)))


def choose_relocation(observation, config):
    known = observation.known_homes
    if observation.home_target in known:
        return observation.home_target
    better = [site for site in known if supply_distance(site, config)
              <= supply_distance(observation.home, config) - ROUTE_IMPROVEMENT]
    return min(better, key=lambda site: (supply_distance(site, config),
               abs(site[0]-observation.position[0]) + abs(site[1]-observation.position[1]), site[1], site[0])) if better else None


def update_experience(previous, current, decisions, observations, config):
    """Count actual supply-seeking ticks on outings that end back at home."""
    trips, strain, memory = {}, {}, {}
    targets = dict(current.home_targets)
    for actor in current.living:
        if previous.age.get(actor, 0) < config.adult_at:
            continue
        view = (observations or {}).get(actor)
        known = view.known_homes if view is not None else previous.shelter_memory.get(actor, ())
        if view is not None and view.relocating and targets.get(actor) not in known:
            targets.pop(actor, None)
        if known:
            memory[actor] = known
        effort = previous.home_trip_ticks.get(actor, 0)
        difficulty = previous.home_strain.get(actor, 0)
        decision = decisions.get(actor)
        away_before = previous.positions[actor] != previous.homes[actor]
        away_after = current.positions[actor] != current.homes[actor]
        if decision is not None and decision.kind in (
                "go", "go_water", "wait", "wait_water", "yield", "ask", "claim", "draw", "fish") and (away_before or away_after):
            effort += 1
        if not away_after and effort:
            difficulty = min(DIFFICULT_OUTINGS, difficulty+1) if effort >= LONG_OUTING else max(0, difficulty-1)
            effort = 0
        if effort:
            trips[actor] = effort
        if difficulty:
            strain[actor] = difficulty
    return replace(current, home_trip_ticks=trips, home_strain=strain, shelter_memory=memory, home_targets=targets)


def site_available(actor, site, homes, living, shelters, config):
    x, y = site
    if not (0 <= x < config.width and 0 <= y < config.height):
        return False
    occupants = sum(homes[p] == site for p in living if p != actor)
    if site in shelters:
        return occupants < HOME_CAPACITY
    rough, spots = config.terrain()
    return (site not in config.all_source_positions() and site not in rough and site not in spots
            and all(pos != site for p, pos in homes.items() if p != actor))


def visible_sites(actor: str, overlay: "Overlay", config: "WorldConfig"):
    origin = overlay.positions[actor]
    radius = config.perception_radius
    sites = []
    for y in range(max(0, origin[1]-radius), min(config.height, origin[1]+radius+1)):
        for x in range(max(0, origin[0]-radius), min(config.width, origin[0]+radius+1)):
            site = (x, y)
            if site_available(actor, site, overlay.homes, overlay.living, overlay.shelters, config):
                sites.append((site, site in overlay.shelters))
    return tuple(sites)


def choose_site(observation, config):
    """Prefer a finished shelter, then short supply routes from known landmarks.

    A chosen destination persists through interruptions. If it is now visible
    and full, pick again. Stock outside sight plays no part in this choice.
    """
    pending = observation.home_target
    visible = dict(observation.home_options)
    if pending is not None:
        distance = max(abs(pending[0]-observation.position[0]), abs(pending[1]-observation.position[1]))
        if distance > config.perception_radius or pending in visible:
            return pending
    if not visible:
        return None

    def distance(a, b):
        return abs(a[0]-b[0]) + abs(a[1]-b[1])

    def rank(site):
        supply = min(distance(site, p) for p in config.food_positions())
        if config.water_on:
            supply += min(distance(site, p) for p in config.water_positions())
        return (not visible[site], supply, distance(site, observation.home), site[1], site[0])
    return min(visible, key=rank)


def apply_housing(overlay, ledger, decisions, config, order, previous=None):
    """Resolve arrivals in the tick's existing rotated order. No person or food teleports."""
    homes, built = dict(overlay.homes), dict(overlay.built)
    targets = {p: pos for p, pos in overlay.home_targets.items() if overlay.alive(p)}
    settled = dict(overlay.home_settled)
    caches = dict(overlay.home_caches)
    sources = dict(ledger.sources)
    production = []
    changed = set()
    for actor in order:
        decision = decisions.get(actor)
        if decision is None or not overlay.alive(actor):
            continue
        relocating = decision.kind in (GO_RELOCATE, RELOCATE)
        first_home = (decision.kind in (GO_SETTLE, SETTLE) and actor in overlay.parent
                      and actor not in settled and overlay.age.get(actor, 0) > config.adult_at)
        if not first_home and not (relocating and can_relocate(actor, previous or overlay, config)):
            continue
        site = decision.home_site
        if site is None:
            continue
        if decision.kind in (GO_SETTLE, GO_RELOCATE):
            targets[actor] = site
            continue
        targets.pop(actor, None)
        if relocating and (site == homes[actor] or site not in overlay.shelters):
            continue
        if (overlay.positions[actor] != site
                or not site_available(actor, site, homes, overlay.living, overlay.shelters, config)):
            continue
        homes[actor] = site
        built[actor] = config.build_ticks if site in overlay.shelters else 0
        settled[actor] = overlay.tick
        changed.add(actor)
        if config.stores_on and site not in caches.values():
            sid = f"home-{site[0]}-{site[1]}"
            if sid in sources:
                raise ValueError(f"new cache would overwrite existing source {sid}")
            caches[sid] = site
            sources[sid] = Source(stock=0, authorised=frozenset(ledger.roster))
            production.append({"source_created": sid})
    together = {pair: count for pair, count in overlay.together.items()
                if not changed.intersection(pair.split("|"))}
    return (replace(overlay, homes=homes, built=built, home_targets=targets,
                    home_settled=settled, home_caches=caches, together=together,
                    home_trip_ticks={p:n for p,n in overlay.home_trip_ticks.items() if p not in changed},
                    home_strain={p:n for p,n in overlay.home_strain.items() if p not in changed}),
            replace(ledger, sources=sources), production)
