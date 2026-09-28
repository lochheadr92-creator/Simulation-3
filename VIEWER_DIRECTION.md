# Viewer direction: Field atlas

## 1. The direction

The world is a floating piece of terrain, cut away at the edges, shown in 3D
in golden-hour light. Visible side faces give the slab weight. Vertex-coloured
ground makes rough cells and shelter spots readable as different ground types.
It should feel like a small place worth watching, with enough detail to follow
someone's journey without losing sight of the whole world.

People, food sources, wells, homes and shelters are 3D objects. Berries show
food stock; the water level in a well shows its stock. Keep fishing spots,
home caches and wood groves distinct when the run contains them. Each person
keeps their own colour from `COLOR` in `world/viewer.js`.

A full inspector sits on the right. Selecting a person shows:

- **Needs:** hunger, thirst and cold histories as sparklines, with the run's
  hungry/thirsty/cold, emergency and death thresholds marked for each need.
  Show only needs and thresholds the run records.
- **Current decision:** recorded eligible candidates and scores, the chosen
  action, its target and reason, and the observations behind that choice.
  Missing scores stay missing; the viewer does not work them out.
- **Settlement:** the kernel outcome and its recorded reason, including
  accepted outcomes. Say when no kernel transaction was recorded.
- **Recent events:** what happened to this person, with jumps to those views.

Click a person in the scene to select them. A small chip names the selected
person. Keep hover and follow useful while the world plays.

The time-of-day control switches between two lighting presets: golden hour
and dusk. Occupied homes show chimney smoke using the existing lit-window
condition described below. Light and smoke make the place feel inhabited.

Chrome, type and colour follow the Nocturne look: a dark blue-grey background,
the single `#9184d9` interface accent used for lines and glow, compact spacing,
8px radii, and outlined rather than filled primary buttons. People's colours
and meaningful scene colours remain distinct. Copy only tokens and component
styles into `world/viewer.css`; do not bring in the Nocturne React bundle.
Use the existing system font stack, with no web fonts or external assets.

## 2. Rules the direction must respect

The page stays self-contained. `test_the_page_is_self_contained` rejects
`<link`, `<script src`, `@import`, `url(`, `fetch(`, `XMLHttpRequest`,
`WebSocket`, `import(`, `localStorage` and `sessionStorage`. It also rejects
`src` or `href` values starting with `//`, `http://` or `https://`.
These are checks on the generated page's text, including inlined library code.

Keep exactly one executable inline `<script>`, which must pass Node's syntax
check in `test_the_page_script_parses_under_node`. The two JSON data blocks
remain separate. Do not load three.js as an ES module in the page. Either
inline a suitable classic build into the executable script or write a small
WebGL renderer. A classic build still has to satisfy the literal bans above;
inlining alone does not establish that it fits.

No new exporter or schema is needed. Keep reading `run-data` (header, ticks
and the existing presentation metadata) and `view-index`, built by
`world/viewer_index.py`. View 0 is genesis; view k shows the world after tick
k-1 with that tick's decisions and outcomes.

Every world number shown is recorded or counted from recorded values.
Movement animation eases the picture between recorded views; it never chooses
an action or changes the world. `test_the_page_runs_no_world_rules` stays intact.
Keep each meaningful visual tied to what the file records:

- Needs history reads `hunger`, `thirst` and `cold` from the saved worlds;
  thresholds come from the saved scenario.
- Decision rationale reads `decisions` (`candidates`, `scores`, `kind`,
  `target`, `reason`) and `observations` (people seen and observed stocks).
- Settlement reads `record.outcomes`, including its reasons.
- Recent events read `view-index` events through `EV_OF`.
- Positions, homes and shelters come from recorded world state; rough cells
  and shelter spots come from the scenario. Stock uses the existing readers
  for saved stock plus recorded production, including newly created caches.
- Smoke uses the current lit-window rule: a living person occupies the shelter
  cell and its identified owner is not dead. Smoke motion is decoration only.
- Golden hour and dusk are display presets. Where `world.season` is recorded,
  use it to choose the default preset and show the actual season separately.
  Otherwise label the control **Display only**. A manual choice is also display
  only; neither preset claims that the run records a day/night cycle.

Reuse `ELEV` for the terrain's shape. It is deterministic display relief,
computed from the seed, cell types and layer settings, not recorded altitude.
It must not imply new travel costs or feed back into the world.

Selection, hover and follow keep using `selected`, `hovered` and `follow`.
Layers keep using `LAYERS`. Honour `REDUCED` for movement, camera motion and
ambient effects. Preserve the `--text` view, old-run fallbacks and
`test_older_world_shapes_still_open`. All of `tests/test_map_viewer.py` must
keep passing. Keep existing recorded information available in the new layout.

## 3. How to get there, in order

Each step is one pull request.

1. **Rendering spike.** Inline the renderer and build the terrain from `ELEV`,
   with pan, zoom and fit. Confirm the self-contained and Node-parse tests pass.
2. **Entities from the run.** Show sources with stock, homes, shelters and
   people, easing positions between views k and k+1. Add the existing layers.
3. **Picking.** Raycast against people meshes, write the result into the
   existing selection state, and add the selection chip.
4. **Inspector.** Restyle the right panel with Nocturne tokens: need
   sparklines and thresholds, decisions and scores, settlement, recent events.
5. **Polish.** Add the lighting presets, carry occupied-home smoke into 3D,
   and refine materials so the world remains easy to read.

## 4. How to check it

Follow `AGENTS.md`: watch it, don't just prove it. After each step, render
`runs/aquarium.jsonl`, `runs/asking.jsonl` and a seasonal run such as
`runs/seasons/seed11-seasons1.jsonl` with
`py -3 -B -m world.viewer <run>.jsonl`.

Screenshot each generated page with
`node tools/shoot.js <page.html> <out-dir> [view ...]` and open the images.
The tool calls `show(k)` and captures `#map`, then the whole viewport; keep
those entry points working. Also open the pages and watch playback, selection,
follow and the inspector. Screenshots alone cannot show how motion reads.

A step is done when the world visibly reads better than before and the
existing tests pass. Don't build new verification infrastructure.

## 5. Open decision

This direction assumes a small hand-written WebGL renderer. It keeps each
saved page smaller and can avoid unused loading code caught by the existing
self-contained checks, but geometry, lighting and picking take more work.
Inlining three.js would add roughly 600 KB per saved page, depending on the
build. Ryan still needs to confirm which trade-off he wants.

**Differences found while reading:**

- Today's scene is Canvas 2D with isometric drawing, not a 3D renderer.
  Smoke and selection labels already exist; `ELEV` is generated display relief.
- The current needs chart combines the recorded needs and marks only the first
  available emergency threshold. Separate sparklines with all thresholds are new.
- Smoke already uses `occupied && !ownerDead`, not occupancy alone.
- There are three script elements: two JSON blocks and one executable script.
  The test bans external `src`/`href` links, not every occurrence of `//`.
  Its additional literal bans are listed above. `run-data` also includes
  timings, end data, problems, checkpoints and prepared details.
- r149 was not the last classic three.js build. The builds remained through
  r160 and were removed in r161; see the
  [three.js migration guide](https://github.com/mrdoob/three.js/wiki/Migration-Guide#r160--r161).
- Recorded seasons are plentiful/lean food seasons. There is no recorded
  time of day or existing golden-hour/dusk control. Nocturne styling is new:
  the current CSS uses teal backgrounds, several accents and 12px base radii.
