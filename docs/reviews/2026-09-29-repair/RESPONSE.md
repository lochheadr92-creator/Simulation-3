# Response to Claude's whole-project review

Prepared by Codex on 2026-09-29 (Australia/Brisbane). This is the builder's repair response, not an independent review or a replacement verdict.

The [signed original report](../2026-09-28-whole-project/REVIEW.md) reviews `81c10b7d25cc2e0f1b8de33bf547083eb0972c64` and remains **FAIL**. Its supplied [evidence](../2026-09-28-whole-project/evidence/probes/README.md) is retained unchanged. [Claude's requested adjustments](CLAUDE_ADJUSTMENTS.md) set the order: F2, F11 assertion, F4, bounded F1 investigation, documentation. No new simulation rule was introduced to force social-memory encounters or witnessed-death awareness.

The repair target is the commit containing this response. The portable reassessment packet records its exact full SHA and tree in `REVIEW_TARGET.json`; do not substitute a later branch tip. The packet includes all tracked source files, this response, original evidence, fresh checks and one ordinary saved example.

## Findings and disposition

| Finding | Builder disposition | Change or evidence | Remaining limit |
| --- | --- | --- | --- |
| F1: ordinary social-memory activation / conditional test | Investigated; coverage claims corrected; behaviour retained | Matched old-departure-only/current sweeps for fixed seeds 1-35 at 400 and 780 ticks, plus seed 14 at 650. Current activation is 0/35 at 400 but 3/35 at 780. Tests explicitly distinguish replay, conditional event provenance and constructed rule proof. | Small deterministic sample, not population statistics or guaranteed frequency. Original reviewer must reassess the blocker. |
| F2: stored XSS in deaths totals | Fixed and reproduced before/after | Escape the actor ID at the dynamic HTML boundary. Real browser regression opens the deep section and tests literal text, element absence, script non-execution and later detail rendering. Claude's supplied forged file passes the repaired check too. Verification labels say consistency only and explain that authorship is not authenticated. | Bounded repair of the reported path, not a claim that all possible hostile run schemas have been security-audited. |
| F3: artificial encounter delay | Documented accurately | Controlled test name/docstring explicitly call out `held=100` as legal but unreachable through ordinary movement. Keep its non-vacuous real-transfer/memory/changed-choice/return-transfer assertions. The fixed sweep separately supplies ordinary-world evidence. | Constructed fixture remains a rule/integration proof, never a frequency claim. |
| F4: malformed integer configuration | Fixed | Validate all 42 scalar integer fields before comparisons, geometry, random seeds or identity generation. Reject bool, string, float and None, including inactive feature settings. Focused coverage checks each field plus valid edge settings and saved replay. | This is scalar integer type validation, not a redesign of every configuration range or feature dependency. |
| F5: sharing with no shared homes | Documented | CLI help explains same-home listeners and suggests `--homes on` for shared homes in generated worlds. Guidance gives a working sharing configuration. | No silent switch activation and no new homes dependency. Deliberate custom states can have shared homes too. |
| F6: waiting after announcer death | Documented; modelling rule unchanged | Expectations can persist for their existing 12-tick cap when the speaker dies, even in view. No witnessed-death field was added. | A future witnessed-death response would be a new rule, outside this repair. |
| F7: dead actors' holdings | Documented; accounting unchanged | Units stay on the dead account and remain in totals; no inheritance, scavenging or deletion is implemented. | Accessibility of those units is a modelling question, not missing conservation. |
| F8: `held` terminology | Clarified | Added a use-site comment: remaining movement delay, not carried food. | Persisted field and canonical overlay unchanged. |
| F9: inactive settings / edge values | Valid behaviour separated from malformed input | Negative integer seeds, zero perception and zero hunger rate remain valid and pass saved replay. Inactive settings can normalize to defaults when restored while declared active rules remain identical; explicit test records this. | No universal dataclass-equality promise or blanket rejection of unusual integers. Existing range/dependency choices are retained. |
| F10: two tick numbers | Clarified | HUD/slider use "World tick"; deep selection/settlement use "Decision tick". Visible explanation states world tick k is the result of decision tick k-1. Browser regression checks labels after stepping. | Stored tick numbers and existing event dates are unchanged. |
| F11: missing assertion / cleanup | Assertion fixed; remaining improvements deferred | Post-birth text test now finds every newborn's row and checks position/hunger against the saved world and the displayed view. | Dead helper removal, duplicated detail payload and repeated-speech presentation were not bundled into this repair. |

## F1: isolate timing, widen the sample, preserve an honest result

The diagnostic replaces only `food_travel_ticks` with the previous nominal `steps_to_source` calculation in worker memory. Terrain, routing, fishing cast addition, need arbitration, observation, settlement, production and all other rules stay unchanged. The reference calculation was checked against `22ffe2748dc4c5ee14c71295ff33810c7f456a7c:world/decide.py:trip_due`. The diagnostic does not save an old-calculation run under a current rule header or modify production source.

The 20-minute investigation began at 2026-09-28 14:37 UTC. The initial requested 400-tick sweep completed first. Because the original selected scenes occur after tick 400, the same preselected seed range was extended to 780, without seed search or parameter tuning. The extended comparison took about 80 seconds; a repeat after the final presentation/comment edits reproduced all counts, divergence records and final ledger/overlay digests. Full per-seed records and code identities are in [f1-results.json](evidence/f1-results.json); the reproducible instrument is [f1_departures.py](probes/f1_departures.py).

| Horizon | Current terrain-aware timing | Previous departure estimate, routing still on |
| --- | --- | --- |
| Seeds 1-35, 400 ticks each | 0/35 seeds; 0 remembered-helper decision ticks | 0/35 seeds; 0 decision ticks |
| Seeds 1-35, 780 ticks each | 3/35 seeds (29, 30, 32); 12 decision ticks | 4/35 seeds (14, 26, 28, 29); 16 decision ticks |
| Seed 14, 650 ticks | 0 decision ticks | 5 decision ticks |
| Seed 26, 780 ticks | 0 decision ticks | 3 decision ticks |

These are decision ticks carrying native `helped_at`, not unique encounters or completed gifts. For both modes at 400 ticks, there are gifts and retained memories. Memory would change the helper target before need priority on 124 current-mode person-ticks and 143 previous-estimate person-ticks, but every such case selects eating, drinking, water collection/travel or shelter/warming instead. At 780, current mode has 344 such opportunities, of which 12 select the memory-influenced offer/travel action. Memory affects a tie-break only when help is actually selected; it does not override personal needs or create an encounter.

The first causal divergence remains decision tick 28 for seed 14 and 334 for seed 26. In both, the actor has the same observation, no food and hunger just below the threshold. The known-route estimate adds one tick and selects departure; the old estimate permits rest/building. Subsequent trajectories differ. This confirms the timing effect on those scenes without attributing all later outcomes to a single independent population benefit.

**Conclusion:** the remembered-donor mechanism is rare in this sample under both estimates. Terrain-aware departure removes some observed scenes and introduces others. The review's zero count is reproducible at its sampled horizons, but "no activation in ordinary default worlds" does not generalize to the same fixed seeds at 780 ticks. Keep terrain-aware departure; no need to force gifts, alter need priorities, add a new configuration switch, skip tests or impose an event-count floor.

The seed-14/26 tests now explicitly promise replay plus conditional event consistency, not activation. The artificial encounter still proves a complete rule chain and requires it to occur. No new favourable seed was pinned as a mandatory regression scene.

## Ordinary saved example

The packet includes seed 29, 780 ticks, all default settings. It was selected transparently from the fixed sweep because it is the first current-mode seed with an actual `offer` carrying `helped_at`; it is an illustration, not a frequency oracle.

- Decision tick 559 / world tick 560: p19 gives one food to p27; kernel transfer accepted.
- Decision ticks 708-710: p27 chooses to take food to remembered donor p19 rather than its otherwise preferred recipient.
- Decision tick 713 / world tick 714: p27 gives one food back to p19; transfer accepted, with native `helped_at=560`.

The file verifies and replays. Cutting after decision tick 708, with social memory active, recovers to exactly the same tick records and the recovered file replays. [The example script](probes/save_social_example.py) checks both transfers and saves the native viewer. See [example-summary.json](evidence/example-summary.json). This establishes one ordinary causal scene, not that every offer succeeds or that social memory improves survival.

## Validation and compatibility

See [VALIDATION.md](VALIDATION.md) for exact commands, environment, test results and evidence boundaries. The F2 test is a real rendered-DOM check, with Node/Playwright/browser prerequisites treated as failures, not silent skips. A Python embedding assertion also protects the script-data boundary; it does not stand in for the DOM test.

No valid configuration's simulation rules, default departure behaviour, schema or persisted `held` field were changed. Strict validation rejects previously accepted malformed Python API inputs. Presentation/help text and comments are clearer. Python source changes still change the existing code identity: old files remain readable, ordinary replay reports identity separately, and recovery requires its existing matching-identity condition. No compatibility checks were weakened.

Please reassess F1 and F2 against the new pinned target, with the wider sweep and rendered-browser evidence. The original signed FAIL is preserved; this builder response does not sign or decide the independent review on Claude's behalf.
