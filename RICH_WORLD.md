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
  as `commitment` ticks more urgent in the least-slack rule, counts a need whose relief can be
  taken this very tick for as much again, lets somebody who reaches a well or patch a tick early
  take what they came for, and holds the start-for-shelter rule back while somebody is out on an
  errand. It is separate from `sky` so each can be switched off and measured alone.

* **Bonds are one small list per person.** `world/society.py` (feature `bonds`, needs `beliefs`):
  each entry is (other, bond, trust, grudge, last, why, grieved, tone), all integers 0 to 100 or
  ticks. Only the person's own list is in their observation, so what A feels about B is never
  visible to B. Bonds change only in `advance_society`, from what the tick's decisions and
  outcomes recorded: a mutual conversation, a mutual greeting, a gift given, a quarrel, an apology.
* **Companionship is a need that does not kill.** `lonely` grows one point every few ticks (staggered
  by person so nobody is lonely on the same tick) and falls while talking. It sets what an idle person
  does (talk, visit) and is shown as a need bar; it has no lethal level and takes no part in the
  least-slack rule.
* **A conversation needs two.** A chat is only made when both people chose it towards each other and
  are within `talk_range`; a chat that was not returned is recorded as a failed attempt, so
  the person tries someone else after `retry_after` ticks. Seeing that somebody is busy (their
  recorded doing) is part of what a person can observe, so they do not keep asking busy people.
* **Greetings, confrontations and what is told are speech acts on a decision.** They cost no tick.
  A greeting needs the other to greet back. A confrontation is one-sided and can be answered with
  an apology if the other person is generous enough and not holding a grudge themselves.
* **Hearsay is gated by trust.** A told fact is only believed when the listener trusts the teller
  at least `believe_at`, and only when the listener also chatted back. Homes are told first,
  then fresh wolf news, at most `told_per_chat` items. A person visits a home they have only heard of.
* **Grievances come from losses the world records.** `beat_to_it`: a refused claim at a source where
  somebody in view had an accepted one. `kept_food`: a starving person saw a free neighbour holding
  two or more food that never offered. Each costs trust, then bond, and is remembered with its reason
  until it fades (`grudge_fade`). Helping prefers friends and leaves out those somebody resents,
  unless a dependent is hungry.

* **Tools are named resources made by recorded production.** `world/crafting.py`: making spends the recipe inputs
  through ordinary kernel `consume` proposals, and only when every input was accepted does the world add the tool
  by a `{"made", "item", "amount"}` production entry (`stream/run_file.apply_production` accepts it, and the ledger audit
  checks that the same actor spent every input that tick). A tool total therefore always equals the number of recorded
  makings. An axe saves two building ticks (never below four), a basket adds two to a food claim, a pick lets a stone
  claim take a whole recipe's worth instead of one.

* **Fields are plots plus a kernel source.** `world/farming.py`: each founder's field is an empty source of grain and a
  plot in `things`. A seed is spent by a kernel consume; growth, rot and spoilage are recorded production entries
  (`{"source","amount"}`, `{"rotted"}`, `{"spoiled"}`) that `apply_production` accepts and the audit accounts for: rot and spoilage move
  units into a named sink, so totals never change by accident. Grain is eaten before berries since it is what spoils.

* **Structures are one more block in `things`.** `world/structures.py`: a shelter's condition, a fire's fuel and a well's
  progress are saved entries; wood for repair, fuel and the well is spent by kernel consume proposals, and a finished well
  gives water by the same recorded production entries berries use. A well is not a landmark: observation lists it only while it
  is in sight. Collapse removes the shelter and starts its residents' building over.

* **Family life is its own block.** `world/family.py` holds partners (always mutual), pregnancies (carrier, due tick, other
  parent), grief, guardians and the traveller count, in the overlay. Nothing about the population is silent: births need a
  couple and fewer than `pop_cap` living plus pregnant, travellers come only below `arrive_below` living, after
  `arrive_every` ticks, `max_arrivals` times, and a lifespan is the seed's draw from `old_age_at` plus `old_age_spread`. All of
  these are settings written in the run header's rule text.

* **Death leaves a record, and the news travels like any other belief.** `world/aftermath.py`: when somebody dies a grave
  (`Struct("grave")`) and a `Death` record go into `things`. The cause is derived from the recorded levels and is for
  whoever reads the run; people only know what they saw (a grave in sight becomes a belief of kind `death`) or were
  told. `kin_dead` in the observation holds only the deaths the person believes in. Belongings stay in the dead person's
  account until somebody collects them: the collector's decision becomes kernel `transfer` proposals issued in the dead
  person's name, so the audit sees ordinary moves. Without the aftermath feature, family grief still reaches everybody who
  loved the dead person at the moment of death, as before; with it, grief needs learned news.

