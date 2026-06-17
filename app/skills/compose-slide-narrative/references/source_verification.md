# Source Verification (post-draft QA)

Instructions for the **verification subagent** dispatched in Step 6 of `compose-slide-narrative`,
after `narrative.md` has been written. The subagent starts cold — everything it needs is in this file
plus the dispatch prompt. Read this file in full before acting.

Its job: confirm that every sourced table and number in `narrative.md` actually matches the data in the
files its `(Source: ...)` breadcrumbs point at, **auto-correct only unambiguous mismatches**, and report
everything else for the human to decide.

---

## Hard constraints (inherited from the parent skill — do not break)

- [ ] **Scope is sacred**: read only `narrative.md` and the files named in its `(Source: ...)` breadcrumbs.
      Never open paths outside the user-specified scope, even ones that look useful.
- [ ] **Network: never** — no `WebFetch`, no remote APIs. Local files only.
- [ ] **Never fabricate a Source** — if a breadcrumb points at a file/locator that does not exist or cannot
      be read, that is a *finding to report*, not something to invent a fix for.
- [ ] **Do not rewrite the analysis or prose voice** — this is a fact-check, not an edit pass. Touch numbers
      and table cells, not framing, argument, or wording.

## Python interpreter

Detect it the same way the parent skill does — don't assume a fixed path. Probe for a project-local env
first (`./.venv/bin/python`, a `uv`/Poetry venv, or a `pyproject.toml`/`requirements.txt`); else fall back
to system `python3`. Confirm packages import before relying on them. Recommended readers: `pandas`
(+`openpyxl`) for CSV/Excel, `python-docx` for Word, `pdfplumber` for PDF, `python-pptx` for PPTX.
For `.md`/`.txt` sources use the Read tool.

---

## What to check

For each `(Source: ...)` breadcrumb in `narrative.md` (both table breadcrumbs and inline-prose ones):

1. **Resolve the locator.** Open the file and navigate to the precise locator: Excel `sheet:`, Word
   `heading:`, PDF `page:`, PPTX `slide:`. A breadcrumb whose file or locator cannot be resolved is a
   **BROKEN-SOURCE** finding.
2. **Compare the values.** For an inline table, every cell with a number must match the source. For an
   inline-prose `(Source: ...)`, the cited figure in the sentence must match. Recompute aggregates
   (sums, totals, % changes, growth rates) from the source rather than trusting the md's arithmetic.
3. **Re-check provisional markers.** For every `[needs-verification]` marker and every numeric claim that
   carries **no** Source, note it — but do NOT auto-attach a source. These go in the report for the human.

---

## Mismatch handling — the auto-fix line

Classify each mismatch into exactly one bucket. **Only AUTO-FIX is edited; everything else is reported.**

### AUTO-FIX (edit `narrative.md` with the Edit tool)
A mismatch is auto-fixable **only when all** of these hold:
- The breadcrumb resolves cleanly to a single, unambiguous location in the source.
- The source value is unambiguous (one cell / one clearly-labeled figure) and the md value is plainly wrong
  against it (e.g. md says `168`, the cited cell says `186` — a transcription error).
- Fixing it is a pure value substitution: replace the wrong number with the source number. No change to
  which rows/columns are shown, no change to prose meaning.

Use the **Edit tool**, not Write — preserve table layout, breadcrumbs, ordering, and surrounding prose.
Log every auto-fix (old → new value, location) for the report.

### REPORT-ONLY (do NOT edit — surface for the human to decide)
Anything that is not a clean value substitution, including:
- **Rounding / aggregation differences** — md shows `1.2M`, source rows sum to `1,187,402`. Could be
  intentional rounding or a different aggregation. Report, don't "correct".
- **Ambiguous locator** — the `sheet:`/`heading:`/`page:` is missing, wrong, or matches multiple places, so
  you can't be sure which source value is authoritative.
- **Stale-source suspicion** — the whole table disagrees systematically (e.g. every value off), suggesting
  the md was built from a different file/version than the breadcrumb names.
- **Structural mismatch** — the table's rows/columns don't line up with the source's shape.
- **BROKEN-SOURCE** — file or locator unreadable / not found.
- **Uncited numeric claims** and **`[needs-verification]` markers** — list each with its sentence.

When unsure which bucket a mismatch belongs to, treat it as REPORT-ONLY. The cost of a wrong auto-edit
(silently breaking a correct number) is higher than the cost of one extra line in the report.

---

## Output: the verification report

Return a single structured report to the parent agent (do not message the user directly). Sections:

1. **Summary line** — N breadcrumbs checked, N auto-fixed, N report-only findings, N broken sources.
2. **Auto-fixed** — a table: `location | source locator | old → new`. (Empty if none.)
3. **Needs human decision** — a table: `location | finding type | what the md says | what the source says |
   suggested action`. Group BROKEN-SOURCE, rounding/aggregation, stale-source, structural together here.
4. **Uncited / unverified** — bullet list of uncited numeric claims and `[needs-verification]` markers,
   each with its surrounding sentence.
5. **Clean** — one line confirming which sourced tables matched exactly (count is enough; no need to list).

The parent agent folds this into its Step 6 report (after the verification pass) and runs the normal
revision loop with the user.
