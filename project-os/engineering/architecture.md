---
title: qari-assets — architecture reference
type: architecture
project: qari-assets
status: READY
owner: Malick
created: 2026-08-02
updated: 2026-08-02
last_verified: 2026-08-02
verified_against: 4f8972d
ttl_days: 180
sources: manifest.json:1, _build_manifest.py:59, _fetch_v4_tajweed.py:15, .github/workflows/auto-release.yml:13, LICENSE.txt:1, README.md:1
confidence: confirmed
---

**Repo**: nmalick/qari-assets · **Last commit checked**: `4f8972d` (2026-06-28) · **Last updated**: 2026-08-02

> MAINTENANCE: run `/update-ref qari-assets` after merges — it reads the cursor above, triages the
> new commits via `ops/ref-map.md`, and re-audits only affected sections.
> This doc is the source of truth — update it here; don't re-read the repo to answer questions
> it covers.

# qari-assets — architecture

This repository is a **published asset bundle, not an application**: Quranic font binaries,
SQLite word databases, a generated `manifest.json`, and the automation that tags and releases
them. Repo landing page: [`README.md`](../../README.md). Regeneration contract:
[`ops/verify.md`](../ops/verify.md).

The public contract this repo owes its consumers is exactly three things: the **manifest schema**,
the **`baseUrl` + git-tag pinning rule**, and the **licensing terms of the bytes it ships**.
Everything below documents those.

## Stack (verified)

- Two Python 3 scripts, standard library only — `argparse, hashlib, json, os, sqlite3, struct, sys, datetime` (`_build_manifest.py:50-57`); the fetcher explicitly advertises "No third-party deps" (`_fetch_v4_tajweed.py:4`).
- Font family names are read by a hand-rolled TTF `name`-table parser (`_build_manifest.py:134:_parse_family`) rather than a font library — this is why there is no dependency file.
- Integrity is SHA-256 over whole file bytes (`_build_manifest.py:173:_file_sha256`); word-DB row counts come from `SELECT COUNT(*) FROM words` over sqlite3 (`_build_manifest.py:185`).
- CI is a single GitHub Actions workflow, `.github/workflows/auto-release.yml:1`.
- **No package manifest, lockfile, dependency file, or test suite exists in this repo** — confirmed absent from the tracked file list at `4f8972d`; the only tracked non-asset files at `4f8972d` are the two scripts, `manifest.json`, `README.md`, `LICENSE.txt`, `.gitignore`, and the workflow. (The doc-kit branch additionally tracks `CLAUDE.md`, `.claude/settings.json`, and `project-os/**`.)

## Entry points & module map

Two scripts, both at repo root, both resolving paths relative to their own location so cwd does not matter (`_build_manifest.py:47-48`).

### `_build_manifest.py` — the manifest generator

Builds `manifest.json` (schemaVersion 4) by scanning the on-disk variant directories (`_build_manifest.py:1`).

Path / value constants:

| Constant | Value | Line |
|---|---|---|
| `REPO_ROOT` | `os.path.dirname(os.path.abspath(__file__))` | `_build_manifest.py:59` |
| `MANIFEST_PATH` | `<REPO_ROOT>/manifest.json` | `_build_manifest.py:60` |
| `LICENSE_FILE` | `LICENSE.txt` | `_build_manifest.py:61` |
| `TOTAL_PAGES` | `604` | `_build_manifest.py:62` |
| `TTF_MAGICS` | `{b"\x00\x01\x00\x00", b"true", b"OTTO"}` | `_build_manifest.py:63` |
| `_DEFAULT_REF` | `"main"` | `_build_manifest.py:68` |
| `_DEFAULT_RELEASE_TAG` | `"v1.4.0"` | `_build_manifest.py:69` |
| `_BACKCOMPAT_WORDS_DB_VARIANT` | `"v4-tajweed"` | `_build_manifest.py:131` |

