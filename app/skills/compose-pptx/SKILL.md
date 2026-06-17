---
name: compose-pptx
description: "Build a .pptx from slide-deck YAML (from narrative-to-slide-outline) and a mandatory sample-slide template: match each slide to the best-fitting sample and fill it via raw OOXML editing (no python-pptx), with a clone-to-grid solver for layouts the template lacks. Manual-only."
disable-model-invocation: true
---

# Compose PPTX (raw-XML build)

**Non-negotiables** (rationale below):

- Both inputs are user-supplied — never scan the project to guess a YAML or template, never invent a template; if either is missing, ask.
- The YAML's `data:` blocks are authoritative — render charts/tables from them; never re-open source CSV/Excel/PDF (only `type: image` reads from disk).
- Raw-XML build only — no python-pptx in the build; run the `scripts/` helpers, don't re-implement their logic inline.
- All structural `sldIdLst` edits come before any content editing.

## Purpose

Final stage of the three-stage pipeline. Consume the slide-deck YAML and produce a `.pptx`.

```
[Raw data / docs / user intent]
        ↓ compose-slide-narrative
[Narrative Markdown]
        ↓ narrative-to-slide-outline
[Slide-deck YAML]
        ↓ (THIS SKILL: compose-pptx)
[.pptx file]
```

The .pptx is built by **editing the raw OOXML** — unpack the template ZIP, edit
the slide XML directly (with the Edit tool + small plumbing scripts), then repack.

It includes a **clone-to-grid solver** (`clone_grid.py`) for the case where a YAML
slide needs a layout the template has no sample for (e.g. a 2×4 card grid when the
template only ships a 3-card row). See [The grid solver](#the-grid-solver-clone_gridpy).

The approach stays **template-driven and template-mandatory**: the user supplies a
template `.pptx` that is a **deck of styled sample slides** (a title sample, a
bullet-list sample, a section divider, a chart sample, a table sample, a 2-column
sample, an image sample, a closing sample, …). For each slide entry we pick the
best-matching sample, **duplicate it, and replace its contents in XML**. There is
**no from-scratch / no-template path** — if no template is supplied, ask for one.

Charts and tables are kept as **native PowerPoint objects** (not PNG), so they
stay editable and on-theme.

**Out of scope**: post-generation visual QA (rendering each finished slide and
inspecting its layout, overflow, contrast). That is a separate skill, to be added
later. This skill uses vision only to *understand and match the template*
(Step 2), never to verify its own output.

## Inputs

1. **Slide-deck YAML** — required. Path to the `slide-outline.yaml` produced by
   `narrative-to-slide-outline`. Its full schema is
   `../narrative-to-slide-outline/references/slide_yaml_schema.md` (read in Step 1).
   The YAML's embedded `data:` blocks (`categories`, `series`, `rows`, `bins`,
   `frequencies`, …) are **authoritative** — this skill renders charts/tables
   straight from them and does **not** re-open the source CSV/Excel/PDF. Only
   `type: image` entries are read from disk (via their `path:`).
