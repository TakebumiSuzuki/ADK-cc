---
name: compose-html-slides
description: Convert a structured Markdown narrative report into a single self-contained, presentation-style HTML deck (left nav + one-slide-at-a-time stage, charts from tables).
disable-model-invocation: true
---

# compose-html-slides: Markdown narrative → presentation HTML deck

## What this produces

A **single self-contained `.html` file** that opens by double-click — no build
step, no server, no bundled JS framework. The only external dependency is Google
Fonts (Inter). Layout:

- a fixed **left nav** listing every slide (chapter dividers styled as "Parts",
  content pages indented beneath them), and
- a scrollable **right stage** that shows exactly one slide at a time.

Each slide is **at least 16:9** (a minimum height derived from the content width)
and **grows taller when the content needs it**, so a dense slide simply scrolls
vertically rather than overflowing or shrinking the type. The reader moves with
the nav, the `←`/`→` keys, or `PageUp`/`PageDown`.

## The reference file — read it before building

`references/template.html` lives next to this file. **Read it before you build
anything.** It is the **design system + every component** in a small skeleton
deck. Its `<style>` block (the design tokens) and its `<script>` block are the
**source of truth**: copy them **verbatim**. Its slides demonstrate one of each
component (cover, chapter divider, stats, bars, histogram, line chart, scatter
plot, donut, bullet/benchmark, callout, two-column, summary, takeaways, Q&A), each
populated with representative demo data and hand-computed charts — so you can see
a component filled in, not just its empty shell. Build your deck by copying this
file and replacing the example slides.

**The demo slides show how each component *looks*, not a size cap.** When one
`###` carries a lot — a long paragraph, many bars, a full table — put **all of it
on that one slide, copied verbatim from `narrative.md`**, and let the slide grow
tall: the 16:9 floor is a minimum, not a ceiling.

## Inputs — both are required

This skill takes **two** inputs, collected up front:

1. **`narrative.md`** — the structured report to render (the build source).
2. **the data directory** — the folder holding the raw source files the narrative
   cites in its `Source:` lines.
   This is **not optional**: it is what the final **Fidelity QA** uses to confirm
   every number in the narrative actually matches its source data.

If the user gives you only the narrative, **stop and ask for the data directory
path before building** (`AskUserQuestion`). Do not proceed on the narrative alone —
the data-integrity pass cannot run without it, and skipping it defeats the QA.

## Build procedure

1. **Read the whole Markdown first.** Map the structure before writing anything:
   the title block, every `##` section, which sections have `###` subsections,
   every table (and the data shape inside it), and the "Key Takeaways" /
   "Anticipated Q&A" sections. The HTML's structure should *mirror* the
   Markdown's heading structure — don't invent divisions the source lacks, and
   don't merge things it separates. The input `narrative.md` follows the shared
   pipeline format spec `../compose-slide-narrative/references/narrative_format.md`
   — consult it if a section's structure is ambiguous.

2. **Plan the deck — decide *what* goes on each slide.** Don't touch any file
   yet; this step only produces the content plan that step 3 will write in.
   - **Map the source's heading structure to pages** using the rules below, and
     plan the nav to match.
   - **For each table, pick the chart** that fits its data shape (see the
     mapping), then **compute the geometry by hand** (see the recipes). Never
     eyeball a bar width or a donut arc — wrong numbers are the most common
     failure here.
   - **Carry every `Source:` line and `[needs-verification]` marker** to the
     right slide (see Fidelity). A source that sits **inline** in the narrative's
     prose stays inline, attached to the claim it backs — don't aggregate it away.

