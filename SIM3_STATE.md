# SIM3_STATE

This file is a project-state snapshot. It MUST NOT override `ROADMAP.md`,
`AGENTS.md`, `DOCTRINE.md`, canonical specifications, or evidence records. It
authorises no stage, slice, run, or acceptance. Passing tests are not treated as
milestone completion. Values that cannot be established from the repository are
UNKNOWN.

```
current_milestone: Stage 2, second step (perception radius and bounded views); checkpoint 3 delivered under OD-009
milestone_status: open; no stage has passed; Stage 1 incomplete; Stage 1 exit unclaimed; slice 1d deferred; Stage 2 open in checkpoint order only; slices 1a and 1b independently reviewed PASS (2026-09-21)
authoritative_head: b305783 (checkpoint 2); kernel 0.2.0-stage1b at 9d1542d, unchanged by Stage 2 work
last_accepted_gate: none
last_accepted_evidence: none
current_hypothesis: A grid world with movement, one renewable source, hunger and a bounded perception radius, composed on the unchanged kernel ledger, produces repeatable, readable trajectories in which who eats and who dies follows from declared rules and kernel contention, not from identity, and in which each decision is taken from a local tick-start view.
proven: none independently accepted (reviews of 1a and 1b are reviewer verdicts on tooling-free kernel claims, not stage acceptance)
not_proven: Stage 1 exit; sealed evidence and replay (deferred part of 1c); instance isolation; 50-actor cost envelope (1d deferred); Stage 2 viability, opportunity counting and confirmation floors; memory or social behaviour; perception as an accepted result (checkpoint 3 is exploration)
parked: Stages 3-6; slice 1d; orchestrator Phase 4 branches; six-person starter world; 50-person behavioural demonstration
blockers: none for delivered checkpoint work; OD-009 names no further checkpoint; Stage 3 (request food) is not authorised
next_gate: none in OD-009 checkpoint order; Stage 2 counting instrument and confirmation floors remain closed; Stage 3 not authorised
authoritative_documents: AGENTS.md; DOCTRINE.md; ROADMAP.md
last_updated: 2026-09-21
```

## Basis (snapshot only)

Sources read for this snapshot: `ROADMAP.md`, `AGENTS.md` (through OD-009),
`DOCTRINE.md`, `evidence/stage-01/RECORD.md`, `kernel/version.py`, and the git
history of `codex/kernel-first-slice`. The checkpoint runs referenced below
were executed locally; their output is exploration, not evidence.

- **Milestone.** OD-009 re-scopes slice 1c to a record stream plus a viewer
  and defers slice 1d; checkpoint 1 (`stream/`) is delivered. Stage 2 is
  open in checkpoint order only: its first step, position, movement, one
  renewable source and hunger, is delivered as checkpoint 2 (`world/`, a map
  over time); its second step, perception radius and bounded views, is
  delivered as checkpoint 3 (`RECORD.md`, "Stage 2, second step"). Stage 1
  exit remains unclaimed; sealed evidence and replay (the deferred part of
  1c) are not built.
- **HEAD.** `b305783` landed checkpoint 2. The kernel is `0.2.0-stage1b`
  (schema `v3.kernel.1b.1`) at `9d1542d`; Stage 2 work composes it and does
  not modify it. A later commit cannot store its own hash in this file.
- **Reviews, not gates.** Slice 1a at `fb5a8959` and slice 1b (snapshot of
  `b915aa0`, landed as `9d1542d`) each received an independent
  different-model PASS on their kernel claims (2026-09-21). No stage exit review
  exists; `last_accepted_gate` and `last_accepted_evidence` are none.
- **Hypothesis.** A grid world with movement, one renewable source, hunger
  and a bounded Chebyshev view on the unchanged kernel ledger gives
  repeatable, readable trajectories in which who eats and who dies follows
  from declared rules and kernel contention, and each person decides from
  what they can see at tick start. Checkpoint 3 showed the same seeded
  300-tick deaths as checkpoint 2 (three of six survive) with native
  per-person observations; radius 12 decisions matched HEAD byte-for-byte.
  It accepts nothing and counts no opportunities.
- **Open observations.** With the default levers the source cannot feed six;
  claim and eat are separate ticks, so two deaths happened at the source
  holding food; reservations never expire (1b declaration); people now see
  neighbours inside radius 3 but do not act on them. `automation/preflight.py`
  reports the milestone and head lines above as mismatches because it
  recognises fixed phrases; recorded, not fixed (OD-009).
- **Parked / not authorised.** Slice 1d; Stages 3–6; orchestrator Phase 4
  branches (parked as drift under OD-009); frozen hashes, provenance packages
  and adversarial acceptance for checkpoint work; the Stage 2
  opportunity-counting instrument and confirmation floors. OD-009 names no
  checkpoint after 3; Stage 3 is not opened by this snapshot.

Capability, reachability, and measurement remain separate. This snapshot does
not infer that Stage 1 is complete.
