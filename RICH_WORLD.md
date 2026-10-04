# Rich world: what exists, what is being added, where it stands

This file is the working record for the expansion of Simulation 3 into a richer
aquarium: people with personalities who learn, form relationships, cooperate,
farm, build, raise families, grow old and die. Everything is rule-based; nothing
chooses at runtime but the rules. It states what the code does today, which
phase each addition belongs to, and exactly where to pick up.

Everything new is an explicit saved option. With every new option off, a run is
byte-for-byte the same as before the work began (`tests/test_disabled_mode_baseline.py`).

## Starting point (checked against source, not old reports)

Baseline: branch `claude/youthful-bardeen-wc346l`, HEAD `02af86b`, clean tree.
The full suite at that commit was run fresh in a pristine export (results in the
"Verification log" below). The reference projects named in the task
(`C:\dev\Claude Experiment\living-world`, `C:\dev\Grok Experiment`) are not
reachable from this machine, so **nothing here is borrowed from their code**.
The feature list in the task, and the information leaks it warns about, were the
specification.

## Inventory against the current source

| Area | Already there | Limited | Missing at the start |
| --- | --- | --- | --- |
| Needs | hunger, thirst, cold; least-slack arbitration; leave-in-time planning | `rest` is an idle action, not a need | fatigue/sleep, safety, companionship |
| Individuality | `yield_at` crowd trait | one trait, only used at food sources | generosity, sociability, caution, diligence, curiosity; skills and practice |
| Relationships | received-food memory (4 donors) | prefers past donors when helping | friendship, trust, attraction, couples, quarrels, apologies, avoidance |
| Speech | one-way announcements (food trips) and firsthand empty-source reports to adjacent housemates | housemates only | greetings, conversations, warnings, gossip, information requests |
| Requests | food requests, answers, promises, direct handoffs (`requests_on`, off by default) | food only; silence is the only refusal; no reservations | water/material/tool/information/building/repair/hauling help, explicit decline/fail/expire, escrow |
| Family | births from settled adjacent pairs; children, parent links (`parent`, `second_parent`); feeding; water care; adult homes; relocation | no couples or pregnancy; nobody ages past adulthood | couples, households as a unit, pregnancy, orphans, elders, old-age death, grief, newcomers |
| Work | build a shelter (12 ticks, optionally paid in wood); wood groves; fishing; shared food caches; provisioning trips | one building kind; one skill-free build | stone, tools, crafting, farming, spoilage, distinct foods, hauling beyond provisioning |
| Buildings | shelter on the home cell; home capacity 2; caches | permanent, never wear | other building kinds, upkeep, collapse, repairs, fires, constructed wells |
| Environment | plentiful/lean seasons; patch wear and recovery | food only | day/night, temperature, rain, storms, exposure |
| Wildlife | none | | wolves, danger perception, attacks, injuries, warnings |
| Knowledge | seen/remembered rough ground; dated empty-source sightings; stale shelter vacancies; firsthand reports with provenance and expiry | each kind is its own special case | one belief model with age/confidence/provenance for places, plots, danger; forgetting; exploration |
| Death | `died_at`; a stone marker in the viewer; cause shown from need levels | belongings stay in the dead person's account for ever, unreachable | graves, recoverable belongings, estate, commitments reacting to death, detailed death record |
| Viewer | isometric canvas, pan/zoom/follow, scrub, 1-32 ticks/s, layers, perception radius, family links, request arcs, inspector with alternatives and kernel outcome, event list | the inspector lists eligible alternatives only | minimap, knowledge fog, intent/path overlays, rejected-choice reasons, seed/scene launcher, save/resume, live mode |

Two facts about the existing code shape the work:

* Source positions are *known landmarks* to everyone from birth. Anything new that
  people should have to discover (plots, huts, wells they did not build, fires,
  graves, wolves) is *not* a landmark and must be seen or told.
* The saved run stores the full overlay on every tick. New per-person state must
  stay compact, and all of it must be integers and strings (the canonical form
  refuses floats and booleans).

## Architectural decisions made so far

* **Overlay updates carry fields forward.** `process.advance` and `_births` used to
  rebuild the whole overlay field by field, so a field they did not name was reset
  every tick. They now use `dataclasses.replace`, so new state survives by default.
  The 16 baseline runs reproduce exactly through the change.
* **Baseline comparisons use content, not trail digests.** Trail digests include
  seals, and seals chain from a hash of every source file, so they change with any
  edit. `tests/fixtures/baseline_digests.json` holds seal-free content digests of
  16 configurations at `02af86b`.
* **Independent ledger audit.** `tests/ledger_audit.py` explains every account
  change in a saved run by an accepted outcome or a recorded production entry.
  Every new feature test runs it. Mutation tests prove it notices tampering.

