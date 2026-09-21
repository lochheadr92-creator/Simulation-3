# SIM3_STATE

This file is a project-state snapshot. It MUST NOT override `ROADMAP.md`,
`AGENTS.md`, `DOCTRINE.md`, canonical specifications, or evidence records. It
authorises no stage, slice, run, or acceptance. Passing tests are not treated as
milestone completion. Values that cannot be established from the repository are
UNKNOWN.

```
current_milestone: exploration leg 5 delivered (crowd-yield trait, visual checkpoint B); visual checkpoint C not accepted
milestone_status: open; no stage has passed; Stage 1 incomplete; Stage 1 exit unclaimed; exploration lane open; ratification lane holds 1c/1d/Stage 1 exit; slices 1a and 1b independently reviewed PASS (2026-09-21)
authoritative_head: a4e8915 (OD-010); kernel 0.2.0-stage1b at 9d1542d, unchanged by Stage 2 work
last_accepted_gate: none
last_accepted_evidence: none
current_hypothesis: A grid world with movement, one renewable source, hunger, a bounded perception radius and a seeded crowd-yield trait, composed on the unchanged kernel ledger, produces repeatable, readable trajectories in which people with the same view can decide differently, and in which each decision is taken from a local tick-start view.
proven: none independently accepted (reviews of 1a and 1b are reviewer verdicts on tooling-free kernel claims, not stage acceptance)
not_proven: Stage 1 exit; sealed evidence and replay (ratification-lane 1c); instance isolation; 50-actor cost envelope (1d, ratification); Stage 2 viability, opportunity counting and confirmation floors; visual checkpoint C; memory or social behaviour; crowd-yield as an accepted result (checkpoint B is exploration)
parked: Stage 3 re-entry; Stage 4; Stages 5-6; slice 1d and Stage 1 exit (ratification lane); orchestrator Phase 4 branches; six-person starter world as confirmation
blockers: none for delivered leg 5; leg 6 (contested scoring, visual checkpoint C) needs its own owner direction and a pre-code declaration
next_gate: wait for owner direction opening exploration leg 6; OD-010 does not open it
authoritative_documents: AGENTS.md; DOCTRINE.md; ROADMAP.md
last_updated: 2026-09-21
```

## Basis (snapshot only)

Sources read for this snapshot: `ROADMAP.md`, `AGENTS.md` (through OD-010),
`DOCTRINE.md`, `evidence/stage-01/RECORD.md`, `kernel/version.py`, and the git
history of `codex/kernel-first-slice`. Checkpoint runs remain exploration, not
evidence.

- **Milestone.** OD-009 Revision 3 opens the exploration lane. OD-010 opened
  leg 5; its stop condition is met (checkpoint B renders; seed-7 ON has
  yield events; ON/OFF is in the stage record). Nothing in this lane may
  claim a Stage exit. Stage 1 exit remains unclaimed.
- **HEAD.** `a4e8915` recorded OD-010. The kernel is `0.2.0-stage1b` (schema
  `v3.kernel.1b.1`) at `9d1542d`. A later commit cannot store its own hash
  in this file.
- **Reviews, not gates.** Slice 1a at `fb5a8959` and slice 1b (landed as
  `9d1542d`) each received an independent different-model PASS on their
  kernel claims (2026-09-21). No stage exit review exists;
  `last_accepted_gate` and `last_accepted_evidence` are none.
- **Mapping.** Legs 1–5 have corresponding delivered exploration work.
  Visual checkpoint B is rendered, not owner-accepted. Leg 6 / visual
  checkpoint C is not delivered and is not opened.
- **Parked / not authorised.** Stage 3 re-entry; Stage 4; orchestrator and
  pilot tooling; frozen hashes, provenance packages and adversarial
  acceptance until the ratification lane; the Stage 2 counting instrument
  and confirmation floors. Next permitted action is an owner direction that
  opens leg 6 with a pre-code declaration.

Capability, reachability, and measurement remain separate. This snapshot does
not infer that Stage 1 is complete.
