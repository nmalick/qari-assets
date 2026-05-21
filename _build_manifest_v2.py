"""Build manifest.json v2 with V1 + V4 variants.

Pulls existing V4 entries from the current manifest.json (to preserve exact
hashes/sizes), computes V1 entries from the local extracted /tmp/qpc-v1-fonts/,
and writes the v2 multi-variant manifest.
"""
import hashlib
import json
import os
import struct
import sys
from datetime import datetime, timezone

ASSETS_DIR = "/Users/malick/CascadeProjects/qari-assets"
V1_SRC_DIR = "/tmp/qpc-v1-fonts"
OLD_MANIFEST = os.path.join(ASSETS_DIR, "manifest.json")
NEW_MANIFEST = os.path.join(ASSETS_DIR, "manifest.json")
TOTAL_PAGES = 604


def family_via_struct(path):
    """Quick TTF name-table family parser (matches _build_manifest.py)."""
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
                return s.decode("utf-16-be" if platform_id == 3 else "mac-roman",
                                errors="replace")
            except Exception:
                continue
    return ""


def build_v1_entries():
    fonts = []
    bad = []
    total = 0
    for p in range(1, TOTAL_PAGES + 1):
        path = os.path.join(V1_SRC_DIR, f"p{p}.ttf")
        if not os.path.exists(path):
            bad.append((p, "missing"))
            continue
        with open(path, "rb") as f:
            data = f.read()
        fam = family_via_struct(path)
        expected = f"QCF_P{p:03d}"
        if fam != expected:
            bad.append((p, f"family mismatch: expected {expected} got {fam!r}"))
            continue
        fonts.append({
            "page": p,
            "filename": f"p{p}.ttf",
            "family": fam,
            "sha256": hashlib.sha256(data).hexdigest(),
            "sizeBytes": len(data),
        })
        total += len(data)
    return fonts, total, bad


def main():
    # Load old V4 entries verbatim
    with open(OLD_MANIFEST) as f:
        old = json.load(f)
    if old.get("schemaVersion") != 1:
        print(f"WARNING: existing manifest schemaVersion={old.get('schemaVersion')}, expected 1",
              file=sys.stderr)
    v4_fonts = old["fonts"]
    v4_total = old["totalSizeBytes"]
    words_db = old["wordsDb"]
    license_info = old["license"]
    assert len(v4_fonts) == TOTAL_PAGES, f"expected {TOTAL_PAGES} v4 fonts, got {len(v4_fonts)}"

    # Build V1 entries
    v1_fonts, v1_total, bad = build_v1_entries()
    if bad:
        print("V1 build failures:", file=sys.stderr)
        for p, why in bad:
            print(f"  p{p}: {why}", file=sys.stderr)
        return 1
    assert len(v1_fonts) == TOTAL_PAGES, f"expected {TOTAL_PAGES} v1 fonts, got {len(v1_fonts)}"

    manifest = {
        "schemaVersion": 2,
        "releaseTag": "v1.1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baseUrl": "https://raw.githubusercontent.com/nmalick/qari-assets/qari-assets/",
        "wordsDb": words_db,
        "variants": {
            "v1-madina": {
                "displayName": "Madina Mushaf V1 (1405H)",
                "pageCount": TOTAL_PAGES,
                "fontDir": "fonts/v1/",
                "familyPattern": "QCF_P{NNN}",
                "tajweedColored": False,
                "fontCount": len(v1_fonts),
                "totalSizeBytes": v1_total,
                "fonts": v1_fonts,
            },
            "v4-tajweed": {
                "displayName": "QPC v4 Tajweed (1441H)",
                "pageCount": TOTAL_PAGES,
                "fontDir": "fonts/v4-tajweed/",
                "familyPattern": "QCF4{NNN}_COLOR",
                "tajweedColored": True,
                "fontCount": len(v4_fonts),
                "totalSizeBytes": v4_total,
                "fonts": v4_fonts,
            },
        },
        "license": license_info,
    }

    with open(NEW_MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote {NEW_MANIFEST}")
    print(f"  V1: {len(v1_fonts)} fonts, {v1_total / 1024 / 1024:.1f} MB")
    print(f"  V4: {len(v4_fonts)} fonts, {v4_total / 1024 / 1024:.1f} MB")
    print(f"  Sample V1 entries:")
    for p in (1, 100, 604):
        e = v1_fonts[p - 1]
        print(f"    p{p:>3}  {e['family']:10s}  {e['sizeBytes']:>7}  sha256={e['sha256'][:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
