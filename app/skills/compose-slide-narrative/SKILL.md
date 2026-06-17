---
name: compose-slide-narrative
description: Composes a Markdown narrative document (from raw data, existing reports, or user intent) as the shared upstream input for downstream rendering skills, such as the slide-outline/pptx pipeline or the HTML deck pipeline.
disable-model-invocation: true
---

# Compose Slide Narrative

**Non-negotiables** (full rules below):

- **Stop at every 🛑 GATE** — get the user's input before proceeding: via `AskUserQuestion`, or by ending your turn and waiting for their reply.
- **Never fabricate a Source** — unbacked claims stay plain prose or `[needs-verification]`.
- **Scope is sacred** — only paths the user pointed at; no network.

## Output format

Two reference files define the target:

- `references/narrative_format.md` — the **single source of truth** for what a valid `narrative.md` is.
- `references/example_narrative.md` — a **complete worked example** of that format.

> **Note**: `example_narrative.md` is written at **Normal** volume. Always use it as the *structure and formatting* reference, but calibrate prose length to the level chosen in Step 3 — see the volume table in Step 5.

This skill adds **writing discipline** on top of that format — most importantly the source-attaches-to-claim rule below.

## The Source-attaches-to-claim rule

Every numeric or factual claim is in one of three states.

1. **Verified** — supporting data exists locally **within the user-specified scope**. Attach a Source breadcrumb (to the table, or inline if qualitative). **Actively hunt for this state** before falling through: scan the in-scope files for names, sheets, or columns that plausibly back the claim.
2. **Asserted-without-source** — the user said it; an active search did not turn up a file that backs it. Keep the prose with no Source. In Step 6 ask _where_ that data lives (usually more productive than asking _whether_ to cite it).
3. **Inferred-by-you** — you suspect it from context but the data doesn't directly say it. Mark inline with `[needs-verification]`. **Never invent a Source path.**

The default failure mode for AI-written narratives is fabricating numbers or sources to sound convincing. This rule makes that failure visible instead of silent.

**Trigger — catch it at the moment of writing.** The instant you're about to put down a number or named fact and can't point to an in-scope file for it, stop: that hesitation *is* the signal. Resolve it into one of the three states — hunt for the backing file (→ Verified), mark `[needs-verification]` (→ Inferred), or leave it as plain prose with no Source (→ Asserted). Never resolve it by inventing a `(Source: ...)`.

## Where this fits

```
[Raw data / docs / user intent]
        │
        ▼
[THIS SKILL: narrative MD]
        │
        ├──→ [narrative-to-slide-outline: slide YAML] ──→ [compose-pptx: .pptx]
        │
        └──→ [compose-html-slides: .html]
```

`narrative.md` feeds two downstream pipelines (slide-outline → pptx, and the HTML deck), so its format is non-negotiable.

## Workflow

> **🛑 GATE = obtain the user's input before proceeding; never act on an assumption you could have checked.** Gates are the user check-ins below — skipping them is the most common failure of this skill. A gate is cleared one of two ways:
>
> - **(a) `AskUserQuestion`** (discrete choices — Steps 3, 5): the call blocks and returns the user's answer, so **the tool call itself is the proof you stopped**. Continue in the same turn once you have the answer; no `⏸` line is needed.
> - **(b) Prose question + turn end** (open / free-form — Step 4): **end your turn with that gate's `⏸ …` pause line** — a literal line stating what you're waiting for — and resume only after the user's next message. For these gates the pause line is the proof you stopped: a prose gate with no `⏸` line was skipped.

### Invariants — true at every step; re-check before each gate

- [ ] **Preflight**: read both reference files before Step 1.
- [ ] **Scope is sacred**: only user-pointed paths; no network.
- [ ] **Never fabricate a Source** (see § The Source-attaches-to-claim rule).
- [ ] **Stop at every 🛑 GATE** (Steps 3–5): clear it via `AskUserQuestion` (Steps 3, 5), or — for the prose gate (Step 4) — by emitting its `⏸` line and ending the turn.
- [ ] **Draft only after the Step 5 gate**.
- [ ] **Verify before reporting** (Step 6 pass → report).

