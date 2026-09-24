# Simulation 3 Slice 1c review bundle

Start with **REVIEW.md**. The verdict is **FAIL**, bounded to Slice 1c at
`d14decec50d285395febb97c06d8eb7d94930b88`. No repository fixes were made.

- `probes/`: reviewer-authored checks, including a small F1/F2 reproducer.
- `outputs/`: raw stdout/stderr, exact subprocess commands, XML test results,
  independent calculations, source inspection record and preservation checks.
- `outputs/artifacts/`: cut, corrupted, forged, regenerated and recovered run
  files. Some are intentionally invalid and are clearly named by their probe.
- `SHA256SUMS.txt`: hashes of bundle files, excluding itself.

To reproduce F1/F2 from any unchanged checkout of the pinned target on Windows:

```powershell
$env:SIM3_REVIEW_REPO = 'C:\path\to\03-Living-World-V3'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
py -3 -B .\probes\reproduce_findings.py
```

Run that command from this bundle folder. It creates a fresh temporary directory
under `outputs/artifacts/`; it never changes the source checkout. The other
probe scripts retain the original review workspace layout in `common.py` and
their recorded command paths. Their original executions are fully captured.
The P8 script deliberately injects faults: use it only with fresh working and
pristine extractions arranged as documented in REVIEW.md, never in a live
development checkout. Its saved patches and commands are sufficient to rerun
individual mutations in a disposable copy.

The original input archive is not duplicated in this output bundle. Its verified
SHA-256 and resolved attachment location are in `outputs/identity.json`; the
pristine extraction remains in the review workspace. No separate OS was tested.
