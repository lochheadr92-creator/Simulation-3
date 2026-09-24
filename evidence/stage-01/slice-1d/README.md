# Slice 1d: 50-actor kernel cost check, 2026-09-25

Workload `v3.bench.kernel.1` (`stream/bench.py`): 50 actors, seed 1, at most one
proposal per actor per tick (45.5 on average) from a fixed mix of claims,
transfers, consumes, reserves and closes. Each run streams complete sealed
evidence. Tick time is settlement plus that tick's evidence write; proposal
generation is excluded and the final flush is listed separately.

Machine: TheWeapon, Windows 11 (10.0.26200), Intel Core Ultra 9 285K
(24 cores), CPython 3.12.10. Memory is the process working set.

| Run | Mean tick | p95 tick | Settle only | Evidence/tick | 10k-tick size | Peak memory | Growth 1k to end |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1,000 a | 3.03 ms | 3.96 ms | 0.67 ms | 22.6 KiB | 0.216 GiB | 22.3 MiB | n/a |
| 1,000 b | 2.96 ms | 3.65 ms | 0.65 ms | 22.6 KiB | 0.216 GiB | 21.9 MiB | n/a |
| 10,000 a | 3.68 ms | 4.49 ms | 0.81 ms | 23.0 KiB | 0.219 GiB | 23.8 MiB | 1.2 MiB |
| 10,000 b | 2.97 ms | 3.40 ms | 0.64 ms | 23.0 KiB | 0.219 GiB | 23.5 MiB | 1.2 MiB |
| Target | 50 ms | 100 ms | | 64 KiB | 1 GiB | 512 MiB | 64 MiB |

Every target is met in every run. Each run file was read back and verified end
to end (every digest and seal, complete, trail equal to the run's result), and
each pair of runs has the same trail digest. Live reservations stay bounded
(at most 24). The evidence write is about three quarters of the tick cost.

Limits: one machine and one workload. The kernel has no production, so the
scarce source is contested only until it runs dry in the first few ticks;
after that, denials come from overdrawn transfers and consumes. This is a
kernel-only check. Stage 2 repeats it with movement and perception active.

Raw results: `results/` (one JSON per run, plus `verification.json`).
The run files themselves (22 MB and 235 MB each) are not committed; rerun with
`py -3 -B -m stream.bench --ticks 10000 --out FILE --result FILE.json`.
