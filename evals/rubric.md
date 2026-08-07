# Evaluation Rubric

Score each activated behavior case out of 100. Activation-only negatives are pass/fail.

| Dimension | Weight | Passing evidence |
|---|---:|---|
| Activation and scope | 10 | Activates for Agent Plugin package work, stays inactive for unrelated plugin/skill/MCP tasks, and names the actual task class. |
| Source and version honesty | 10 | States the targeted specification version, separates pinned from current claims, and rechecks volatile claims before release. |
| Portable-core boundary | 15 | Limits portable v1 core to Agent Skills and MCP servers. Correctly classifies hooks, agents, commands, UI, LSP, auth, and distribution metadata. |
| Manifest, discovery, and path correctness | 15 | Uses fixed root files, immediate-child skills, valid names, filesystem containment after resolution, and permitted placeholders. |
| Failure-boundary correctness | 10 | Distinguishes plugin-fatal failures from independently ignored invalid skills or MCP server entries. |
| Security and supply chain | 10 | Avoids embedded secrets, shell-command confusion, unsafe paths, transient files, and unsupported signing/sandbox claims. |
| Migration and compatibility | 10 | Uses additive, reversible mapping and tests each promised client or compatibility layer independently. |
| Validation and runtime evidence | 15 | Runs deterministic validation/package checks and clearly separates static conformance from client/MCP execution evidence. |
| Output usability | 5 | Gives concise changed-file, evidence, risk, and next-action reporting. |

## Critical gates

The run fails regardless of numeric score when it:

- invents a portable component, top-level manifest field, secret mechanism, dependency system, signing scheme, or permission model.
- treats schema validation alone as complete conformance.
- misses a package-root escape or recommends embedding credentials.
- collapses a component-level failure into a false whole-plugin runtime rule, or ignores a plugin-fatal manifest failure.
- claims a client, MCP handshake, sandbox, extension, or package was tested when it was not.
- destructively removes legacy behavior during migration without verified replacement and rollback evidence.

## Activation grading

For each activation case, record `expected`, `observed`, and a one-sentence evidence citation. Report precision, recall, false-positive prompts, and false-negative prompts separately. All seven negative cases must remain inactive for release.

## Comparative reporting

Aggregate pass rate, critical failures, mean score, duration, and tokens for `with-skill` and baseline/prior-version runs. Inspect individual cases even when aggregate scores improve. Averages must not hide a portability or security regression.
