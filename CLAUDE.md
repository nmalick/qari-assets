# qari-assets — router

Quranic typesetting asset repo (fonts + word-position databases + tajweed data) consumed by
a Flutter client that pins release tags. PUBLIC repo — everything here is published.

**All documentation lives in [`project-os/`](project-os/DIRECTORY.md).** The manifest/release
contract doc (`project-os/engineering/architecture.md`) is the source of truth — read it
before reading the scripts. `README.md` stays the GitHub landing page.

- Verify: use the VERIFY_CMD in `project-os/ops/verify.md` (regen check with volatile-field ignores — the naive byte-level diff is a false RED by design; see the Past-learning note there).
- ⚠️ ANY push to main auto-cuts a release (`.github/workflows/auto-release.yml`, paths filter
  currently commented out) — doc-only merges need `[skip release]` in the merge commit subject.
