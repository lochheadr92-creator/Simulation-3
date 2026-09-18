"""The declared resource units and numeric rules.

One resource kind exists in slice 1a. It is abstract: it acquires meaning in
Stage 2, not here. Quantities are integers, units are indivisible, and a
transaction amount is at least one, so there is no representation in which a
partial credit could be expressed.
"""

from __future__ import annotations

from typing import Any

RESOURCE_UNIT = "unit"
MINIMUM_TRANSACTION_AMOUNT = 1


def is_integer(value: Any) -> bool:
    """True for an integer quantity.

    `bool` is excluded even though Python treats it as an integer subclass: a
    flag is not a unit count, and silently reading `True` as one unit would be a
    numeric rule nobody declared.
    """
    return isinstance(value, int) and not isinstance(value, bool)


def is_valid_balance(value: Any) -> bool:
    return is_integer(value) and value >= 0


def is_valid_transaction_amount(value: Any) -> bool:
    return is_integer(value) and value >= MINIMUM_TRANSACTION_AMOUNT
