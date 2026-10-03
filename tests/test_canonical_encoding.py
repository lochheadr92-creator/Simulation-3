"""Canonical identity stays byte-for-byte stable across encoder paths."""

import json
import sys
from types import MappingProxyType

import pytest

from kernel.canonical import CanonicalError, canonical_bytes


def test_canonical_json_keeps_escaping_order_and_immutable_inputs():
    data = MappingProxyType({"z": (None, -123, 0, "é\n\t\"\\\ud800"),
                             "a": MappingProxyType({"𐀀": 2, "a": 1})})
    assert canonical_bytes(data) == (b'{"a":{"a":1,"\\ud800\\udc00":2},'
                                     b'"z":[null,-123,0,"\\u00e9\\n\\t\\\"\\\\\\ud800"]}')
    assert data["z"][0] is None


def test_arbitrary_size_positive_and_negative_integers_keep_decimal_identity():
    digits = "1" + "0" * 5000
    limit = sys.get_int_max_str_digits()
    assert canonical_bytes({"n": -(10 ** 5000), "p": 10 ** 5000}) == (
        '{"n":-' + digits + ',"p":' + digits + '}').encode('ascii')
    assert sys.get_int_max_str_digits() == limit


@pytest.mark.parametrize("value", [True, False, 1.0, float('nan'), float('inf'),
                                   {1: "bad-key"}, {"nested": [True]}, set(), object()])
def test_invalid_values_still_fail_before_encoding(value):
    with pytest.raises(CanonicalError):
        canonical_bytes(value)


def test_supported_json_values_match_the_declared_canonical_format():
    for number in (-10**100, -1, 0, 1, 10**100):
        value = {"z": [number, "line\nreturn\rnull\x00"], "a": {"\uffff": "\U0001f642"}}
        expected = json.dumps(value, ensure_ascii=True, sort_keys=True,
                              separators=(',', ':')).encode('utf-8')
        assert canonical_bytes(value) == expected