* **Features are a table, not a pile of switches.** `world/registry.py` collects named
  features (each declared next to the code that implements it: needs, integer
  settings, rule text, display tables). A configuration lists the ones that are on;
  the header gains `features`, `feature_levers`, `feature_rules` and `feature_tables`
  only then, and `from_describe` still insists on exact round trips. Settings equal to
  their defaults are not stored, so a rebuilt configuration compares equal.
* **Inner state is one sub-state.** `world/persona.py` holds traits, skills, fatigue,
  sleep, recent attempts and "what I was doing" in one immutable `Persona` carried in
  the overlay, validated against the roster, sparse in the canonical form.
* **Hysteresis comes from remembered doing.** Boundary choices (errand versus bed) resist
  flip-flopping because the person remembers what they decided last tick.
* **Viewer features are parts.** `world/viewer.js` exposes extension points and
  `world/viewer_<feature>.js` files are spliced in only for runs that record the
  feature; `world/viewer_rich.py` derives their events from recorded values.

## Prior art on other branches (not part of this work)

Unmerged lines of work exist in this repository and were looked at, not merged:

* `codex/wood-yard-stone-axe`: auto-generated commits from an older baseline adding a
  live server with pause/step/speed, checkpoint resume, a wood yard, stone and an axe
  held as a world possession rather than a ledger resource. Evaluate at P6 and P12.
* `codex/remembered-contribution`: remembering witnessed household food contributions.
* `claude/isometric-viewer`: a zip of 3D-diorama UI mockups. The existing 2D isometric
  viewer is being extended instead; the page must stay self-contained (no network).

## Phases

Status: `done` means built, tested, replay and recovery checked, and watched in
the viewer. `partial` says what is missing.

| Phase | Scope | Status |
| --- | --- | --- |
| P0 | Baseline, golden digests, ledger audit, replace-based overlay updates, this record | done |
| P1 | Traits, skills, fatigue and sleep | done for its scope (committed); sociability and curiosity are stored but act only once P4/P11 exist; skills farming/crafting count practice once P6/P7 exist |
| P2 | Day/night, temperature, rain, storms, exposure | not started |
| P3 | Belief model, wolves, danger knowledge, safety | not started |
| P4 | Relationships, conversations, quarrels, apologies | not started |
| P5 | Generalised requests, commitments, escrow, cooperation, hosting | not started |
| P6 | Stone, tools, crafting, hauling | not started |
| P7 | Farming, spoilage, distinct foods | not started |
| P8 | Building kinds, upkeep, fire, constructed wells | not started |
| P9 | Couples, pregnancy, ageing, orphans, grief, newcomers | not started |
| P10 | Graves, belongings, aftermath, detailed death records | not started |
| P11 | Exploration, forgetting, desire paths, pathfinding audit | not started |
| P12 | Viewer: minimap, fog, overlays, launcher, save/resume, live mode | not started |
| P13 | Rich-world preset, long multi-seed runs, performance, review, final report | not started |

## Verification log

Entries say who ran what and when. A number here is a result of that run only.

* Baseline `02af86b`, pristine `git archive` export, full suite, run fresh on this
  machine (Linux, 4 cores, Python 3.11.15, pytest 9.1.1, Playwright with the
  browser-path mapping below): **1172 passed in 452.91s (7m32s)**, none failed.
  The recorded 1149 in `docs/ai/05_CURRENT_STATE.md` predates two later commits.
* `tests/test_disabled_mode_baseline.py`: 16 passed on the refactored overlay code.
* `tests/test_ledger_audit.py`: 29 passed (4 real runs audit clean; 6 tampering
  mutations are each detected).
* P1: `tests/test_individuality.py` 41 passed (config and header round trips, strict
  persona validation, each trait changing a real decision, sleep/wake/collapse rules,
  fatigue and skill arithmetic against saved runs, replay, recovery from cuts that
  contain sleepers and newborns, ledger audit); `tests/test_rich_viewer.py` 4 passed
  (index events, spliced parts, a real browser selecting a sleeper).
* P1 fast selection after all changes: 1216 passed, 46 deselected in 97.6s. Golden
  guard 16/16. **Full suite at the P1 commit: 1262 passed in 605.22s (10m05s)**, run
  fresh on this machine (the baseline's 1172 plus 90 new tests).

## Environment notes

* The container's Chromium is build 1194; the locked Playwright (1.63) looks for
  build 1243. A scratch directory of symlinks plus `PLAYWRIGHT_BROWSERS_PATH`
  lets `tests/test_viewer_security.py` run without touching the repository.

## Next step

P2: a recorded sky
(day/night, temperature, rain, storms) that acts on cold, perception, travel and
sleep. The deterministic sky is derived from the seed and tick and written into
each tick's overlay so the viewer reads it rather than recomputing it.
