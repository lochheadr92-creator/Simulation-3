# Using the AI knowledge pack

## Source snapshot

- Source branch: `codex/kernel-first-slice`
- Source HEAD: `eda72d290bdb33aaaf620ad136149c6ef04e0a96`
- Constructed: 2026-09-28 from local source inspection and recorded documentation.
- Currency: snapshot only; not automatically current after this revision. Recheck relevant source and Git state before acting.
- Authority: [AGENTS.md](../../AGENTS.md) wins over this pack; [WORLD_DIRECTIONS.md](../../WORLD_DIRECTIONS.md) supplies current development direction.
- Evidence source: task requirements; repository AGENTS.md; pack retrieval structure.
- Refresh trigger: when pack usage, authority or retrieval structure changes.

## Purpose and authority

This pack compresses context. It is a retrieval aid, not a replacement instruction hierarchy, project brief, roadmap authority or execution permission. Read the repository's AGENTS.md first and follow applicable task instructions. Where this pack and AGENTS.md disagree, AGENTS.md wins.

Use current implementation as the strongest evidence of what exists. Tests describe checked contracts; recorded results describe particular executions. WORLD_DIRECTIONS.md supplies development direction, but its accumulated feature reports and suggestions must be read in context. Historical doctrine, roadmap, state and evidence files supply background unless current authority explicitly references them. A fixture can remain a test dependency without its surrounding governance becoming active.

## Load only what the task needs

1. Check branch, HEAD, tracked/staged changes and untracked files. Do not assume the snapshot or the remote is current.
2. Read [current state](05_CURRENT_STATE.md). Read [current slice](06_CURRENT_SLICE.md) when scope matters.
3. Use [system map](03_SYSTEM_MAP.md) to select the relevant source entry points and tests.
4. Read [architecture](01_ARCHITECTURE.md) or [invariants](02_INVARIANTS.md) for ownership and integrity questions.
5. Load [decisions](04_DECISIONS.md), [roadmap](07_ROADMAP.md) or historical evidence only when needed.

Do not load all eleven documents by default. Use [repo map](09_REPO_MAP.md) to locate unfamiliar material and [glossary](10_GLOSSARY.md) for terms. Follow links into live source before editing. If a summary is insufficient, inspect the missing path rather than infer its details.

## Keep claims and evidence separate

- **Fact:** directly observed in identified source, Git output or an execution artifact.
- **Inference:** a conclusion drawn from identified facts; state the reasoning and limits.
- **Hypothesis:** an explanation still requiring a check.
- **Recommendation:** a proposed action, not existing implementation or authorization.
- **UNKNOWN:** the available evidence does not establish the claim.

Label a test result as recorded or freshly executed. A committed feature, successful test, watched example and explicit owner acceptance are different facts. A local origin-tracking match does not independently establish current remote publication.

## Working with a compressed description

Trace the relevant chain: input and validation -> observation -> decision -> proposal or non-resource action -> settlement -> world processing -> saved record -> visible consequence -> later decision. Distinguish selection from successful execution. Refusal, interruption and death can be real outcomes.

For architecture changes, identify semantic ownership and existing dependency direction first. Describe which contract changes, why, and which consumers need updating. Preserve unrelated work. Do not invent a new subsystem because a summary omits an existing one.

Protect deterministic state, ordering, explicit resource accounting and replayable changes. See the precise settlement/production boundary in the architecture; do not generalize it into “all ledger changes occur through settlement.”

Use verification appropriate to the authorized change. For world behaviour, current AGENTS.md calls for watching the result as well as preserving trustworthy mechanics. A documentation-only or read-only task does not authorize extra simulations merely because this pack lists commands.

When something fails, locate the earliest broken boundary: opportunity, choice, execution, consequence or instrument. Preserve the failure and avoid changing a fixture just to obtain PASS.

## Maintaining this pack

Refresh only affected summaries after checking their source. Update each changed document's source metadata honestly; do not bulk-relabel untouched descriptions as freshly inspected. Volatile snapshots expire when the repository changes.

Preserve existing decision IDs. A pack-local label is a navigation label, not a new historical decision or approval. Record undocumented reasoning as UNKNOWN.

At completion report scope, changed files, checks actually performed, results, unresolved limits and Git state. Do not claim a commit, push, independent review or acceptance that did not occur. No new governance, orchestration or evidence-management machinery is required to maintain these Markdown files.
