"""Shared food caches at founding homes. Quantities live only in the ledger."""

from typing import TYPE_CHECKING

from kernel.proposals import OP_DEPOSIT

if TYPE_CHECKING:
    from world.observe import Observation

STORE_TARGET = 6
STORE_LOW = 2
FOOD_EXPECT_TICKS = 12


def food_expectation(memory, tick, home, others, store_food):
    """An announcement lasts briefly; only local evidence can end it early."""
    if memory is None:
        return None, None
    speaker, heard = memory[0], memory[1]
    if tick >= heard + FOOD_EXPECT_TICKS:
        return None, "the announcement expired"
    if store_food is not None and store_food >= STORE_LOW:
        return None, "the home cache is stocked"
    if any(person.actor == speaker and person.position == home and person.food <= 1 for person in others):
        return None, "the housemate returned without spare food"
    return (speaker, heard), None


def eligible_announcements(previous, current, decisions) -> dict[str, tuple[str, ...]]:
    """Speakers a listener can hear this tick, in ascending actor id.

    The same gate as the original announcement rule: the listener is alive,
    still in the household they had at tick start, and the speaker named them.
    """
    heard: dict[str, list[str]] = {}
    for speaker, choice in sorted(decisions.items()):
        for listener in choice.announced_to:
            if (current.alive(listener) and listener in current.homes and listener in previous.homes
                    and current.homes[listener] == previous.homes[listener]):
                speakers = heard.setdefault(listener, [])
                if speaker not in speakers:
                    speakers.append(speaker)
    return {listener: tuple(speakers) for listener, speakers in sorted(heard.items())}


def prefer_contribution(existing: tuple[str, int] | None, candidate: tuple[str, int]) -> tuple[str, int]:
    """Keep the later contribution tick. The same tick keeps the lower actor id."""
    if existing is None or candidate[1] > existing[1]:
        return candidate
    if candidate[1] == existing[1] and candidate[0] < existing[0]:
        return candidate
    return existing


def update_food_expectations(previous, current, decisions, observations,
                             contribution_memory=None, contribution_selection=None):
    """Hear actual departures after choices; speech does not allocate a worker.

    Several eligible speakers still resolve by ascending actor id. A remembered
    contribution replaces that choice only when that contributor is one of the
    speakers. One speaker is left as announced.
    """
    memories = {}
    selections = {}
    prior_selection = contribution_selection or {}
    remembered = contribution_memory or {}
    for actor in current.living:
        if current.homes[actor] != previous.homes[actor]:
            continue
        view = observations.get(actor)
        expected = (view.food_expected if view is not None else food_expectation(
            previous.food_expected.get(actor), previous.tick, previous.homes[actor], (), None)[0])
        if expected is not None:
            speaker, heard = expected[0], expected[1]
            memories[actor] = (speaker, heard)
            prior = prior_selection.get(actor)
            if prior is not None and prior[2] == speaker and prior[4] == heard:
                selections[actor] = tuple(prior)
    for listener, speakers in eligible_announcements(previous, current, decisions).items():
        fallback = speakers[0]
        chosen = fallback
        memory = remembered.get(listener)
        if memory is not None and len(speakers) >= 2 and memory[0] in speakers:
            chosen = memory[0]
            changed = 0 if chosen == fallback else 1
            selections[listener] = (memory[0], memory[1], chosen, changed, current.tick)
        else:
            selections.pop(listener, None)
        memories[listener] = (chosen, current.tick)
    return memories, selections


def _cache_cells(previous, config) -> dict:
    cells = {sid: pos for sid, pos in previous.home_caches.items()}
    if not config.homes_on:
        from world.config import store_sites
        for sid, pos, _resident in store_sites(config):
            cells.setdefault(sid, pos)
    return cells


