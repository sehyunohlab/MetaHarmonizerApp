# MetaHarmonizer Curator Guide

This guide covers the curator workflow on the hosted application at
<https://metaharmonizer.online> and on an equivalent self-hosted instance.

Administrator tasks — approving accounts, promoting schema versions, managing
aliases, promoting learned decisions, federation — are in the
[administrator guide](admin-guide.md). To drive harmonization from an AI client
instead of the browser, see the [MCP server](../mcp/README.md).

## Getting access

1. Open the application and choose **Create account**, then supply your
   institutional email address and a password. Passwords that appear in known
   public breaches are rejected.
2. Confirm the verification link sent to that address. You cannot sign in until
   the address is verified.
3. If the instance restricts registration to specific email domains, an
   administrator must approve an address outside those domains. You will be told
   that approval is pending, and you will receive a message once it is granted.
4. Sign in. The first account created on a new instance becomes the
   administrator; every later account is a curator.

To evaluate the interface without an account, choose **Explore a live demo — no
account needed** on the sign-in page. The demo shows a sample study with
realistic results and blocks every write, so nothing you do is saved. Leave the
demo before real work.

If you forget your password, use **Forgot password?** and follow the emailed
link. Sessions expire after a period of inactivity; signing in again restores
your work, because decisions are stored on the server rather than in the
browser.

## What the application does

MetaHarmonizer proposes; you decide. For each uploaded study it suggests how
source columns map to a target schema, and how source values map to ontology
terms. Nothing is final until a curator accepts it, and your original file is
never modified.

Two pieces of vocabulary appear throughout the interface:

**Stage** shows how a proposal was produced, from most to least deterministic:

| Badge | Meaning |
| --- | --- |
| S1 Dict/Fuzzy | Dictionary or close-string match |
| S2 Value/Ontology | Match derived from the column's values or ontology context |
| S3 Semantic | Semantic similarity from an embedding model |
| S4 LLM | Optional language-model fallback, when enabled |
| Invalid / Unmapped | No usable proposal; the column needs your decision |

**Confidence** is the engine's own estimate for a proposal. High-confidence
proposals may be accepted automatically by the instance's configured threshold;
everything below it is held for review. Treat confidence as triage guidance, not
evidence: a confident proposal can still be wrong, which is why the review
queue puts risky items first.

Each study also records the schema version and the ontology snapshot used to
produce it, so a result can be reproduced and audited later.

## Before you upload

Upload only de-identified clinical metadata. Do not upload names, contact
details, medical-record numbers, protected health information (PHI), or other
direct patient identifiers. The upload confirmation appears before the browser
previews or sends the selected file. Choosing **Cancel** leaves no file
selected.

Supported inputs are CSV and TSV files. Check the browser preview before
starting: the first row should contain column names and the previewed values
should be split into the expected columns.

## 1. Upload and harmonize

Open **Upload**, select the file, and choose a run mode:

- **Both** maps columns to a target schema and then resolves selected values to
  ontology terms.
- **Schema only** maps column names and skips value-to-ontology resolution.
- **Ontology only** resolves values and skips schema mapping.

For schema mapping, select the target standard shown by the application. The
default is the lab's curated cBioPortal vocabulary (OmicsMLRepoData's
cBioPortal data dictionary: `body_site`, `disease_type`, `sex`, `patientId`, and
40 more), the fields of the lab's harmonized metadata and of its schema-mapping
ground truth. **cBioPortal clinical attributes** maps instead to cBioPortal's own
attribute IDs (`AGE`, `OS_STATUS`, …), and GDC and curatedMetagenomicData have
their own vocabularies. For an
ontology run, the optional column selector limits value resolution to the
chosen columns; leaving it empty uses all eligible columns.

Select **Run harmonization**. The job continues on the server if you change
pages or refresh the browser. Its progress remains in the jobs tray. A failed
job shows an error and can be submitted again after correcting the input.

The jobs tray in the header shows every run you have started, with live
progress. You may leave the page, review another study, or close the tab; the
run continues and the result appears when it completes. Each curator may have a
small number of runs in flight at once, and the instance refuses new work when
its queue is full — in both cases, wait for a run to finish and submit again.
Submitting the same file twice while it is still running returns the run already
in progress instead of duplicating the work.

