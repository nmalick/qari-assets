# qari-assets

Fonts and Quranic typesetting/Tajweed data assets for the [Qari](https://github.com/nmalick/Qari)
Tajweed Helper app. Kept in a separate repository so the app repo stays lean and the assets can be
versioned and released independently.

## Contents
| Path | Contents |
|---|---|
| `fonts/` | Quranic fonts (e.g. DigitalKhatt v1/v2, KFGQPC Nastaleeq, per-page mushaf fonts) |
| `QCF_*.ttf` | Surah header / glyph fonts |
| `_fetch_*.py`, `_build_manifest.py` | Scripts to fetch and build asset manifests |
| `.github/workflows/` | Automated release workflow |

## Licensing
See [`LICENSE.txt`](LICENSE.txt). Note that bundled third-party Quranic fonts retain their own
upstream licenses — consult each font's source before redistribution.

## Usage
Consumed by the Qari app. Releases are produced via the GitHub Actions `auto-release` workflow.
