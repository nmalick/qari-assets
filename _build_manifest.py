"""Build manifest.json for the v4-tajweed font set.

Produces a manifest matching the schema in qari/plans/qpc-traditional-remote-assets.md
section 1.4, adapted for the per-page model and the v4-tajweed variant.
"""
import hashlib
import json
import os
import struct
import sys
from datetime import datetime, timezone

FONT_DIR = "fonts/v4-tajweed"
OUT_PATH = "manifest.json"
TOTAL_PAGES = 604
TTF_MAGICS = {b"\x00\x01\x00\x00", b"true", b"OTTO"}


def parse_family(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    num_tables = struct.unpack(">H", data[4:6])[0]
    name_off, name_len = None, None
    for i in range(num_tables):
        off = 12 + i * 16
        tag = data[off:off + 4]
        if tag == b"name":
            name_off = struct.unpack(">I", data[off + 8:off + 12])[0]
            name_len = struct.unpack(">I", data[off + 12:off + 16])[0]
            break
    if not name_off:
        return ""
    fmt, count, string_offset = struct.unpack(">HHH", data[name_off:name_off + 6])
    storage = name_off + string_offset
    for i in range(count):
        rec = name_off + 6 + i * 12
        platform_id, encoding_id, language_id, name_id, length, offset = struct.unpack(
            ">HHHHHH", data[rec:rec + 12]
        )
        if name_id == 1:
            s = data[storage + offset:storage + offset + length]
            try:
                return s.decode("utf-16-be" if platform_id == 3 else "mac-roman", errors="replace")
            except Exception:
                continue
    return ""


def main() -> int:
    fonts = []
    bad = []
    for p in range(1, TOTAL_PAGES + 1):
        path = os.path.join(FONT_DIR, f"p{p}.ttf")
        if not os.path.exists(path):
            bad.append((p, "missing file"))
            continue
        with open(path, "rb") as f:
            data = f.read()
        if data[:4] not in TTF_MAGICS:
            bad.append((p, f"bad magic {data[:4]!r}"))
            continue
        fam = parse_family(path)
        expected_family_prefix = f"QCF4{p:03d}_"
        if not fam.startswith(expected_family_prefix):
            bad.append((p, f"family mismatch: expected {expected_family_prefix}* got {fam!r}"))
            continue
        fonts.append({
            "page": p,
            "filename": f"p{p}.ttf",
            "family": fam,
            "sha256": hashlib.sha256(data).hexdigest(),
            "sizeBytes": len(data),
        })

    if bad:
        print("VALIDATION FAILURES:", file=sys.stderr)
        for p, why in bad:
            print(f"  p{p}: {why}", file=sys.stderr)
        return 1

    total_bytes = sum(f["sizeBytes"] for f in fonts)
    manifest = {
        "schemaVersion": 1,
        "releaseTag": "v1.0.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "variant": "v4-tajweed",
        "source": "https://static-cdn.tarteel.ai/qul/fonts/quran_fonts/v4-tajweed/ttf",
        "baseUrl": "https://github.com/nmalick/qari-assets/releases/download/v1.0.0",
        "fontCount": len(fonts),
        "totalSizeBytes": total_bytes,
        "fonts": fonts,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote {OUT_PATH} with {len(fonts)} fonts, {total_bytes / 1024 / 1024:.1f} MB total")
    # Spot-check a few
    print("\nSample entries:")
    for p in (1, 100, 300, 604):
        e = fonts[p - 1]
        print(f"  p{p:>3}  {e['family']:20s}  {e['sizeBytes']:>7} bytes  sha256={e['sha256'][:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
