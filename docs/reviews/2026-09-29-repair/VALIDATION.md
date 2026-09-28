# Repair validation

Builder: Codex. Executed on 2026-09-28 UTC / 2026-09-29 Australia/Brisbane. These checks support the repair; they do not replace Claude's independent signed FAIL or supply independent acceptance.

## Environment and results

Windows; Python 3.12.14; pytest 9.1.1; Node v24.19.0; locked Playwright package; installed Microsoft Edge in headless mode. Browser prerequisites were present, so no browser security check was skipped. Python source identity is stored in the F1 and ordinary-example evidence. The packaged source commit/tree are pinned in the portable packet's `REVIEW_TARGET.json`.

| Check | Fresh result | Evidence |
| --- | --- | --- |
| F2 real-DOM regression before fix | Expected FAIL: one injected image, script marker 7, literal actor ID absent | [xss-before.log](evidence/xss-before.log) |
| F2 and F11 after fix | 2 passed | [xss-after.log](evidence/xss-after.log) |
| F4 reproduction before fix | 5 failed (four malformed seed types and an inactive malformed integer accepted) | [config-before.log](evidence/config-before.log) |
| Complete configuration type checks | 171 passed | [config-after.log](evidence/config-after.log) |
| Focused viewer/config/social/review regression group | 216 passed in 39.83 seconds | [focused.log](evidence/focused.log) |
| Full suite with required browser available | **901 passed in 223.57 seconds; no skips or errors** | [full-suite.log](evidence/full-suite.log) |
| Claude's supplied forged file, rendered with repaired viewer | File still verifies; literal actor ID visible; zero injected elements; no script execution; no page errors | [reviewer-forgery-check.json](evidence/reviewer-forgery-check.json) |
| F1 isolated departure comparison | Fixed seeds 1-35 at 400 and 780, plus 14 at 650; 71 matched pairs. A final-source repeat matched all counts, first divergences and final ledger/world digests | [f1-results.json](evidence/f1-results.json), [sweep output](evidence/f1-sweep.log) |
| Ordinary default seed 29, 780 ticks | File verifies/replays; original and return transfers accepted; recovery from after decision tick 708 matches uninterrupted ticks and replays | [example-summary.json](evidence/example-summary.json) |
| Browser example at world tick 714 | Native return-gift reason, event and decision-tick label checked; no page errors; screenshot inspected by builder | [browser check](evidence/example-browser.json), [scene](evidence/return-gift.png) |

The checked social example was selected from the declared sweep because it contains an accepted return gift; no additional seed search or parameter tuning was performed. Counts refer to decision ticks, not unique interactions. The artificial encounter unit/integration test remains labelled as such. The first 400-tick sweep did not by itself establish absence beyond 400 ticks; the wider result is reported without discarding the zero result.

## Reproduction from the pinned source root

Use a fresh checkout/extracted source and unused output/temp directories. Supply Python with pytest. Install locked Node dependencies with `npm ci`; Linux/macOS normally need `npx playwright install chromium`, while Windows defaults to installed Edge. Set `V3_BROWSER_CHANNEL` only if selecting another installed supported channel. Missing Node or browser prerequisites fail the security test explicitly.

```powershell
python -B -m pytest -q -rs tests/test_viewer_security.py tests/test_claude_review_findings.py tests/test_config_types.py tests/test_social_memory.py tests/test_map_viewer.py -p no:cacheprovider
python -B -m pytest -q -rs -p no:cacheprovider
python -B docs/reviews/2026-09-29-repair/probes/f1_departures.py --out runs/reassessment-f1.json
python -B docs/reviews/2026-09-29-repair/probes/save_social_example.py runs/reassessment-example
python -B docs/reviews/2026-09-29-repair/probes/check_reviewer_forgery.py runs/reassessment-forgery node
```

Create `runs/` first if it does not exist before the F1 output command. The F1 diagnostic runs the live step path and switches only the departure estimate in worker memory. It writes diagnostic JSON, not ordinary saved worlds labelled with false rule descriptions. The example script writes real current-mode worlds and checks original gift, return transfer, replay and recovery. `check_reviewer_forgery.py` accepts an absolute Node executable path instead of `node` if necessary; it reads the supplied forged file without altering it.

To reproduce the ordinary browser screenshot, run the included `ordinary_browser.cjs` from the source root with three arguments: the example HTML's file URL, screenshot output path and browser-result JSON output path. It resolves Playwright from the checkout. For example:

```powershell
node docs/reviews/2026-09-29-repair/probes/ordinary_browser.cjs "file:///ABSOLUTE/PATH/seed29-current.html" "runs/return-gift.png" "runs/example-browser.json"
```

The actual Windows suite invocation used the bundled Python/Node executables, set `PYTHONPATH` to the existing isolated pytest dependency directory, and used `--basetemp` in this task's workspace. No global package or Git configuration was changed. Generated ordinary runs/HTML remain outside Git and are included as supplementary examples in the packet.

## Evidence boundaries

- The original reviewer supplied 35 evidence files (239,494 bytes) plus the signed report. The evidence README explicitly says large generated HTML/JSONL outputs are omitted. Scripts, the forged JSONL and recorded outputs are available; not every named large artifact is present. [ORIGINAL_EVIDENCE.json](ORIGINAL_EVIDENCE.json) hashes all supplied files and the report. No original content or verdict was rewritten.
- The supplied full-suite log records the reviewer's 729-pass run. The fresh 901-pass result above includes 172 new regression cases; it does not mean 172 new simulation features or independent approval.
- Claude's supplied forged input was exercised against the repair. Other original probes were inspected as relevant, not all rerun. Fresh local probes and suite evidence are distinguished from inherited results.
- The screenshot is a builder inspection of a headless browser capture, not human visual acceptance.
- The F1 comparison is bounded to the declared seeds/horizons. No general frequency, statistical significance or survival claim is made.
- The new integer checks reject malformed API inputs; existing valid defaults and rule descriptions remain. Python source changes update code identity. Prior compatible files remain readable/replayable with the existing identity-reporting distinction; recovery continues to require matching source identity.
- The originally reported F2 path is fixed; a universal audit of every hostile schema/type is not claimed. The reviewer should reassess the exact repair target before changing the signed verdict.

The full whitespace check flags existing spaces in the supplied `stream_attack2.py` and captured pytest failure output. Those evidence bytes are intentionally preserved. The scoped check of authored source, tests and documentation is clean; evidence is excluded only from whitespace cleanup, not from review or hash verification.
