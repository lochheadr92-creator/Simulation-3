# Whole-project review report

**Status: NOT_REVIEWED**

This is an unsigned template. No checks or findings below have been completed by a reviewer. Replace placeholders with your own evidence; do not copy builder results into your executed-check list.

## Identity and scope

- Reviewed source commit: `81c10b7d25cc2e0f1b8de33bf547083eb0972c64`
- Expected source tree: `f17ceeec11372b4ff4ec1a6db82d80423d8a7466`
- Actual revision / source manifest verification: [fill in]
- Packet ZIP SHA-256, if used: [fill in, or not used]
- Review location and whether source was modified: [fill in]
- Reviewer agent name: [fill in]
- Provider / model / version: [self-report if known; otherwise unknown]
- Task or session identifier: [if available]
- Review started / finished (UTC): [fill in]
- Independence: [state any involvement in building the reviewed code; otherwise say none]
- OS, Python, pytest, Node and browser versions used: [fill in]

## Verdict

- Verdict: [PASS / FAIL / INCOMPLETE]
- Reason: [fill in]
- Blocking finding IDs: [fill in, or none established]
- Essential checks not completed: [fill in, or none]

## Coverage

Use `CHECKED`, `PARTIAL`, `NOT_CHECKED` or `NOT_APPLICABLE` with a reason. Link files inspected, actual commands and artifacts. Distinguish inspection from execution.

| Area | Coverage | Source inspected | Checks/evidence | Limits |
| --- | --- | --- | --- | --- |
| Kernel transactions, state and ordering | NOT_CHECKED | | | |
| World tick ownership and resource accounting | NOT_CHECKED | | | |
| Perception, needs, routes and terrain | NOT_CHECKED | | | |
| Social memory, requests, offers and sharing | NOT_CHECKED | | | |
| Families, birth, death and caregiving | NOT_CHECKED | | | |
| Homes, stores, provisioning and coordination | NOT_CHECKED | | | |
| Ecology, fishing, wood and construction | NOT_CHECKED | | | |
| Configuration, defaults and disabled modes | NOT_CHECKED | | | |
| Streams, verification, replay and recovery | NOT_CHECKED | | | |
| Current and older viewers, browser behaviour | NOT_CHECKED | | | |
| Tests, fixtures and independent counterexamples | NOT_CHECKED | | | |
| Local operation, dependencies and helper tools | NOT_CHECKED | | | |
| Architecture, docs and historical artifact consumers | NOT_CHECKED | | | |
| Scale, ordinary-world behaviour and causal trace | NOT_CHECKED | | | |

## Findings

No findings have been entered. This does not mean that no defects exist.

For each finding use:

### [ID] [P0 / P1 / P2 / P3] [concrete title]

- Classification: [defect / evidence gap / modelling concern / improvement]
- Blocking: [yes/no, with reason]
- Confidence: [reproduced / source-demonstrated / hypothesis]
- Location: [repository-relative path and verified line(s) at the pinned commit]
- Trigger and scope: [configuration, seed, tick, inputs, relevant preconditions]
- Expected behaviour and contract: [fill in]
- Actual behaviour: [fill in]
- Reproduction: [exact command or self-contained probe; attach file if needed]
- Evidence: [output/artifact reference; preserve the failure]
- Impact: [fill in]
- Introduced by recent changes: [yes/no/unknown, with evidence]
- Suggested smallest correction and regression check: [proposal only]

Severity guide: P0 = fundamental unusability or pervasive integrity failure; P1 = serious correctness/data integrity or major broken workflow; P2 = bounded defect with material user impact; P3 = minor issue or improvement. Explain scope and priority rather than relying on the label.

## Checks actually executed

| Command/check | Configuration and inputs | Exit/result, counts including skips | Evidence file | What it establishes |
| --- | --- | --- | --- | --- |
| [fill in] | | | | |

## Observed causal scene

[Record an ordinary saved world's configuration and source identity, person, ticks, need/opportunity, observation, choice, actual action or refusal, consequence and later choice. Distinguish saved/native evidence from your interpretation. Record browser playback and inspector checks separately.]

## Counterexamples and negative results

[Record attacks tried, why they matter and what happened. An unsuccessful attack is bounded evidence, not proof that the whole area is correct.]

## Unresolved limits and follow-up

[Record missing tools, untested configurations, cost limits, remaining uncertainties and the smallest useful next checks. Keep repair proposals separate from executed repairs.]

## Reviewer signature

I attest that this report identifies the source I examined, distinguishes checks I performed from inherited claims, records known failures and incomplete coverage, and discloses my involvement in building the code. My typed name attributes this review to me; it is not a cryptographic signature or owner acceptance.

- Signed name / agent name: **[unsigned]**
- Provider / model (if known): [fill in]
- Signed at (UTC): [fill in]
- Reviewed commit: [repeat the full verified source SHA]
- Final verdict: [PASS / FAIL / INCOMPLETE]
