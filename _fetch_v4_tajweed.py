"""Parallel fetcher for the 604 V4-tajweed per-page fonts from QUL CDN.

Downloads -> fonts/v4-tajweed/p{N}.ttf, verifies each is a real TTF (sfnt magic),
re-tries transient failures, and prints a final report. No third-party deps.
"""
from __future__ import annotations
import concurrent.futures as cf
import hashlib
import os
import sys
import time
import urllib.request
import urllib.error

BASE = "https://static-cdn.tarteel.ai/qul/fonts/quran_fonts/v4-tajweed/ttf"
OUT_DIR = "fonts/v4-tajweed"
TOTAL_PAGES = 604
MAX_WORKERS = 24
MAX_RETRIES = 4
TIMEOUT = 30
TTF_MAGICS = {b"\x00\x01\x00\x00", b"true", b"OTTO"}  # truetype / mac / cff

os.makedirs(OUT_DIR, exist_ok=True)


def fetch(page: int) -> tuple[int, int, str, str]:
    """Return (page, bytes, sha256_hex, status). status='ok' or error reason."""
    url = f"{BASE}/p{page}.ttf"
    path = os.path.join(OUT_DIR, f"p{page}.ttf")
    last_err = ""
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "qari-assets-fetcher/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read()
            if len(data) < 200:
                last_err = f"too small ({len(data)} bytes)"
                continue
            magic = data[:4]
            if magic not in TTF_MAGICS:
                last_err = f"bad magic {magic!r}"
                continue
            with open(path, "wb") as f:
                f.write(data)
            return page, len(data), hashlib.sha256(data).hexdigest(), "ok"
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code == 404:
                break  # don't retry 404
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(0.5 * (attempt + 1))
    return page, 0, "", last_err or "unknown"


def main() -> int:
    print(f"Fetching {TOTAL_PAGES} pages from {BASE} with {MAX_WORKERS} workers...")
    start = time.time()
    failed: list[tuple[int, str]] = []
    total_bytes = 0
    pages_ok = 0
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(fetch, p) for p in range(1, TOTAL_PAGES + 1)]
        for fut in cf.as_completed(futures):
            page, nbytes, sha, status = fut.result()
            if status == "ok":
                pages_ok += 1
                total_bytes += nbytes
                if pages_ok % 50 == 0:
                    print(f"  ... {pages_ok}/{TOTAL_PAGES} fetched ({total_bytes/1024/1024:.1f} MB so far)")
            else:
                failed.append((page, status))
                print(f"  FAIL p{page}: {status}", file=sys.stderr)
    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s — {pages_ok}/{TOTAL_PAGES} ok, {len(failed)} failed, {total_bytes/1024/1024:.1f} MB total")
    if failed:
        print("\nFailed pages:")
        for p, s in sorted(failed):
            print(f"  p{p}  {s}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