Flow: `main()` (`_build_manifest.py:324`) composes `baseUrl` from `--ref` (`_build_manifest.py:326-328`), walks `_VARIANTS` (`_build_manifest.py:333`), dispatches per variant `mode` (`_build_manifest.py:289-296`), aborts with exit code 1 if any variant reported a validation failure (`_build_manifest.py:345-349`), then writes the assembled dict to `manifest.json` (`_build_manifest.py:359-375`).

Adding a variant is a two-step, documented in the module docstring: drop the assets in place and append an entry to `_VARIANTS` (`_build_manifest.py:15-21`).

### `_fetch_v4_tajweed.py` — the one-shot asset fetcher

Parallel fetcher for the 604 V4-tajweed per-page fonts from the QUL CDN; downloads, verifies sfnt magic, retries transient failures, prints a report (`_fetch_v4_tajweed.py:1-4`).

| Constant | Value | Line |
|---|---|---|
| `BASE` | `https://static-cdn.tarteel.ai/qul/fonts/quran_fonts/v4-tajweed/ttf` | `_fetch_v4_tajweed.py:15` |
| `OUT_DIR` | `fonts/v4-tajweed` | `_fetch_v4_tajweed.py:16` |
| `TOTAL_PAGES` | `604` | `_fetch_v4_tajweed.py:17` |
| `MAX_WORKERS` | `24` | `_fetch_v4_tajweed.py:18` |
| `MAX_RETRIES` | `4` | `_fetch_v4_tajweed.py:19` |
| `TIMEOUT` | `30` | `_fetch_v4_tajweed.py:20` |
| `TTF_MAGICS` | `{b"\x00\x01\x00\x00", b"true", b"OTTO"}` | `_fetch_v4_tajweed.py:21` |

Per-page guards: responses under 200 bytes are rejected as truncated (`_fetch_v4_tajweed.py:36-38`), the first four bytes must be a known sfnt magic (`_fetch_v4_tajweed.py:40-42`), HTTP 404 breaks out instead of retrying (`_fetch_v4_tajweed.py:48`), and other failures back off linearly (`_fetch_v4_tajweed.py:52`). Any failed page makes the script exit 1 (`_fetch_v4_tajweed.py:76-80`).

**This script only populates `fonts/v4-tajweed/`.** The other four variants have no fetcher in this repo — confirmed absent from the tracked file list at `4f8972d`; they were added as committed binaries.

## Data layer

### The five variants and their two structural shapes

The registry is `_VARIANTS` (`_build_manifest.py:78-125`). `mode` is the dispatch key: `per_page` means 604 per-page fonts using PUA codepoints (glyph encoding differs per page, so fonts cannot be shared across pages); `single_font` means Unicode shaping with one OTF/TTF covering all 604 pages, with Tajweed layered as a character-level overlay rather than baked into a COLR table (`_build_manifest.py:3-13`).

| Variant id | displayName | Shape | fontDir | Font(s) | familyPattern | tajweedColored | wordsDb |
|---|---|---|---|---|---|---|---|
| `v4-tajweed` | Madina Mushaf v4 1441H | per-page | `fonts/v4-tajweed/` | 604 × `p{N}.ttf` | `QCF4{NNN}_COLOR` | true | `qpc-v4.db` |
| `v1-madina` | Madina Mushaf v1 1405H | per-page | `fonts/v1/` | 604 × `p{N}.ttf` | `QCF_P{NNN}` | false | `qpc-v1.db` |
| `v2-dk` | KFGQPC V2 1421H print | single-font | `fonts/dk-v2/` | `DigitalKhattV2.otf` | `null` | true | `qpc-hafs.db` |
| `v1-madina-tajweed` | Madina Mushaf v1 + Tajweed | single-font | `fonts/dk-v1/` | `DigitalKhattQuranicV1.otf` | `null` | true | `qpc-hafs.db` |
| `nastaleeq` | KFGQPC Nastaleeq 15 lines | single-font | `fonts/nastaleeq/` | `KFGQPCNastaleeq-Regular.ttf` | `null` | true | `qpc-hafs.db` |