## 2. Review schema mappings

Open **Schema** and select the study. The default **Pending** tab contains
columns that still need a curator decision.

For each proposed mapping:

- **Accept** confirms that the source column should map to the displayed target
  field.
- **Reject** confirms that this proposed mapping should not be used. It does
  not mean the source column is invalid in general.
- **Edit** replaces the proposed target with the curator-selected field and can
  include a note.

**Accept** and **Reject** keep a field you set with **Edit**, from the row
buttons and from **Accept all** / **Reject all** alike: rejecting an edited
mapping and accepting it again exports your edited field, not the original
suggestion.

Decisions are saved immediately. Accepted, rejected, and edited decisions are
remembered for the curator so repeated columns can be prefilled or rejected on
later studies. An admin must separately promote a learned decision before it
applies globally.

These remembered decisions form two layers. Your own decisions are personal and
apply only to your studies. An administrator can promote a reviewed decision to
a shared layer used by everyone on the instance. Where both exist, your personal
decision wins, so a shared default never silently overrides your judgement.

The default **Smart review order** places risky mappings first and keeps
look-alike columns together. Clicking a sortable header cycles through
descending, ascending, and back to smart order. Missing values remain last.

Use the row checkboxes or a look-alike group control to select several pending
rows, then choose **Accept all** or **Reject all**. Batch actions leave the view
on **Pending**.

Keyboard shortcuts:

| Key | Action |
| --- | --- |
| `j` / `k` | Move down / up |
| `a` | Accept focused mapping |
| `r` | Reject focused mapping |
| `e` | Edit focused mapping |
| `x` | Select focused mapping |
| `Enter` | Open details |
| `/` | Focus search |

## 3. Confirm ontology terms

Open **Ontology** after an ontology-capable run. Each matched value shows its
proposed standard term, code, and confidence.

### Which columns produce ontology terms

The Ontology stage does not cover every column. Values are resolved only for
columns whose accepted target field has a term vocabulary:

1. **Fields the target schema's data dictionary gives terms.** The lab's data
   dictionaries name, per field, the ontology branches and terms its values
   come from (for example, every descendant of NCIt *Disease or Disorder*).
   Each value is matched against them one ontology at a time, and the
   best-scoring term wins:

   | Target schema | Target field | Terms |
   | --- | --- | --- |
   | OmicsMLRepo cBioPortal (default) | `disease_type`, `target_condition` | NCIt Disease or Disorder |
   | | `country` | NCIt Country |
   | | `age_group` | the NCIt terms the dictionary lists |
   | curatedMetagenomicData | `disease`, `disease_details`, `target_condition` | NCIt Disease or Disorder, MONDO diseases, and the NCIt terms the dictionary lists (such as Healthy) |
   | | `body_site` | the UBERON terms the dictionary lists |
   | | `body_site_details` | UBERON anatomical entities |
   | | `treatment` | NCIt Drug, Food, Chemical or Biomedical Material, and the NCIt terms the dictionary lists |
   | | `country`, `sex`, `age_group`, and its other listed-term fields | NCIt |

2. **Other disease, body-site, and treatment fields**, by name, in any target
   schema (GDC included):

   | Target field | Vocabulary |
   | --- | --- |
   | `disease`, `target_condition`, `cancer_type`, `disease_type`, `primary_diagnosis`, `primary_disease` | NCIt Neoplasm |
   | `body_site`, `primary_site`, `tissue_or_organ_of_origin`, `site_of_resection_or_biopsy`, `biospecimen_anatomic_site` | NCIt Body Part |
   | `treatment`, `treatment_name`, `treatment_type`, `therapeutic_agents` | NCIt Pharmacologic Substance |

Anything else falls back to the value dictionary, which covers far less. That
includes fields whose dictionary names an ontology the engine cannot search
yet, such as ancestry (HANCESTRO) and smoking status (SNOMED CT), so the
Ontology stage can show only a handful of rows for a study whose columns all
mapped. That is the current coverage, not a failed run.

- **Accept** confirms the displayed term and code.
- **Reject** declines that proposed term for the raw value.
- **Edit/Override** searches for and assigns a different term.

