# Simulation 3: whole-project adversarial review

Update 2026-09-29: the [signed REVIEW.md](REVIEW.md) and
[reviewer evidence](evidence/probes/README.md) have been supplied. The
verdict is FAIL. The [separate repair response](../2026-09-29-repair/RESPONSE.md)
does not replace that verdict. Instructions below describe the original
packet preparation; its unsigned-template statements are historical.

Review the whole project, not just the last change. Try to disprove its important claims with concrete counterexamples, and report what survives those checks. The intended product is a watchable, deterministic civilisation aquarium whose people make rule-based decisions from local observations and retained knowledge.

## Exact subject

- Repository: https://github.com/lochheadr92-creator/Simulation-3
- Branch at publication: `codex/kernel-first-slice`
- Source commit: `81c10b7d25cc2e0f1b8de33bf547083eb0972c64`
- Source tree: `f17ceeec11372b4ff4ec1a6db82d80423d8a7466`
- Published and checked against the remote branch on 2026-09-28.
- Previous commit: `22ffe2748dc4c5ee14c71295ff33810c7f456a7c`. The supplied patch from that commit is context only; it is not the review boundary.
- Prepared by Codex at the user's request. Independent review has **not** been performed by preparing this packet.

The later documentation commit containing this packet is not the source target. Pin the full source SHA above even if the remote branch advances. `SOURCE_MANIFEST.json` lists every tracked source file at that commit, its Git object identity and its SHA-256. `INVENTORY.md` summarizes the contents.

## Start here

1. Read source `AGENTS.md`, `docs/ai/00_AGENT_CONSTITUTION.md`, current `WORLD_DIRECTIONS.md`, then the architecture, invariants, system map and testing notes needed for the review. Follow live source when a summary is stale. `VIEWER_DIRECTION.md` includes future design aspirations, not an implemented 3D viewer.
2. Use a separate checkout pinned to the source SHA, or the portable packet's `source/` directory. Check for existing changes before running anything. Do not review the branch name alone.
3. Read `VALIDATION.md`: it separates prior builder results from checks still required of you and gives supported command forms.
4. Work through the coverage table in `REVIEW.md`. Add concrete findings, commands, actual results, artifacts and limitations. Use your own probes where existing tests leave gaps. Test success is not a substitute for reading the implementation.
5. Save your completed `REVIEW.md` and evidence, then fill in and sign its attribution block. Do not sign on behalf of another agent or claim an independent role if you helped build the reviewed code.

In a Git checkout this packet is under `docs/reviews/2026-09-28-whole-project/`. In the portable ZIP it is under `review/`, beside a complete `source/` snapshot and selected `builder-examples/`. The source snapshot does not include this later packet. Keep your completed report outside the source checkout or in your own copy of the packet. If a report already has a signature, create a separately named report instead of overwriting it.

## Scope and working limits

Every tracked file is in scope for relevance assessment. Give all active subsystems substantive coverage. Review archived tools and evidence according to their current consumers and risks; do not reactivate or run retired orchestration merely because it is included. Historical records are not current instructions. Existing fixtures may still be live test inputs.

This is an executing review: inspect code, run relevant tests, create isolated diagnostic probes and saved worlds, and inspect a viewer in a browser where available. Write your report and artifacts in your own review area. Preserve the pinned source, existing fixtures and other people's work. Do not repair implementation, rewrite expected outputs, install global tooling, change repository configuration, merge, publish or push as part of this review. Propose repairs in the report. If your environment prevents a check, record exactly what is blocked and leave that coverage incomplete.

Report defects separately from modelling preferences. Earlier departures, interruptions, refused transfers and deaths may be intended consequences. A rule can be implemented correctly yet produce poor viewing experiences; explain that distinction. Prioritize reproducible correctness, integrity, knowledge-boundary and persistence failures over stylistic suggestions.

## Whole-project attack plan