Published sizes and family names, as emitted: `v4-tajweed` 604 fonts / 166,986,824 B (`manifest.json:19-20`); `v1-madina` 604 fonts / 95,020,860 B (`manifest.json:4286-4287`); `v2-dk` 1 font / 521,832 B, family `DigitalKhatt New Madina` (`manifest.json:4264-4277`); `v1-madina-tajweed` 1 font / 451,816 B, family `DigitalKhatt Old Madina` (`manifest.json:8531-8544`); `nastaleeq` 1 font / 254,720 B, family `KFGQPC Nastaleeq` (`manifest.json:8553-8566`).

The three single-font variants all share one Hafs Unicode words DB, `qpc-hafs.db` (`_build_manifest.py:92`, `_build_manifest.py:110`, `_build_manifest.py:120`); the two per-page variants each carry their own PUA-encoded DB (`_build_manifest.py:84`, `_build_manifest.py:102`). All three DBs report `rowCount` 83668 (`manifest.json:10`, `manifest.json:4270`, `manifest.json:4292`).

### `manifest.json` schema v4 — field by field

Top level (`manifest.json:1-12`, `manifest.json:8570`):

| Field | Type | Emitted value at `4f8972d` | Source |
|---|---|---|---|
| `schemaVersion` | int | `4` | `manifest.json:2`, set literally at `_build_manifest.py:360` |
| `releaseTag` | string | `"v1.4.0"` | `manifest.json:3`, from `--release-tag` / `QARI_ASSETS_RELEASE_TAG` / default `_build_manifest.py:69` |
| `generatedAt` | ISO-8601 UTC, second precision | `"2026-05-27T20:03:51+00:00"` | `manifest.json:4`, `datetime.now(timezone.utc).isoformat(timespec="seconds")` at `_build_manifest.py:362` |
| `baseUrl` | string, trailing slash | `https://raw.githubusercontent.com/nmalick/qari-assets/qari-assets-6/` | `manifest.json:5`, composed at `_build_manifest.py:326-328` |
| `wordsDb` | object | the `v4-tajweed` DB block, for schemaVersion-2/3 back-compat only | `manifest.json:6-11`, `_build_manifest.py:354-357` |
| `variants` | object keyed by variant id | five entries | `manifest.json:12`, `_build_manifest.py:331-338` |
| `license` | object | `{filename, sha256, sizeBytes}` for `LICENSE.txt` | `manifest.json:8570-8574`, `_build_manifest.py:366-370` |

Every variant entry carries the same nine keys, whatever its shape (`_build_manifest.py:233-243` per-page, `_build_manifest.py:267-286` single-font):

| Field | Type | Notes |
|---|---|---|
| `displayName` | string | human label, straight from `_VARIANTS` |
| `pageCount` | int | always `604` — `TOTAL_PAGES` for per-page, `cfg["pageCount"]` for single-font (`_build_manifest.py:251`) |
| `fontDir` | string, trailing slash | repo-relative directory |
| `familyPattern` | string or `null` | `{NNN}` is the zero-padded page number; `null` for single-font (`_build_manifest.py:73-77`) |
| `tajweedColored` | bool | `false` only for `v1-madina` (`manifest.json:4285`) |
| `fontCount` | int | `604` per-page, `1` single-font |
| `totalSizeBytes` | int | sum of the variant's font bytes |
| `wordsDb` | object | `{filename, sha256, sizeBytes, rowCount?}` (`_build_manifest.py:189-192`) |
| `fonts` | array | populated per-page; **empty array is the explicit single-font signal** (`_build_manifest.py:283-285`) |

