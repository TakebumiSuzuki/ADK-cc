"""Attach speaker notes to a slide (raw-XML), by cloning a template notes slide.

add_slide.py strips the notes relationship when it duplicates a slide (so two
slides never share one notes part — the same hazard as shared charts). To give a
built slide its own notes, this clones an existing notesSlide from the template
(reusing its notesMaster wiring and body styling), repoints it at this slide,
rewrites the notes body text, and registers it.

The notes body is assembled from the slide entry (`--entry-json`), in this order:
  1. `speaker_notes` — the prose notes.
  2. `prose_sources` — a "Supporting claims" block: each claim + its source.
  3. `data` — a "Data sources" block: each entry's name, type and source/path.
A slide that has none of these gets no notes part. (`--text-file` is still
accepted for raw, pre-assembled text.)

If the template contains no notesSlide at all (no notesMaster to hang one on),
it prints a warning and does nothing — notes are skipped for that deck.

Usage:
    # Preferred: read the whole slide entry straight from the slide-deck YAML.
    python set_notes.py <unpacked_dir> <slideN.xml> --yaml <deck.yaml> --index N
    python set_notes.py <unpacked_dir> <slideN.xml> --entry-json <entry.json>
    python set_notes.py <unpacked_dir> <slideN.xml> --text-file <notes.txt>

With `--yaml/--index`, the script extracts `slides[N]` itself, so the notes
prose and source citations come straight from the YAML with no hand-transcription.
Run it for every slide unconditionally — it emits a notes part only when the
entry has `speaker_notes`, `prose_sources`, or `data`, and no-ops otherwise.
"""

import argparse
import json
import re
import shutil
from pathlib import Path

import defusedxml.minidom as minidom

R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def build_notes_text(entry: dict) -> str:
    """Assemble the notes body from a slide entry: speaker_notes, then a
    Supporting-claims block (prose_sources), then a Data-sources block (data)."""
    sections = []

    notes = (entry.get("speaker_notes") or "").rstrip()
    if notes:
        sections.append(notes)

    prose = entry.get("prose_sources") or []
    if prose:
        lines = ["── Supporting claims ──"]
        for ps in prose:
            claim = (ps.get("claim") or "").strip()
            source = (ps.get("source") or "").strip()
            line = f'• "{claim}"' if claim else "•"
            if source:
                line += f"\n  — {source}"
            lines.append(line)
        sections.append("\n".join(lines))

    data = entry.get("data") or {}
    if data:
        lines = ["── Data sources ──"]
        for name, d in data.items():
            d = d or {}
            typ = d.get("type")
            source = d.get("source") or d.get("path")
            label = f"{name} ({typ})" if typ else name
            line = f"• {label}"
            if source:
                line += f": {source}"
            lines.append(line)
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def _next_index(d: Path, stem: str, ext: str) -> int:
    nums = [int(m.group(1)) for f in d.glob(f"{stem}*{ext}")
            if (m := re.match(rf"{stem}(\d+){re.escape(ext)}", f.name))]
    return max(nums, default=0) + 1


def _set_body_text(notes_dom, text):
    """Write `text` into the notes body placeholder (ph type='body')."""
    for sp in notes_dom.getElementsByTagName("p:sp"):
        phs = sp.getElementsByTagName("p:ph")
        if not phs or phs[0].getAttribute("type") != "body":
            continue
        txBodies = sp.getElementsByTagName("p:txBody")
        if not txBodies:
            return False
        txBody = txBodies[0]
        # Drop existing paragraphs, keep bodyPr/lstStyle.
        for p in list(txBody.getElementsByTagName("a:p")):
            txBody.removeChild(p)
        a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
        for line in (text.split("\n") or [""]):
            p = notes_dom.createElementNS(a_ns, "a:p")
            r = notes_dom.createElementNS(a_ns, "a:r")
            t = notes_dom.createElementNS(a_ns, "a:t")
            t.appendChild(notes_dom.createTextNode(line))
            r.appendChild(t)
            p.appendChild(r)
            txBody.appendChild(p)
        return True
    return False


