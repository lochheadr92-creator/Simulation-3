# SIM3_STATE

This file is a project-state snapshot. It MUST NOT override `ROADMAP.md`,
`AGENTS.md`, `DOCTRINE.md`, canonical specifications, or evidence records. It
authorises no stage, slice, run, or acceptance. Passing tests are not treated as
milestone completion. Values that cannot be established from the repository are
UNKNOWN.

```
current_milestone: exploration leg 5 open under OD-010 (inter-agent state, visual checkpoint B); not started; visual checkpoint C not accepted
milestone_status: open; no stage has passed; Stage 1 incomplete; Stage 1 exit unclaimed; exploration lane open; ratification lane holds 1c/1d/Stage 1 exit; slices 1a and 1b independently reviewed PASS (2026-09-21)
authoritative_head: 9d354414 (checkpoint 3); kernel 0.2.0-stage1b at 9d1542d, unchanged by Stage 2 work
last_accepted_gate: none
last_accepted_evidence: none
current_hypothesis: A grid world with movement, one renewable source, hunger and a bounded perception radius, composed on the unchanged kernel ledger, produces repeatable, readable trajectories in which who eats and who dies follows from declared rules and kernel contention, not from identity, and in which each decision is taken from a local tick-start view.
proven: none independently accepted (reviews of 1a and 1b are reviewer verdicts on tooling-free kernel claims, not stage acceptance)
not_proven: Stage 1 exit; sealed evidence and replay (ratification-lane 1c); instance isolation; 50-actor cost envelope (1d, ratification); Stage 2 viability, opportunity counting and confirmation floors; visual checkpoints B and C; memory or social behaviour; perception as an accepted result
parked: Stage 3 re-entry; Stage 4; Stages 5-6; slice 1d and Stage 1 exit (ratification lane); orchestrator Phase 4 branches; six-person starter world as confirmation
blockers: none for leg 5; OD-010 carries its pre-code declaration; leg 6 stays closed until leg 5 reaches its stop condition
next_gate: visual checkpoint B (leg 5 stop condition: a rendered map with at least one yield event and its ON/OFF comparison recorded)
authoritative_documents: AGENTS.md; DOCTRINE.md; ROADMAP.md
last_updated: 2026-09-21
```

## Basis (snapshot only)

Sources read for this snapshot: `ROADMAP.md`, `AGENTS.md` (through OD-009
Revision 3), `DOCTRINE.md`, `evidence/stage-01/RECORD.md`, `kernel/version.py`,
and the git history of `codex/kernel-first-slice`. Checkpoint runs remain
exploration, not evidence.

- **Milestone.** OD-009 Revision 3 opens the exploration lane and governs
  sequencing until visual checkpoint C is accepted or the direction is
  withdrawn. Nothing in this lane may claim a Stage exit. Stage 1 exit
  remains unclaimed; slices 1c and 1d wait in the ratification lane.
- **HEAD.** `9d354414` landed checkpoint 3 (perception). The kernel is
  `0.2.0-stage1b` (schema `v3.kernel.1b.1`) at `9d1542d`. A later commit
  cannot store its own hash in this file.
- **Reviews, not gates.** Slice 1a at `fb5a8959` and slice 1b (landed as
  `9d1542d`) each received an independent different-model PASS on their
  kernel claims (2026-09-21). No stage exit review exists;
  `last_accepted_gate` and `last_accepted_evidence` are none.
- **Mapping to the new leg order (historical, not a pass).** Leg 1 (close
  1b) is done. Legs 2–4 have corresponding delivered exploration work:
  world presence, position/locality (visual checkpoint A / old checkpoint 2),
  and decision-time observations (old checkpoint 3). Leg 5 (people notice
  each other, differentiated by a declared trait) is not delivered: people
  can see neighbours but do not act on them, and no trait differentiates
  them. Leg 6 / visual checkpoint C is not delivered. This revision does
  not open those legs.
- **Parked / not authorised.** Stage 3 re-entry; Stage 4; orchestrator and
  pilot tooling; frozen hashes, provenance packages and adversarial
  acceptance until the ratification lane; the Stage 2 counting instrument
  and confirmation floors. Next permitted action is an owner direction that
  opens one exploration leg with a pre-code declaration.

Capability, reachability, and measurement remain separate. This snapshot does
not infer that Stage 1 is complete.
