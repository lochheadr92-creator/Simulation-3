# SIM3_STATE

This file is a project-state snapshot. It MUST NOT override `ROADMAP.md`,
`AGENTS.md`, `DOCTRINE.md`, canonical specifications, or evidence records. It
authorises no stage, slice, run, or acceptance. Passing tests are not treated as
milestone completion. Values that cannot be established from the repository are
UNKNOWN.

```
current_milestone: Stage 1, slice 1c
milestone_status: open; no stage has passed; Stage 1 incomplete; Stage 1 exit unclaimed; exploration lane closed by OD-014 (checkpoint C owner-accepted 2026-09-23; OD-009 Revision 3 closed; sequencing authority with ROADMAP.md); ratification lane open at slice 1c (OD-013, 2026-09-23), bounded by the ROADMAP 1c proof object (OD-015, 2026-09-23); slice 1c independently reviewed FAIL at d14decec (2026-09-23), completed executing review lodged with 2 blocking, 1 should fix, 2 observations; slice 1d not started and dependent work blocked by unresolved 1c prerequisites; obtain and eat remain separate actions; no same-tick obtain/eat; exploration leg 7 not opened; slices 1a and 1b independently reviewed PASS (2026-09-21)
authoritative_head: d14decec50d285395febb97c06d8eb7d94930b88
last_accepted_gate: none
last_accepted_evidence: none
current_hypothesis: slice 1c declared claims, independently reviewed FAIL at d14decec with reader/recovery findings F1/F2 unresolved: a v3.stream.3 run seals its header and every tick in one chain; replay from genesis and the recorded inputs reproduces every tick payload byte for byte; recovery through the last verified sealed tick, with live reservations at the cut, reproduces the uninterrupted run's sealed content; two engines restored from one sealed tick share no mutable object; kernel canonical forms and recorded fixtures stay unchanged. Essential claims are on kernel-only scenario runs; world runs are optional targets. The lodged review retains the exact per-claim verdicts and limitations.
proven: none independently accepted as a stage (1a/1b PASS and the bounded PASS subclaims within the 1c FAIL review are reviewer verdicts, not stage acceptance)
not_proven: Stage 1 exit; slice 1c overall (independent review FAIL: malformed suffixes prevent recovery of an intact sealed prefix; a later unsealed header controls recovery); 50-actor cost envelope (1d, ratification); Stage 2 viability, opportunity counting and confirmation floors; browser layout quality and owner acceptance of the OD-012 world view (checkpoint C acceptance is not viewer acceptance); memory or social behaviour; survival/fairness benefit from scored actions; crowd-yield as an accepted result
parked: the Stage 1 exit review until the 1d record exists (OD-013); orchestrator Phase 4 branches; six-person starter world as confirmation; Stages 2-6 are later roadmap stages and are not opened by OD-014 or OD-015; the source-at-cap question (OD-014 owner-supplied basis) waits for a later exploration direction
blockers: publication blocker resolved by owner direction 2026-09-22 ("push"): the local branch is merged with the published Phase 4 snapshot (810ab25) and pushed to the public origin; the earlier public-origin prohibition is superseded for this publication. Claim-then-eat latency resolved by OD-013 and grounded by OD-014 (2026-09-23): obtain and eat stay separate actions; no same-tick obtain/eat; owner design decision, not experimental proof; no kernel or world change. Checkpoint C accepted by OD-014 as closing the exploration question; exploration leg 7 is not opened. Whole-world leg-6 budget exhausted (3/3). Slice 1c boundary settled by OD-015 (ROADMAP proof object: sealed evidence, replay, recovery, private instance isolation). Slice 1c independent executing review FAIL is lodged at evidence/stage-01/review-2026-09-23-slice-1c/REVIEW.md. F1/F2 are blocking and unresolved; F3 should fix; F4/F5 observations. Slice 1d remains not started; unresolved prerequisites block dependent work under ROADMAP.md. Stage 1 exit review requires an independent reviewer once the 1c and 1d records are complete (OD-013); none requested yet.
next_gate: slice 1c ratification: sealed evidence stream and replay, with recovery through the last verified sealed tick and private instance isolation (ROADMAP proof object, OD-015): independent executing review FAIL lodged 2026-09-23. First unmet requirement is resolution and revalidation of the blocking 1c reader/recovery findings F1/F2; F3 remains a should-fix finding. Slice 1d capacity envelope is not started and dependent work is blocked; Stage 1 exit review waits for complete 1c and 1d records. Claim-then-eat latency retained per OD-013 and OD-014; exploration leg 7 not opened; no acceptance inferred. This lodging sitting authorises no repair or rerun.
authoritative_documents: AGENTS.md; DOCTRINE.md; ROADMAP.md
last_updated: 2026-09-23 (completed independent slice 1c review lodged; no rerun)
```

