# SIM3_STATE

This file is a project-state snapshot. It MUST NOT override `ROADMAP.md`,
`AGENTS.md`, `DOCTRINE.md`, canonical specifications, or evidence records. It
authorises no stage, slice, run, or acceptance. Passing tests are not treated as
milestone completion. Values that cannot be established from the repository are
UNKNOWN.

```
current_milestone: Stage 1, slice 1c
milestone_status: open; no stage has passed; Stage 1 incomplete; Stage 1 exit unclaimed; exploration lane closed by OD-014 (checkpoint C owner-accepted 2026-09-23; OD-009 Revision 3 closed; sequencing authority with ROADMAP.md); ratification lane open at slice 1c (OD-013, 2026-09-23), bounded by the ROADMAP 1c proof object (OD-015, 2026-09-23); slice 1c declared before code 2026-09-23 (RECORD.md active card), not implemented; obtain and eat remain separate actions; no same-tick obtain/eat; exploration leg 7 not opened; slices 1a and 1b independently reviewed PASS (2026-09-21)
authoritative_head: 6f500408b59e69f6f9c0da2be14172bb2f30a993
last_accepted_gate: none
last_accepted_evidence: none
current_hypothesis: slice 1c, declared and not implemented: a v3.stream.3 run seals its header and every tick in one chain; replay from genesis and the recorded inputs reproduces every tick payload byte for byte; recovery through the last verified sealed tick, with live reservations at the cut, reproduces the uninterrupted run's sealed content; two engines restored from one sealed tick share no mutable object; kernel canonical forms and recorded fixtures stay unchanged. Essential claims are on kernel-only scenario runs; world runs are optional targets.
proven: none independently accepted (reviews of 1a and 1b are reviewer verdicts on tooling-free kernel claims, not stage acceptance)
not_proven: Stage 1 exit; slice 1c (sealed evidence, replay, recovery through the last verified sealed tick, instance isolation; ROADMAP proof object per OD-015); 50-actor cost envelope (1d, ratification); Stage 2 viability, opportunity counting and confirmation floors; browser layout quality and owner acceptance of the OD-012 world view (checkpoint C acceptance is not viewer acceptance); memory or social behaviour; survival/fairness benefit from scored actions; crowd-yield as an accepted result
parked: slice 1d and the Stage 1 exit until the 1c record exists; orchestrator Phase 4 branches; six-person starter world as confirmation; Stages 2-6 are later roadmap stages and are not opened by OD-014 or OD-015; the source-at-cap question (OD-014 owner-supplied basis) waits for a later exploration direction
blockers: publication blocker resolved by owner direction 2026-09-22 ("push"): the local branch is merged with the published Phase 4 snapshot (810ab25) and pushed to the public origin; the earlier public-origin prohibition is superseded for this publication. Claim-then-eat latency resolved by OD-013 and grounded by OD-014 (2026-09-23): obtain and eat stay separate actions; no same-tick obtain/eat; owner design decision, not experimental proof; no kernel or world change. Checkpoint C accepted by OD-014 as closing the exploration question; exploration leg 7 is not opened. Whole-world leg-6 budget exhausted (3/3). Slice 1c boundary settled by OD-015 (ROADMAP proof object: sealed evidence, replay, recovery, private instance isolation). Slice 1c declared before code (RECORD.md active card, 2026-09-23); implementation not started. Stage 1 exit review requires an independent reviewer; none requested yet.
next_gate: slice 1c ratification: sealed evidence stream and replay, with recovery through the last verified sealed tick and private instance isolation (ROADMAP proof object, OD-015): commit A (seal, inputs, reader, reconstruction, replay), then commit B (recovery, isolation, frozen references, results), per the declaration in RECORD.md; then slice 1d capacity envelope; Stage 1 exit review requested from an independent reviewer once the 1c and 1d records are complete. Claim-then-eat latency retained per OD-013 and OD-014; exploration leg 7 not opened; no acceptance inferred. First unmet work is slice 1c commit A.
authoritative_documents: AGENTS.md; DOCTRINE.md; ROADMAP.md
last_updated: 2026-09-23 (slice 1c declaration)
```

## Basis (snapshot only)