Single-font variants add one key: `singleFont` = `{filename, family, sha256, sizeBytes}` (`_build_manifest.py:276-281`, shape visible at `manifest.json:4272-4277`).

Per-page `fonts[]` elements are `{page, filename, family, sha256, sizeBytes}` (`_build_manifest.py:224-230`, shape visible at `manifest.json:28-34`).

`wordsDb.rowCount` is **optional**: it is omitted when the sqlite query fails, and the build only warns rather than aborting (`_build_manifest.py:183-192`).

### Version-compatibility rules baked into the schema

- The top-level `wordsDb` is preserved pointing at the V4 DB so schemaVersion-2 clients still parse and keep their existing behavior (`_build_manifest.py:23-24`, `_build_manifest.py:127-131`).
- The 3 → 4 bump is deliberately gated by the `singleFont` block so a v3 parser fails loud rather than silently reading a single-font variant as a per-page one with an empty `fonts` array (`_build_manifest.py:25-27`).

### Words databases and unmanifested root assets

Three SQLite DBs sit at repo root and are referenced by bare filename: `qpc-v4.db`, `qpc-v1.db`, `qpc-hafs.db` (`manifest.json:7`, `manifest.json:4267`).

**Four root-level font files are tracked but absent from `manifest.json`** — `QCF_SurahHeader_COLOR-Regular.ttf`, `surah_names.ttf`, `surah-name-v4.ttf`, `quran-common.ttf` (verified absent by name search over `manifest.json` at `4f8972d`, 2026-08-02). They are real, published bytes with no manifest entry, no hash, and no size — a consumer wanting them must hard-code the path. `README.md:11` documents only the `QCF_*.ttf` family of these.

## External integrations

- **`raw.githubusercontent.com`** — the delivery CDN. `baseUrl` is the raw-content prefix for one git ref (`_build_manifest.py:326-328`), so every path field in the manifest is repo-relative and resolves as `baseUrl + <path>`: a per-page font is `baseUrl + fontDir + filename`, a words DB or the license is `baseUrl + filename`.
- **`static-cdn.tarteel.ai` (QUL)** — upstream source of the 604 V4-tajweed page fonts, hit only by the one-shot fetcher, never at runtime (`_fetch_v4_tajweed.py:15`).
- **GitHub Releases** — the auto-release workflow creates one release per tag via `gh release create` (`.github/workflows/auto-release.yml:103`).

### The `baseUrl` / tag-pinning contract

This is the contract consumers depend on, and it is stated in the builder's own docstring (`_build_manifest.py:36-42`):

- `--ref` is baked into `baseUrl`. It **must** match the git tag created alongside that manifest, because the consuming client SHA-verifies font bytes and therefore the tag has to point at the commit containing this manifest (`_build_manifest.py:37-40`).
- Release invocation is explicit in the docstring: `python3 _build_manifest.py --ref qari-assets-6 --release-tag v1.4.0` (`_build_manifest.py:35`).
- Both flags fall back to env vars `QARI_ASSETS_REF` and `QARI_ASSETS_RELEASE_TAG`, then to the module defaults (`_build_manifest.py:44-45`, `_build_manifest.py:303-320`).
- The default ref `main` is a **development-only** setting — it makes the CDN serve whatever is latest on main, which is by definition unpinned (`_build_manifest.py:40-42`, `_build_manifest.py:68`).
- There are **two independent version namespaces**: `releaseTag` (`v1.4.0`, hand-set, semver-shaped) and the `qari-assets-N` git tag that CI cuts. Only the latter appears in `baseUrl`, and only the latter is what a consumer actually pins.

## Build / deploy / CI

One workflow: `Auto-tag + release on main` (`.github/workflows/auto-release.yml:1`). Its stated purpose is to give the consuming app a stable anchor per main-move without anyone touching the Releases page by hand (`.github/workflows/auto-release.yml:3-6`).

**Trigger, verbatim** (`.github/workflows/auto-release.yml:13-28`):

