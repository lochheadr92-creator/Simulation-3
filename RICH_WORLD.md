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
* **The sky is a pure function of seed and tick, and is also recorded.** `world/sky.py`
  derives phase, weather (fronts chained through a fixed table) and temperature; every
  tick's overlay carries the sky, so the viewer reads it and replay checks it. Weather
  draws come from `world/draw.py` (sha256 of seed, label and numbers), never from a
  shared generator, so adding a weather draw cannot move anything else.
* **Planning uses the rate people actually suffer.** `Observation.chill` is the extra
  cold of being out in the current sky; `cold_slack` and `shelter_trip_due` use
  `cold_rate + chill`, and away from home the walk back is taken off the time left. With
  the sky off `chill` is 0 and every number is what it was.
* **Putting an errand off is a recorded reason.** `weather_hold` keeps somebody at home
  when the round trip would push their cold past the emergency level and the need can
  still wait. The held errand is left out of the candidates and shows as a `weather`
  entry in the decision's set-aside list. Later holds (danger, injury) follow the same shape.
* **One belief model, general by kind.** `world/belief.py`: a belief is (kind, subject, x, y,
  seen, learned, via). Sight files first-hand beliefs; being told files hearsay that keeps the
  original `seen`, so a rumour never gets younger. The same thing is one belief (later sighting
  wins, first-hand wins a tie); beliefs older than `memory_span` are forgotten and only the
  freshest `memory_slots` are kept. Confidence is derived, never stored. Only wolves are a belief
  kind so far; each later phase that adds a thing people must find out about adds a kind. The
  older special-case memories (empty sources, sightings, reports, rough ground) are untouched.
* **Things in the world are one block.** `world/things.py` carries what is neither a person, food
  nor a building (wolves so far) in the overlay and writes it into every tick.
* **Wolves hunt in the dark and rest by day.** They need the sky: they bite only at dusk and
  night, only people in the open, and walk back to a den (an edge cell nobody lives on) to rest
  by day or after a bite. People see a wolf only inside their sight, which shrinks at night.
  By day a wolf seen is lying by its den and nobody runs; at night every wolf seen looks
  dangerous. Everybody knows wolves hunt after dusk, so by day no place counts as dangerous.
* **Danger is a path cost, not a wall.** A believed wolf makes the cells near it cost
  `danger_cost` more to cross. The whole map is searched so a step taken now is the first step of
  the same cheapest way next tick; an earlier version searched a window and sent people round the
  map's edge. Ground nobody has seen still counts as open.
* **Risk is recorded.** A need at its emergency level, or with no more than the ticks to reach and
  finish the errand plus a margin left, sends a person to a place they believe is dangerous, and
  the decision's reason says so ("taking the risk: ...").
* **Steadiness is its own feature.** `steady` makes what a person served last tick count
  as `commitment` ticks more urgent in the least-slack rule. It is separate from `sky`
  so each can be switched off and measured alone.

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
| P2 | Day/night, temperature, rain, storms, exposure, planning in the weather, steadiness | done (see log); farming and fire do not use the sky yet; lighting by fire waits for P8 |
| P3 | Belief model, wolves, danger knowledge, safety | done for wolves (see log); no other kind of thing is believed in yet; stored beliefs are not yet exchanged in conversation (P4); dens are not themselves beliefs |
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

* P2: `tests/test_sky.py` 24 passed (the recorded sky equals the rule at every tick,
  exposure and cold arithmetic, sight, storms, planning with the sky's rate, errand holds and
  their recorded reasons, steadiness, replay, recovery from a cut at a rainy tick, ledger audit,
  the page and its index). Disabled-mode guard 16/16 after the sky and steady code was added.
  **Full suite at the P2 commit: 1286 passed in 631.12s (10m31s)**, run fresh on this machine
  from an isolated copy of the working tree.
* P2 survey (8 seeds: 7, 11, 14, 23, 31, 42, 57, 64; 300 ticks; explain, personality, skills and
  sleep on). People who died / people in the run: no sky 34 / 93 (0 of cold); first sky 51 / 87
  (27 of cold); planning with the sky's cold rate 38 / 75 (12 of cold); adding steadiness and the
  walk-back rule 34 / 82 (2 of cold). Out-and-straight-back door moves (go_shelter, go, go_water,
  warm in an A, B, A pattern) in seeds 7, 42, 57: 63, 52, 125 without steadiness, 4, 11, 9 with it.
  Holding errands back for the weather made no measurable difference to survival in these runs
  (12 cold deaths with and without, before steadiness). These are what those runs did, not a
  claim about every seed. Tick time stayed about 7-8 ms and a 300-tick file about 2 MB.

* P3: `tests/test_wolves.py` 52 passed (belief merging, forgetting, hearsay keeping its date,
  strict validation, overlay round trip; every wolf rule; what is observed and decided depends
  only on sight and belief, with a counterfactual that moves a wolf out of sight; flight, holds,
  risk, speech, routes that go round danger and never dither; bites, healing, limping, death;
  whole saved world: audit, replay, recovery from a cut, every first-hand belief matches a recorded
  sighting, every hearsay belief matches a recorded telling, every flight followed a wolf seen;
  a real browser selects somebody who was warned). Five mutations of the rules (hunting hours,
  posture, danger price, first-hand tie-break, hearsay dating) were each caught by a test.
  Disabled-mode guard 16/16. Survey (8 seeds, 300 ticks, personality, skills, sleep, sky, steady,
  explain, beliefs on): people who died / people in the run, no wolves 34 / 82; one wolf 33 / 77
  (18 bites, 202 ticks spent running, 5 of cold); two wolves 38 / 71 (37 bites). Same eight seeds with
  one wolf, switching the holds off: without the danger and hurt holds 37 / 76 died, without any
  hold (weather too) 48 / 77, with all of them 33 / 77, so the holds help. At 700 ticks in
  four seeds: no wolves 14 / 29, one wolf 15 / 27, two wolves 15 / 24. Nobody was killed by a wolf
  in these runs: wolves cost people time, and the deaths come from need they could not meet.
  Tick time about 7.4 ms; a 300-tick file about 1.6 MB. **Full suite at the P3 commit: 1338
  passed in 658.68s (10m59s)**, run fresh from an isolated copy of the working tree.

## Environment notes

* The container's Chromium is build 1194; the locked Playwright (1.63) looks for
  build 1243. A scratch directory of symlinks plus `PLAYWRIGHT_BROWSERS_PATH`
  lets `tests/test_viewer_security.py` run without touching the repository.

## Next step

P4: relationships and conversation. Greetings, visits, conversations that pass on what people
believe (with its age and teller kept), gifts, quarrels, apologies and avoidance, all grounded
in what two people actually know of each other, and a companionship need.
