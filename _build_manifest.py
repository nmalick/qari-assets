"""Build manifest.json (schemaVersion 4) by scanning on-disk variant dirs.

Two variant shapes:

  * **per-page**     — V1 and V4 use PUA codepoints + 604 per-page fonts
                       (different glyph encoding per page; can't share fonts
                       across pages). Each variant pairs with its own
                       PUA-encoded words DB.
  * **single-font**  — V2 DK, V1 + Tajweed, Nastaleeq use Unicode shaping +
                       one OTF/TTF per variant + a shared Hafs Unicode words
                       DB (`qpc-hafs.db`). One font handles all 604 pages,
                       Tajweed (when present) is layered as character-level
                       overlay rather than baked into a COLR table.

Adding a new variant: drop its assets in the right place, append an entry to
`_VARIANTS` below.

  * per-page:    `fonts/<id>/p1.ttf` … `p604.ttf` + words DB at repo root
  * single-font: `fonts/<id>/<file>.{otf,ttf}` + words DB at repo root
                 (the shared `qpc-hafs.db` is fine — manifest entries can
                 reference the same DB filename; build script handles it)

The top-level `wordsDb` field is preserved (pointing at the V4 DB) so
schemaVersion-2 clients still parse — they keep their existing behavior.
The schema bump from 3 → 4 is gated by the new `singleFont` block: a v3
parser will fail-loud rather than silently misinterpret a single-font
variant as a per-page one with an empty `fonts` array.

Usage (during development — defaults are fine):

    python3 _build_manifest.py

Usage (cutting a release):

    python3 _build_manifest.py --ref qari-assets-6 --release-tag v1.4.0

The `--ref` value is baked into the manifest's `baseUrl` field. Match it
to the git tag you intend to create alongside this manifest (the Flutter
client SHA-verifies font bytes, so the tag must point at the commit
containing this manifest). Defaults — when no flag and no env var is set
— to `main`, which is fine for development (raw.githubusercontent.com
serves the latest commit on main).

Both flags also accept env-var fallbacks: `QARI_ASSETS_REF` and
`QARI_ASSETS_RELEASE_TAG`.

The script reads/writes paths relative to its own location, so it works
regardless of the cwd.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import struct
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(REPO_ROOT, "manifest.json")
LICENSE_FILE = "LICENSE.txt"
TOTAL_PAGES = 604
TTF_MAGICS = {b"\x00\x01\x00\x00", b"true", b"OTTO"}

# Defaults when no CLI flag and no env var is set. `main` resolves on the
# raw.githubusercontent.com CDN to the latest commit, which is what
# development reads should see.
_DEFAULT_REF = "main"
_DEFAULT_RELEASE_TAG = "v1.4.0"

# Variant id → variant config. Schema v4 dispatches on `mode`:
#
#   `per_page`   — 604 per-page fonts under `fontDir`, families follow
#                  `familyPattern` (`{NNN}` is a zero-padded page number).
#   `single_font` — one OTF/TTF at `fontDir + singleFontFile`. `familyPattern`
#                  is ignored (set to None); manifest emits a `singleFont`
#                  block instead of populated `fonts`.
_VARIANTS = {
    "v4-tajweed": {
        "displayName": "Madina Mushaf v4 1441H",
        "fontDir": "fonts/v4-tajweed/",
        "familyPattern": "QCF4{NNN}_COLOR",
        "tajweedColored": True,
        "wordsDb": "qpc-v4.db",
        "mode": "per_page",
    },
    "v2-dk": {
        "displayName": "KFGQPC V2 1421H print",
        "fontDir": "fonts/dk-v2/",
        "familyPattern": None,
        "tajweedColored": True,
        "wordsDb": "qpc-hafs.db",
        "mode": "single_font",
        "singleFontFile": "DigitalKhattV2.otf",
        "pageCount": TOTAL_PAGES,
    },
    "v1-madina": {
        "displayName": "Madina Mushaf v1 1405H",
        "fontDir": "fonts/v1/",
        "familyPattern": "QCF_P{NNN}",
        "tajweedColored": False,
        "wordsDb": "qpc-v1.db",
        "mode": "per_page",
    },
    "v1-madina-tajweed": {
        "displayName": "Madina Mushaf v1 + Tajweed",
        "fontDir": "fonts/dk-v1/",
        "familyPattern": None,
        "tajweedColored": True,
        "wordsDb": "qpc-hafs.db",
        "mode": "single_font",
        "singleFontFile": "DigitalKhattQuranicV1.otf",
        "pageCount": TOTAL_PAGES,
    },
    "nastaleeq": {
        "displayName": "KFGQPC Nastaleeq 15 lines",
        "fontDir": "fonts/nastaleeq/",
        "familyPattern": None,
        "tajweedColored": True,
        "wordsDb": "qpc-hafs.db",
        "mode": "single_font",
        "singleFontFile": "KFGQPCNastaleeq-Regular.ttf",
        "pageCount": TOTAL_PAGES,
    },
}

# The variant whose words DB also lives at the top level for schemaVersion 2/3
# back-compat. Clients on v2/v3 ignore per-variant `wordsDb` for unknown variant
# ids and read this instead — they get the V4 DB, which matches their existing
# behavior for the V4 default.
_BACKCOMPAT_WORDS_DB_VARIANT = "v4-tajweed"


def _parse_family(path):
    """Parse the TTF `name` table and return the family name (nameID=1)."""
    with open(path, "rb") as f:
        data = f.read()
    num_tables = struct.unpack(">H", data[4:6])[0]
    name_off = None
    for i in range(num_tables):
        off = 12 + i * 16
        tag = data[off:off + 4]
        if tag == b"name":
            name_off = struct.unpack(">I", data[off + 8:off + 12])[0]
            break
    if name_off is None:
        return ""
    _, count, string_offset = struct.unpack(">HHH", data[name_off:name_off + 6])
    storage = name_off + string_offset
    for i in range(count):
        rec = name_off + 6 + i * 12
        platform_id, _encoding_id, _language_id, name_id, length, offset = struct.unpack(
            ">HHHHHH", data[rec:rec + 12]
        )
        if name_id == 1:
            s = data[storage + offset:storage + offset + length]
            # platformID 0 (Unicode) and 3 (Windows) both store strings as
            # UTF-16BE. Only platformID 1 (Mac) uses single-byte mac-roman.
            # Prior versions of this script lumped platform 0 in with mac-roman
            # which produced garbled \x00-interleaved family strings for OTFs
            # whose first name record is platform 0 (e.g. the Digital Khatt
            # fonts) — fixed.
            try:
                return s.decode(
                    "mac-roman" if platform_id == 1 else "utf-16-be",
                    errors="replace",
                )
            except Exception:
                continue
    return ""


def _file_sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest(), os.path.getsize(path)


def _words_db_block(filename):
    """Build the {filename, sha256, sizeBytes, rowCount} block for a words DB."""
    abs_path = os.path.join(REPO_ROOT, filename)
    sha, size = _file_sha256(abs_path)
    row_count = None
    try:
        con = sqlite3.connect(abs_path)
        row_count = con.execute("SELECT COUNT(*) FROM words").fetchone()[0]
        con.close()
    except Exception as e:
        print(f"  ⚠️  {filename}: could not query row_count ({e})", file=sys.stderr)
    block = {"filename": filename, "sha256": sha, "sizeBytes": size}
    if row_count is not None:
        block["rowCount"] = row_count
    return block


def _build_per_page_variant(cfg):
    """Build a variant entry from a per-page font directory."""
    display = cfg["displayName"]
    font_dir = cfg["fontDir"]
    family_pattern = cfg["familyPattern"]
    fonts = []
    total = 0
    bad = []
    abs_dir = os.path.join(REPO_ROOT, font_dir)
    for p in range(1, TOTAL_PAGES + 1):
        filename = f"p{p}.ttf"
        path = os.path.join(abs_dir, filename)
        if not os.path.exists(path):
            bad.append((p, "missing file"))
            continue
        with open(path, "rb") as f:
            head = f.read(4)
        if head not in TTF_MAGICS:
            bad.append((p, f"bad TTF magic {head!r}"))
            continue
        family = _parse_family(path)
        expected = family_pattern.replace("{NNN}", f"{p:03d}")
        # V4 family names have trailing `_COLOR` suffix; V1 is exact.
        # Accept either a prefix match (V4) or exact match (V1).
        if not (family == expected or family.startswith(expected.rstrip("_"))):
            bad.append(
                (p, f"family mismatch: expected {expected!r} got {family!r}"))
            continue
        sha, size = _file_sha256(path)
        fonts.append({
            "page": p,
            "filename": filename,
            "family": family,
            "sha256": sha,
            "sizeBytes": size,
        })
        total += size

    return {
        "displayName": display,
        "pageCount": TOTAL_PAGES,
        "fontDir": font_dir,
        "familyPattern": family_pattern,
        "tajweedColored": cfg["tajweedColored"],
        "fontCount": len(fonts),
        "totalSizeBytes": total,
        "wordsDb": _words_db_block(cfg["wordsDb"]),
        "fonts": fonts,
    }, bad


def _build_single_font_variant(cfg):
    """Build a variant entry from a single OTF/TTF + shared words DB."""
    display = cfg["displayName"]
    font_dir = cfg["fontDir"]
    font_file = cfg["singleFontFile"]
    page_count = cfg.get("pageCount", TOTAL_PAGES)
    bad = []
    font_path = os.path.join(REPO_ROOT, font_dir, font_file)
    if not os.path.exists(font_path):
        bad.append((0, f"missing single font {font_dir}{font_file}"))
        return None, bad
    with open(font_path, "rb") as f:
        head = f.read(4)
    if head not in TTF_MAGICS:
        bad.append((0, f"bad TTF/OTF magic {head!r} for {font_file}"))
        return None, bad
    family = _parse_family(font_path)
    if not family:
        bad.append((0, f"could not parse family name from {font_file}"))
        return None, bad
    sha, size = _file_sha256(font_path)
    return {
        "displayName": display,
        "pageCount": page_count,
        "fontDir": font_dir,
        "familyPattern": None,
        "tajweedColored": cfg["tajweedColored"],
        "fontCount": 1,
        "totalSizeBytes": size,
        "wordsDb": _words_db_block(cfg["wordsDb"]),
        "singleFont": {
            "filename": font_file,
            "family": family,
            "sha256": sha,
            "sizeBytes": size,
        },
        # Empty per-page list is the explicit signal to v4 parsers that this
        # variant is single-font-only. v3 parsers will reject the manifest
        # outright via the schemaVersion check.
        "fonts": [],
    }, bad


def _build_variant(variant_id, cfg):
    mode = cfg["mode"]
    if mode == "per_page":
        return _build_per_page_variant(cfg)
    elif mode == "single_font":
        return _build_single_font_variant(cfg)
    else:
        raise ValueError(f"unknown variant mode {mode!r} for {variant_id}")


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Build manifest.json (schemaVersion 4) for qari-assets.",
    )
    parser.add_argument(
        "--ref",
        default=os.environ.get("QARI_ASSETS_REF", _DEFAULT_REF),
        help=(
            "Git ref baked into the manifest's `baseUrl` field "
            "(e.g. qari-assets-6, main). Falls back to the QARI_ASSETS_REF "
            f"env var, then to {_DEFAULT_REF!r}."
        ),
    )
    parser.add_argument(
        "--release-tag",
        default=os.environ.get("QARI_ASSETS_RELEASE_TAG", _DEFAULT_RELEASE_TAG),
        help=(
            "Value for the manifest's `releaseTag` field "
            "(e.g. v1.4.0). Falls back to the QARI_ASSETS_RELEASE_TAG env "
            f"var, then to {_DEFAULT_RELEASE_TAG!r}."
        ),
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    base_url = (
        f"https://raw.githubusercontent.com/nmalick/qari-assets/{args.ref}/"
    )
    print(f"  baseUrl:    {base_url}")
    print(f"  releaseTag: {args.release_tag}")
    variants = {}
    all_bad = []
    for vid, cfg in _VARIANTS.items():
        v, bad = _build_variant(vid, cfg)
        all_bad.extend((vid, p, why) for p, why in bad)
        if v is None:
            continue
        variants[vid] = v
        wb = v["wordsDb"]
        mode_marker = "1×" if cfg["mode"] == "single_font" else f"{v['fontCount']}×"
        print(f"  {vid}: {mode_marker} fonts, "
              f"{v['totalSizeBytes'] / 1024 / 1024:.2f} MB; "
              f"wordsDb {wb['filename']} ({wb.get('rowCount','?')} rows)")

    if all_bad:
        print("\nVALIDATION FAILURES:", file=sys.stderr)
        for vid, p, why in all_bad:
            print(f"  {vid} p{p}: {why}", file=sys.stderr)
        return 1

    license_path = os.path.join(REPO_ROOT, LICENSE_FILE)
    license_sha, license_size = _file_sha256(license_path)

    # Top-level wordsDb for schemaVersion-2/3 client back-compat. New clients
    # on v4 ignore this and read each variant's own wordsDb block.
    backcompat_filename = _VARIANTS[_BACKCOMPAT_WORDS_DB_VARIANT]["wordsDb"]
    top_level_words_db = _words_db_block(backcompat_filename)

    manifest = {
        "schemaVersion": 4,
        "releaseTag": args.release_tag,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baseUrl": base_url,
        "wordsDb": top_level_words_db,
        "variants": variants,
        "license": {
            "filename": LICENSE_FILE,
            "sha256": license_sha,
            "sizeBytes": license_size,
        },
    }

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nWrote {os.path.relpath(MANIFEST_PATH, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