Assigning a term to a repeated raw value applies the same correction to all of
its occurrences within that field. The preview shows how accepted terms will
rewrite exported values; the original uploaded file is never modified.

When **Edit** moves a column into one of these fields, its values are mapped
again for the new field and appear here; the terms you set for them apply in
every export. Terms belong to a field, not to a column: rejecting or moving one
column keeps the terms of values that another column of the same field still
uses.

Values under **No ontology match** may be identifiers, names, free text, or
terms absent from the current corpus. Use **Find suggestions** to search the
ontology index. Review each suggestion before applying it; dismissing a
suggestion only removes that suggestion from the current view.

**Find suggestions** reports `No confident ontology suggestions found` when
nothing clears the confidence threshold. Compound raw values such as
`Blood_normal` are a common cause: the search matches whole words against
ontology labels, so an underscore-joined value usually matches nothing. Use
**Edit/Override** to assign the term directly in that case.

## 4. Check quality and readiness

Open **Quality** to inspect coverage, confidence, stage distribution, and
lowest-confidence pending columns.

The readiness checklist verifies:

1. At least one mapping is accepted.
2. No schema mappings remain pending.
3. Every column has a mapped field.

The first condition blocks export readiness. Pending columns require a decision.
Unmapped columns are identified in the checklist and are dropped from export.
When the banner says **Ready to export**, select **Go to export**.

## 5. Preview and download outputs

Open **Export**. Before downloading, select **Preview changes** to compare the
Harmonized CSV with your original upload. Previewing is read-only: it does not
export anything or mark the study as exported.

- The summary shows the row count (rows are never added, removed, or
  reordered), how many columns are exported, renamed, merged, or left out, and
  how many cell values change.
- Columns you accepted for the same field are merged into it, placed where the
  first of them is in your file, the way the lab's harmonized metadata
  consolidates them. Each row lists those columns' values in file order,
  separated as the lab's data dictionary for the target schema specifies for
  that field. In the lab's cBioPortal vocabulary that is `<;>` (a value may
  itself contain `;`) for most fields, such as body site, disease type,
  specimen type and treatments, but `;` for target condition, study design,
  smoker and ancestry, as in the lab's published curated metadata; in
  curatedMetagenomicData it is `;` for most fields. A field the dictionary
  says nothing about uses `<;>`. Blank and missing values
  are skipped. Only accepted columns are merged: a column whose mapping is
  still an unreviewed suggestion is not added to a field you accepted columns
  for, and a field with no accepted column uses its best suggestion alone. To
  leave a column out of the merge, reject or edit its mapping.
- A field whose values are mapped to ontology terms (such as disease or body
  site) is written as four columns, as in the lab's harmonized files
  (MetaHarmonizer_Test_Data): `original_<field>_value` holds each row's
  uploaded values joined by `<;>`, in capitals, repeats included;
  `curated_<field>` holds their accepted terms, each once and joined by the
  field's separator, so `F` and `female`
  that both became `Female` give `Female`; `curated_<field>_ontology_term_id`
  holds the terms' ids in the same order; and `curated_<field>_source` names
  the columns the row's values came from, joined by `;`. A value without an
  accepted term is left out of `curated_<field>` but stays in
  `original_<field>_value`, and an empty cell is written `NA`. When one value
  needs several terms (`Abdomen, Pelvis` is Abdomen and Pelvis), edit its term
  to the terms joined by `<;>` and its id to their ids in the same order. The
  preview compares only `curated_<field>` with your upload; the **Columns**
  list says what each companion column holds. Any other field is one column
  named after it.
- An identifier field (`PATIENT_ID`, `SAMPLE_ID`, or a field named like
  `subject_id` or `sample_id`) holds one value per row, so only one of the
  columns mapped to it is exported: a mapping you accepted or edited wins over
  one the engine accepted on its own, which wins over an unreviewed suggestion;
  then higher confidence; then the column that comes first in your file. The
  others are left out and counted as not exported, like a column that is not
  mapped to a schema field. The cBioPortal files use the same columns.
- A column whose mapping you **rejected** is never used for a schema field. The
  Harmonized CSV keeps it unchanged under its own name, unless a mapped column
  is already exported under that name. The cBioPortal files leave it out.
