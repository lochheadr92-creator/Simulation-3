# SIM3_STATE

This file is a project-state snapshot. It MUST NOT override `ROADMAP.md`,
`AGENTS.md`, `DOCTRINE.md`, canonical specifications, or evidence records. It
authorises no stage, slice, run, or acceptance. Passing tests are not treated as
milestone completion. Values that cannot be established from the repository are
UNKNOWN.

```
current_milestone: Stage 1, slice 1a
milestone_status: open; no stage has passed; Stage 1 incomplete; Stage 1 exit unclaimed; independent post-repair review pending
authoritative_head: 53f42de1229401db1eeca2ca52390c3356c2a30f
last_accepted_gate: none
last_accepted_evidence: none
current_hypothesis: Two authorised claimants compete for one resource unit; settlement is atomic; observation is immutable.
proven: none independently accepted
not_proven: Stage 1 exit; independent post-repair acceptance; slices 1b, 1c, 1d; reservations; replay; sealed evidence stream; instance isolation; 50-actor cost envelope; any world, person, need, movement, memory, or social behaviour
parked: Stages 2-6; slices 1b-1d (not authorised); six-person starter world; 50-person behavioural demonstration
blockers: independent post-repair review of the Stage 1a repair is pending; no owner direction opens slice 1b or Stage 1 exit
next_gate: independent post-repair review of the Stage 1a repaired source
authoritative_documents: AGENTS.md; DOCTRINE.md; ROADMAP.md
last_updated: 2026-09-20
```

## Basis (snapshot only)

Sources read for this snapshot: `ROADMAP.md`, `AGENTS.md`, `DOCTRINE.md`,
`evidence/stage-01/RECORD.md`, `kernel/version.py`, and the git history of
`codex/kernel-first-slice`. No live simulation was run to populate this file.

- **Milestone.** `ROADMAP.md` states that no stage has passed and that Stage 1
  is open at slice 1a under OD-001. `evidence/stage-01/RECORD.md` states that
  only slice 1a is open, the Stage 1 exit gate is not claimed, and Stage 1
  remains incomplete. OD-002 authorises Stage 1a defect repair only. OD-003
  authorises publication of the existing branch and does not open a later slice
  or accept a stage.
- **HEAD.** `53f42de1229401db1eeca2ca52390c3356c2a30f` is `docs(stage-1a):
  record publication authority (OD-003)`. Preceding repair commit:
  `fb5a8959fb6a7a23d6e3107fe32be8248cc19901`.
- **Gates and evidence.** No stage exit review has a PASS verdict in this
  repository. An adversarial review of `fa8be6083b31ead3c7e6aae844c0fd749927e6d0`
  recorded CHANGES REQUIRED (R1–R5) under
  `evidence/stage-01/repair-1/review-before-repair/`. Repair 1 revalidation is
  recorded, not independently accepted. `last_accepted_gate` and
  `last_accepted_evidence` are therefore none.
- **Hypothesis.** The Stage 1a card claim in `evidence/stage-01/RECORD.md`: two
  authorised claimants, one unit, one winner; invalid writes and observer
  mutation cannot commit.
- **Recorded demonstrations, not gates.** Attempt 1 at
  `b48542b3567bfba9f0fa7a831ab8ace0eb6ddc1f` recorded 107 passing focused tests
  for A1–A11; that completeness claim was superseded by the later review.
  Repair 1 at `fb5a8959fb6a7a23d6e3107fe32be8248cc19901` recorded R1–R5 as
  resolved in tested repair, 148 passing tests, ordinary state identities
  unchanged, and record payloads differing only in `engine_version`
  (`0.1.1-stage1a`; schema `v3.kernel.1a.1`). Independent post-repair review is
  pending.
- **Parked / not authorised.** Slices 1b, 1c and 1d; Stages 2–6; worlds;
  experiments; capacity benchmarks. No experiment directory exists. No world
  seed or observation horizon is configured for the active slice. Stage 1a
  whole-world executions authorised: 0.
- **Automation tooling, not a gate.** Phase 1–3 development automation
  (`automation/preflight.py`, `automation/verify_evidence.py`,
  `automation/run_gate.py`) is present as read-only/safe tooling under OD-004.
  `authoritative_head` remains the last kernel/evidence publication
  (`53f42de1229401db1eeca2ca52390c3356c2a30f`). A later tooling commit cannot
  store its own hash in this file. Generated `evidence/automation-runs/`
  packages are local receipts, not accepted evidence.

Capability, reachability, and measurement remain separate. This snapshot does
not infer that Stage 1a or Stage 1 is complete.