3. **Write the deck — copy the template, then mutate it only with `Edit`, never
   `Write`.** This step pours the step-2 plan into the file.
   - First: `cp references/template.html <out>.html` (a real, byte-for-byte copy).
   - **Bright-line rule: after that `cp`, the `Write` tool must never target the
     output file again — every later change is an `Edit`.** Re-`Write`-ing the
     whole file re-emits the ~300-line design system (`<style>` + `<script>`) from
     memory: it's slow and silently risks CSS/JS drift. If you catch yourself
     assembling the full file in a `Write`, stop — you've thrown away the copy.
   - You touch **only two regions** — build each up with as many `Edit` calls
     as you need (one big replace, or several smaller ones, whatever is cleanest):
       1. **nav** — replace the template's `<ul id="navlist"> … </ul>` block.
       2. **slides** — replace from the first `<!-- ░░ COVER ░░ -->` section
          through the last `</section>` before `</main>`.
     Leave the shared `<defs>` SVG, and everything above `<main>` / below
     `</main>`, untouched. The `old_string` is the template's *existing* text
     (known and fixed); only your new content goes in `new_string`. The head,
     `<style>`, and `<script>` are never retyped.

4. **Fidelity QA** (see "Fidelity QA"). Three **mandatory** passes — coverage,
   no-drift (the `check_prose_verbatim.py` substring check), and data-integrity;
   apply every discrepancy before continuing.

5. **Verify the structure** (see the checklist).

## Page-splitting rules (Markdown → slides)

The guiding idea: **one slide per `###`, one divider per `##`** — mirror the
source's heading structure faithfully (don't merge two `###`s onto one slide). A
single `###` is **one** slide that **grows as tall as its content needs**, never
split for size.

- **Cover** — build a leading cover slide from the title block (title, author/org,
  audience, duration, date) using `.cover` + `.kicker` + `h1` + `.lede` + `.meta`.
  It is slide 0 and starts with class `show`. **The `h1` is the report title by
  default;** only if you want a punchier headline may you use a phrase **lifted
  verbatim from a real narrative sentence** (e.g. a Conclusion thesis) — **never an
  invented tagline.** The cover is the single highest-risk spot for invented prose,
  so the `h1` and any non-title `.lede` go in the no-drift allowlist (the file
  `chrome.txt`, one string per line — see Fidelity QA pass 2).
- **`##` section → a chapter-divider slide** (`<section class="slide chapter">`):
  a near-empty page showing only the section title (as `h1`), a `Part N` kicker,
  a one-line lede, and a big faded numeral watermark. This is the pptx
  "section header" slide. It gets a nav entry styled `class="part"`.
- **`###` subsection → one content slide.** Its prose becomes `.lede`/`.lede.sm`,
  its table becomes a chart. It gets a nav entry styled `class="sub"`.
- **A `##` with body prose but no `###`s** (e.g. a short "Executive Summary"):
  render its body as its **own** content slide. Don't fold that prose into the
  chapter divider — the divider stays near-empty (title + one-line lede only) and
  the body gets a page of its own, so no source paragraph is ever dropped.
- **Conclusion → three separate slides, never merged:** (1) the chapter divider,
  (2) a **Summary** slide carrying the section's wrap-up paragraph as a short
  `.big-quote` (`<h2>Summary</h2>` + the paragraph), then (3) the **Key Takeaways**
  list. Never put the wrap-up paragraph *or* the takeaways onto the divider — that
  merge is exactly how a Conclusion's intro paragraph gets silently dropped.
- **Key Takeaways → its own takeaways slide** (`.takeaways`) — a standalone page,
  not appended to a divider or to the Summary slide.
- **Anticipated Q&A → a Q&A slide** (`.qa` with `.item`/`.q`/`.a`).

**Nav contract:** every slide has **exactly one** `<a>` in `#navlist`, in slide
order, with `data-i` running `0,1,2,…` with no gaps. Chapter dividers use
`class="part"` (and a Roman numeral in `.n`); content slides use `class="sub"`.
The script auto-numbers the page footers, so you don't hand-write `NN / NN`.

## Table → chart mapping

Pick the component whose shape matches the data. The goal the user cares about:
**every table becomes a chart** unless a chart genuinely can't represent it.