```yaml
on:
  push:
    branches: [main]
    # Optional path filter — uncomment to skip releases on doc-only commits.
    # When enabled, README tweaks and build-script changes won't burn a
    # tag number. Asset/manifest changes will still trigger a release.
    # paths:
    #   - 'manifest.json'
    #   - 'fonts/**'
    #   - 'qpc-*.db'
    #   - '*.ttf'
    #   - '*.otf'
    #   - 'LICENSE.txt'
  # Manual fallback for backfilling missed releases or recovering from
  # an aborted run. Same behavior as a push.
  workflow_dispatch:
```

**Versioning scheme.** Highest existing `qari-assets-N` plus one; gaps in the sequence are tolerated by design (`.github/workflows/auto-release.yml:9-11`). The bumper lists `qari-assets-*`, filters strictly on `^qari-assets-[0-9]+$` to defend against ad-hoc styles like `qari-assets-rc1`, sorts numerically, and takes the tail (`.github/workflows/auto-release.yml:62-67`); an empty result defaults to `0`, so the first run cuts `qari-assets-1` (`.github/workflows/auto-release.yml:68-70`).

**Opt-out.** A commit-message flag, evaluated as a job-level `if` (`.github/workflows/auto-release.yml:46`):

```yaml
if: "!contains(github.event.head_commit.message, '[skip release]')"
```

It is a substring test against the message of the commit that lands on main, intended for cases where a release is deliberately unwanted (`.github/workflows/auto-release.yml:44-46`).

**Job shape.** Serialized by a `concurrency` group with `cancel-in-progress: false`, because half-released tags are worse than late releases (`.github/workflows/auto-release.yml:30-35`). Needs `contents: write` for both the tag push and the release creation (`.github/workflows/auto-release.yml:37-39`). Checks out with `fetch-depth: 0` because shallow clones carry no tags (`.github/workflows/auto-release.yml:48-53`). Creates an **annotated** tag as `github-actions[bot]` so the release page can show the auto-release message next to the generated notes (`.github/workflows/auto-release.yml:83-88`), then calls `gh release create --generate-notes`, adding `--notes-start-tag <previous>` when a previous tag resolves (`.github/workflows/auto-release.yml:102-111`).

**Tag reality at `4f8972d`.** Seven tags exist: `qari-assets`, then `qari-assets-2` … `qari-assets-7`. `qari-assets-7` points at `4f8972d`, the current `origin/main` head (`tag qari-assets-7`). `qari-assets-6` points at merge commit `a031010`, the commit that introduced this workflow (`tag qari-assets-6`). Tags `qari-assets` … `qari-assets-5` are lightweight and predate the workflow; `qari-assets-6` and `qari-assets-7` are annotated objects, matching the `git tag -a` at `.github/workflows/auto-release.yml:87`.

**The pipeline never rebuilds the manifest.** `manifest.json` is committed by hand; no workflow step runs `_build_manifest.py` — confirmed absent from `.github/workflows/auto-release.yml` at `4f8972d`, 2026-08-02. The regeneration check lives in [`ops/verify.md`](../ops/verify.md) as a local command, not in CI.

## Gotchas (each with file:line evidence)