### Preflight reads — do this before Step 1, every time

**In a single parallel batch (one round-trip), Read both reference files together:**

- **`references/narrative_format.md`** — the **rules**: document skeleton, inline tables, `(Source: ...)` breadcrumbs, images. Defines what is *valid*.
- **`references/example_narrative.md`** — the **shape to imitate**: a full narrative showing density, voice, and how Source breadcrumbs attach to claims in living prose. The spec's inline snippets do **not** substitute for it.

**Two entry points**:

- **New narrative** — start at Step 1 below.
- **Working from an existing document** (editing a narrative.md, or converting a Word/txt/PDF/MD to a new narrative) — skip to the "Working from an existing document" subsection at the end of Step 6.

### Step 1: Capture initial intent + scope

Two things only:

1. **Rough goal** — "H1 sales review + strategy", "case study for Y Corp", "risk exploration in this data", etc.
2. **Source scope** — folder or file paths.

If invoked with no context (just `/compose-slide-narrative`), ask: _"What kind of slide narrative do you want, and where is the source material?"_ If only one is missing, ask just for that. Detailed scoping is Step 3's job — don't try to extract it all here.

**Hard rule**: never autonomously scan directories the user did not point at, even ones that look obviously useful like `./data/` next to the working directory.

**Network access**: never. Local files only — no `WebFetch` or remote APIs.

### Step 2: Inventory the scope (do not analyze yet)

**Why its own step:** you can't know which files deserve a deep read until the angle is locked _with the user_ in Step 3 — relevance is defined by an angle not yet chosen. So the deliverable is **a map of what's in scope**.

Build the inventory from cheap signal only — file names, folder structure, lightweight metadata (Excel sheet names, CSV column headers, row counts, PDF page counts). This is what lets Step 3 ask **specific** questions instead of generic ones.

For `.txt`/`.md` files (which have no headers or sheet names to sample), the cheap signal is the **first few lines only**: use the **Read tool with a small `limit`** to identify what the file is — never `cat`/`head`/`tail`.

**Not in this step:** full file contents, summaries, metrics, or drafting — those wait for Step 4.

**Python interpreter** (used here and in Step 4): detect it each run — don't assume a fixed path from CLAUDE.md or memory (this project may run in different environments). Probe for a project-local env first (`./.venv/bin/python`, a `uv`/Poetry venv, or a `pyproject.toml`/`requirements.txt`); else fall back to system `python3`. Confirm packages import before relying on them.

Recommended libraries:

- **CSV / Excel** — `pandas` (with `openpyxl` for `.xlsx`)
- **Word** (`.docx`) — `python-docx` (read paragraphs and tables; cite by enclosing heading text)
- **PDF** — `pdfplumber`; fall back to `pdftotext` or `markitdown` for scanned PDFs
- **PPTX** — `python-pptx`
- **Markdown / text** (`.md`, `.txt`) — **Read tool only** (see the Step 2 note above).
- **Images** — note path + filename only; do not OCR unless asked

### Step 3: Initial scoping dialogue

With the Step 2 inventory in hand, questions can be specific instead of generic. Agree on a **tentative** direction so you know what to read deeply in Step 4. Two things:

1. **Story angle** — the main thread of the narrative.
2. **Audience and output volume** — who it's for, how much prose the narrative should carry, plus tone if not obvious. Offer three discrete volume levels via `AskUserQuestion`: **Concise** (keyword-level, minimal prose per section), **Normal** (balanced — short paragraphs with the essential context), **Long** (fuller explanation and supporting detail per section).

Use the inventory to make questions specific. Bad: _"What kind of analysis do you want?"_ Good: _"For the H1 sales review, I see q1_sales.csv, q2_sales.csv, and promotion_cost.xlsx. Three angles: (a) sales trend only; (b) strategy/recommendation focus; (c) include promotion-cost ROI as a third pillar. Which fits?"_