| The table shows… | Use | Component |
| --- | --- | --- |
| A handful of headline KPIs (one number each) | **Stat band** | `.stats` (3 cols) / `.stats.four` (4) |
| One series across categories (e.g. revenue by practice) | **Horizontal bars** | `.barwrap` › `.bar` |
| The distribution of one variable — how often each value-range occurs | **Histogram** | `.hist` (contiguous bins) |
| One metric over time, where the *shape* of the trend matters (a dip-and-recover) | **Line chart** | `<svg class="linechart">` |
| Two numeric variables, one point per item — correlation / spread | **Scatter plot** | `<svg class="scatter">` (vary `r` → bubble) |
| Two periods compared per metric (FY24 vs FY25) | **Bars with a FY-tick + delta chip** | `.bar` + `.tick` + `.chip up/dn` |
| Parts of a whole (NPS mix, win/loss split) | **Donut** | `<svg>` + `.ring` + `.legend` |
| One headline number that needs emphasis as a "watch" item | **Callout** | `.callout` (big number + text) |
| Many metrics × {us / industry / top} benchmark | **Bullet chart** | `.bul` rows |
| A genuinely tabular matrix a chart would distort | A clean **styled table** | (build one in the deck's palette) |

Two visuals on one slide → wrap them in `.two` (two columns) or `.two.wide-left`.

## Chart-geometry recipes (compute, don't guess)

Show your arithmetic in your reasoning so it can be checked.

- **Horizontal bar** — `style="--w: P%"` where `P = value / max(values) × 100`.
  Use the data max as 100% by default. When the differences are small but you
  want to keep them honest (e.g. utilization all near 73–76%), keep the same
  `value%` scale and say so in the caption rather than zooming the axis (zooming
  exaggerates and misleads). Annotate each bar's true value in `.val` (with a
  `<small>` for secondary figures like YoY).

- **Histogram** — vertical bars for one variable's distribution, bins
  **contiguous** (a hair of gap, not the airy spacing of a bar chart). For each
  bin `style="--h: P%"` where `P = count / max(counts) × 100` — the height is a
  percent of the plot area, so the tallest bin is 100%. Put the raw count in
  `data-c` (it renders above the bar) and label each bin with its **range** (e.g.
  `20–30`) centered beneath it. Keep bins in value order, ≤ ~7 of them so the
  axis stays legible.

- **Donut** — the ring is a circle of radius `r=87`, so its circumference is
  `C = 2πr ≈ 547`. Each segment is
  `stroke-dasharray: <len> 547` where `len = share × 547`, and
  `stroke-dashoffset: -<cumulative length of all earlier segments>`.
  The first segment has offset `0`. **The segment lengths must sum to 547.**
  Put the total (e.g. "112 surveys" or "29% win rate") in `.donut .center`.

- **Line chart** (SVG `viewBox="0 0 560 240"`, baseline `y=195`) — choose a value
  window `[lo, hi]` that frames the data (not 0-based, so the movement is
  visible), then for each point `y = 195 − (value − lo)/(hi − lo) × 160`. Place
  x at evenly spaced columns (e.g. 80, 280, 480). Build the `.area` polygon as
  `baseline-left → each point → baseline-right`, the `.ln` polyline through the
  points, a `.dot` per point, a `.vlab` value label above each, and `.xlab`
  category labels under the baseline.
  The fill gradient `#lg` is defined **once globally** in a 0×0 `<defs>` SVG at
  the top of `<main>` (already in the template). Every line chart — no matter how
  many the deck has — just uses `class="area"` + `url(#lg)`; **never give a chart
  its own `<defs>` or a second gradient id.** Two `<svg>`s both declaring
  `id="lg"` is invalid HTML and the ids collide (a common multi-line-chart bug).

- **Scatter plot** (SVG `viewBox="0 0 560 300"`, plot box L=56 R=544 T=16 B=260 →
  `plotW=488`, `plotH=244`) — unlike the line chart, **both** axes are real value
  scales, so pick a window for each: `[xlo, xhi]` and `[ylo, yhi]` (pad the data so
  no point sits on an edge). For every point
  `cx = 56 + (x − xlo)/(xhi − xlo) × 488` and
  `cy = 260 − (y − ylo)/(yhi − ylo) × 244`. Draw a few `.grid` lines at the round
  ticks (same formulas), `.alab` tick labels, the two `.axis` lines, an x-axis
  `.atitle` and a rotated y-axis `.atitle`, then one `.mk` circle per point.
  **Never** connect the points and **never** add an `.area` — a scatter has no
  line, and it does **not** use the `#lg` gradient. For a **bubble** chart, size
  each marker by a third value: `r = 5 + (size − slo)/(shi − slo) × 11`. EXAMPLE:
  x-window `[0,60]`, y-window `[0,100]`; point (38, 70) →
  `cx = 56 + 38/60 × 488 = 365.1`, `cy = 260 − 70/100 × 244 = 89.2`.