2. **Template `.pptx`** — required, sample-slide deck (see [Purpose](#purpose)).

**Both paths must be supplied explicitly by the user.** Do **not** scan the project
to guess which YAML or template to use — if either path is missing, ask for it. Do
not invent a template.

## Output

A `.pptx` file. **Default location: same directory as the input YAML**, fixed
basename `deck.pptx`. The user may override the path.

## Environment and tools

Pick a Python interpreter — prefer a project-local env (e.g. `./.venv/bin/python`),
else system `python3`. Before relying on it, confirm `defusedxml`, `openpyxl`,
`yaml` (PyYAML) and `PIL` all import, and install any that are missing.

| Tool | Use |
| ---- | --- |
| `defusedxml` / the Edit tool | Unpack/pack and edit the raw slide XML (the build) |
| `openpyxl` | Regenerate a chart's embedded workbook so "Edit Data" matches |
| `soffice` (LibreOffice) + `pdftoppm` (poppler) | Render template samples → image grid for vision matching (Step 2) |
| `PIL` | Thumbnail composition; `type: image` handling |

These live in `scripts/` as command-line scripts: launch each one from the shell
with the chosen interpreter (`python <script>.py …`) rather than re-implementing its
logic inline. **Run from the `scripts/` directory** (use it as the working dir) so
the local `office` package — `scripts/office/`, imported as `from office.soffice
import …` — resolves on `sys.path`.

**Build scripts (Step 4):**

| Script | Role |
| ------ | ---- |
| `office/unpack.py <pptx> <dir>` | Extract + pretty-print + escape smart quotes |
| `office/pack.py <dir> <pptx>` | Condense + zip back to .pptx |
| `slide_order.py <dir> [--index N]` | Resolve 0-based presentation order → `slideN.xml` |
| `add_slide.py <dir> <slideN.xml>` | Duplicate a sample slide (handles rels/Content_Types/rId) |
| `clone_grid.py …` | Replicate a styled shape into an R×C grid |
| `set_chart_data.py …` | Fork the slide's chart part + write YAML data into it |
| `add_chart.py …` | Author a native chart **from scratch**; swaps a wrong-type sample chart in place, else places fresh |
| `fill_table.py …` | Reshape + fill a template table |
| `fill_text.py …` | Fill title/insight/caption + bullet bodies from a JSON spec (**optional** bulk helper; falls back to the Edit tool for rich formatting) |
| `set_image.py …` | Replace a sample picture with a file |
| `set_notes.py …` | Attach speaker notes — `speaker_notes` + claim/data sources — (clones a template notesSlide) |
| `clean.py <dir>` | Remove orphaned slides/media/rels/Content-Types |

**Inventory scripts (Step 2, template inspection only):**

| Script | Role |
| ------ | ---- |
| `render_template_thumbnails.py <pptx> <scratch>/thumbs` | Labelled thumbnail grid for vision matching (write into the scratch dir — disposable) |
| `inspect_template.py <pptx>` | JSON inventory of each slide's structure (read-only, python-pptx) — Step-2 complement / fallback |


## Workflow

### Invariants — hold at every step

- [ ] **Inputs are user-supplied**: never scan/guess a YAML or template; never invent a template; ask if either is missing.
- [ ] **`data:` is authoritative**: render from the YAML's data blocks; never re-open source CSV/Excel/PDF (only `type: image` reads from disk). Feed the scripts the YAML directly (`--yaml/--index`) — never hand-transcribe values into a temp JSON (that's where `↑`→"up", en-dash→hyphen, and dropped rows creep in).
- [ ] **Raw-XML only**: edit slide XML with the Edit tool + `scripts/` helpers; no python-pptx in the build (it appears only in the read-only Step-2 inventory fallback).
- [ ] **Use the scripts**: launch the `scripts/` helpers from the `scripts/` working dir; don't re-implement their logic inline.
- [ ] **Structure before content**: finish all `sldIdLst` edits (add new, remove samples) before filling any slide text.
- [ ] **Notes on every slide**: call `set_notes.py` once per built slide, unconditionally — the script no-ops when there's nothing; never decide per-slide whether notes are "needed" (that drops `data`-only provenance).
- [ ] **Scratch dir**: delete `<scratch>` only after `deck.pptx` is confirmed packed; leave it in place if the build failed.

### Step 1: Resolve inputs and read references

With both input paths in hand (see [Inputs](#inputs) — ask if either is missing),
issue together in one parallel batch:

- **Read the YAML** (the required input).
- **Read `../narrative-to-slide-outline/references/slide_yaml_schema.md`** — the
  schema you parse against.
- Pick the **interpreter**.

**Create the scratch dir.** All intermediate build artifacts (the template
thumbnails of Step 2, the unpacked XML tree of Step 4) live in **one** working
directory: `<yaml_dir>/.compose-pptx-build/`, where `<yaml_dir>` is the directory
holding the input YAML (also where `deck.pptx` is written). `mkdir -p` it now; the
rest of this doc refers to it as `<scratch>`. It is **disposable** — keep it out of
`scripts/` (the skill's own tree) and delete it in Step 5 once the deck is packed.

### Step 2: Build a template inventory

Understand what sample slides the template offers, using both tools when available —
they're complementary.

**Structure — `inspect_template.py`:** run it first for a JSON inventory of each
slide: whether a chart is **native** vs a picture of one (`has_chart`), table/picture
presence, and the **number of text-bearing placeholders** (`n_text_placeholders` —
placeholders that actually hold text; empty ones aren't counted). This decides the chart branch in
Step 3 (`set_chart_data.py` vs `add_chart.py`), which vision alone can misread.

**Vision — look & layout:** run `render_template_thumbnails.py <template.pptx>
<scratch>/thumbs` and Read the resulting JPG(s). The output prefix **must** sit
inside `<scratch>`. For each slide note
its **index** (0-based presentation order), **role/layout** (title, bullets, divider,
chart, table, 2-column, image, closing, …), and **visual character**. With the
structure facts already in hand, you can label each thumbnail confidently.

If `soffice`/`poppler` are missing, skip the vision pass — the structure inventory
stands on its own.

Hold this inventory in your **working context** — it is a scratch catalogue, not a
saved file; the persisted decisions go to `mapping.json` in Step 3.

### Step 3: Map slide entries → template sample slides

For each slide entry in the YAML, choose the best-fitting sample, in priority order:

1. **`suggested_layout`** — the primary hint from the YAML.
2. **Body shape** — `body: ""` → a section-divider sample; numbered/bulleted body
   → a bullet sample; title-slide-style subtitle → the title sample.
3. **`data` type** — `bar_chart`/`line_chart`/`pie_chart`/`histogram` → **prefer a
   sample whose chart is that exact plot type**; a `table` → a table sample; an
   `image` → a picture sample.
   - **No sample of the needed plot type, but the template has *some* chart** → map
     to the **closest chart sample** and note `add_chart (swap type)` in `notes`.
   - **No chart sample at all** → map to any plain sample and note `add_chart` in `notes`.

   (These notes drive the Step-4 chart branch; see [Charts](#charts).)

**Closest match, never block.** If nothing fits, pick the nearest sample and move
on. If the content needs a layout no sample provides (e.g. a 2×4 grid), pick the
closest sample that has **one** styled cell to replicate and flag it for the grid
solver in Step 4.

Write decisions to **`mapping.json`** next to the YAML — a list of
`{yaml_index, template_index, notes}`. Note any fallback in `notes`.

### Step 4: Build the deck (raw XML)

Work inside `<scratch>` (created in Step 1).

1. **Unpack** the template:
   `python office/unpack.py <template.pptx> <scratch>/unpacked`

2. **Resolve order → files:** `python slide_order.py <scratch>/unpacked` gives the
   `index → slideN.xml` map. Translate every `mapping.json` `template_index` into a
   concrete sample slide file.

3. **Duplicate samples, in YAML order.** For each slide entry, run
   `python add_slide.py <scratch>/unpacked <sampleSlideN.xml>`. It creates a new
   `slideK.xml` (copying rels/Content_Types/rIDs correctly) and **prints the
   `<p:sldId …/>` line** to add. Collect these lines.

4. **Rebuild `<p:sldIdLst>`** in `ppt/presentation.xml` with the Edit tool: insert
   the new `<p:sldId>` entries **in YAML order**, and **remove the original
   sample-slide `<p:sldId>` entries** (the leftover samples). Do all structural
   changes before editing content.

5. **Fill each new slide** by editing its XML. For each built `slideK.xml`:
   - **Title / body text** → **use the Edit tool** on the slide XML. Replace the
     sample's placeholder text; render light Markdown as separate `<a:p>`
     paragraphs (bold → `<a:rPr b="1">`, `-`/numbered → one `<a:p>` each); **strip
     `{{placeholder}}` tokens** (they only marked where an object goes — the sample
     already positions it). Follow the formatting rules below.
     - **Bulk shortcut**: for the common cases (title, the insight line, the
       caption, and plain/numbered/bold-lead bullet bodies) you may instead drive
       `fill_text.py <dir> slideK.xml --spec <spec.json>`, which sets them from a
       JSON spec while reusing the sample's styling — handy when a deck has many
       text slides. It only covers what its spec expresses; **fall back to the
       Edit tool** for richer formatting (hyperlinks, per-word colour, superscript,
       mixed sizes, multi-level nesting). See `fill_text.py`'s header for the schema.
   - **`data` entries** — the chart/table/notes scripts read the YAML **directly**
     via `--yaml <input.yaml> --index <yaml_index>` (and `--data <key>` to pick one
     of several `data` entries; omit when the slide has just one). **Never hand-write
     a temp JSON of the data** — that transcription step is where cell values get
     altered (e.g. `↑` → "up", en-dash → hyphen) and rows get dropped. Route by `type`:
     - `bar_chart`/`line_chart`/`pie_chart`/`histogram` → route by the `mapping.json`
       note (see [Charts](#charts) for the why):
       - Same-type sample (no `add_chart` note) → reuse it:
         `python set_chart_data.py <scratch>/unpacked slideK.xml --yaml <input.yaml> --index <i> [--data <key>]`.
       - `add_chart` note (wrong plot type, or no chart sample) → build from scratch:
         `python add_chart.py <scratch>/unpacked slideK.xml --yaml <input.yaml> --index <i> [--data <key>]`.
     - `table` → `python fill_table.py <scratch>/unpacked slideK.xml --yaml <input.yaml> --index <i> [--data <key>]`.
     - `image` → `python set_image.py <scratch>/unpacked slideK.xml --path <file> --alt "<caption>"`.

     (Each still accepts a pre-extracted `--data-json <entry.json>` if you ever need
     it, but `--yaml/--index` is the default — it keeps values verbatim from source.)
   - **Notes / provenance — run for *every* slide, unconditionally.** Run
     `python set_notes.py <scratch>/unpacked slideK.xml --yaml <input.yaml> --index <i>`
     (it extracts the whole slide entry from the YAML itself).
     **Do not pre-judge whether the slide "has notes"** — call this once per built
     slide regardless. The script decides: it assembles the notes body from the
     `speaker_notes` prose, then a **Supporting claims** block (each `prose_sources`
     claim + its source), then a **Data sources** block (each `data` entry's name,
     type and source/path), and emits a notes part when *any* of those three is
     present (no-op otherwise). Keying this off `speaker_notes` alone silently drops
     the **Data sources** provenance on chart/table slides that carry `data` but no
     prose notes.
   - **Grid layouts** the sample can't express → see
     [The grid solver](#the-grid-solver-clone_gridpy).

   Slides are independent XML files — if subagents are available, fill them in
   parallel (tell each subagent: the slide path, **"use the Edit tool"**, and the
   formatting rules below).

6. **Clean:** `python clean.py <scratch>/unpacked` (drops the orphaned sample slides
   and now-unreferenced media/charts).

7. **Pack:** `python office/pack.py <scratch>/unpacked <out>/deck.pptx`.

### Step 5: Clean up and report

Once `deck.pptx` is packed and confirmed to exist, **delete `<scratch>`** (`rm -rf
<yaml_dir>/.compose-pptx-build/`) — it holds only disposable intermediates
(thumbnails, the unpacked XML tree). If the build failed before packing, **leave
`<scratch>` in place** so its contents can be inspected.

Then tell the user:

- Output path and slide count.
- The per-slide template mapping (slide entry → sample used).
- Any slide that fell back to a **non-ideal** sample (from `mapping.json` notes) or
  used the **grid solver**, so the user can adjust the template or YAML.
- Any **missing image files** (`type: image` paths that didn't exist).

## Re-running and edits

The deck is regenerated from the YAML, so to change content **edit the YAML and
re-run** rather than hand-editing the `.pptx`:

- Content/structure changes → edit the YAML via `narrative-to-slide-outline`, then
  re-run this skill.
- A different look → swap the template `.pptx` and re-run.

The YAML is the single source of truth; the `.pptx` is a disposable build artifact.

## Charts

Two scripts produce native, editable charts; which one to use is fixed by Step 3's
mapping note:

| Mapped sample's chart | Script | What it does |
| --- | --- | --- |
| **Same plot type** | `set_chart_data.py` | Reuse the sample chart: fork its part, write the YAML data, keep its axes/colours/placement (**preferred**) |
| **Wrong plot type** | `add_chart.py` | Build from scratch, but **take over the wrong-type chart's frame in place** (same position & size); the old part is orphaned and `clean.py` drops it |
| **No chart sample** | `add_chart.py` | Build from scratch into `--area-in` or a default box below the title |

The rest of this section explains the why.

**Why fork (`set_chart_data.py`).** `add_slide.py` duplicates a slide by copying its
XML **and its rels**, so two slides built from the same chart sample would **share one
chart part** — writing data into one corrupts the other. `set_chart_data.py` avoids this:
it **forks** the chart part (`chart{N}.xml` + its embedded `.xlsx` get fresh copies, the
slide is repointed, `[Content_Types].xml` updated), rewrites the cached categories/series,
and **regenerates the embedded workbook with openpyxl** so "Edit Data" stays consistent.
Only the data changes — axes, colours and plot type are inherited, which is why each YAML
chart type must route to a same-type sample in Step 3.

**Why from-scratch (`add_chart.py`).** When no same-type sample exists, it builds a
complete chart part from scratch (`c:chartSpace` XML + an openpyxl-generated `.xlsx` +
rels + `[Content_Types].xml`). For a **wrong-type** sample it **takes over the copied
chart's `<p:graphicFrame>` in place** — reusing its `<a:off>`/`<a:ext>` so the new plot
lands at the template's chosen position/size (old part orphaned, dropped by `clean.py`);
with **no chart sample** it places at `--area-in` or a default box below the title. It
stays on-theme via `<a:schemeClr val="accentN"/>` references (no hard-coded colours,
`theme1.xml` never parsed) and supports `bar_chart`, `line_chart`, `pie_chart`,
`histogram` (pie is axis-less, slice-coloured via `varyColors`). **Prefer
`set_chart_data.py` when a same-type sample exists** — it inherits exact axis/label
styling the from-scratch path only approximates.

## Tables

`fill_table.py` reuses the sample table object: it grows/shrinks rows and columns by
deep-copying the last `<a:tr>`/`<a:gridCol>`/`<a:tc>` (so new cells inherit the
sample's fills, borders, fonts), redistributes the original total width so a grown
table still fits, and rewrites each cell's text **in place**, preserving the first
run's `<a:rPr>` so the template's cell font/size/colour survives. Apply the schema's
number-vs-string rule — string cells render verbatim, numbers may be formatted.

## Images

`set_image.py` replaces a sample `<p:pic>`'s image with a file from disk, reusing the
sample's position/size/crop: it copies the new image into `ppt/media`, adds a
`[Content_Types].xml` Default for its extension if missing, adds a fresh image
relationship, repoints the `<a:blip>` `r:embed`, and sets the alt text (`descr`)
from `caption`.

## The grid solver (`clone_grid.py`)

For the "novel layout" case where a slide entry needs a grid the template ships no
sample for.

**Do not hand-author bare shapes and compute EMU by hand.** Instead:

1. Map the slide to the closest sample that contains **one** already-styled cell
   (a card / icon-box / stat tile — *card* is an informal name for a styled
   `<p:sp>`/`<p:grpSp>`) — note its shape's `cNvPr id` from the slide XML.
2. After duplicating that sample, run:
   ```
   python clone_grid.py <scratch>/unpacked slideK.xml \
       --shape-id <id> --rows R --cols C \
       [--area-in "x,y,w,h"] [--margin-in 0.5] [--gap-in 0.25] [--no-resize]
   ```
   It removes the source shape and lays **R×C deep-copies** of it across a computed
   grid, each placed (and by default resized) into its cell with a unique shape id
   and a name `gridcell_r{r}c{c}`. Every cell inherits the template's real visual
   language (fill, outline, font, effects) — **only the geometry is solved here**.
3. Fill each cell's text with the Edit tool (find each by its `gridcell_rNcM` name).

`clone_grid.py` does **not** fit text — a cell narrower than the source may overflow
(caught in the separate QA stage).

## Formatting rules (when editing slide XML)

- **Bold headers, subheadings and inline labels**: `b="1"` on `<a:rPr>`.
- **No unicode bullets (•)**: let bullets inherit from the layout; only specify
  `<a:buChar>`/`<a:buNone>` to override.
- **Multi-item content** → one `<a:p>` per item; never concatenate into one string.
  Copy the sample paragraph's `<a:pPr>` to preserve spacing.
- **Smart quotes**: unpack escapes them to entities (`&#x201C;` …) and pack leaves
  them; when you add quoted text by hand, type the entity, since the Edit tool
  normalizes curly quotes to ASCII.
- **Remove, don't blank, excess sample elements**: if the sample has 4 cells and
  the content has 3, delete the 4th element entirely (not just its text).
