"""Named ways to start a world: the plain world, the rich world and a few scenes.

A scene is a seed, a length, some features and a few settings, written down so the launcher can offer it by name and
anybody can start the same world again. Nothing here changes how a world behaves: a scene is only a world configuration,
and the saved run records the configuration it ran under like any other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from world.config import WorldConfig
from world.registry import FEATURES

RICH_FEATURES = tuple(sorted(FEATURES))
WOOD_FEATURES = frozenset({"crafting", "structures"})       # these need wood and building on


@dataclass(frozen=True)
class Scene:
    name: str
    summary: str
    seed: int
    ticks: int
    features: tuple[str, ...] = ()
    levers: tuple[tuple[str, int], ...] = ()
    options: dict[str, Any] = field(default_factory=dict)     # other WorldConfig settings, such as width and actors

    def config(self, seed: int | None = None) -> WorldConfig:
        return make_config(self.seed if seed is None else seed, self.features, dict(self.levers), self.options)


def make_config(seed: int, features: tuple[str, ...] = (), levers: dict[str, int] | None = None,
                options: dict[str, Any] | None = None) -> WorldConfig:
    """A world configuration from plain pieces. Features that need wood to build with switch it on."""
    settings = dict(options or {})
    if WOOD_FEATURES & set(features):
        settings.setdefault("wood_on", True)
    return WorldConfig(seed=seed, features=tuple(sorted(features)), feature_levers=tuple(sorted((levers or {}).items())), **settings)


def rich_world(seed: int, **changes: Any) -> WorldConfig:
    """Every optional feature on, at its default settings."""
    return make_config(seed, RICH_FEATURES, options=changes)


SCENES: tuple[Scene, ...] = (
    Scene("plain", "The original small world: needs, shelter, sharing and nothing else.", 7, 300),
    Scene("rich", "Everything on at once: temperament, weather, wolves, friendships, requests, tools, fields, families, graves.",
          7, 600, RICH_FEATURES, (), {"wood_on": True}),
    Scene("wolves", "Two wolves hunt at dusk and in the night; people warn each other, avoid them and get hurt.", 14, 400,
          ("beliefs", "bonds", "explain", "personality", "skills", "sky", "sleep", "steady", "wolves"), (("wolves", 2),)),
    Scene("village", "Neighbours ask and keep promises, make tools, tend fields and mend shelters.", 11, 600,
          ("beliefs", "bonds", "crafting", "explain", "farming", "personality", "pledges", "skills", "sky", "sleep", "steady", "structures"),
          (), {"wood_on": True}),
    Scene("families", "Couples form, children are born and grow up, elders die and the bereaved grieve and visit graves.", 23, 700,
          ("aftermath", "beliefs", "bonds", "explain", "family", "personality", "sky", "sleep", "steady"), ()),
    Scene("explorers", "A larger map where the curious go and look, wells are found and paths wear into the ground.", 31, 500,
          ("beliefs", "bonds", "explain", "exploration", "paths", "personality", "sky", "sleep", "steady", "structures"),
          (), {"wood_on": True, "width": 20, "height": 20, "actors": 8}),
)


def scene_named(name: str) -> Scene:
    for scene in SCENES:
        if scene.name == name:
            return scene
    raise ValueError(f"no scene is called {name!r}; known: {', '.join(s.name for s in SCENES)}")
