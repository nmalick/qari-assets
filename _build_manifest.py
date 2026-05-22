"""Build manifest.json (schemaVersion 3) by scanning on-disk variant dirs.

Walks each `fonts/<variantId>/` directory in this repo and pairs it with the
corresponding words DB (one per variant — V1 and V4 use different PUA glyph
encodings, so a shared words DB would render the wrong ligatures in the
mismatched font set). Emits a fresh manifest.json with per-page SHA-256s,
sizes, and per-variant `wordsDb` blocks.

Adding a new variant: drop its TTFs under `fonts/<new-id>/`, commit its
words DB at the repo root, and append an entry to `_VARIANTS` below.

The top-level `wordsDb` field is preserved (pointing at the V4 DB) so
clients still on schemaVersion 2 keep parsing — they'll use the V4 DB for
both variants (the V1 rendering bug pre-fix behavior), which is no worse
than what they had before.

Run from anywhere:

    python3 _build_manifest.py

The script reads/writes paths relative to its own location, so it works
regardless of the cwd.
"""
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

# Variant id → variant config. Each value is a tuple:
#   (displayName, fontDir, familyPattern, tajweedColored, wordsDbFilename)
# `familyPattern` uses {NNN} as a zero-padded 3-digit page number.
_VARIANTS = {
    "v1-madina": (
        "Madina Mushaf v1 1405H",
        "fonts/v1/",
        "QCF_P{NNN}",
        False,
        "qpc-v1.db",
    ),
    "v4-tajweed": (
        "Madina Mushaf v4 1441H",
        "fonts/v4-tajweed/",
        "QCF4{NNN}_COLOR",
        True,
        "qpc-v4.db",
    ),
}

# The variant whose words DB also lives at the top level for schemaVersion 2
# back-compat. Clients on v2 ignore the per-variant `wordsDb` and read this
# instead — they get the V4 DB, which is the same as their existing behavior.
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
            try:
                return s.decode(
                    "utf-16-be" if platform_id == 3 else "mac-roman",
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


def _build_variant(variant_id, display_name, font_dir, family_pattern,
                   tajweed_colored, words_db_filename):
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
        "displayName": display_name,
        "pageCount": TOTAL_PAGES,
        "fontDir": font_dir,
        "familyPattern": family_pattern,
        "tajweedColored": tajweed_colored,
        "fontCount": len(fonts),
        "totalSizeBytes": total,
        "wordsDb": _words_db_block(words_db_filename),
        "fonts": fonts,
    }, bad


def main():
    variants = {}
    all_bad = []
    for vid, (display, font_dir, pattern, colored,
              words_db_filename) in _VARIANTS.items():
        v, bad = _build_variant(vid, display, font_dir, pattern, colored,
                                words_db_filename)
        all_bad.extend((vid, p, why) for p, why in bad)
        variants[vid] = v
        wb = v["wordsDb"]
        print(f"  {vid}: {v['fontCount']} fonts, "
              f"{v['totalSizeBytes'] / 1024 / 1024:.1f} MB; "
              f"wordsDb {wb['filename']} ({wb.get('rowCount','?')} rows)")

    if all_bad:
        print("\nVALIDATION FAILURES:", file=sys.stderr)
        for vid, p, why in all_bad:
            print(f"  {vid} p{p}: {why}", file=sys.stderr)
        return 1

    license_path = os.path.join(REPO_ROOT, LICENSE_FILE)
    license_sha, license_size = _file_sha256(license_path)

    # Top-level wordsDb for schemaVersion-2 client back-compat. New clients
    # on v3 ignore this and read each variant's own wordsDb block.
    backcompat_filename = _VARIANTS[_BACKCOMPAT_WORDS_DB_VARIANT][4]
    top_level_words_db = _words_db_block(backcompat_filename)

    manifest = {
        "schemaVersion": 3,
        "releaseTag": "v1.2.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baseUrl":
            "https://raw.githubusercontent.com/nmalick/qari-assets/qari-assets-4/",
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