* **What people know of the ground is stored per person and checkable from where they stood.** `world/ground.py` keeps, for each
  person, the last tick any cell of each 3x3 patch was in sight; the rough cells a person remembers (the existing
  `terrain_memory`) are dropped once their patch has gone unseen for `terrain_span` ticks, and with exploration on that is the only writer.
  `world/paths.py` stores wear per cell in `things.paths`; a path that was rough ground costs no extra tick, but a person who
  remembers the cell as rough still plans round it until they see it again. The new observation fields (`ground`,
  `patches_seen_now`, `worn_in_view`, `wells_seen`) are all built from what is in sight or remembered. The test
  `test_a_saved_world_audits_replays_and_what_people_know_of_the_ground_follows_from_where_they_stood` re-derives every
  person's remembered rough cells, patch dates and the whole wear table from recorded positions and sky alone.

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
| P3 | Belief model, wolves, danger knowledge, safety | done for wolves (see log); homes are the second believed kind (P4); no other kind of thing is believed in yet; dens are not themselves beliefs |
| P4 | Relationships, conversations, quarrels, apologies | done for its scope (see log); quarrels need a cause the world already produces (a lost race for food, a meal withheld), so declined help and broken promises join them in P5; couples and attraction wait for P9 |
| P5 | Generalised requests, commitments, escrow, cooperation, hosting | built and tested but not reviewed or run through the full suite: water, food, wood (hand over or fetch), building help, news, hosting; no tools or repair requests yet (P6, P8); the viewer part was checked by eye, with no browser test for it |
| P6 | Stone, tools, crafting, hauling | built and tested (focused tests only): a quarry, axe/pick/basket/hoe made from wood and stone, effects of axe, basket and pick; the hoe waits for P7; hauling is the wood fetch from P5; no stone or tool requests yet |
| P7 | Farming, spoilage, distinct foods | built and tested (focused tests only): a field per founder, planting, tending, harvest, soil wear, rot, grain as a second food, spoilage; newborns have no field yet (P9); no grain requests or trading |
| P8 | Building kinds, upkeep, fire, constructed wells | built and tested (focused tests only): shelters wear, are mended (neighbours may help) or collapse; fires burn wood, warm, light and keep wolves off; wells are dug and give water by recorded production and are used once seen; **no hut, house or storehouse kinds**; a finished well is forgotten out of sight (no belief of it yet, P11) |
| P9 | Couples, pregnancy, ageing, orphans, grief, newcomers | built and tested (focused tests only): couples from talk and a shared bond, pregnancy with a fixed gestation, births only from pregnancies, elders, lifespans, old-age death, orphans taken in, grief, travellers when few are left, explicit population limits; **couples are rare in small worlds at the default bond level**, so the rich-world preset will set it lower; no marriage rites, no inheritance (P10) |
| P10 | Graves, belongings, aftermath, detailed death records | built and tested (focused tests only): a grave and a saved death record (tick, cell, age, cause, who was in sight, what they held, who collected it) for every death; deaths are believed only by those who saw the grave or were told; grief follows learned news; belongings are collected from the grave by kernel transfers in the dead person's name, heirs first and anybody in need after a grace period; mourning at the grave; **telling a death by conversation is rare in small worlds (3 chats in 700 ticks in the survey seed)**; no burial rites or wills |
| P11 | Exploration, forgetting, desire paths, pathfinding audit | built and tested (focused tests only): per-person memory of which map patches were in sight and when; remembered rough ground is forgotten when its patch goes unseen for `terrain_span` ticks; curious people with spare time go and look at stale patches near home; wells seen become beliefs and are used from out of sight; walked cells wear into paths that make rough ground free to cross and attract walkers; a route audit re-derives every person's memory from where they stood. **Exploring is rare**: 0 to 6 trips in 500 to 600 ticks in the seeds surveyed, because spare time is scarce; **no rough cell was worn through in a surveyed world**; **no well was built in the surveyed rich worlds** (so well beliefs are tested on constructed scenes only) |
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

* Steadiness, second round (found while watching a world with relationships: somebody stepped
  between a well and their door twelve ticks running): out-and-straight-back moves in seeds 7,
  14, 31, 42 and 57 went from 4, 18, 11, 11, 9 to 3, 4, 0, 8, 0. Switching the three additions
  off one at a time: the shelter-rule patience does most of it (24 in total with it alone), the
  take-it-on-the-spot rule and the early draw bring it to 15. Deaths over eight seeds with and
  without them ranged 33 to 42 of about 80 with wolves and 33 to 35 without, so no effect on
  survival was measurable either way.

