---
name: narrative-to-slide-outline
description: "Convert a Markdown narrative/strategy document into slide-deck YAML for a downstream pptx pipeline (narrative → YAML → pptx). Manual-only: never auto-triggers — start it by running /narrative-to-slide-outline."
disable-model-invocation: true
---

# Narrative to Slide Outline

**Non-negotiables** (full rules below):

- During generation (Steps 1-5), never open referenced data files — that's the Step 6 QA subagent's job.
- Never fabricate data or invent a `source:` path.
- Scope: read prose → produce YAML; never generate the pptx.
- Never report without a completed Step 6 QA pass; Step 7 is the only exit.

## Purpose

Convert a Markdown narrative document (flowing prose containing analysis, recommendations, and embedded data references) into a structured YAML intermediate file consumed by a downstream pptx-generation skill.

This skill is the middle stage of a three-stage pipeline:

```
[Raw data]
        ↓ (CSV, txt, Excel, Word, PDF, PPTX)
[Upstream AI: writes a narrative strategy document]
        ↓ (Markdown)
[THIS SKILL: produces slide-deck YAML]
        ↓ (YAML)
[Downstream pptx skill: produces .pptx file]
```

Keep your scope narrow: read prose, produce YAML. Do not generate pptx.

**Rule on data files**: during YAML generation (Steps 1-5), do **not** open the referenced data files (CSV, txt, Excel, Word, PDF, PPTX). The narrative's inline tables are authoritative — they are what you transcribe into `data:` blocks. The original data files are read only later, by the QA subagent in Step 6, to verify two things:

1. The inline tables were transcribed correctly from their source.
2. Any prose-claim citations are supported by their sources.

Treating the file paths as lineage breadcrumbs (not generation-time inputs) keeps this skill fast and deterministic, and confines all file I/O for raw data to the QA step.

## Editing an existing YAML in a new conversation

YAML files outlive the conversation that created them. A common workflow is to generate the YAML in one thread, then return days later — in a fresh thread — to edit it. This skill supports that as a distinct entry point.

**Use this entry point when** the user wants a non-trivial change to an existing YAML: adding or removing slides, splitting or merging slides, adding a new claim that needs a citation, swapping a chart's data source, restructuring the deck.

For a trivial text-only tweak (rename a title, fix a typo, reword `speaker_notes`), skip this skill entirely — just do it with Edit; you don't need this skill's machinery.

### What to ask the user

1. **The YAML path** — required.
2. **The original narrative path** — preferred but optional. Supplying it widens the citation-reuse pool in Step 8; if it's missing, Step 8 operates in degraded mode.

### What to do