## Basis (snapshot only)

Lodging reconciliation, 2026-09-23: current governing documents, stage record,
git state at `d14decec`, and the completed independent review in
`evidence/stage-01/review-2026-09-23-slice-1c/REVIEW.md` and its existing
evidence. The owner requested lodging only; no scientific check was rerun.
The review's own RERUN/READ/UNKNOWN labels describe the reviewer's work,
not this filing sitting. Prior builder-snapshot sources are retained below.

Sources read for the builder snapshot: `ROADMAP.md` (banner, Stage 1, stage-card
template), `AGENTS.md` (authority sections; OD-009 through OD-015),
`DOCTRINE.md`, `evidence/stage-01/RECORD.md` (top cards and the OD-013 to
OD-015 entries), `kernel/state.py`, `kernel/engine.py`, `kernel/proposals.py`,
`kernel/canonical.py`, `kernel/outcomes.py`, `kernel/version.py`,
`stream/run_file.py`, `stream/run.py`, `stream/scenario.py`, `world/run.py`,
`world/config.py`, `world/overlay.py`, the format checks in
`viewer/world_view.py`, `tests/test_dependency_direction.py`, and the git
history of `codex/kernel-first-slice` at `028ffa8`, with the commit-B changes and the frozen references. The latency bullet rests
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
- **HEAD.** `d14decec` is slice 1c commit B, the reviewed target and current
  checkout HEAD at lodging. The preceding builder snapshot named commit A
  (`028ffa8`) because commit B could not contain its own hash.
  Kernel version `0.2.0-stage1b` and schema `v3.kernel.1b.1` are unchanged;
  `kernel/state.py` gains additive `from_canonical` constructors, and no
  settlement rule or canonical form changes.
- **Reviews, not gates.** Slice 1a at `fb5a8959` and slice 1b (landed as
  `9d1542d`) each received an independent different-model PASS on their
  kernel claims (2026-09-21). Slice 1c at `d14decec` received an independent
  executing **FAIL** (2026-09-23): **2 blocking, 1 should fix, 2 observations**.
  Reviewer: Codex / GPT-6, exact serving identifier unavailable; builder:
  Claude, configured `claude-opus-5-5`. The earlier summary-only PASS is
  superseded. No stage exit review exists;
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
- **Slice 1c record delivered; independent review FAIL lodged.** The declaration in `RECORD.md`
  (active card and "Slice 1c declaration") fixes the v3.stream.3 schema, seal,
  replay, recovery and isolation before any writer. It departs from the
  2026-09-23 build brief where the code required it; the differences are
  listed at its end. Essential claims are on kernel-only scenario runs; world
  runs are optional targets. Commits A and B built the sealed writer and
  reader, inputs, reconstruction, replay, recovery and isolation; the frozen
  references and the reviewer's `reproduce.py` are under
  `evidence/stage-01/slice-1c/`. New run files are v3.stream.3; older
  v3.stream.2 files stay readable, unsealed. The completed executing review
  reports FAIL for essential claims (1) sealing/reader break reporting and
  (3) broken-file recovery, and PASS for (2) replay, (4) isolation,
  (5) compatibility and (6) dependency direction. F1/F2 remain unresolved;
  intact-reference success does not close the damaged-file requirements.
  The review package and original ZIP are preserved byte for byte; filing
  details are in `review-2026-09-23-slice-1c/LODGING.md` under the stage record.
  The separate owner-requested 1c review superseded the card's review-timing
  restriction only for that review. OD-013's Stage 1 exit-review timing stands.
- **Owner decision draft, 2026-09-23.** Written against `df99524`; its
  decisions are OD-013 and OD-014 and are not entered again. Its tentative
  slice list placing isolation in 1d is superseded by OD-015; its note that
  checkpoint C acceptance is not viewer acceptance is carried in
  `not_proven`.
- **Tooling.** Local `run_gate` receipts are gitignored and are not evidence.
  The orchestrator does not decide acceptance.

Capability, reachability, and measurement remain separate. This snapshot does
not infer that Stage 1 is complete.