Sources read for this snapshot: `ROADMAP.md` (banner, Stage 1, stage-card
template), `AGENTS.md` (authority sections; OD-009 through OD-015),
`DOCTRINE.md`, `evidence/stage-01/RECORD.md` (top cards and the OD-013 to
OD-015 entries), `kernel/state.py`, `kernel/engine.py`, `kernel/proposals.py`,
`kernel/canonical.py`, `kernel/outcomes.py`, `kernel/version.py`,
`stream/run_file.py`, `stream/run.py`, `stream/scenario.py`, `world/run.py`,
`world/config.py`, `world/overlay.py`, the format checks in
`viewer/world_view.py`, `tests/test_dependency_direction.py`, and the git
history of `codex/kernel-first-slice` at `6f50040`. The latency bullet rests
on the sources the OD-014 snapshot read (`kernel/settlement.py`,
`world/decide.py`). Checkpoint runs remain exploration, not evidence.

- **Milestone line.** `current_milestone` is `Stage 1, slice 1c`, the slice
  ROADMAP.md's banner names. Earlier snapshots carried `Stage 1, slice 1a`
  because `automation/preflight.py` could only derive that phrase from the
  historical record line "Only slice 1a is open", and the orchestrator
  refuses every action on any inconsistency. The parser now reads the
  banner's explicit active-slice statement (OD-014, tooling scope); the
  orchestrator's blocking rule is unchanged. The two remaining preflight
  inconsistencies (`record_rollback_describes_no_remote`,
  `stage_card_review_status_stale`) are informational.
- **Milestone.** OD-014 accepts checkpoint C and closes OD-009 Revision 3.
  Sequencing authority returns to `ROADMAP.md`. The ratification lane opened
  by OD-013 is slice 1c, then 1d, then an independent Stage 1 exit review.
  OD-015 (owner, 2026-09-23: "folow roadmap") bounds slice 1c by the ROADMAP
  proof object: sealed evidence, replay, recovery, and private instance
  isolation. Exploration leg 7 is not opened. OD-014 and OD-015 are owner
  decisions. Neither accepts the Stage 1 exit.
- **HEAD.** `6f50040` records OD-015 and is the commit this entry sits on;
  the commit recording the declaration cannot contain its own hash. Kernel
  `0.2.0-stage1b`, schema `v3.kernel.1b.1`, unchanged since `9d1542d`. No
  simulation source is changed by the declaration.
- **Reviews, not gates.** Slice 1a at `fb5a8959` and slice 1b (landed as
  `9d1542d`) each received an independent different-model PASS on their
  kernel claims (2026-09-21). No stage exit review exists;
  `last_accepted_gate` and `last_accepted_evidence` are none.
- **Exploration delivered, historical.** Legs 1-6 correspond to delivered
  work: 1b landed; stream checkpoint 1; world checkpoint 2 (A); perception
  checkpoint 3; crowd-yield trait (B); scored actions (C). ON/OFF results for
  B and C are recorded in `RECORD.md` as pictures of a difference, not
  claims. No survival or fairness benefit is established. Checkpoint C was
  owner-inspected in the OD-012 world view (tick 135 OFF, tick 300 ON);
  carried forward as an input: in the ON run the source sits at its cap
  while people are hungry and away from it, so renewal is discarded. The
  leg-6 card in `RECORD.md` is a closed preceding card (rows unchanged).
- **Latency.** Obtain and eat stay separate (OD-013, rationale in OD-014).
  A credit settled in a tick is spendable at the next tick start
  (`kernel/settlement.py`). Eat is eligible from food already held at tick
  start (`world/decide.py`). The deaths at the source holding newly claimed
  units remain a recorded consequence of that rule.
- **Slice 1c declared, not implemented.** The declaration in `RECORD.md`
  (active card and "Slice 1c declaration") fixes the v3.stream.3 schema, seal,
  replay, recovery and isolation before any writer. It departs from the
  2026-09-23 build brief where the code required it; the differences are
  listed at its end. Essential claims are on kernel-only scenario runs; world
  runs are optional targets. The exploration stream (`v3.stream.2`) is not the
  ROADMAP seal.
- **Owner decision draft, 2026-09-23.** Written against `df99524`; its
  decisions are OD-013 and OD-014 and are not entered again. Its tentative
  slice list placing isolation in 1d is superseded by OD-015; its note that
  checkpoint C acceptance is not viewer acceptance is carried in
  `not_proven`.
- **Tooling.** Local `run_gate` receipts are gitignored and are not evidence.
  The orchestrator does not decide acceptance.

Capability, reachability, and measurement remain separate. This snapshot does
not infer that Stage 1 is complete.