| Area | Questions and counterexamples to pursue |
| --- | --- |
| Kernel transactions and immutable state | Trace validation, authority, proposal identity, atomic settlement and outcomes. Attack negative/invalid units, duplicate proposals, contention, reservation cancellation/completion and incoming-credit timing. Check conservation per resource, detached observations, re-entry protection and order independence. |
| World ownership and accounting | Trace an ordinary tick from input through observation, choice, proposal, settlement, processing and output. Distinguish kernel transfers/consumption from explicitly recorded production and structural changes. Check births, deaths, zero-stock caches, source renewal and interrupted actions for double credit, lost stock or hidden gains. |
| Perception and decision rules | Look for access to unseen current quantities, deaths or progress; known landmark positions are allowed. Check need priority, starvation/liveness loops, ties, route costs, rough terrain, held movement, child limits and unreachable targets. Compare chosen actions with executed outcomes. |
| Social and household behaviour | Exercise requests, offers, actual gifts, memory, caregiver changes, provisioning, promises, cache contention, adult homes, relocation and construction together. Check expiry, refusal, interruption, death and birth boundaries. Confirm remembered events can change later choices through real execution. |
| Ecology and resource extensions | Check food, water, warmth, wood, fishing, regrowth and seasonal transitions. Probe multi-tick casts/building, depletion, capacity, conservation and conflicts between personal and household uses. |
| Configuration and disabled modes | Follow CLI arguments, validation, defaults, serialization and exact rule descriptions. Identify forbidden combinations and untested interactions. Check legacy/missing fields, invalid values, booleans where integers are required, optional features off and deterministic configuration identity. |
| Saved streams, replay and recovery | Attack truncated/malformed/invalid-UTF-8 suffixes, duplicate or later headers, seals, tick order, broken prefix and incompatible code/rules. Distinguish readability, integrity checking, semantic reconstruction, replay and recoverable continuation. Verify restored overlays, active trips/casts/memories and later births do not diverge. |
| Viewer and observability | Trace displayed reasons, events, quantities and family links to saved native data. Check playback, selection, scrubbing, inspectors, earlier file shapes and absent fields in the browser. Probe HTML/JSON escaping and unsafe content, self-contained loading, browser errors, accessibility and large-run responsiveness. Include the older `viewer/` path and its stated compatibility limits. |
| Tests and evidence quality | Inspect assertions and fixtures, not only pass counts. Look for circular expectations, implementation-mirroring tests, untested branches, convenient seeded scenes, silent skips and imports from historical evidence. Use independent counterexamples. Check baseline changes against the intended contract. |
| Local operation, dependencies and tools | Verify a clean source copy can be tested, run and viewed with declared prerequisites. Inspect Python/Node requirements, lockfile, helper scripts, paths and reproducibility assumptions. Audit active entry points and relevant legacy tools; do not execute unknown orchestration blindly. |
| Architecture, maintenance and documentation | Check dependency direction and semantic ownership, size/concentration of central modules, persisted schema growth and duplication. Identify misleading claims, stale snapshots and future plans described as current. Judge maintainability with concrete consequences, not speculative redesign. |
| Scale and product behaviour | State machine, configuration, population, ticks and measurement method for any cost claim. Historical benchmarks do not measure today's full feature combination. Watch ordinary worlds and trace at least one complete need/observation/choice/action/consequence/later-choice chain; describe what is understandable or obscured. |

## Recent changes deserving extra challenge

These are review leads, not the limit of the assignment or pre-decided findings.

- Terrain-aware personal food departure is now the default under the existing planned-trips/terrain/routing combination. Check what the estimate knows, including remembered rough ground and current delay, and what it cannot predict. Challenge excessive early departures, interactions with other needs and source ranking.
- Knowledge sharing is optional and requires source memory. Reports must come from a firsthand empty-food sighting, reach only adjacent visible housemates, influence choices from the next tick, retain the original sighting date, expire after twenty ticks and never relay. Challenge current/newer personal evidence, repeat speech, deterministic report conflicts, unseen refill/death and attribution of actual report influence.
- Check the two new sparse overlay fields through serialization, replay, recovery, births and deaths, including disabled mode. Check that food and household provisioning use the same permitted evidence without inventing delivery success.
- Two previously failing fixed social scenes (seeds 14 and 26) were intentionally replaced after the user chose the new departure behaviour. Their full original horizons still receive replay checks. The replacement causal fixture uses actual transfers and holds neighbours in place for an encounter. Determine whether it proves gift -> memory -> changed choice -> return gift, and expose any lost ordinary-world coverage or artificial assumptions. Do not assume a contract change makes every replacement test adequate.
- Old headers using the previous departure rule with planned trips, terrain and routing enabled cannot replay under the changed rule. Inspect the exact compatibility policy and its user impact. Readability alone is not successful continuation.

## Findings and completion

For each finding provide severity, exact source path and verified line(s), trigger/preconditions, reproduction, expected versus actual result, evidence and impact. Label inference or suspicion when it is not reproduced. Identify whether the issue predates the recent patch if established; otherwise say unknown. Do not invent findings to sound adversarial, or suppress a valid issue because many tests pass.

Use `FAIL` for substantiated blockers, `INCOMPLETE` when essential coverage is missing, or `PASS` only with the checked scope and limits stated. A blocker can establish FAIL before every check is finished; still disclose unreviewed areas. A full-project PASS requires substantive inspection of all active areas, relevant execution and an honest coverage table. Optional improvement notes can remain without being acceptance blockers. A review of only the latest diff cannot receive a whole-project PASS.

Your signature is a typed attribution of the work you actually performed, not a cryptographic signature, a guarantee of absence of bugs, or the user's acceptance.
