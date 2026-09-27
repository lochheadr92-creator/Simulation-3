# Claude's Repository Review

## Source and scope

This is a structured summary of Claude's review pasted by Ryan into the
conversation, not a verbatim copy of the private review page. The reviewed
commit was `c1d13cb`. The findings below describe that commit, before the
subsequent local repairs.

Claude reported **13 verified defects and 1 hypothesis**. The pasted summary
groups some promise defects under M1 and M2; that grouping is preserved here
without inventing a more precise assignment between those two labels.

## High Priority

### H1: The child leash is not enforced

Children born too far from food can still walk to it through the early
departure rule or while asking for food. Across seeds 7, 11 and 23, Claude
observed six such children reach a source and feed themselves.

In Claude's trial with the leash enforced, seed 11 changed from 4 alive to
8 and seed 23 from 18 alive to 12. The published childhood results therefore
used a leaky leash and need remeasurement under the intended rule.

### H2: Routing-off runs cannot replay or recover

The header only records routing when it is on, and reconstruction does not
read that setting back. Claude checked 13,312 valid switch combinations and
reported `route_around` as the only failing round-trip. With terrain off it
silently changes; with terrain on it prevents replay and recovery.

## Medium Priority

### M1 and M2: Errand promises end incorrectly

- Losing sight of the asker does not lapse the promise, despite the saved
  rules saying it does. Claude counted 43 later requests blocked across
  eight seeds.
- A handoff to anyone ends the promise, rather than only a delivery to its
  intended recipient.
- A dead helper's promise remains in saved state indefinitely.

### M3: The viewer misreports errands

At the final tick of seed 23, the viewer still tells p11 that p02 agreed to
bring them food, although p02 died at tick 189. Claude also observed a
213-tick-old promise from p04 in the final saved state.

### M4: Saved request rules are stale

Behavior changed in `3d0aa58`, but the header's rule text did not. An older
requests-on file is accepted as the same rules and then diverges at tick 86.
It should instead be rejected up front as a different rule set.

### M5: Grown offspring receive child-first food handoffs

Child priority uses the parent relationship without requiring the recipient
to still be a dependent child. Four of the ten reported child feedings in
the seed 23 spacing-30 results row went to adults.

### M6: Newborn homes can occupy terrain that should be excluded

Newborn homes can land on rough ground or shelter spots, contradicting the
saved rule that homes are always on open ground.

### M7: The map viewer crashes on a damaged but readable run

The reader permits damaged files to be inspected, but the map viewer crashes
on such a file rather than displaying the usable data with a warning.

## Low Priority

### L1: Text viewing crashes after births

`world.viewer --text` crashes once somebody has been born.

### L2: Route ties do not preserve the straight step

Knowing one irrelevant rough cell changes 37% of first steps in Claude's
check. Four of the 18 documented cases described as memory changing the
route were tie flips rather than meaningful routing changes.

### L3: The older viewer silently omits newborns

It constructs its roster from the genesis header only. People born later
are never drawn, and current runs are accepted without warning.

### L4: Water decisions display the food-source crowd

The seen-crowd label for water decisions counts people at the food source.
Claude counted 424 affected water decisions in the seed 23 run.

## Hypothesis

A helper can agree to carry food to an asker who died on the tick they
asked. Claude reached this with a constructed state, but did not observe
it during 12,000 simulated ticks. Reachability was demonstrated; frequency
in ordinary runs was unknown.

## What Claude Reported as Passing

- 472 tests passed on both Python 3.11 and Python 3.12.
- The 400-tick run and its replay reproduced identically.
- In 9,000 randomized kernel ticks, totals were conserved and proposal
  arrival order did not change the result.
- Recovery from a mid-line cut reproduced the uninterrupted run byte for
  byte, apart from timing lines: 402 content lines matched.
- All six results-table rows reproduced. The identical seed 11 and seed 23
  spacing-30 rows were a real coincidence, not a copy error.

## Review Limitations

- Only the packet README reached Claude, not the source zip, test output,
  saved runs, screenshots or manifest. Claude cloned the pinned GitHub
  commit instead; the branch tip and 569 tracked files matched the packet.
- Manifest hashes and the builder's saved artifacts were not checked.
- `archive/` and `evidence/` were not reviewed.
- Windows line endings were not tested.
- Claude changed none of the source under review. H2, L1 and L2 fixes were
  trialled in a separate copy only.
- The L2 trial fix changed movement and broke one seed-specific viewer test.
- The full review page was private and needed sharing for others to access.

## Claude's Recommended Order

1. Fix H2 first.
2. Settle the child-leash behavior for H1 and remeasure childhood results.
3. Fix M1 through M4 together, including the saved promise-rule text.

## Subsequent Local Repairs

This section is Codex's follow-up, not part of Claude's independent review.

At the end of the repair session on 2026-09-27:

- All 13 tests in the supplied Claude test file passed. The repository copy
  is `tests/test_claude_review_findings.py`; its SHA-256 matched the attachment.
- The full suite passed: **504 tests** on Python 3.12.
- Fresh 400-tick requests-on runs for seeds 7, 11 and 23 replayed identically.
  Their saved promises involved no dead or out-of-sight participants.
- Browser checks covered playback, a damaged sealed run's verified prefix,
  and the old seed-23 file. The latter correctly identified p02's promise to
  p11 as inactive because the helper died. No JavaScript errors were reported
  in those checks.
- The older viewer now explicitly refuses changing populations; it has not
  been upgraded to render newborns.
- Historical childhood and route measurements have not all been rerun under
  the combined repairs. The original review packet remains unchanged.
- These were implementation checks, not another independent review. Repairs
  were uncommitted and unpushed at that session's end.

No tests were rerun merely to write this summary.
