"""Fill a slide's text from a JSON spec (raw-XML, defusedxml — no python-pptx).

A general-purpose helper for the *common* text cases in Step 4, so you don't
hand-edit dozens of `<a:p>` blocks: title / insight / caption single-run swaps,
and multi-paragraph bullet bodies with per-paragraph bullet mode and bold-lead
runs. It edits the slide XML in place, reusing the sample's run/paragraph
styling (font, size, colour, spacing) — only text, bold flag and bullet glyph
change.

It does NOT replace the Edit tool. Reach for the Edit tool when the formatting
is richer than this spec can express (hyperlinks, per-word colour, superscript,
mixed sizes, multi-level nesting, custom spacing). Use this for the bulk, the
Edit tool for the exceptions.

Usage:
    python fill_text.py <unpacked_dir> <slideN.xml> --spec <spec.json>
    python fill_text.py <unpacked_dir> <slideN.xml> --spec-json '<json string>'

Spec schema (all keys optional):
    {
      "replace": [
        {"find": "<exact current run text>", "text": "<new text>"}
      ],
      "bodies": [
        {
          "anchor": "<exact text of a run inside the target body textbox>",
          "paragraphs": [
            {"bullet": "number"|"bullet"|"none",   # omit to keep the sample's
             "runs": [{"text": "Lead: ", "bold": true},
                      {"text": "rest of the line", "bold": false}]}
          ]
        }
      ]
    }

`body` (singular object) is accepted as a shorthand for a one-element `bodies`.

- `replace` swaps the text of the FIRST run whose current text equals `find`
  (titles, the insight line, the caption, a closing subtitle). Run styling is
  preserved; only the characters change.
- each `bodies` entry finds the textbox containing `anchor`, clears its
  paragraphs, and rebuilds them from `paragraphs`, cloning the anchor
  paragraph's `<a:pPr>` and the anchor run's `<a:rPr>` as the style template.

Non-ASCII (—, •, ≥, →, curly quotes) is written as UTF-8; `&`,`<`,`>` are
escaped by the serializer. Exits non-zero with a clear message if a `find` or
`anchor` is not present on the slide.
"""

import argparse
import json
from pathlib import Path

import defusedxml.minidom as minidom

BULLET_CHAR = "•"  # •


def _text_of(node):
    return "".join(c.data for c in node.childNodes if c.nodeType == c.TEXT_NODE)


def _set_text(node, dom, s):
    while node.firstChild:
        node.removeChild(node.firstChild)
    node.appendChild(dom.createTextNode(s))


def _kids(el, tag):
    return [c for c in el.childNodes
            if c.nodeType == c.ELEMENT_NODE and c.tagName == tag]


def _apply_replace(dom, slidefile, repls):
    ats = dom.getElementsByTagName("a:t")
    for r in repls:
        find, new = r["find"], r["text"]
        for at in ats:
            if _text_of(at) == find:
                _set_text(at, dom, new)
                break
        else:
            raise SystemExit(f"{slidefile}: replace target not found: {find!r}")


def _set_bullet(pPr, dom, mode):
    if mode is None:
        return
    for tag in ("a:buNone", "a:buAutoNum", "a:buChar", "a:buFont"):
        for e in _kids(pPr, tag):
            pPr.removeChild(e)
    if mode == "number":
        pPr.appendChild(dom.createElement("a:buAutoNum")).setAttribute(
            "type", "arabicPeriod")
    elif mode == "bullet":
        pPr.appendChild(dom.createElement("a:buFont")).setAttribute(
            "typeface", "Arial")
        pPr.appendChild(dom.createElement("a:buChar")).setAttribute(
            "char", BULLET_CHAR)
    elif mode == "none":
        pPr.setAttribute("marL", "0")
        pPr.setAttribute("indent", "0")
        pPr.appendChild(dom.createElement("a:buNone"))
    else:
        raise SystemExit(f"unknown bullet mode: {mode!r} (use number|bullet|none)")


def _apply_body(dom, slidefile, body):
    anchor = body["anchor"]
    target_p = None
    for p in dom.getElementsByTagName("a:p"):
        if any(_text_of(at) == anchor for at in p.getElementsByTagName("a:t")):
            target_p = p
            break
    if target_p is None:
        raise SystemExit(f"{slidefile}: body anchor not found: {anchor!r}")

    txBody = target_p.parentNode
    tmpl_p = target_p.cloneNode(deep=True)
    runs = _kids(tmpl_p, "a:r")
    if not runs:
        raise SystemExit(f"{slidefile}: anchor paragraph has no run to template")
    tmpl_r = runs[0].cloneNode(deep=True)

    for p in _kids(txBody, "a:p"):
        txBody.removeChild(p)

    for para in body["paragraphs"]:
        p = tmpl_p.cloneNode(deep=True)
        for r in _kids(p, "a:r"):
            p.removeChild(r)
        pPr_list = _kids(p, "a:pPr")
        if pPr_list:
            _set_bullet(pPr_list[0], dom, para.get("bullet"))
        for run in para["runs"]:
            r = tmpl_r.cloneNode(deep=True)
            rpr = _kids(r, "a:rPr")
            if rpr:
                rpr[0].setAttribute("b", "1" if run.get("bold") else "0")
            _set_text(_kids(r, "a:t")[0], dom, run["text"])
            p.appendChild(r)
        txBody.appendChild(p)


def main():
    ap = argparse.ArgumentParser(description="Fill a slide's text from a JSON spec.")
    ap.add_argument("unpacked_dir")
    ap.add_argument("slide", help="slide file name, e.g. slide20.xml")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--spec", help="path to the spec JSON")
    g.add_argument("--spec-json", help="the spec as an inline JSON string")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8")
                      if args.spec else args.spec_json)

    path = Path(args.unpacked_dir) / "ppt" / "slides" / args.slide
    if not path.exists():
        raise SystemExit(f"Error: {path} not found")
    dom = minidom.parse(str(path))

    if spec.get("replace"):
        _apply_replace(dom, args.slide, spec["replace"])
    bodies = spec.get("bodies", [])
    if spec.get("body"):
        bodies = [spec["body"]] + list(bodies)
    for body in bodies:
        _apply_body(dom, args.slide, body)

    path.write_bytes(dom.toxml(encoding="utf-8"))
    n_r = len(spec.get("replace", []))
    print(f"Filled {args.slide}: {n_r} replace(s), {len(bodies)} body/bodies.")


if __name__ == "__main__":
    main()
