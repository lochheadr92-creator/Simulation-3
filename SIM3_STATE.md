# SIM3_STATE

This file is a project-state snapshot. It MUST NOT override `ROADMAP.md`,
`AGENTS.md`, `DOCTRINE.md`, canonical specifications, or evidence records. It
authorises no stage, slice, run, or acceptance. Passing tests are not treated as
milestone completion. Values that cannot be established from the repository are
UNKNOWN.

```
current_milestone: Stage 1, slice 1c (record stream and viewer, re-scoped by OD-009; checkpoint 1 delivered)
milestone_status: open; no stage has passed; Stage 1 incomplete; Stage 1 exit unclaimed; slices 1a and 1b independently reviewed PASS (2026-09-21); slice 1d deferred
authoritative_head: 6c2c0efd (OD-009 recorded); kernel 0.2.0-stage1b at 9d1542d
last_accepted_gate: none
last_accepted_evidence: none
current_hypothesis: The kernel's contested transactions and two-tick reservations can be written to a record stream and read back, reproducibly, so a world built on them can be looked at before it is argued about.
proven: none independently accepted (reviews of 1a and 1b are reviewer verdicts on tooling-free kernel claims, not stage acceptance)
not_proven: Stage 1 exit; sealed evidence and replay (deferred part of 1c); instance isolation; 50-actor cost envelope (1d deferred); any world, person, need, movement, memory, or social behaviour
parked: Stages 3-6; slice 1d; orchestrator Phase 4 branches; six-person starter world; 50-person behavioural demonstration
blockers: none for checkpoint work; the first Stage 2 step (position, movement, food source, hunger) needs only the checkpoint cadence in OD-009
next_gate: checkpoint 2, a map over time, after the first Stage 2 step
authoritative_documents: AGENTS.md; DOCTRINE.md; ROADMAP.md
last_updated: 2026-09-21
```

## Basis (snapshot only)

Sources read for this snapshot: `ROADMAP.md`, `AGENTS.md` (through OD-009),
`DOCTRINE.md`, `evidence/stage-01/RECORD.md`, `kernel/version.py`, and the git
history of `codex/kernel-first-slice`. The checkpoint 1 run referenced below
was executed locally; its output is exploration, not evidence.

- **Milestone.** OD-009 re-scopes slice 1c to a record stream plus a viewer
  that renders from the stream, and defers slice 1d. Checkpoint 1 is
  delivered: `stream/` writes and verifies append-only JSONL runs and renders a
  self-contained HTML page from them (`RECORD.md`, "Slice 1c (re-scoped) —
  checkpoint 1"). Stage 1 exit remains unclaimed; sealed evidence and replay
  (the deferred part of 1c) are not built.
- **HEAD.** `6c2c0efd` records OD-009. The kernel is `0.2.0-stage1b`
  (schema `v3.kernel.1b.1`) at `9d1542d`, which landed slice 1b with both
  review records. A later stream/tooling commit cannot store its own hash in
  this file.
- **Reviews, not gates.** Slice 1a at `fb5a8959` and slice 1b (snapshot of
  `b915aa0`, landed as `9d1542d`) each received an independent
  different-model PASS on their kernel claims (2026-09-21). No stage exit review
  exists; `last_accepted_gate` and `last_accepted_evidence` are none.
- **Hypothesis.** The 1b kernel claims (phased settlement, two-tick
  reservations, availability = stock − holds, rails) can be written to a
  record stream, read back with every digest recomputed, and reproduced
  byte-for-byte from a seed. Checkpoint 1 demonstrated this for one seeded
  200-tick run; it does not accept anything.
- **Open observations.** Reservations never expire (1b declaration), so holds
  accumulate over long runs; the economy has no production. Both feed Stage 2
  scoping. `automation/preflight.py` reports the milestone line above as a
  mismatch because it recognises fixed phrases; recorded, not fixed (OD-009).
- **Parked / not authorised.** Slice 1d; Stages 3–6; orchestrator Phase 4
  branches (parked as drift under OD-009); frozen hashes, provenance packages
  and adversarial acceptance for checkpoint work. Stage 2 opens only in
  checkpoint order: position, movement, food source, hunger, then
  checkpoint 2, a map over time.

Capability, reachability, and measurement remain separate. This snapshot does
not infer that Stage 1 is complete.
