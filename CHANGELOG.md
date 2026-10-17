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
- Engine updates are now tracked automatically: `backend/vendor/ENGINE_REF`
  records the exact upstream commit, a daily **Engine Watch** workflow starts
  **Engine Upgrade** when upstream `main` moves, and the KB is rebuilt after an
  upgrade that changes KB code. Fixed the scheduled KB refresh failing with
  `EACCES` when grafting the model cache over the one the build downloaded.
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
- The **Preview changes** grid (now **Exported values**) lists every row and
  every exported column by default; **Changed rows only**, **Changed columns
  only**, and the column picker narrow it. The preview API's `changed_only`
  now defaults to `false`.
- The export preview shows every change. **Changed columns only** also keeps
  renamed columns, whose headers are highlighted with the uploaded name struck
  through, and both filters show their counts. Every ontology term change is
  listed for its column; the 25-item limit now applies only to spreadsheet-safe
  escapes. Before, a study with 19 renamed columns and 30 ontology changes in
  one column showed only that column under **Changed columns only**, and listed
  25 of its 30 changes. The Export page's row and column count is also readable
  in dark mode.
- Fixed curator decisions that did not reach the exports. The row
  **Accept**/**Reject** buttons discarded a field set with **Edit** (the batch
  actions kept it), so rejecting and re-accepting an edited mapping exported
  the engine's suggestion. Ontology terms set for values mapped again after a
  schema edit were never applied when the upload's values were type-inferred
  (`1` vs `1.0`, `TRUE` vs `True`). Rejecting or moving a column deleted the
  ontology terms of values another column of the same field still used.
- cBioPortal exports keep the uploaded text of every cell they do not rewrite
  (sample ID `0012` was written as `12`, age `045` as `45.0`), type
  `TRUE`/`FALSE` columns as BOOLEAN rather than NUMBER, and keep each row on one
  line: a line break or tab inside a value becomes a space, and values are no
  longer quoted, since `validateData.py` reads quotes literally. A numeric
  column whose values became ontology terms, and the attributes cBioPortal
  defines as text (such as `SEX`, `SAMPLE_TYPE` or `OTHER_SAMPLE_ID`), are
  declared STRING; a coded `1`/`2` sex column failed validation before.
- The KB refresh and engine upgrade workflows no longer fail after their work
  succeeded when GitHub won't let Actions open pull requests. They open an issue
  whose link opens the PR with its title and description filled in, and a newer
  bump closes the PRs and issues it supersedes. The October KB refresh
  republished `kb-latest`, which production deployed, but failed to open its
  `KB_BUNDLE_SHA256` bump.
- The Harmonized CSV and the export preview build faster on large uploads:
  each distinct value's ontology term is looked up once, not once per cell.
  On the 21,881-row sample the table builds in 0.44 s, down from 0.76 s.
- Production health checks pause while an application or KB deployment holds
  the deploy lock. Planned restarts no longer raise critical alerts, and the
  automatic storage cleanup can't remove KB volumes a rollout has staged. A
  deployment that holds the lock for over an hour is reported.
- Fixed engine upgrades failing at install. Removing the engine's unused NLTK
  dependency rewrote the wheel's whole METADATA file and wrapped a long
  requirement in the middle of its marker, so pip rejected the wheel built from
  upstream `9c7f100` on Oct 9. Only the NLTK line is removed now; every other
  byte is kept.
- The export preview no longer has a **Column changes** table, and its grid of
  exported values is now called **Harmonized metadata**. The summary still
  counts the columns left out of the export.
- The preview's **Values changed in** list offered only columns whose values
  changed, one at a time, so a study whose only rewritten column was `disease`
  offered nothing else. It is replaced by a **Columns** checklist of every
  exported column, marked as renamed, with its number of changed values, or
  unchanged. It shows any combination of columns, or **All**, **Changed**
  (replacing **Changed columns only**), or **None**, and **Changed rows only**
  counts and keeps rows changed in the shown columns. The preview API's
  `column` parameter can be repeated, and `rows.changed_total` counts the rows
  changed in those columns.
- Columns mapped to the same schema field are merged into one column, as the
  lab's curated metadata consolidates them, instead of exporting one and
  leaving the others out. Each row holds those columns' values in upload
  order, each replaced by its accepted ontology term, separated by `<;>`, with
  blank values skipped and repeats listed once; MetaHarmonizer's own example
  data (`examples/data/query_with_selected_fields_for_bie.csv`) uses this
  format. The Harmonized CSV and the cBioPortal files merge alike, and a
  merged cBioPortal attribute is declared STRING when its cells hold several
  numbers or yes/no values; `validateData.py` accepts the result. Identifier
  fields (PATIENT_ID, SAMPLE_ID, and fields named like `subject_id` or
  `sample_id`) still take one column, chosen by the existing rule. The export
  preview marks merged columns, and its summary counts them.
- A column merged from many columns no longer stretches the export preview:
  its header and the **Columns** list name the first two merged columns and
  how many more (all of them on hover), and the list stays inside its
  dropdown. Before, a field merged from 18 columns made the list 1,504 px wide
  in a 320 px dropdown and the column header wider than the whole table.
- The Harmonized CSV now writes a field mapped to ontology terms the way the
  lab's harmonized files do (MetaHarmonizer_Test_Data, 17 cBioPortal studies):
  `original_<field>_value` (the row's uploaded values joined by `<;>`, in
  capitals, repeats kept), `curated_<field>` (their accepted terms, each once;
  a value without an accepted term is left out), `curated_<field>_ontology_term_id`
  (the terms' ids, in the same order) and `curated_<field>_source` (the columns
  used, joined by `;`), with `NA` for an empty cell. A term recorded as several
  terms joined by `<;>` is split, so each is listed once with its id. Run on
  those 17 studies with the lab's own column assignments and curation maps,
  our export reproduces 97.8% of the lab's `curated_<field>` and id cells
  exactly; every other cell holds the same terms in the order of the lab's
  per-study merge plan, apart from one malformed cell in the lab's file.
- Only accepted columns are merged into a field, as in the lab's harmonized
  files, where every merged column is one a curator assigned. An unreviewed
  suggestion is no longer merged into a field that has accepted columns; a
  field with none still uses its best suggestion.

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
