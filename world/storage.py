"""Shared food caches at founding homes. Quantities live only in the ledger."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from world.observe import Observation

STORE_TARGET = 6
STORE_LOW = 2
FOOD_EXPECT_TICKS = 12


def food_expectation(memory, tick, home, others, store_food, witnessed_deaths=()):
    """An announcement lasts briefly; only local evidence can end it early."""
    if memory is None:
        return None, None
    speaker, heard = memory
    if speaker in witnessed_deaths:
        return None, "witnessed the housemate's death"
    if tick >= heard + FOOD_EXPECT_TICKS:
        return None, "the announcement expired"
    if store_food is not None and store_food >= STORE_LOW:
        return None, "the home cache is stocked"
    if any(person.actor == speaker and person.position == home and person.food <= 1 for person in others):
        return None, "the housemate returned without spare food"
    return memory, None


def update_food_expectations(previous, current, decisions, observations):
    """Hear actual departures after choices; speech does not allocate a worker."""
    memories = {}
    for actor in current.living:
        if current.homes[actor] != previous.homes[actor]:
            continue
        view = observations.get(actor)
        expected = (view.food_expected if view is not None else food_expectation(
            previous.food_expected.get(actor), previous.tick, previous.homes[actor], (), None)[0])
        if expected is not None:
            memories[actor] = expected
    heard_now = set()
    for speaker, choice in sorted(decisions.items()):
        for listener in choice.announced_to:
            if (current.alive(listener) and listener not in heard_now
                    and current.homes[listener] == previous.homes[listener]):
                memories[listener] = (speaker, current.tick)
                heard_now.add(listener)
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
