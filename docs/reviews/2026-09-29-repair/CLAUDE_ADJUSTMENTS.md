Yes, with three adjustments. The plan is sound and in two places it's sharper than my report.

**Where they're right and I'd sign off as written**

- Step 1 (preserve the FAIL, track F1–F11 in a separate response) is the correct discipline. The evidence zip I sent contains every probe and the damaged files, so "reviewer-reported until reproduced" should be a short state.
- Step 3's critique of my A/B is correct. `route_around=False` also changes movement paths, so it doesn't isolate departure timing; I flagged that in the report but their proposed diagnostic (restore only the departure calculation, keep routing on) is the right experiment. Their "do not force remembered gifts by delaying collection or imposing an arbitrary threshold" is exactly the line to hold. An honest zero is an acceptable outcome of that investigation.
- Step 4's pushback on F9 is fair. I listed zero perception, zero hunger rate and negative seed as *silently accepted*, not as defects; if the contract permits them, document that and move on.
- F8: not renaming the persisted `held` field is a better call than mine. A rename changes the canonical overlay, which changes code identity and breaks replay/recovery of every existing file for a cosmetic gain.

**Three adjustments**

1. **Sequence and time-box it.** Six workstreams is not "a focused repair pass". F2 plus the F11 assertion are an hour. F4 is small and mechanical. F1 is the only open-ended item and it should be time-boxed, because the doctrine already allows the answer "the mechanism is demonstrated but rare in ordinary worlds". Docs items (F5, F7, F10) can ride along. Order: F2 → F11 → F4 → F1 → docs.

2. **Widen the F1 baseline before concluding anything was lost.** Their diagnostic compares old vs new departure timing on seeds 14/26, which the builder originally selected *because* the rule fired there. Run the old-departure diagnostic across the same 1–35 sweep. If the old rate was, say, 2 seeds in 35, the honest statement is "this rule was always rare and is now rarer", not "terrain-aware departure removed a behaviour". That changes what the docs should say and whether any repair is warranted at all.

3. **The F2 regression must be a rendered-DOM check, not a source grep.** Their wording ("actually opens the relevant viewer section") is right; just be aware the suite already skips three tests without Node, so this test will silently skip in the same environments. Either make Node a hard requirement for that test file or add a Python-side assertion that `RUN.details`/deep totals contain no unescaped `<` from ids as a floor.

One minor: for F6 I'd downgrade "investigate" to "document". A listener waiting 12 ticks on an announcer who died in view is a modelling choice with a cap, and fixing it properly means adding witnessed-death to the observation model, which is a new rule, not a repair.

Everything else: agree. When the new commit lands, send me the packet and the F1–F11 response and I'll reassess the two blockers against the pinned SHA.

Claudes concerns