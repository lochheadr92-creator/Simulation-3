# Pinned source inventory

Source: `81c10b7d25cc2e0f1b8de33bf547083eb0972c64`. Tree: `f17ceeec11372b4ff4ec1a6db82d80423d8a7466`.

The source snapshot contains **609 tracked files**, totalling **32,262,693 uncompressed bytes**. Every Git blob was checked against the archive bytes when packaging. `SOURCE_MANIFEST.json` contains the complete file list and hashes.

| Top-level area | Tracked files | Bytes |
| --- | ---: | ---: |
| `(root files)` | 11 | 120,420 |
| `.codex-remote-attachments` | 3 | 27,222 |
| `archive` | 27 | 400,399 |
| `docs` | 11 | 72,666 |
| `evidence` | 455 | 30,566,448 |
| `kernel` | 12 | 64,823 |
| `stream` | 8 | 86,312 |
| `tests` | 56 | 468,375 |
| `tools` | 3 | 4,621 |
| `viewer` | 2 | 34,014 |
| `world` | 21 | 417,393 |

The complete tree is the review boundary. Active implementation is primarily in `kernel/`, `stream/`, `world/` and `viewer/`; tests, tools, dependencies and documentation are also in scope. `archive/`, `evidence/` and historical review attachments require relevance assessment, including references from current tests. Inclusion does not make historical instructions active.

The ZIP additionally contains this later review packet and the builder examples described in `EXAMPLE_MANIFEST.json`. It excludes `.git`, ignored local runs outside those named examples, installed dependencies, caches, credentials and unrelated local files. Dependencies must be supplied in the reviewer environment. This is a complete tracked project snapshot, not a complete Git history or a bundled execution environment.
