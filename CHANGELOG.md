# Changelog

All notable project changes are documented here. The project follows semantic
versioning once a stable `1.x` release is declared.

## [Unreleased]

- Institutional handover and authority transfer.
- Continued observability, availability, and mixed-load hardening.
- Refreshed dependency baselines and expanded auditing to frontend build tools.
- Published a reproducible summary of the August schema benchmark.
- Migrated React Router to v7 and removed the engine's unused NLTK dependency,
  clearing all Python and npm dependency-audit findings without exceptions.
- Pinned CPU-only PyTorch wheels by container architecture, avoiding unsupported
  CUDA packages on ARM production hosts and enforcing `pip check` in image builds.
- Made KB packaging, import, readiness, and job admission fail closed; completed
  the real deployment validation gates; and fixed authenticated browser downloads.
- Added a documented developer-to-production release process and a backup-first,
  exact-revision routine deployment command with automatic image rollback.
- Upgraded the dashboard to Tailwind CSS 4 and patched `source-map-js`, clearing
  new high-severity npm audit findings (GHSA-vfj7-8cjw-p6xm, GHSA-68fv-2mgg-jv7q)
  without visual changes. The SPA now targets Safari 16.4+, Chrome 111+, and
  Firefox 128+.
- Raised the contrast of the shared filter tabs (emerald, amber and rose tones
  and the active count pill) to WCAG AA, and made card and section titles `h2`
  under the page `h1`, so automated accessibility checks of the review, ontology,
  admin, profile, activity, upload and export pages report no contrast or
  heading-order issues in these components.
- Added a read-only **Preview changes** view to the Export page (and
  `GET /api/v1/export/{study_id}/preview`) that compares the Harmonized CSV with
  the original upload: column renames and drops with their mapping decisions,
  grouped value changes, and a paged grid of changed cells with their cause.
- Fixed the Harmonized CSV silently reformatting untouched cells: it now keeps
  the uploaded text, so `NA` no longer becomes blank and `51` no longer becomes
  `51.0`.
- Every export now uses the same column for a schema field: a rejected mapping
  never fills one; a mapping a curator reviewed beats one the engine accepted
  on its own, which beats a pending suggestion; then higher confidence, then
  the column that comes first in the upload. The cBioPortal exports previously
  ranked by confidence alone, so they could take SAMPLE_ID from a rejected
  column or a field from an unreviewed suggestion, and ties depended on
  database order.
- cBioPortal exports now write yes/no attributes as `TRUE`/`FALSE`, which
  `validateData.py` requires; the bundled sample metadata failed validation
  before. The CI validator gate now covers a yes/no column.

## [0.1.0] - 2026-08-19

Initial public deployment of the complete GSoC 2026 application:

- human-in-the-loop schema and ontology review;
- versioned target schemas and ontology snapshots;
- personal and shared learned decisions;
- cBioPortal-compatible export and quality gates;
- JWT/RBAC authentication, audit history, and federation-lite;
- asynchronous arq jobs with retries, cancellation, progress, and backpressure;
- optional MCP server and LLM fallback;
- Docker/Caddy deployment, encrypted off-host backups, restore drill, Slack
  alert delivery, capacity reporting, rollback, and protected security CI;
- measured dashboard and real-ML operating limits.

[Unreleased]: https://github.com/sehyunohlab/MetaHarmonizerApp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sehyunohlab/MetaHarmonizerApp/releases/tag/v0.1.0