Keep it short: 1–2 rounds, not exhaustive — Step 4 will validate against actual data anyway. One-line plan confirmation before moving on.

Style:

- Plain prose for open questions; `AskUserQuestion` only when there's a clean set of discrete options

> **🛑 GATE — do not start Step 4 until the user has answered.** You MUST put the scoping questions to the user via `AskUserQuestion` (for the discrete ones) and get a reply before opening any source file. The angle they pick decides *which* files Step 4 reads — reading ahead means reading the wrong ones. Do not begin deep reading until their answer is in hand; once it is, continue in the same turn.

### Step 4: Deep exploration + scope confirmation

Open the files implied by the tentative angle and read enough to evaluate whether the angle holds. Out-of-scope files are not touched.

Then **check in with the user** with what you found:

- What the data supports cleanly
- What's thinner, missing, or contradictory
- Whether a different angle from Step 3's options now looks stronger

> **🛑 GATE — stop here and end your turn.** Present what the data supports cleanly, what's thin or contradictory, and whether another angle now looks stronger — then **wait for the user's reply**. Do not start drafting in the same turn on the assumption the angle still holds. The user's response is what locks the scope; only after it do you go to Step 5. If they switch to an angle needing other files, loop back: read those, report, wait again. End the turn with:
>
> `⏸ Waiting for you to lock the angle before Step 5 (draft).`

### Step 5: Draft the narrative

> **🛑 GATE — ask before writing a single line.** Put one final question to the user via `AskUserQuestion` — **closing Q&A section, yes or no?** — and get the answer before drafting. One short question only; don't reopen the scoping dialogue.

Closing Q&A is common for board/executive decks, often skipped for status updates, tutorials, short pitches.

**Match the example's structure, not necessarily its prose length** — it's written at **Normal**, so calibrate to the level chosen in Step 3 using these targets:

| Level       | Prose per section                                        | Executive Summary | Anticipated Q&A answers |
| ----------- | ------------------------------------------------------- | ----------------- | ----------------------- |
| **Concise** | One short framing sentence (or none) + keyword bullets; let tables carry the data | Bullets           | ≤ 1 sentence each       |
| **Normal**  | Short framing/interpretation around each table, roughly as the example shows      | Short paragraph   | 1–2 sentences each      |
| **Long**    | Fuller multi-sentence interpretation per section, more than the example           | Full paragraph(s) | Multi-sentence each     |

Tables are not prose — keep the tables a section needs at every level; the volume level scales the **words around** them, not the data.

**Q&A count** (when a closing Q&A is included): ≤2 questions at Concise, ~3 at Normal, ~5 at Long — always within the format's 1–5 range.

Then produce the full first draft in one pass.

Composition rules:

- **Tables vs. inline citation.** When a section should show data visually, extract just the relevant rows and columns from the source file into an inline Markdown table and attach a Source breadcrumb to it. When the number is just supporting a prose claim and doesn't need its own visualization, skip the table and put an inline `(Source: ...)` at the end of the sentence. The downstream pptx skill turns tables into charts, so embedding a table is a deliberate "render this as a chart" signal.
- **Apply the three-state rule** (see above) — never fabricate a Source path. Missing numbers → placeholder like `$XX M`, flag in Step 6.
- **Respect the source author when re-formatting an existing document.** Lift structure and claims; adapt density and framing for the audience, but don't rewrite the analysis. Don't treat the source document itself as a terminal citation — actively hunt in-scope data files (CSV, Excel, etc.) that back its claims and attach Source breadcrumbs to those instead.
- **Images.** Embed an image (`![meaningful alt](path)`) only when the visual itself carries meaning that prose or a table cannot — a team/event photo, product or UI screenshot, logo, or an existing diagram the user supplied or that lives in scope.
- **Closing block**: a Conclusion with Key Takeaways (3–5 bullets) is recommended for most decks but skippable for short talks, tutorials, or case-studies. Include Anticipated Q&A (1–5 questions with brief answers, scaled by volume level — see the Q&A count note above) only if the user said yes above.
- **One slide ≠ one section** — write flowing narrative prose; let the downstream skill decide slide breaks.

