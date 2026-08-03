---
title: qari-assets — verify contract
type: ops
project: qari-assets
status: READY
owner: Malick
created: 2026-08-02
updated: 2026-08-02
last_verified: 2026-08-02
verified_against: 4f8972d
ttl_days: 180
sources: _build_manifest.py:31, .github/workflows/auto-release.yml:1
confidence: confirmed
---

# VERIFY_CMD

```
python3 _build_manifest.py && git diff -I '"generatedAt"' -I '"baseUrl"' --exit-code manifest.json; RC=$?; git checkout -- manifest.json; exit $RC
```
Regeneration must match the committed manifest **modulo the two volatile fields** —
`generatedAt` (stamped per run) and `baseUrl` (dev regen points at `main`; the committed
value carries the release tag, written by the workflow's `--release-tag` invocation:
`_build_manifest.py:35`). Any other diff means the scripts and the published manifest have
drifted.

> **Past learning (2026-08):** the naive byte-level form (`git diff --exit-code
> manifest.json` without the `-I` ignores) is a false RED by design — recorded here so
> nobody "fixes" the contract back to it. Baseline established GREEN 2026-08-02 under the
> corrected contract.

## Release safety
- `auto-release.yml` fires on **any** push to main (its `paths:` filter is commented out)
  and cuts tag `qari-assets-N+1`, which the consuming app pins. Doc-only merges MUST carry
  `[skip release]` in the merge-commit subject until the paths filter is re-enabled
  (tracked improvement).
- Never push tags matching the release scheme by hand.