- **Harmonized metadata** lists every row and every exported column of the
  Harmonized CSV. A renamed column's header is highlighted, with its uploaded
  name struck through beneath the schema field name; a merged column's header
  lists the columns merged into it, or past three the first two and how many
  more (hover over the header for all of them). Changed cells show the
  exported value with the uploaded value struck through beneath it, colored by
  cause: an accepted ontology term, a value left out because it has no
  accepted term (shown as `NA` when nothing is left), or an
  apostrophe added so spreadsheets treat formula-like text (such as values
  starting with `=`, `+`, `-`, or `@`, but not plain numbers like `-5`) as
  text. **Columns** opens a checklist of every exported column, each marked
  as renamed, merged, with its number of changed values, or unchanged. Show any
  combination of columns, or pick **All**, **Changed** (renamed, merged, or with
  a changed value), or **None**; search finds a column by its export or
  uploaded name. **Changed rows only** keeps rows with a changed value in the
  shown columns, and shows how many there are.
- A warning appears when exported columns still use unreviewed mapping
  suggestions; review them first so the field names are final.

Then switch to **Downloads** and download any required formats before
completing the study:

- **Harmonized CSV** contains renamed fields and, for fields mapped to ontology
  terms, the four curated columns described above. Every other cell keeps its
  uploaded text exactly, including number formatting and missing-value markers
  such as `NA`.
- **cBioPortal Format** is a tab-separated clinical file with cBioPortal header
  lines. Cells keep their uploaded text apart from accepted ontology terms, so
  a sample ID `0012` stays `0012` and an age `045` is not rewritten as `45.0`.
  Yes/no columns are written as `TRUE`/`FALSE`, the only values the cBioPortal
  format accepts for a yes/no attribute. A column whose values became ontology
  terms, and attributes cBioPortal defines as text (such as `SEX` and
  `SAMPLE_TYPE`), are declared as text even when the uploaded values are
  numbers or yes/no.   Merged attributes hold the same values, with the same separators, as
  the Harmonized CSV, and are declared as text when a cell holds more than one
  number or yes/no value. cBioPortal reads one line per row and
  does not unquote values, so a line break or tab inside a value is written as a
  space and values are never wrapped in quotes.
- **cBioPortal Study Folder (ZIP)** contains metadata and clinical data files
  for validation/import, written the same way.
- **Mapping Report (JSON)** records mapping proposals and curator decisions.
- **Labeled Dataset (CSV or JSONL)** includes curator-confirmed mappings for
  evaluation or training.

Downloaded data can still contain sensitive source values if the upload was not
properly de-identified. MetaHarmonizer does not certify de-identification.

## 6. Complete the study

After downloading every required output, choose **Complete**. Completion removes
the study from the active work list and cannot be undone from the application.
Do not complete a study until required exports have been downloaded. Incomplete
studies are automatically removed after the configured retention period.

## Troubleshooting

- **A study is not visible on a review page:** wait for the job to finish in the
  jobs tray, then select the study again.
- **A column is unmapped:** inspect its values and alternatives, then edit the
  mapping or accept that it will be omitted from export.
- **An ontology value has no match:** use **Find suggestions**, assign a term
  manually, or leave it unmatched when no standard term is appropriate.
- **An export looks incomplete:** return to **Quality** and review its readiness
  checklist and unmapped-column count.
- **A download fails:** sign in again if the session expired, then retry from
  **Export**. Downloads use the authenticated session and show the server error
  in the application; they no longer open a protected API URL directly.
- **The session expired:** sign in again. Saved curator decisions are stored on
  the server and do not depend on the browser tab remaining open.

## Reporting problems

Use the project's [GitHub Issues](https://github.com/sehyunohlab/MetaHarmonizerApp/issues)
for non-sensitive bugs and feature requests. Never paste or attach PHI, raw
patient metadata, credentials, API tokens, or private exports to a public issue.
For a report that may contain sensitive information, contact the operator of
your MetaHarmonizer instance and provide only the minimum necessary details.

Include the application page, study ID if non-sensitive, approximate time,
expected result, actual result, and reproducible steps. Redact values and file
names that could identify a patient or institution.

If you are evaluating whether this guide is sufficient on its own, use
[curator-usability-protocol.md](curator-usability-protocol.md).