Write the draft to the output path.

**Default path convention: `./Output/{YYYY-MM-DD}-{slug}/narrative.md`**

- `{YYYY-MM-DD}` — today's date.
- `{slug}` — a short **English** kebab-case identifier derived from the confirmed title/angle (lowercase ASCII, hyphen-separated, e.g. `h1-sales-review`). Always English even when the title is in another language: transliterate or summarize into English. Fall back to `narrative` if no sensible slug can be formed.
- **Collision handling**: if that directory already exists (same theme rebuilt the same day), suffix the directory with `-02`, `-03`, … — e.g. `./Output/2026-05-29-h1-sales-review-02/`.

The folder — not the file — is the unit of work: it is the home for all downstream artifacts of this deck (the slide outline YAML and the final `.pptx`), so the narrative file name stays the fixed `narrative.md`. The user may override this path.

### Step 6: Verify against sources, then report and iterate

**Source-verification pass (runs automatically, before the report).** Once the draft is written, dispatch a
subagent (Agent tool, `subagent_type: general-purpose`) to fact-check every `(Source: ...)` breadcrumb in
the draft against the file it points at. This is the QA gate that catches the skill's default failure mode —
numbers that drift from their source.

- The subagent's full instructions live in **`./references/source_verification.md`** — point it there and
  have it read that file before acting. Do not inline the procedure here.
- In the dispatch prompt, hand it: the `narrative.md` path, the in-scope source paths, and the standing
  constraints (**scope is sacred, no network, never fabricate a Source**). It starts cold and inherits none
  of this conversation.
- **Fix policy** (enforced by the reference file): the subagent **auto-fixes only unambiguous value
  mismatches** (a plain transcription error against a single clearly-resolved source cell) with the Edit
  tool. Everything judgment-dependent — rounding/aggregation differences, ambiguous or broken locators,
  stale-source suspicion, structural mismatches, uncited claims, `[needs-verification]` markers — is
  **reported, not edited**.
- It returns a structured report; fold that into the report below rather than messaging the user mid-pass.

This pass is read-and-verify plus narrow auto-correction — it does **not** replace the user's authority over
un-cited claims and markers. Those still go to the user in the report below.

After verification, report back:

- Output path
- Section count and inline-table count
- Sources cited — number of distinct files referenced
- **Verification result** (from the Step 6 pass): breadcrumbs checked, **auto-fixes applied** (list each as
  old → new with location), and **findings needing a human decision** (broken/ambiguous locators,
  rounding/aggregation or stale-source mismatches). User decides each.
- **Un-cited claims** — list each. User decides: add evidence, accept, or drop.
- **`[needs-verification]` markers** — list each with surrounding sentence. User decides: provide source → cite it; confirm without data → drop the marker, keep as prose; reject → remove or rephrase.
- _"Anything to refine?"_

Revision loop:

- Accept one instruction (or a small batch) per turn
- Apply with the **Edit tool, not Write** — preserves breadcrumbs, ordering, formatting
- One-sentence confirmation of what changed
- For a new claim that needs evidence: check what you already read from the source materials first, then ask the user where the data is.
- If the user asks for a full rewrite, go back to Step 3 and re-ask from the start
- Repeat until the user signals done ("OK", "looks good", "ship it")

**Working from an existing document (new conversation)**:

_Editing an existing narrative.md:_

- Ask for the narrative path (required)
- Ask if the original data sources are still accessible (only if revisions add new sourced claims)
- Skip Steps 1–5. Read the existing narrative, then run the Step 6 report on it (sources cited, un-cited claims, `[needs-verification]` markers) and enter the revision loop above.

_Converting an existing document (Word, txt, PDF, MD) to a new narrative:_

- Ask for the source document path and any additional in-scope data files
- Skip Steps 1–2. Read the document → abbreviated Step 3 (angle + audience only) → Steps 4–5 (hunt backing data files, draft) → Step 6 report.

**Exit**: re-run the Step 6 report on the updated file, then stop.