1. **The published manifest is one tag behind its own release.** `baseUrl` pins `qari-assets-6` (`manifest.json:5`) while `origin/main` is tagged `qari-assets-7` (`tag qari-assets-7`). The docs-only commit `4f8972d` burned tag 7 without a manifest rebuild, so a consumer pinned to `qari-assets-7` fetches a manifest whose asset URLs resolve under `qari-assets-6`. Harmless only because the asset bytes are identical between the two tags.
2. **The paths filter is commented out, so every push to main burns a tag number** (`.github/workflows/auto-release.yml:16-25`). This is the direct cause of gotcha 1 and is the repo's most consequential known caveat. Until it is re-enabled, doc-only merges must carry `[skip release]`.
3. **The bumper ignores the un-numbered bootstrap tag.** `qari-assets` (no suffix) exists but is filtered out by `^qari-assets-[0-9]+$` (`.github/workflows/auto-release.yml:63`), so it never participates in numbering.
4. **The workflow comment about a missing `qari-assets-4` is stale.** The comment states that tag was never cut (`.github/workflows/auto-release.yml:9-11`), but `qari-assets-4` exists, pointing at commit `744521e` ("Add files via upload") (`tag qari-assets-4`). The `max + 1` logic tolerates gaps regardless, so this is a documentation defect, not a behavioral one.
5. **Manifest builds are all-or-nothing.** Any bad page in any variant — missing file (`_build_manifest.py:208`), wrong sfnt magic (`_build_manifest.py:213`), or a family name that does not match `familyPattern` (`_build_manifest.py:219-221`) — collects into `all_bad` and exits 1 without writing (`_build_manifest.py:345-349`). A missing single-font file both drops the variant and registers a failure (`_build_manifest.py:254-256`).
6. **Family-name parsing is platform-ID sensitive.** `_parse_family` decodes UTF-16BE for platformID 0 and 3 and mac-roman only for platformID 1; a prior version lumped platform 0 in with mac-roman and produced garbled family strings for the DigitalKhatt OTFs (`_build_manifest.py:156-162`). Any new OTF whose first `name` record uses an unexpected platform is the likely suspect if family validation fails.
7. **Per-page family matching is loose by design.** V4 families carry a trailing `_COLOR`, so the check accepts an exact match *or* a prefix match on the pattern with trailing underscores stripped (`_build_manifest.py:217-221`) — a font named `QCF4001_ANYTHING` would pass.
8. **Four root fonts ship unmanifested** (see Data layer) — no hash, no size, no schema entry.

## Licensing

- `LICENSE.txt` is the KFGQPC Electronic End-User License Agreement (`LICENSE.txt:1`), copyright 2009 King Fahd Glorious Quran Printing Complex (`LICENSE.txt:5`). It grants free-of-cost rights to use, copy and distribute (`LICENSE.txt:7`), forbids sale, modification, translation, reverse engineering and decompilation (`LICENSE.txt:9`), disclaims all warranty and liability (`LICENSE.txt:11`), and points at qurancomplex.org for the full text (`LICENSE.txt:13`).
- The license is a first-class published artifact: `LICENSE_FILE` is a build constant (`_build_manifest.py:61`) and the manifest publishes its filename, SHA-256 and size so consumers can verify the exact terms they received (`manifest.json:8570-8574`, `_build_manifest.py:366-370`).
- `README.md:16-18` is the pointer of record: it directs readers to `LICENSE.txt` and states that bundled third-party Quranic fonts retain their own upstream licenses, which must be consulted at source before redistribution.
- **No per-font license files exist in this repo.** The only license file tracked at `4f8972d` is `LICENSE.txt`; `fonts/dk-v1/`, `fonts/dk-v2/` and `fonts/nastaleeq/` each contain exactly one font binary and nothing else (verified by directory listing, 2026-08-02). So the DigitalKhatt fonts and the QUL-sourced V4-tajweed set (`_fetch_v4_tajweed.py:15`) carry no vendored license text here — `README.md:17-18` is the whole of the in-repo guidance for them.

## Maintenance Log
| Date | Commits Covered | Notable Changes |
|---|---|---|
| 2026-08-02 | `4f8972d` (baseline — 26 commits on `origin/main`, 2026-05-16 → 2026-06-28) | Initial code-verified baseline: manifest schema v4 documented field-by-field, five variants across two structural shapes, `baseUrl`/tag pinning contract, auto-release pipeline, licensing pointers. Two live defects recorded: manifest `baseUrl` one tag behind `qari-assets-7`, and the commented-out `paths:` filter that causes it. |
