# On-Demand Upstream Review

This protocol updates research baselines without silently changing product behavior. It is user-triggered. Nothing runs on a schedule.

## Recognized requests

- **review**: inspect changes after the recorded commits and produce a read-only classification report.
- **review and record**: perform a complete review, then atomically advance baselines when no product change is needed.
- **review and update**: perform a complete review, modify the skill in a clean candidate tree, validate it, then atomically update product files and baselines.

No other phrase authorizes baseline advancement or product mutation.

## Preflight

1. Read `maintenance/upstreams.lock.json` without editing it.
2. Verify each repository URL, branch, recorded 40-hex commit, source role, policy, and license identity.
3. Fetch or query immutable candidate commit IDs. Do not review a mutable branch name after resolving it.
4. Stop on rewritten/unrelated history, unavailable recorded commits, changed repository identity, unclear license, or incomplete source access.
5. Preserve the current product tree and record its hash/status before any authorized update.

## Review scope

For every source, inspect changes after its recorded commit only in relevant paths, plus renamed/moved files that replace them. Classify each material change as:

- **normative adoption required**: Agent Plugins or Agent Skills contract changed,
- **compatibility update**: client support/install/namespace behavior changed,
- **MCP reference update**: wire/lifecycle/transport context changed,
- **engineering improvement**: useful non-normative practice,
- **no product impact**: editorial, governance, unrelated, or already represented,
- **blocked/uncertain**: identity, license, ambiguity, or insufficient evidence.

Explicitly check:

- specification status/version and canonical schema IDs,
- manifest fields and recoverable versus fatal handling,
- component locations/discovery and filesystem containment,
- skill frontmatter and progressive-disclosure rules,
- MCP variants, placeholders, environment, URL/header/auth behavior,
- failure boundaries and client conformance requirements,
- extension namespace rules,
- compatible-client matrix,
- future/non-goals that prevent overclaiming.

## Read-only review output

Report:

- old and candidate immutable IDs,
- changed relevant paths,
- classification and evidence for every material change,
- proposed product files and tests if an update is warranted,
- license/provenance disposition,
- whether baseline advancement is safe.

A plain `review` never edits files or the ledger.

## Review and record

Advance a source baseline only when:

- all relevant changes through the immutable candidate were reviewed,
- every material change was classified,
- no blocked uncertainty remains,
- no product update is necessary,
- the recorded license URL is pinned to the candidate where applicable.

Write the complete new JSON to a temporary sibling, parse and validate it, then atomically replace the ledger. Never partially update one source after an incomplete multi-source review.

## Review and update

1. Copy the product to a clean temporary candidate outside the authoritative checkout.
2. Apply the smallest evidence-backed changes. Preserve local wording and architecture unless upstream requirements changed.
3. Update references, schemas, notices, audit, evals, validator semantics, and compatibility snapshot as applicable.
4. Run all script self-tests and `validate_skill.py <candidate> --package`.
5. Validate bundled example plugins and package a deterministic test artifact.
6. Review the full candidate diff and provenance map.
7. Only after all gates pass, replace changed product files and the ledger atomically or through one intentional commit.

## Prohibitions

- no destructive reset, force checkout, unreviewed copy, or automatic reinstall,
- no branch-name-only provenance after candidate resolution,
- no baseline advancement to hide unclassified changes,
- no importing client-native fields into the portable core without normative evidence,
- no claiming a new client/version works based only on a documentation table,
- no replacing the published specification with local validator behavior.
