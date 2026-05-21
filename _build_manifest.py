"""Build manifest.json (schemaVersion 2) by scanning on-disk variant dirs.

Walks each `fonts/<variantId>/` directory in this repo and emits a fresh
manifest.json with per-page SHA-256s and sizes. Adding a new variant is a
matter of dropping its TTFs under `fonts/<new-id>/` and adding an entry
to `_VARIANTS` below.

Run from the repo root:

    python3 _build_manifest.py

The script reads/writes paths relative to its own location, so it works
regardless of the cwd.
"""
import hashlib
import json
import os
import struct
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(REPO_ROOT, "manifest.json")
WORDS_DB = "qpc-v4.db"
LICENSE_FILE = "LICENSE.txt"
TOTAL_PAGES = 604
TTF_MAGICS = {b"\x00\x01\x00\x00", b"true", b"OTTO"}

# Variant id → (displayName, fontDir, familyPattern, tajweedColored).
# `familyPattern` uses {NNN} as a zero-padded 3-digit page number.
_VARIANTS = {
    "v1-madina": (
        "Madina Mushaf V1 (1405H)",
        "fonts/v1/",
        "QCF_P{NNN}",
        False,
    ),
    "v4-tajweed": (
        "QPC v4 Tajweed (1441H)",
        "fonts/v4-tajweed/",
        "QCF4{NNN}_COLOR",
        True,
    ),
}


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


def _build_variant(variant_id, display_name, font_dir, family_pattern, tajweed_colored):
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
        "id": variant_id,
        "displayName": display_name,
        "pageCount": TOTAL_PAGES,
        "fontDir": font_dir,
        "familyPattern": family_pattern,
        "tajweedColored": tajweed_colored,
        "fontCount": len(fonts),
        "totalSizeBytes": total,
        "fonts": fonts,
    }, bad


def main():
    variants = {}
    all_bad = []
    for vid, (display, font_dir, pattern, colored) in _VARIANTS.items():
        v, bad = _build_variant(vid, display, font_dir, pattern, colored)
        all_bad.extend((vid, p, why) for p, why in bad)
        # Strip the duplicated `id` key — it's already the variant's map key.
        v.pop("id")
        variants[vid] = v
        print(f"  {vid}: {v['fontCount']} fonts, "
              f"{v['totalSizeBytes'] / 1024 / 1024:.1f} MB")

    if all_bad:
        print("\nVALIDATION FAILURES:", file=sys.stderr)
        for vid, p, why in all_bad:
            print(f"  {vid} p{p}: {why}", file=sys.stderr)
        return 1

    words_path = os.path.join(REPO_ROOT, WORDS_DB)
    words_sha, words_size = _file_sha256(words_path)

    license_path = os.path.join(REPO_ROOT, LICENSE_FILE)
    license_sha, license_size = _file_sha256(license_path)

    # Preserve the existing wordsDb `rowCount` if available so we don't
    # need to query SQLite from this script.
    row_count = None
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH) as f:
                existing = json.load(f)
            row_count = (existing.get("wordsDb") or {}).get("rowCount")
        except Exception:
            pass

    manifest = {
        "schemaVersion": 2,
        "releaseTag": "v1.1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baseUrl":
            "https://raw.githubusercontent.com/nmalick/qari-assets/qari-assets-2/",
        "wordsDb": {
            "filename": WORDS_DB,
            "sha256": words_sha,
            "sizeBytes": words_size,
            **({"rowCount": row_count} if row_count is not None else {}),
        },
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
