"""Why something a person might have done was not done.

A decision records what was chosen. With the `explain` feature on it also records
the options that were weighed and set aside, each with one reason from this list.
They come from the same checks the decision itself used, at the moment it used
them; nothing is recomputed afterwards by the viewer or anything else.
"""

from __future__ import annotations

from world.feature import Feature

UNKNOWN = "unknown"              # they do not know of a way: no place, no stock, no route
UNAVAILABLE = "unavailable"      # they know of it, but it is empty, taken, closed or not theirs
MISSING = "missing"              # a prerequisite they lack: material, tool, seed, shelter
LESS_URGENT = "less_urgent"      # another need runs out sooner
TOO_LATE = "too_late"            # relief could not be reached and finished in time
FAILED_BEFORE = "failed_before"  # their last attempt at it failed
UNWILLING = "unwilling"          # their own temperament, or a grudge, says no
DANGEROUS = "dangerous"          # a danger they know of lies in the way

REASONS = {
    UNKNOWN: "did not know of a way",
    UNAVAILABLE: "known, but not available",
    MISSING: "missing something it needs",
    LESS_URGENT: "another need was more urgent",
    TOO_LATE: "could not be finished in time",
    FAILED_BEFORE: "the last attempt failed",
    UNWILLING: "not willing",
    DANGEROUS: "a known danger in the way",
}

Rejection = tuple[str, str, str]    # what, reason code, plain detail

EXPLAIN = Feature(
    name="explain",
    summary="Each decision records the options it set aside, and why.",
    rule=(
        "Beside the chosen action, each decision records the options the person weighed and set aside, each "
        "with one reason: unknown (no way to do it is known), unavailable (known but empty, taken or closed), "
        "missing (a prerequisite is lacking), less_urgent (another need runs out sooner), too_late (relief "
        "could not be reached and finished in time), failed_before (the last attempt failed), unwilling (the "
        "person's own temperament or a grudge) or dangerous (a known danger lies in the way). The options come "
        "from the checks the decision itself made, when it made them. People also remember their last four "
        "distinct attempts: what, where, when and whether it worked."),
    tables={"rejection_reasons": REASONS},
)


def rejection(what: str, code: str, detail: str) -> Rejection:
    if code not in REASONS:
        raise ValueError(f"unknown rejection reason {code!r}")
    return (what, code, detail)