* P4: `tests/test_society.py` 42 passed (storage and strict validation, each rule on its own,
  decisions that talk, visit, greet and confront, hearsay gated by trust and reciprocal chat, a
  whole saved world that audits, replays and recovers; provenance audits: every warm or greeting
  entry was mutual and within reach, every grudge that grew has a recorded cause, every home belief
  traces to a telling; a counterfactual that moves a person out of sight changes nothing they
  decide; a real browser opens the Relationships section at the tick a grudge begins). Seven mutations
  of the rules (a chat that needs only one side, greetings never throttled, everybody believed whatever
  the trust, resented people still helped, starvation nobody could see counting as a grievance, no
  cooldown on confronting, bonds left unbounded) were each caught by a test. Disabled-mode guard 16/16.
  Survey (8 seeds, 300 ticks, beliefs, sky, steady, sleep, personality, explain on): people who died /
  people in the run, bonds on 20 / 70, bonds off 35 / 85; births differ chaotically between the two
  runs so this is not a claim that company helps. Tick time 7 to 13 ms; a 300-tick file 2 to 3.6 MB.
  Watched in the viewer (seed 11, 300 ticks, screenshots taken with Playwright, no console errors):
  a conversation at the well with its speech bubble and teal thread and a "?" over a lonely person
  nearby (tick 58), and a night scene with quarrel threads between people and the Company bar at
  42 of 60 (tick 213). Gifts, apologies and walking to a home somebody had only heard of are pinned
  by tests on constructed scenes; I did not pick them out of an ordinary run by eye.
  Limits seen: in small spread-out worlds (6 people) friendships rarely form; quarrels come only from
  crowded patches or withheld meals until P5; loneliness saturates at its cap in an isolated world;
  a mutual quarrel can repeat on consecutive ticks because the cooldown is per confronter.
  **Full suite at the P4 commit: 1383 passed in 673.73s (11m14s)**, run fresh from an isolated copy
  of the working tree that was then committed unchanged.

* P5 (not committed with a full-suite run): `tests/test_pledges.py` 83 passed; with it, the disabled-mode guard
  (16/16), society, wolves, sky, individuality and rich-viewer tests passed in the same run (264 in all) until the guard
  caught my hosting change leaking into legacy asking runs; that was fixed and the guard and pledge tests reran green
  (98 passed). Three saved 450-tick worlds audit clean and replay identically; recovery from a cut with a promise
  held by the kernel gives the same run. Seven rule mutations: six were caught by a test; **one was not**: letting a
  helper make two promises at once still passes, because the test's second request comes from somebody too far away
  to be answered anyway. The test needs a nearer second asker. **The full suite has not been run on P5.**
  Seen in worlds: requests for water, food, wood and building help answered, reserved, kept, declined and broken; most
  declines in stormy worlds are `unfit`, so askers ask several people in turn.

* P6 to P9 (each committed with its focused tests; the full suite was deferred to the end by request): `tests/test_crafting.py`
  11, `tests/test_farming.py` 17, `tests/test_structures.py` 13, `tests/test_family.py` 22 passed, each with the disabled-mode
  guard (16/16), and the whole-world tests audit clean and replay identically in saved 700-tick worlds. Honest limits: shelters
  collapse often and cold deaths are common in worlds with structures and family on (no calibration done yet); no hut, house or
  storehouse kinds; couples form rarely at the default bond level (lowered to 18); newborns have no fields; no tool or stone
  requests. The viewer sections for these parts were checked by screenshots only.

* P10: `tests/test_aftermath.py` 21 passed (storage and strict validation, the record and grave made on death, each cause,
  seeing and being told, grief only from learned news, collecting by transfers in the dead person's name, strangers waiting
  out the grace period, two collectors at one grave, mourning relief, a whole saved world: audit, replay, every taker has a
  recorded transfer, every belief of a death was seen at the grave or told, every grief follows news, the viewer index events).
  Seven mutations (collectors taken from the dying tick, kin deaths exposed before they are known, no grace period,
  grief from old news, no belief from seeing a grave, no mourning relief, starvation never named) were each caught.
  Two bugs came out of writing them: a unit given away on the tick somebody died would have been recorded as a collection,
  and the observation listed kin deaths the person had not heard of. Both fixed. Neighbouring focused suites and the
  disabled-mode guard pass (280 passed in 190s before the last small changes; family, aftermath and the guard rerun: 59
  passed). **The full suite has not been run on P6 to P10.**

* P11: `tests/test_exploration.py` 25 passed (storage and strict validation, patch geometry, rough ground known only from
  sight and memory with a counterfactual out-of-sight cell, forgetting after exactly `terrain_span` ticks, curiosity and each
  reason not to explore, wear arithmetic, rough ground worn through costing no tick, the worn tie-break, a worn cell still
  looking rough to somebody who remembers it, wells believed and used from afar, a whole saved world re-derived from
  positions). Ten mutations (no forgetting, worn cells still costing a tick, no tie-break, worn cells still rough in the plan,
  an omniscient rough map, a wider patch window, an uncapped wear, exploring at night, dry wells in sight still chosen, no well
  beliefs) were each caught; two survived the first version of the tests (the wear cap and the dry-well rule) because the scenes
  did not reach them, and the scenes were changed so they do. Neighbouring suites and the disabled-mode guard pass (272 passed
  in 209s). Survey (5 seeds, 600 ticks, everything on): explore trips 0, 0, 1, 2, 0; saved runs about a third larger than
  without the two features. **The full suite has not been run on P6 to P11.**

## Environment notes

* The container's Chromium is build 1194; the locked Playwright (1.63) looks for
  build 1243. A scratch directory of symlinks plus `PLAYWRIGHT_BROWSERS_PATH`
  lets `tests/test_viewer_security.py` run without touching the repository.

## Next step

P12 (the viewer) and P13 (the rich-world
preset, multi-seed surveys, performance, old-save compatibility, the full suite, a critical review and the final report). Still
owed from earlier phases: the two-promises test, browser checks for the new inspector sections, and a cold-death survey.