- **Bullet / benchmark row** (`.bul`) — for each metric pick a window `[lo, hi]`
  padding the three values, then `pos% = (value − lo)/(hi − lo) × 100` for each
  of `.mcg` (us), `.ind` (industry), `.topq` (top quartile). **Orient every row
  so "better" is rightward**: for lower-is-better metrics (e.g. attrition),
  invert with `pos% = 100 − pos%` so the best value still sits on the right; note
  that inversion in the row's `<small>` and the legend. The `.band` spans from the
  industry marker to the top-quartile marker (`left` = min of the two, `width` =
  their distance). Echo the raw numbers in `.vals` (us **bold** / industry / top).

- **Stat** — `<div class="num">42<span>%</span></div>` — the number in the body,
  the unit/suffix in the `<span>` (it renders smaller).

## Fidelity rules

These keep the deck trustworthy — the single most important property for an exec
readout.

- **Transcribe prose; don't paraphrase it.** Reader-visible prose is copied
  **verbatim** from `narrative.md` — each text run a *contiguous span* of the
  source. No synonyms, no reordering, no added words, and **never retype a number
  from memory — copy it.** The only edit allowed is **splitting** one span across
  elements on the same slide (which grows to hold it); never **truncate or
  condense** a passage to make it "fit". The no-drift check
  (`check_prose_verbatim.py`) proves you didn't. The sole exception is **chrome**
  the narrative lacks — the cover `<h1>`, chapter-divider ledes, "Part N" kickers —
  which you keep tiny and list in the allowlist (`chrome.txt`).
- **Language follows the source.** If the report is in English, the slides
  (including UI chrome like the nav and "Part N") are in English. Don't translate
  unless asked.
- **Visualize tables; don't drop their data.** Every figure in the table should
  appear either in the chart or in its labels.