1. In a single parallel batch, read the YAML, the narrative (if provided), and `references/slide_yaml_schema.md` — your edits must conform to the schema.
2. **Skip Steps 1-7. Jump directly to [Step 8](#step-8-iterative-revision-user-driven-loop)**. All operating rules — Edit-tool usage, citation reuse, degraded mode, exit handling (re-run Step 6 then Step 7) — live there.

## Input

A narrative Markdown document. **The file format is specified in `../compose-slide-narrative/references/narrative_format.md`** (read up front in [Step 1](#step-1-read-the-input-and-references)). It covers the document skeleton, inline tables, `(Source: ...)` breadcrumbs, and image references.

Input may be supplied as:

- A file path (e.g., `./narrative.md`)
- Pasted text in the chat

If neither is provided, ask the user. See [Step 1](#step-1-read-the-input-and-references).

## Output

A YAML file. Default location: **same directory as the input file** the user gave you, with the **fixed basename `slide-outline.yaml`** (e.g., if the input is `<dir>/narrative.md`, write `<dir>/slide-outline.yaml`). If the input was pasted text with no source file, ask the user for the desired output path before writing.

### Output schema

The full YAML format — top-level fields, the per-`type` schemas
(`bar_chart`/`line_chart`/`pie_chart`/`histogram`/`table`/`image`), the number-vs-string
rule for cell values, and YAML formatting conventions — is defined in
**`references/slide_yaml_schema.md`** (read up front in
[Step 1](#step-1-read-the-input-and-references)). A complete worked example
lives in `references/example_output.yaml`, paired with its input in
`../compose-slide-narrative/references/example_narrative.md`.

The key under `data:` MUST match the `{{placeholder_name}}` token in `body`. The
narrative does not carry these names, so this skill coins them from context in
short `snake_case` (e.g. `revenue_trend`, `team_photo`, `segment_breakdown`).

## Workflow

### Invariants — hold at every step

- [ ] **No data-file I/O during generation** (Steps 1-5): inline tables are authoritative; raw files are opened only by the Step 6 QA subagent.
- [ ] **Never fabricate**: no invented numbers, no invented `source:` paths. Missing data → ask in Step 3 or omit.
- [ ] **Stay in scope**: read prose → produce YAML; never generate the pptx.
- [ ] **QA before reporting**: run the full Step 6 pass before the Step 7 summary — a full re-run after any Step 8 edit, never partial.
- [ ] **Step 7 is the only exit**: every Step 8 → 6 → 7 cycle terminates through it.

### Step 1: Read the input and references

Issue these reads **together in a single parallel batch** (one round-trip), so later steps aren't stalled by sequential reads:

- **The narrative input** — if a file path was given, Read it; if text was pasted, use it directly (nothing to read); if neither, ask: "Where is the narrative document?"
- **`../compose-slide-narrative/references/narrative_format.md`** — the input format spec you parse against in Step 2 (document skeleton, inline tables, `(Source: ...)` breadcrumbs, image references)
- **`references/slide_yaml_schema.md`** — the output YAML schema you generate against in Step 4

(If you instead entered at Step 8 to edit an existing YAML, you do the equivalent batched read there — see that section.)

### Step 2: Analyze the document

Recognize each pattern below using the syntax defined in the [Input](#input) section; here we focus on **what to extract and how to handle priority/conflicts**, not on the syntax. Do this without rewriting the user's content:

- **Metadata**: title and any author/date/audience/duration lines
- **Slide candidates**: each `##` typically becomes one or more slides; long sections may split, short adjacent ones may merge
- **Inline data tables**: the **primary source** of chart/table data. Lift as-is into `data:`. Do not paraphrase or aggregate numbers
- **Data source breadcrumbs**: capture as lineage metadata, keeping any `heading:`/`page:`/`slide:` locator (QA needs it). **Do not open the referenced files during generation** — see [Purpose](#purpose) for the rationale
- **Image references**: capture path (plus caption / alt text when present)
- **Numbers embedded in prose**: use as supporting facts in body text. Prefer the adjacent inline table for the `data:` block when one exists. **If only prose numbers are available (no inline table), do not fabricate a chart from them** — surface the gap in Step 3 and ask the user
- **Prose-claim citations**: collect into the slide's `prose_sources` list, paired with the claim they back (QA-checked in Step 6)
- **Tone**: formal/casual, optimistic/cautious, internal/external audience
- **Anticipated Q&A**: often appears in a closing section

### Step 3: Clarify with the user

This is the **only** point where the skill checks in with the user. `AskUserQuestion` is already a blocking call — it waits for the answer before the flow continues — so no extra stop-and-end-turn gate is needed. The one risk it does not cover is *not asking at all*: do not start Step 4 while any question below still lacks a clear answer.

Use AskUserQuestion. Batch related questions into one call (the tool accepts up to 4 questions).

Common questions:

1. **Target slide count** — Count distinct ideas in the document to derive a baseline **M** (≈ one slide per idea; long `##` sections may split, short ones may merge). Ask: *"About N sections → ~M slides at one-idea-per-slide. Target?"* with three options scaled to M:

    - **Concise** ≈ 0.6×M — merge related sections, drop secondary charts
    - **Standard** ≈ M — one slide per section/idea
    - **Detailed** ≈ 1.5×M — split dense sections, add a chart per data table

    Fill the labels with the rounded numbers (e.g. M=13 → "Concise (~8) / Standard (~13) / Detailed (~20)") — a short memo and a 40-page report should land on very different numbers.

2. **Body verbosity** — "Terse (keywords and short bullets; the speaker carries the content, so push depth into `speaker_notes`)" / "Balanced (mixed bullets and short sentences)" / "Verbose (full sentences and prose paragraphs; the slide should read on its own as a document)". This is orthogonal to slide count (Q1): few slides can still be terse, and many slides can still be verbose. Q1 decides how the narrative is partitioned; Q2 decides how each slide is written.
3. **Missing data sources** — For every chart/table where the narrative didn't supply a source (whether the inline table lacks a breadcrumb, or the prose mentions data with no table at all), ask. Don't make paths up
4. **Proactive additions** — If a section would clearly be strengthened by a chart not in the prose, suggest it: "Section X talks about trend Y. A line chart would help — do you have the data?"
5. **Audience/tone** — only if unclear from the document

Skip questions that already have clear answers. Over-asking is friction.

### Step 4: Generate the YAML

Generate against `references/slide_yaml_schema.md` (read in Step 1; read it now only if you somehow skipped it).

Map the document to slides:

- **Title slide**: title + body containing author/date/audience as subtitle-like lines; `suggested_layout: "Title Slide: Large centered title, with date in smaller text below"`
- **Agenda slide** (if the document has an executive summary or section list): numbered list of sections
- **Section divider slides** for major `##` transitions: `body: ""`, `suggested_layout: "Section Divider: Large centered title only"`
- **Content slides**: title + prose summary (1-3 short paragraphs or bullets) + `{{placeholder}}` where any data lives + `data:` block
- **Closing block** (in this order, as a deliberate pattern):
    1. Section divider with title like "Conclusion" — `body: ""`, `suggested_layout: "Section Divider: Large centered title only"`, signals the wrap-up. Keep this even when the narrative's `## Conclusion` has a wrap-up paragraph: the divider opens the closing section, the paragraph goes on the next slide.
    2. Summary slide — carries the narrative's `## Conclusion` wrap-up paragraph (the input format in `../compose-slide-narrative/references/narrative_format.md` guarantees one) as a short centered prose body. **Never drop this paragraph.** Omit this slide only when the Conclusion has no wrap-up text.
    3. Recap slide — 2-4 bullets capturing the key takeaways (often Markdown bullets pulled from the final section of the narrative)
    4. Thank-you slide — title like "Thank you", body holds "Q&A". If the narrative includes an Anticipated Q&A section, lift those question/answer pairs into `speaker_notes`; otherwise keep `speaker_notes` minimal (e.g., a brief prompt to open the floor) or omit it.

    Collapse into a single slide only when the document is very short (<5 slides total).

For each non-divider slide, set a `suggested_layout` that reflects the slide's character. Examples:

- Bullet slide → `"Bullet list: N items stacked vertically in a larger font"`
- Chart slide → `"One-line comment on top, a large [bar|line|pie|histogram] chart centered below"`
- Table slide → `"Table placed large in the center of the slide"`
- Two-column comparison → `"2-column: XXX on the left, YYY on the right"`
- Image slide → `"Large image centered, with a comment on top"`

When the narrative contains an inline data table, lift it into a structured `data` entry. Example:

Narrative excerpt:

```markdown
Revenue kept growing through 2025; Q3 reached a record high of $168 million, up 15.9% year-over-year.

| Quarter | 2024 | 2025 |
| ------- | ---: | ---: |
| Q1      |  100 |  110 |
| Q2      |  120 |  135 |
| Q3      |  145 |  168 |

(Source: ./data/q3_financials.xlsx, sheet: Sales_Trend)
```

Becomes:

```yaml
body: |
  Quarterly revenue kept growing through 2025. Q3 reached a record high of $168 million.

  {{revenue_trend}}
data:
  revenue_trend:
    type: bar_chart
    source: "./data/q3_financials.xlsx, sheet: Sales_Trend"
    x_axis: "Quarter"
    y_axis: "Revenue ($M)"
    categories: ["Q1", "Q2", "Q3"]
    series:
      - name: "2024"
        values: [100, 120, 145]
      - name: "2025"
        values: [110, 135, 168]
```

Notice the `source:` field. This breadcrumb makes the data verifiable: Step 6 (QA verification) reads the source file and cross-checks against the values above. Always include `source` when the narrative provided a data-source reference.

When a prose sentence carries a `(Source: ...)` breadcrumb but no table/chart, record it at the slide level under `prose_sources` instead. It renders no visual, but Step 6 QA still checks whether the source supports the claim:

```yaml
body: |
  We are growing ~2x faster than our nearest competitor.
prose_sources:
  - claim: "growing ~2x faster than nearest competitor"
    source: "./data/market_share.csv"
```

### Step 5: Write to file

Write the YAML to the default path defined in the [Output](#output) section (ask first if the input was pasted text with no destination). Confirm the final path back to the user in your summary.

### Step 6: QA verification (subagent)

After the YAML is on disk, spawn a subagent (use the Agent tool, `subagent_type: general-purpose`) to verify data integrity against the source files. Delegating to a subagent keeps the main flow lean and isolates the file-reading concern.

The subagent reads the YAML, opens every referenced source file, cross-checks the data, and reports back slide-by-slide. It only sees the prompt you hand it — not this skill — so the prompt below is self-contained. Adapt paths as needed:

```
QA task: verify the data in this slide-deck YAML against its source files.

YAML path: <absolute-path-to-yaml>
Working directory for resolving relative source paths: <usually the YAML's directory>

Use a Python where `pandas`, `openpyxl`, `pdfplumber`, `python-pptx`, `python-docx` are all importable — check the project's venv first (e.g. `./.venv/bin/python`), then any system-wide venv, then plain `python3`. `pdf2image`/`pytesseract`/`markitdown`/`pdftotext` are available as fallbacks for scanned PDFs or text-heavy slides. Plain `.txt` files need no library — read them directly.

1. For every referenced file — `data:` entries with `source:`, slide-level `prose_sources` entries, and `type: image` entries (which use `path:`) — open or stat it. Sheet name follows "sheet:", heading text follows "heading:" (Word), page/slide number follows "page:"/"slide:" in the source string. For a Word `heading:`, locate the matching heading in the `.docx` and verify against the content under it (CSV and `.txt` carry no locator — verify against the whole file). For `type: image`, do an existence check only — never inspect contents. If a file/sheet/page/slide is missing or extraction yields nothing, record it and continue (don't crash).

2. Compare YAML against source:
   - Charts/tables from CSV/Excel (or an extracted Word table): `categories`/`series.values`/`bins`/`frequencies`/`headers`/`rows` must match the source values
   - `prose_sources` and any txt/Word/PDF/PPTX prose source: softer semantic check — does the source plausibly *support* the claim or numbers? Treat extraction noise as "can't-confirm", not "discrepancy". Flag only clear contradictions.
   - YAML that is a clear subset/aggregate of the source → "summarized", not "discrepancy"

3. Report slide-by-slide, discrepancies first:
   - ✓ verified — data matches / claim supported / image file exists
   - ⚠ summarized or can't-confirm — aggregated view or plausible-but-unsettled claim
   - ✗ discrepancy — specifics (e.g., "YAML Q1 = 100, source = 102") or contradicted claim
   - ✗ source not accessible — missing file or invalid locator
   - ⊘ skipped — entry has no source to verify

Keep the report under 400 words.
```

After the subagent reports back, surface its findings to the user. If there are real discrepancies, ask whether to:

- Update the YAML to match the source
- Keep the YAML as-is (when the narrative deliberately aggregated/rounded)
- Investigate manually

If all source files are inaccessible (e.g., the upstream pipeline hasn't produced them yet, or the user is testing with paths that don't exist), the subagent will report all ⊘/✗ — that's a valid outcome. Note it and continue.

### Step 7: Summarize and offer revision

Tell the user:

- Where the YAML was written
- How many slides were generated
- QA findings from Step 6 (verified / summarized / discrepancies / inaccessible)
- How many chart/table entries were emitted **without** a `source`, and which ones — so the user can spot data that should have carried a breadcrumb (these are valid, just un-cited)
- Any data sources that are still TODOs (the user said they'd provide but haven't)
- Open question: "Anything to refine?" — if yes, proceed to Step 8; if no, **the workflow ends here**. Step 7 is the sole termination point; any Step 8 → Step 6 → Step 7 cycle always exits through this same question.

### Step 8: Iterative revision (user-driven loop)

This step is the editing loop, reached from two entry points:

- **After Step 7** in the fresh-creation flow — the user will often want to refine the just-generated YAML. Skip if they're already satisfied.
- **Direct invocation** to edit an existing YAML (see [Editing an existing YAML in a new conversation](#editing-an-existing-yaml-in-a-new-conversation)) — Step 8 is the whole point of the invocation. (Do not re-ask the Step 3 clarifications — the existing YAML already embodies those answers.)

Typical revisions: split a slide into two, add a bullet, fold in data they forgot, reorder slides, drop something, etc.

**Scope shift**: in Steps 1-5 the narrative is the source of truth and you must not invent claims. In Step 8 that constraint relaxes — the user's revision instruction is the new authority. You may reorder, restate, split, merge, or drop content freely to honor the request. (You are still not free to fabricate data — see below.)

**Rules for new data introduced in Step 8**:

If a revision adds a new prose claim or a new chart/table that needs a data source, the source must come from one of two places:

1. **Reuse an existing citation**: scan the current YAML (`data.*.source`, `prose_sources[*].source`) and the original narrative for a source that plausibly covers the new claim. If you find a candidate, **confirm the match with the user before reusing it** — semantic matching by an LLM is not reliable enough to silently bind a source to a new claim. (**Degraded mode**: when the narrative isn't available, the reuse pool shrinks to YAML-only sources, so falling through to rule 2 is more common.)
2. **Ask the user for the source**: if no existing citation fits, ask. Do not make up a path.

If the user cannot supply a source, keep the addition as prose (no chart, no `prose_sources` entry) or drop the addition — never invent a `source:` value.

**Loop mechanics**:

- Accept one revision instruction (or a small batch) per turn
- Apply via the Edit tool, not Write — preserve indentation, quoting style, literal block scalars (`|`), and the existing field order
- Briefly confirm what changed (one sentence)
- Repeat until the user signals they are done (e.g. "OK", "looks good", "run QA")

**Exiting Step 8**:

When the user is satisfied, **re-run Step 6 (QA) in full against the updated YAML** — not just on the bits Step 8 changed. Step 8 edits can rearrange, restate, or merge content in ways that make diff-based partial QA brittle; a full re-verification is simpler and safer. Then re-run Step 7 with the updated summary.

## Important principles

- **Layout hints go only in `suggested_layout`**, never inside `body`. The downstream pptx skill decides actual layout.
- **Respect the upstream author's words**. Lightly compress prose for slide brevity, but don't invent claims or rewrite analysis. If something is unclear, ask the user, don't paper over it.
- **Honest gaps**. If the prose mentions a visualization without an inline table, ask. Do not infer numbers from prose summaries when a structured table was expected.
- **One slide, one idea**. If a `##` section spans multiple distinct topics, split it.
- **Speaker notes carry the depth**. Pull supporting context, caveats, and anticipated questions into `speaker_notes` so the slide itself stays clean.
