"""Reject malformed API configuration before genesis or saved identity exists."""
from dataclasses import replace
from typing import get_type_hints

import pytest

from stream.run_file import read_run
from world.config import WorldConfig
from world.replay import replay_world
from world.run import run_world

INTEGER_FIELDS = [name for name, kind in get_type_hints(WorldConfig).items() if kind is int]
BOOLEAN_FIELDS = [name for name, kind in get_type_hints(WorldConfig).items() if kind is bool]


@pytest.mark.parametrize('name', BOOLEAN_FIELDS)
@pytest.mark.parametrize('value', [0, 1, 'off', None, [], 1.0])
def test_boolean_settings_reject_non_booleans_at_construction(name, value):
    with pytest.raises(ValueError, match=rf'boolean.*\b{name}\b'):
        replace(WorldConfig(seed=7), **{name: value})


@pytest.mark.parametrize('name', INTEGER_FIELDS)
@pytest.mark.parametrize('value', [True, '7', 1.5, None])
def test_integer_settings_reject_non_integers_at_construction(name, value):
    with pytest.raises(ValueError, match=rf'integer.*\b{name}\b'):
        replace(WorldConfig(seed=7), **{name: value})


def test_valid_edge_settings_save_and_replay(tmp_path):
    # These values are permitted modelling choices, not malformed types.
    cfg = WorldConfig(seed=-1, perception_radius=0, hunger_rate=0)
    path = tmp_path / 'edges.jsonl'
    run_world(cfg, 12, path)
    assert read_run(path).complete
    assert replay_world(path).identical


def test_disabled_integer_settings_still_require_integers():
    with pytest.raises(ValueError, match='integer.*thirst_rate'):
        WorldConfig(seed=7, water_on=False, thirst_rate='7')


def test_disabled_settings_may_normalize_without_changing_saved_rules():
    cfg = WorldConfig(seed=7, water_on=False, thirst_rate=7)
    restored = WorldConfig.from_describe(cfg.describe())
    assert restored != cfg
    assert restored.describe() == cfg.describe()


@pytest.mark.parametrize('value', [None, 1, True, '123', {1, 2}, (), [], (True,), ('1',), (0,)])
def test_yield_settings_reject_malformed_collections(value):
    with pytest.raises(ValueError, match='yield_set'):
        WorldConfig(seed=7, yield_set=value)


def test_yield_list_is_copied_to_immutable_tuple():
    values = [1, 2, 3]
    cfg = WorldConfig(seed=7, yield_set=values)
    values.append(4)
    assert cfg.yield_set == (1, 2, 3)
    assert WorldConfig.from_describe(cfg.describe()) == cfg