- **Keep every `Source:` attribution — and keep its granularity.**
  - A source that backs a **table or chart** → a `<p class="src">Source: …</p>`
    on that slide. If a slide pulls from several files, join them with ` · `.
  - A source the narrative puts **inline in a sentence** (e.g. "Headcount 105
    (Source: …)") → keep it **inline, right after that same claim**, as
    `<span class="note">(Source: …)</span>`. Do **not** roll it up into the
    slide-level `.src` — that severs which sentence the source actually backs.
  - The test: every `Source:` in the narrative appears in the deck, attached to
    the same thing it was attached to in the source.
- **Preserve `[needs-verification]` markers.** Render them inline as
  `<span class="note">[needs verification]</span>` — visible but understated.
  Never silently "clean them up": their job is to show what isn't yet confirmed.
- **`template.html` is a layout/geometry reference only** — never lift its
  placeholder wording, headings, or demo figures into your output.

## Restyling via design tokens

Everything visual is centralized in `:root` so a restyle is a few-line change —
you should not be hunting through rules.

- **Type size — one master knob.** `--fs-scale` (default `1.2`) multiplies
  **every** font size at once (`1.0` is the original design size). For a larger
  room push it higher; for a denser deck drop it toward `1.0`. Two display roles —
  the cover/chapter `h1` titles and the Summary body — carry a fixed `/1.2` offset
  so they keep their intended size, but still track the knob. To resize a single
  role instead, edit its own `--fs-*` token (e.g.
  `--fs-lede`, `--fs-h2`, `--fs-barname`). The tokens are grouped and commented
  (headings, body, chart elements, nav). **Never hard-code a `font-size` in px on
  a slide;** if you truly need a one-off, write `calc(<px> * var(--fs-scale))` so
  it still tracks the master knob.
- **Colour.** The palette lives in `:root` too (`--paper`, `--ink`, `--espresso`,
  `--crema`, `--terracotta`, `--olive`, …). Recolouring the deck = editing these.
- **Layout.** `--nav-w` (nav width), `--slide-max` (content width), `--slide-min-h`
  (the 16:9 floor), `--slide-pad`, `--fs-watermark`.

## Fidelity QA — one mechanical pass + two delegated to a sub-agent

After the deck is built but **before** the structural checklist, run **three
mandatory passes**. Pass 2 is **mechanical** — a script you run yourself. Passes 1
and 3 are judgement calls: **delegate them to a fresh sub-agent** (the `Agent`
tool), handing it `deck.html`, `narrative.md`, and the **data directory**. Use a
separate agent on purpose — the author that wrote the prose rationalises its own
gaps as "fine"; a clean context will not. The sub-agent only **reports**; you
apply every fix, then re-run. **If you cannot spawn a sub-agent, run passes 1 and
3 yourself as an explicit, separate step — never skip them.**

1. **Coverage (narrative → deck): nothing dropped.** Enumerate every `##` section,
   `###` subsection, section-intro paragraph, list, and `Source:` line in the
   narrative; for each, name the slide that carries it. Anything with no slide is
   a dropped item (this is the failure that lost the Conclusion intro paragraph).

2. **No-drift (deck → narrative): nothing reworded or invented — MECHANICAL.** Run:
   ```
   python3 references/check_prose_verbatim.py <out>.html <narrative>.md chrome.txt
   ```
   It confirms every reader-visible prose run in the deck is a **contiguous,
   verbatim substring** of the narrative — proving the wording, and the numbers
   embedded in it, did not drift. Whatever it flags is either **chrome** (cover
   `h1` / divider lede / kicker) you add to the allowlist `chrome.txt`, one string
   per line — keeping chrome explicit and countable — or **drift** you rewrite to a
   verbatim span. This replaces eyeballing provenance with a check, and covers
   *all* prose (takeaways, Q&A answers, captions), not a hand-picked element list.

3. **Data integrity (narrative → data): numbers are real.** For every figure the
   narrative cites with an inline or table `Source:`, open the referenced file in
   the data directory and confirm the number actually appears / is correctly
   derived. Report any figure the source data does not support — including a
   **`Source:` whose file is missing** from the data directory. This pass is **why
   the data directory is a required input** — it never gets skipped.

Apply every discrepancy from all three passes, then proceed to the structural
checklist.

## Before you finish — verification checklist

- **Chrome is byte-identical:** the `<style>` and `<script>` blocks must exactly
  match `references/template.html`. Verify:
  ```
  for tag in style script; do
    diff <(awk -v t=$tag 'BEGIN{o="^<"t">$";c="^</"t">$"} $0~o{f=1} f{print} $0~c{f=0}' references/template.html) \
         <(awk -v t=$tag 'BEGIN{o="^<"t">$";c="^</"t">$"} $0~o{f=1} f{print} $0~c{f=0}' <out>.html) \
      && echo "$tag OK";
  done
  ```
  Any diff → discard the file, re-`cp`, and redo the nav + slides edits.
- **Counts match:** number of `.slide` sections == number of `#navlist a`, and
  `data-i` runs `0..n−1` with no gaps. (`grep -c` both.)
- **Donuts close:** each donut's segment lengths sum to ~547.
- **One gradient id:** `grep -c 'id="lg"'` → 1 (the shared global def).
- **Bars in range:** every bar `--w` and histogram `--h` is ≤ 100%; every bullet
  `pos%` is within 0–100; every scatter `.mk` sits in the plot box (`cx` 56–544,
  `cy` 16–260).
- **Sources & flags carried:** every `Source:` and `[needs-verification]` from the
  Markdown appears in the deck — table/chart sources at slide level, **inline
  sources kept inline** next to their claim (`grep -c 'Source:'` deck vs. narrative).
- **Fidelity QA passed:** all three passes ran — coverage, the mechanical no-drift
  check (`check_prose_verbatim.py` exits 0), and data-integrity — and every
  discrepancy was applied.
- **It runs:** confirm the structure with a quick `grep`/script check.
