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


def remember_sightings(previous, visible, tick):
    """Retain firsthand empty/stocked sightings; fresh sight defeats older reports."""
    recent = {sid: (sid, stocked, when) for sid, stocked, when in previous
              if tick - when < EMPTY_SOURCE_TICKS}
    for sid, stock in visible:
        recent[sid] = (sid, int(stock > 0), tick)
    return tuple(recent[sid] for sid in sorted(recent))


def usable_reports(previous, sightings, tick):
    own = {sid: when for sid, _, when in sightings}
    return tuple(e for e in previous
                 if tick - e[2] < EMPTY_SOURCE_TICKS and own.get(e[0], -1) < e[2])


def update_reports(previous, decisions, observations, died_at, tick):
    """Hear recorded firsthand reports after choices; retelling cannot refresh age."""
    sightings, reports = {}, {}
    for actor in previous.living:
        if actor in died_at:
            continue
        view = observations.get(actor)
        own = (view.food_sightings if view is not None else
               remember_sightings(previous.food_sightings.get(actor, ()), (), previous.tick))
        heard = (view.source_reports if view is not None else
                 usable_reports(previous.source_reports.get(actor, ()), own, previous.tick))
        if own:
            sightings[actor] = own
        reports[actor] = {e[0]: e for e in heard}
    for speaker, choice in sorted(decisions.items()):
        if choice.source_report is None:
            continue
        sid, when = choice.source_report
        view = observations.get(speaker)
        if view is None or (sid, 0, when) not in view.food_sightings:
            continue
        for listener in choice.report_to:
            if listener not in reports or listener not in view.report_listeners:
                continue
            entry = (sid, speaker, when, tick)
            if not usable_reports((entry,), sightings.get(listener, ()), previous.tick):
                continue
            old = reports[listener].get(sid)
            if old is None or (-when, speaker) < (-old[2], old[1]):
                reports[listener][sid] = entry
    return sightings, {p: tuple(entries[sid] for sid in sorted(entries))
                       for p, entries in reports.items() if entries}
