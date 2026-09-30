# Repository navigation

## Source snapshot

- Source branch: `codex/kernel-first-slice`
- Source HEAD: `eda72d290bdb33aaaf620ad136149c6ef04e0a96`
- Constructed: 2026-09-28 from local source inspection and recorded documentation.
- Currency: snapshot only; not automatically current after this revision. Recheck relevant source and Git state before acting.
- Authority: [AGENTS.md](../../AGENTS.md) wins over this pack; [WORLD_DIRECTIONS.md](../../WORLD_DIRECTIONS.md) supplies current development direction.
- Evidence source: repository inventory, tracked paths, .gitignore and test references.
- Refresh trigger: after significant repository restructuring.

Repository root: `C:\dev\03-Living-World-V3`. This is a directory guide; use [system map](03_SYSTEM_MAP.md) for function/test routing.

| Location | Role and retrieval guidance |
| --- | --- |
| [AGENTS.md](../../AGENTS.md) | Repository-level agent authority and product brief. Read first. |
| [WORLD_DIRECTIONS.md](../../WORLD_DIRECTIONS.md) | Current direction plus accumulated feature reports/examples. Check chronology and correction notices. |
| [docs/ai](00_AGENT_CONSTITUTION.md) | This source-pinned context-compression pack. Start with 00 and 05, then 03. |
| [kernel](../../kernel/) | Ledger state, proposal construction, settlement, reservations, ordering, canonical encoding, outcomes and diagnostics. |
| [stream](../../stream/) | JSONL writer/reader, generic scenario runner, replay/recovery, text/HTML inspection and synthetic benchmark. |
| [world](../../world/) | Configuration, overlay, observe/decide/process, domain helpers (including `yard.py` and `work.py` for shared wood yards, `tools.py` for stone and the axe), runner, replay/recovery, benchmark and current viewer assets. |
| [viewer](../../viewer/) | Older independent isometric viewer. Narrower feature compatibility; not the default recommendation for the current world. |
| [tests](../../tests/) | Pytest contracts and regressions. Some historical artifacts are live test dependencies. |
| [tools](../../tools/) | Small JavaScript viewer helpers: shoot.js, feed.js and why.js. Inspect before use; these are not simulation entry points. |
| [evidence](../../evidence/) | Historical reviews, fixture instruments/results and workload records. Background authority, but do not assume files are unused. |
| [archive](../../archive/README.md) | Inactive governance and parked orchestrator code/tests. Not the current development workflow. |
| `runs/` | Ignored local saved worlds and generated HTML/images. May be absent in a clean clone. |

## Configuration and launch points

[pyproject.toml](../../pyproject.toml) configures pytest. [package.json](../../package.json) declares Playwright as a development dependency; the Python simulation is not a Node application. [package-lock.json](../../package-lock.json) records that dependency resolution.

`world.config.WorldConfig` owns simulation levers and saved descriptions. `world.run` is the world CLI, `world.viewer` renders saved worlds, `stream.run` runs generic kernel scenarios, and `world.bench`/`stream.bench` are distinct cost workloads. See [testing](08_TESTING_AND_PROOFS.md) for supported command forms.

[.gitignore](../../.gitignore) excludes runs, Python/pytest caches and node_modules, with a separate rule for local automation receipts. Their existence on one machine is not repository publication. [.gitattributes](../../.gitattributes) includes repository file-handling rules; preserve them.

## Historical documents and dependencies

Root [DOCTRINE.md](../../DOCTRINE.md) and [ROADMAP.md](../../ROADMAP.md) describe earlier design/process material. [CLAUDE_REVIEW.md](../../CLAUDE_REVIEW.md) attributes findings to a review of c1d13cb, before later repairs. Neither is a current HEAD certification.

The archived governance directory contains the old state file and OD register; no root SIM3_STATE file was found. Do not invent missing root paths from older references. The parked orchestrator lives under archive rather than an active root automation package.

For retained reference execution, start with [test_reference_results.py](../../tests/test_reference_results.py), its [fixture instrument](../../evidence/stage-01/instrument/fixture_digests.py) and [recorded output](../../evidence/stage-01/slice-1b/fixtures-stage1b.txt). “Historical” means its original process authority is inactive, not that it is safe to remove.

No existing canonical AI-doc directory or .github workflow directory was found before pack creation. Refresh this navigation after restructuring rather than assuming those absences persist.