def main():
    ap = argparse.ArgumentParser(description="Attach speaker notes to a slide.")
    ap.add_argument("unpacked_dir")
    ap.add_argument("slide", help="slide file name, e.g. slide5.xml")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--yaml", help="slide-deck YAML; the slide entry is extracted directly (no temp JSON)")
    src.add_argument("--entry-json", help="slide entry JSON; notes are assembled from it")
    src.add_argument("--text-file", help="file holding raw, pre-assembled notes text")
    ap.add_argument("--index", type=int, help="0-based slide index in --yaml")
    args = ap.parse_args()

    unpacked = Path(args.unpacked_dir)
    if args.yaml:
        if args.index is None:
            ap.error("--index is required with --yaml")
        from office.yaml_entry import load_slide_entry
        entry = load_slide_entry(args.yaml, args.index)
        notes_text = build_notes_text(entry).rstrip("\n")
    elif args.entry_json:
        entry = json.loads(Path(args.entry_json).read_text(encoding="utf-8"))
        notes_text = build_notes_text(entry).rstrip("\n")
    else:
        notes_text = Path(args.text_file).read_text(encoding="utf-8").rstrip("\n")

    if not notes_text:
        print(f"No speaker notes / sources for {args.slide}; skipped.")
        return

    notes_dir = unpacked / "ppt" / "notesSlides"
    samples = sorted(notes_dir.glob("notesSlide*.xml")) if notes_dir.exists() else []
    if not samples:
        print("Warning: template has no notesSlide/notesMaster; speaker notes skipped.")
        return
    sample = samples[0]

    # 1. Clone the sample notes part.
    n = _next_index(notes_dir, "notesSlide", ".xml")
    new_notes = notes_dir / f"notesSlide{n}.xml"
    shutil.copy2(sample, new_notes)

    # 2. Clone + repoint its rels: keep notesMaster, point the slide rel at our slide.
    sample_rels = notes_dir / "_rels" / f"{sample.name}.rels"
    new_rels = notes_dir / "_rels" / f"notesSlide{n}.xml.rels"
    if sample_rels.exists():
        rdom = minidom.parse(str(sample_rels))
        for rel in rdom.getElementsByTagName("Relationship"):
            if rel.getAttribute("Type").endswith("/slide"):
                rel.setAttribute("Target", f"../slides/{args.slide}")
        new_rels.write_bytes(rdom.toxml(encoding="utf-8"))

    # 3. Rewrite the notes body text.
    ndom = minidom.parse(str(new_notes))
    if not _set_body_text(ndom, notes_text):
        print("Warning: no body placeholder in notes sample; notes left as template text.")
    new_notes.write_bytes(ndom.toxml(encoding="utf-8"))

    # 4. Content_Types override.
    ct_path = unpacked / "[Content_Types].xml"
    ct = ct_path.read_text(encoding="utf-8")
    part = f"/ppt/notesSlides/notesSlide{n}.xml"
    if part not in ct:
        ov = (f'<Override PartName="{part}" '
              f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>')
        ct = ct.replace("</Types>", f"  {ov}\n</Types>")
        ct_path.write_text(ct, encoding="utf-8")

    # 5. Relate the slide to its new notes part.
    slide_rels = unpacked / "ppt" / "slides" / "_rels" / f"{args.slide}.rels"
    sdom = minidom.parse(str(slide_rels))
    # Remove any stale notesSlide rel first.
    for rel in list(sdom.getElementsByTagName("Relationship")):
        if rel.getAttribute("Type").endswith("/notesSlide"):
            rel.parentNode.removeChild(rel)
    rids = [int(m) for m in re.findall(r'Id="rId(\d+)"', slide_rels.read_text(encoding="utf-8"))]
    rid = f"rId{max(rids, default=0) + 1}"
    rel = sdom.createElement("Relationship")
    rel.setAttribute("Id", rid)
    rel.setAttribute("Type", f"{R_NS}/notesSlide")
    rel.setAttribute("Target", f"../notesSlides/notesSlide{n}.xml")
    sdom.documentElement.appendChild(rel)
    slide_rels.write_bytes(sdom.toxml(encoding="utf-8"))

    print(f"Attached notesSlide{n}.xml to {args.slide} ({len(notes_text)} chars).")


if __name__ == "__main__":
    main()
