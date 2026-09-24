# Living World V3: notes for agents

Solo project. The owner is Ryan, and his word in chat is enough to commit,
push, start work or change direction. There is no approval register.

## What this is

A deterministic living-world simulation, in dependency order:

- `kernel/`: state, proposals and settlement. The only place resources move.
- `stream/`: sealed run files, replay and recovery.
- `world/`: people, positions, hunger, perception and decisions, built on the kernel.
- `viewer/`: renders run files; never reads live state.

Lower layers never import higher ones (`tests/test_dependency_direction.py`).
Design lives in `DOCTRINE.md` (principles) and `ROADMAP.md` (plan and tick
algorithm). Past results are in `evidence/stage-01/RECORD.md`; appending to it
is optional. The old governance is in `archive/governance/`.

## Run

    py -3 -B -m pytest -q -p no:cacheprovider
    py -3 -B -m world.run --seed 7 --ticks 300 --twice --html
    py -3 -B -m stream.run --replay FILE
    py -3 -B -m stream.bench --ticks 10000 --out FILE   # slice 1d cost check

## Rules

1. Tests green before a commit.
2. Never edit a test, fixture or reference file (`tests/fixtures/`, the frozen
   files under `evidence/`) just to make something pass. If a reference has to
   change, say why in the commit message.
3. No force push, history rewrite or branch deletion unless Ryan asks.
4. Report plainly: what you ran, what passed, what you assumed. Don't call
   something done that you didn't run.

## Conventions

- Branch `codex/kernel-first-slice`; origin
  `https://github.com/lochheadr92-creator/Simulation-3.git` (public).
- Commit subjects in ASCII, as `area(scope): what changed`.
- No runtime randomness; genesis uses a named, seeded generator.
- On Windows, if git complains about ownership, pass
  `-c safe.directory=C:/dev/03-Living-World-V3` rather than changing global config.
