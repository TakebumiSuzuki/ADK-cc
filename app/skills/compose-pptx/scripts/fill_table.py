"""Reshape and fill a template table from a YAML `table` entry (raw-XML).

A table lives entirely inside the slide XML (`<a:tbl>` in a `<p:graphicFrame>`) —
there is no separate part to fork (unlike charts), so this just edits the slide.
It reuses the sample table's styling: rows/columns are grown by deep-copying the
last `<a:tr>`/`<a:gridCol>` (so new cells keep the sample's fills, borders and
fonts) or trimmed, the original total width is redistributed so a grown table
still fits, and each cell's text is rewritten in place — keeping the first run's
properties so the template's cell font/size/colour is preserved.

Usage:
    # Preferred: read the table entry straight from the slide-deck YAML (no temp JSON).
    python fill_table.py <unpacked_dir> <slideN.xml> --yaml <deck.yaml> --index N [--data KEY] [--table-index 0]
    # Or pass a pre-extracted entry as JSON.
    python fill_table.py <unpacked_dir> <slideN.xml> --data-json <entry.json> [--table-index 0]

With `--yaml/--index`, the script extracts `slides[N].data[KEY]` itself (KEY may
be omitted when the slide has a single data entry), so cell values — including
strings like "↑" or "68%" — are copied verbatim and never retyped by hand.
`entry.json` is one YAML `table` data entry:
    {"type":"table","headers":["Segment","Customers","Revenue"],
     "rows":[["Enterprise",45,112],["SMB",620,18]]}
"""

import argparse
import copy
import json
from pathlib import Path

import defusedxml.minidom as minidom

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _kids(el, tag):
    return [c for c in el.childNodes if c.nodeType == c.ELEMENT_NODE and c.tagName == tag]


def _fmt(v):
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return ("%g" % v)
    return str(v)


def _reshape(tbl, nrows, ncols):
    grid = _kids(tbl, "a:tblGrid")[0]
    cols = _kids(grid, "a:gridCol")
    cur_c = len(cols)
    total_w = sum(int(c.getAttribute("w")) for c in cols if c.getAttribute("w"))

    if ncols > cur_c:
        for _ in range(ncols - cur_c):
            grid.appendChild(cols[-1].cloneNode(deep=True))
            for tr in _kids(tbl, "a:tr"):
                tcs = _kids(tr, "a:tc")
                tr.appendChild(tcs[-1].cloneNode(deep=True))
    elif ncols < cur_c:
        for gc in cols[ncols:]:
            grid.removeChild(gc)
        for tr in _kids(tbl, "a:tr"):
            for tc in _kids(tr, "a:tc")[ncols:]:
                tr.removeChild(tc)
    # Redistribute the original total width across the new column count.
    if total_w:
        each = total_w // ncols
        for gc in _kids(grid, "a:gridCol"):
            gc.setAttribute("w", str(each))

    trs = _kids(tbl, "a:tr")
    cur_r = len(trs)
    if nrows > cur_r:
        for _ in range(nrows - cur_r):
            tbl.appendChild(trs[-1].cloneNode(deep=True))
    elif nrows < cur_r:
        for tr in trs[nrows:]:
            tbl.removeChild(tr)


def _set_cell_text(tc, text, dom):
    """Set a cell's text, preserving the first run's <a:rPr> styling."""
    txBody = _kids(tc, "a:txBody")
    if not txBody:
        txBody = dom.createElementNS(A_NS, "a:txBody")
        tc.insertBefore(txBody, tc.firstChild)
    else:
        txBody = txBody[0]
    paras = _kids(txBody, "a:p")
    # Keep (or create) one paragraph; drop the rest.
    if paras:
        p = paras[0]
        for extra in paras[1:]:
            txBody.removeChild(extra)
    else:
        p = dom.createElementNS(A_NS, "a:p")
        txBody.appendChild(p)

    runs = _kids(p, "a:r")
    if runs:
        run = runs[0]
        for extra in runs[1:]:
            p.removeChild(extra)
    else:
        run = dom.createElementNS(A_NS, "a:r")
        # Insert the run before a trailing endParaRPr if present, else append.
        endpr = _kids(p, "a:endParaRPr")
        p.insertBefore(run, endpr[0]) if endpr else p.appendChild(run)

    t = _kids(run, "a:t")
    if t:
        t = t[0]
        while t.firstChild:
            t.removeChild(t.firstChild)
    else:
        t = dom.createElementNS(A_NS, "a:t")
        run.appendChild(t)  # after rPr if rPr exists (rPr is first child by schema)
    t.appendChild(dom.createTextNode(text))


def main():
    ap = argparse.ArgumentParser(description="Reshape and fill a template table.")
    ap.add_argument("unpacked_dir")
    ap.add_argument("slide", help="slide file name, e.g. slide4.xml")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--yaml", help="slide-deck YAML; the table entry is extracted directly (no temp JSON)")
    src.add_argument("--data-json", help="path to one pre-extracted YAML table entry as JSON")
    ap.add_argument("--index", type=int, help="0-based slide index in --yaml")
    ap.add_argument("--data", help="data key within the slide (omit if it has a single data entry)")
    ap.add_argument("--table-index", type=int, default=0,
                    help="which table on the slide (0 = first), default 0")
    args = ap.parse_args()

    unpacked = Path(args.unpacked_dir)
    slide_path = unpacked / "ppt" / "slides" / args.slide
    if args.yaml:
        if args.index is None:
            ap.error("--index is required with --yaml")
        from office.yaml_entry import load_data_entry
        entry = load_data_entry(args.yaml, args.index, args.data)
    else:
        entry = json.loads(Path(args.data_json).read_text(encoding="utf-8"))

    headers = entry.get("headers")
    rows = entry.get("rows", []) or []
    grid = ([headers] if headers else []) + rows
    if not grid:
        raise SystemExit("Error: table entry has no headers/rows")
    ncols = max(len(r) for r in grid)
    nrows = len(grid)

    dom = minidom.parse(str(slide_path))
    tbls = dom.getElementsByTagName("a:tbl")
    if not tbls:
        raise SystemExit(f"Error: no <a:tbl> on {args.slide}")
    if args.table_index >= len(tbls):
        raise SystemExit(f"Error: table-index {args.table_index} out of range "
                         f"({len(tbls)} table(s) on slide)")
    tbl = tbls[args.table_index]

    _reshape(tbl, nrows, ncols)

    trs = _kids(tbl, "a:tr")
    for r, row_vals in enumerate(grid):
        tcs = _kids(trs[r], "a:tc")
        for c in range(ncols):
            val = row_vals[c] if c < len(row_vals) else ""
            _set_cell_text(tcs[c], _fmt(val), dom)

    slide_path.write_bytes(dom.toxml(encoding="utf-8"))
    print(f"Filled table[{args.table_index}] on {args.slide}: {nrows} rows x {ncols} cols.")


if __name__ == "__main__":
    main()
