"""A person's dated observations of empty natural food sources."""

EMPTY_SOURCE_TICKS = 20


def remember_empty(previous, visible, tick):
    """Only current sight can refresh or clear a memory; age eventually clears it."""
    recent = {sid: when for sid, when in previous if tick - when < EMPTY_SOURCE_TICKS}
    for sid, stock in visible:
        if stock == 0:
            recent[sid] = tick
        else:
            recent.pop(sid, None)
    return tuple(sorted(recent.items()))
