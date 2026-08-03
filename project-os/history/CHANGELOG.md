---
title: qari-assets — changelog
type: history
project: qari-assets
status: IN_PROGRESS
owner: Malick
created: 2026-08-02
updated: 2026-08-02
last_verified: 2026-08-02
verified_against: 4f8972d22a92989558778ead04d605965fa9e339
ttl_days: 90
sources: manifest.json:2, manifest.json:5, .github/workflows/auto-release.yml:9
confidence: inferred
superseded_by:
related: project-os/history/2026.md
---

# Changelog

Keep-a-Changelog shape; newest first. Every `qari-assets-N` section below is **backfilled** —
reconstructed from the tag graph and the commits between tags, not from release notes written at
the time. Each section heading below carries the inferred-needs-review marker plus its evidence.
`baseline-2026-08` is the first *verified* boundary: the first release cut with a code-verified
documentation baseline in place.

Release-tag mechanics for readers: tags `qari-assets` … `qari-assets-5` are **lightweight** tags
created by hand; `qari-assets-6` and `-7` are **annotated** tags cut by the auto-release workflow.
Section dates are the tagged commit's author date; where the machine tagger date differs it is
noted inline.

## [baseline-2026-08] — 2026-08-02
### Added
- Code-verified documentation baseline (`project-os/`): history reconstruction and this
  changelog, authored from git archaeology against `origin/main` at `4f8972d`.
- First release boundary for which the repository's state is documented rather than inferred.

## [qari-assets-7] — 2026-06-28  ·  `Inferred — needs review`
Annotated tag cut automatically on 2026-06-29 UTC against the 2026-06-28 commit. One commit
since `qari-assets-6`; no asset or manifest change.
### Added
- `README.md` describing repo layout, asset variants, helper scripts and the release model.
### Notes
- First release produced end-to-end by the auto-release workflow with no human tagging step, and
  the first release number burned by a documentation-only commit.
**Evidence**: commit 4f8972d; tag qari-assets-7

