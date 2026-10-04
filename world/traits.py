"""Trait and skill vocabulary, and the small pure helpers every rule uses.

A leaf module: nothing here imports another world module, so the rules that read
a person's temperament (rest, decide, storage) and the state that holds it
(persona) can all depend on it without a cycle.
"""

from __future__ import annotations

from bisect import bisect_right

TRAITS = ("generosity", "sociability", "caution", "diligence", "curiosity")
GENEROSITY, SOCIABILITY, CAUTION, DILIGENCE, CURIOSITY = range(5)
SKILLS = ("gathering", "fishing", "building", "farming", "crafting")
GATHERING, FISHING, BUILDING, FARMING, CRAFTING = range(5)
SKILL_STEPS = (0, 8, 24, 48, 80, 120)      # practice points at which levels 0..5 begin
NEUTRAL = 50
STINGY_BELOW = 35                          # generosity under this keeps the last unit
GENEROUS_FROM = 75                         # generosity from this shares water with strangers


def level_of(points: int) -> int:
    """Skill level for a practice total: how many step thresholds it has reached."""
    return bisect_right(SKILL_STEPS, points) - 1


def trait_lean(traits: tuple[int, ...], index: int) -> int:
    """How far a trait sits from the middle; 0 when traits are off. An effect
    built on this vanishes for anybody middling and whenever personality is off,
    so switching it on moves nobody who is exactly average."""
    return traits[index] - NEUTRAL if traits else 0


def skill_level(skills: tuple[int, ...], index: int) -> int:
    return level_of(skills[index]) if skills else 0


def caution_ticks(traits: tuple[int, ...]) -> int:
    """Ticks earlier a cautious person sets off (later, when negative, for a bold one)."""
    return trait_lean(traits, CAUTION) // 10


def stingy(traits: tuple[int, ...]) -> bool:
    return bool(traits) and traits[GENEROSITY] < STINGY_BELOW


def generous(traits: tuple[int, ...]) -> bool:
    return bool(traits) and traits[GENEROSITY] >= GENEROUS_FROM


def build_goal(build_ticks: int, skills: tuple[int, ...], saves: int = 0) -> int:
    """Work ticks a shelter takes this builder: each building level takes one off, and an axe `saves`
    more, never below four (or the configured total, if that is already smaller)."""
    return max(min(build_ticks, 4), build_ticks - skill_level(skills, BUILDING) - saves)


def provision_low(base: int, traits: tuple[int, ...]) -> int:
    """Meals in a shared cache that count as low: one more for a diligent person
    (diligence 70 or more), one fewer for an idle one (under 30), at least one."""
    if not traits:
        return base
    return max(1, base + (traits[DILIGENCE] >= 70) - (traits[DILIGENCE] < 30))