def accepted_food_deposits(record) -> tuple[tuple[str, str, int], ...]:
    """Accepted base-food deposits that add a positive amount to a source."""
    found = []
    for outcome in record.outcomes:
        if not outcome.accepted or outcome.operation != OP_DEPOSIT:
            continue
        credit = None
        food_debit = False
        for effect in outcome.effects:
            if effect.account == f"actor:{outcome.actor}" and effect.delta < 0:
                food_debit = True
            elif effect.account.startswith("source:") and effect.delta > 0 and credit is None:
                credit = effect
        if food_debit and credit is not None:
            found.append((outcome.actor, credit.account[len("source:"):], credit.delta))
    return tuple(found)


def remember_contributions(previous, current, record, observations, config) -> dict[str, tuple[str, int]]:
    """Each observer's latest witnessed deposit into their shared home cache.

    Witnessing is the observation taken at tick start, before this tick's
    movement. It counts only together with an accepted positive base-food
    deposit into that cache. The observer must see the contributor standing
    on the cache cell and share that home. Someone who steps into view, or
    onto the cell, during the tick was not in that observation and learns
    nothing. Someone who was in it and then steps away still remembers.
    Changing household drops the observer's memory, including a sight from
    the home they just left.
    """
    memories: dict[str, tuple[str, int]] = {}
    for actor, memory in previous.contribution_memory.items():
        if (actor in current.homes and actor in previous.homes
                and current.homes[actor] == previous.homes[actor]):
            memories[actor] = (memory[0], memory[1])
    cells = _cache_cells(previous, config)
    deposits = []
    for contributor, source_id, _amount in accepted_food_deposits(record):
        cache = cells.get(source_id)
        if cache is None or previous.homes.get(contributor) != cache:
            continue
        if previous.positions.get(contributor) != cache:
            continue
        deposits.append((contributor, cache))
    deposits.sort()
    for observer in sorted(observations):
        if observer not in current.homes or observer not in previous.homes:
            continue
        if current.homes[observer] != previous.homes[observer]:
            memories.pop(observer, None)
            continue
        view = observations[observer]
        if view is None or view.home != previous.homes[observer]:
            continue
        seen = {person.actor: person.position for person in view.others}
        kept = memories.get(observer)
        for contributor, cache in deposits:
            if contributor == observer or previous.homes.get(contributor) != view.home:
                continue
            if cache != view.home or seen.get(contributor) != cache:
                continue
            kept = prefer_contribution(kept, (contributor, current.tick))
        if kept is not None:
            memories[observer] = kept
    return memories


def start_provisioning(observation, config):
    """A resident can notice a low cache only while standing at home."""
    return (config.provisioning_on and observation.alive and observation.at_home
            and observation.home_built and observation.home_store_food is not None
            and observation.home_store_food < STORE_LOW and observation.food <= 1
            and not (config.childhood_on and observation.age < config.adult_at))


def update_provisioning(previous, current, decisions, record):
    """Keep one outing through interruptions; an actual collection starts the return."""
    trips = dict(previous.provision_trips)
    collected = {out.actor for out in record.outcomes if out.accepted
                 and decisions.get(out.actor) is not None
                 and decisions[out.actor].kind == "claim"}
    for actor in current.positions:
        choice = decisions.get(actor)
        if (not current.alive(actor) or current.homes[actor] != previous.homes[actor]
                or (current.positions[actor] == current.homes[actor]
                    and actor in trips)):
            trips.pop(actor, None)
            continue
        if choice is not None and choice.provisioning is not None:
            trips[actor] = choice.provisioning
        if actor in trips and actor in collected:
            trips[actor] = "return"
    return trips


def store_id(resident: str) -> str:
    return f"store-{resident}"


def spare_for_store(observation: "Observation") -> int:
    """Only a resident at their finished shelter can put food aside.

    Keep one carried meal and stop filling at six. Needs and help get their
    normal turn first; the caller uses this only instead of resting.
    """
    if (not observation.alive or not observation.at_home or not observation.home_built
            or observation.home_store_food is None):
        return 0
    return max(0, min(observation.food - 1, STORE_TARGET - observation.home_store_food))
