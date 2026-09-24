# 50-person world cost check, 2026-09-25

Workload (`world/bench.py`): the one-source world with its rules unchanged,
50 people on a 9x9 grid (every home within 8 steps of the source), food levers
raised (starting food 3, stock 200, cap 400, +12 per tick) so everyone can
live. Yield on, scoring off, seed 1. Tick time is a full world tick (observe,
decide, settle, process) plus that tick's sealed evidence write.

Machine: TheWeapon, Windows 11 (10.0.26200), Intel Core Ultra 9 285K
(24 cores), CPython 3.12.10. Memory is the process working set.

| Run | Alive at end | Mean tick | p95 tick | World step | Evidence/tick | 10k-tick size | Peak memory | Growth 1k to end |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 a | 50 | 5.98 ms | 8.81 ms | 2.51 ms | 26.6 KiB | 0.254 GiB | 23.0 MiB | n/a |
| 1,000 b | 50 | 5.83 ms | 8.52 ms | 2.42 ms | 26.6 KiB | 0.254 GiB | 23.2 MiB | n/a |
| 10,000 a | 50 | 6.01 ms | 8.47 ms | 2.46 ms | 26.8 KiB | 0.256 GiB | 24.5 MiB | 1.4 MiB |
| 10,000 b | 50 | 5.77 ms | 8.38 ms | 2.40 ms | 26.8 KiB | 0.256 GiB | 24.8 MiB | 1.7 MiB |
| Target | | 50 ms | 100 ms | | 64 KiB | 1 GiB | 512 MiB | 64 MiB |

Every target is met in every run; nobody dies. Each run file was read back and
verified end to end, and each pair of runs has the same trail digest.

Before commit `919bc21` the same workload measured 34.8 ms mean tick, 46 ms
p95 and 81 KiB per tick (over target): each person recorded every other
person in view with position and food, and observe() rebuilt a full kernel
view for every person seen. Recording identities only and building one
availability map per tick fixed both without changing any decision, record,
state or world field (checked tick by tick over 1,000 ticks).

Limits: one machine and one workload, crowded near worst case for perception
(most people are in view of most others). Observation size still grows with
the square of the population, now at about 7 bytes per pair.

These results were measured at `986a276`, under the short-range defaults
later replaced by the range fix; `world.bench` now runs the new defaults.

Raw results: `results/` (one JSON per run, plus `verification.json`). The run
files are not committed; rerun with
`py -3 -B -m world.bench --ticks 10000 --out FILE --result FILE.json`.
