# Evaluation Guide

These cases test both **activation precision** and **engineering behavior**. They are intentionally model- and harness-neutral.

## Run protocol

1. Start every run in a clean context with the same tools and input files.
2. For each line in `scenarios.jsonl`, run the prompt once with this skill available and once without it. When comparing revisions, use the previous skill version as the baseline instead.
3. Record whether the skill activated, the final output, created files, validation output, commands, duration, token usage when available, and any execution transcript.
4. Grade each run against `rubric.md` and the `expectations` and `anti_expectations` of the scenario.
5. Require concrete evidence for each pass. A heading or assertion without matching substance is not evidence.
6. Review false activations, missed activations, conformance mistakes, invented portability claims, and unnecessary token/tool cost before release.

## Recommended workspace

```text
agent-plugin-workspace/
└── iteration-1/
    ├── author-skill-only-plugin/
    │   ├── with-skill/
    │   └── baseline/
    ├── review-plugin-package/
    │   ├── with-skill/
    │   └── baseline/
    └── benchmark.json
```

We recommend that each run folder contain `output/`, `transcript.txt` when available, `timing.json`, and `grading.json`. Keep generated plugin fixtures outside this skill directory so package validation remains reproducible.

## Regression policy

A release fails when any critical gate in the rubric fails, negative-trigger precision regresses, or a new version claim lacks a fresh upstream check. A quality increase that materially raises token or execution cost merits a report rather than concealment.