## [qari-assets-6] — 2026-05-27  ·  `Inferred — needs review`
Annotated tag cut automatically on 2026-05-27. Spans three merged pull requests (#5, #6, #7) —
the largest release in the repo's history.
### Added
- Three mushaf variants: `v2-dk` (Digital Khatt V2), `v1-madina-tajweed` (Digital Khatt V1 +
  Tajweed) and `nastaleeq` (KFGQPC Nastaleeq), taking the catalogue from 2 variants to 5.
- `qpc-hafs.db` (83,668 words), the shared Unicode words DB for all three new variants.
- `single_font` variant mode in `_build_manifest.py`, emitting a `singleFont` manifest block
  alongside the existing 604-font `per_page` mode.
- `.github/workflows/auto-release.yml` — tag + GitHub Release on every push to `main`, with a
  `[skip release]` opt-out, a serialized concurrency group and a `workflow_dispatch` fallback.
- `--ref` / `--release-tag` CLI flags (and `$QARI_ASSETS_REF` / `$QARI_ASSETS_RELEASE_TAG`
  env-var fallbacks) on `_build_manifest.py`.
### Changed
- `manifest.json` schemaVersion 3 → 4; `releaseTag` v1.2.0 → v1.4.0 (v1.3.0 skipped).
### Fixed
- `_parse_family()` decoded `platformID=0` (Unicode) OpenType name records as mac-roman instead
  of UTF-16BE, garbling family names for affected OTFs.
- Manifest `baseUrl` and `releaseTag` no longer hardcoded in the builder.
**Evidence**: commit fdb32da; commit 791ee7c; commit 0a367e7; commit a031010; commit a0dc7a1;
commit 2478555; tag qari-assets-6

## [qari-assets-5] — 2026-05-21  ·  `Inferred — needs review`
Lightweight tag on the PR #4 merge commit.
### Added
- `qpc-v1.db` — V1-encoded per-word codepoint mapping (83,668 rows, schema mirroring
  `qpc-v4.db`), extracted from the archive staged at `qari-assets-4`.
- Per-variant `wordsDb` blocks in `manifest.json` (`v1-madina` → `qpc-v1.db`,
  `v4-tajweed` → `qpc-v4.db`).
### Changed
- `manifest.json` schemaVersion 2 → 3; `releaseTag` → v1.2.0. Top-level `wordsDb` retained
  pointing at `qpc-v4.db` so schemaVersion-2 clients keep parsing unchanged.
- Variant display names updated to "Madina Mushaf v4 1441H" / "Madina Mushaf v1 1405H".
### Fixed
- V1 pages rendered fragmented/garbled because V4 PUA codepoints (U+FC41..U+FDFD) were being
  resolved against V1 `QCF_P{NNN}` fonts, which expect U+FB00..U+FBFF.
### Removed
- Every remaining zip archive in the repo, including the V1 glyph-codes source and the deferred
  Nastaleeq / V2 layout archives.
**Evidence**: commit bfc84c3; commit c0d6d74; tag qari-assets-5

## [qari-assets-4] — 2026-05-21  ·  `Inferred — needs review`
Lightweight tag on a direct-to-main web-UI upload; no pull request.
### Added
- `qpc-v1-glyph-codes-wbw.db.zip`, the source archive for `qpc-v1.db` (extracted and deleted at
  `qari-assets-5`).
### Notes
- The auto-release workflow's own comment states `qari-assets-4` "was never cut", yet the tag
  exists on `origin` at `744521e`. Most plausible reading: the tag was created but no GitHub
  Release was ever published against it. Unresolvable from inside the repo.
**Evidence**: commit 744521e; tag qari-assets-4; .github/workflows/auto-release.yml:9-11

## [qari-assets-3] — 2026-05-21  ·  `Inferred — needs review`
Lightweight tag on the PR #3 merge commit.
### Changed
- `_build_manifest_v2.py` renamed to `_build_manifest.py` and rewritten to be self-contained —
  it walks `fonts/<variantId>/` on disk and recomputes SHA-256 and sizes on every run, so adding
  a variant is a data change rather than a code change.
- `manifest.json` regenerated with the new builder; `baseUrl` repointed to `qari-assets-2`.
### Removed
- `QPC V1 Font.ttf.bz2` (54 MB), redundant once the 604 V1 TTFs were extracted.
- The previous single-variant builder, and two debug-only manifest fields.
### Fixed
- V4 `totalSizeBytes` was inflated by exactly the size of `qpc-v4.db`
  (169,423,944 → 166,986,824).
**Evidence**: commit 37ef690; commit 9ff1baf; tag qari-assets-3

## [qari-assets-2] — 2026-05-21  ·  `Inferred — needs review`
Lightweight tag on the PR #2 merge commit. The release that turned a single-mushaf repo into a
variant catalogue.
### Added
- 604 V1 Madina (1405H) per-page TTFs under `fonts/v1/`.
- `_build_manifest_v2.py` for reproducible multi-variant manifest builds.
- `QPC V1 Font.ttf.bz2` and the Nastaleeq / V1 / V2 layout + words DB archives, staged via
  web-UI uploads on 2026-05-20 and 2026-05-21.
### Changed
- `manifest.json` schemaVersion 1 → 2: a multi-variant document holding `v1-madina` and
  `v4-tajweed`, each with its own `fontDir`, `familyPattern`, `tajweedColored` flag and per-page
  metadata. V4 entries preserved verbatim; the shared words DB promoted to top level.
  `releaseTag` → v1.1.0.
**Evidence**: commit 998b7e8; commit cbdfa90; commit d465a9b; commit 75ca4e9; commit c9209b7;
tag qari-assets-2

## [qari-assets] — 2026-05-16  ·  `Inferred — needs review`
Lightweight tag on the PR #1 merge commit — the initial release. Eight commits, all on the
same day.
### Added
- 604 QCF V4 tajweed-color per-page fonts (family `QCF4{NNN}_COLOR`, COLR/CPAL color tables,
  159.3 MB) fetched from the QUL CDN.
- `manifest.json` at schemaVersion 1 — single-variant, indexing filename, family, sha256 and
  sizeBytes per page. `releaseTag` v1.0.0.
- `_fetch_v4_tajweed.py` (parallel fetcher with sfnt-magic verification and retry) and
  `_build_manifest.py`.
- `qpc-v4.db` — V4 per-word codepoint mapping, 83,668 rows, verified end-to-end against the
  layout DB and the page fonts' cmaps.
- `LICENSE.txt` — KFGQPC electronic end-user terms, registered in the manifest with sha256
  and size.
- Surah-header and common-glyph fonts unzipped to raw `.ttf`.
### Removed
- A byte-identical duplicate words-DB archive, a JSON twin of the same DB, two archives
  belonging bundled inside the consuming Flutter client, `pages.zip` (a DOCX duplicate of
  `qpc-v4.db`) and the unused `surah-name-v2.ttf`.
### Notes
- Each `fonts/v4-tajweed/p*.ttf` embeds a stricter clause in its `name` table (id 10) than
  `LICENSE.txt` states: charitable use only, printing and publishing barred without prior
  KFGQPC permission. Recorded in commit history only — never promoted into `LICENSE.txt`.
**Evidence**: commit ba9dd9e; commit 186b5fe; commit f614411; commit b51d07b; commit 4de5d8c;
commit 407d8ae; commit 68e0200; commit 4f5cbe6; commit a68ae3c; tag qari-assets
