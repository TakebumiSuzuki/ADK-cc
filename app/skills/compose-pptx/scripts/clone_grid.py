"""Clone a styled shape into an R x C grid (the "novel-layout" helper).

For the "novel-layout" case: when a YAML
slide needs a grid the template has no sample for (e.g. a 2x4 card layout but the
template only ships a 3-card row), you do NOT hand-author bare shapes and compute
EMU by hand. Instead you point this script at ONE already-styled shape on the
slide and it replicates that shape across a computed grid, so every cell inherits
the template's real visual language (fill, outline, font, effects) and only the
geometry is solved here.

What it does:
  * reads the slide size from ppt/presentation.xml,
  * computes an R x C grid inside an area (default: whole slide minus margins),
  * removes the source shape and appends R*C deep-copies of it, each placed (and,
    by default, resized) into its cell with a fresh unique shape id and a
    name `gridcell_r{r}c{c}` so the caller can find each cell to fill its text.

It does NOT fit text — a cell narrower than the source may overflow; that is the
job of the (separate) visual-QA stage.

Usage:
    python clone_grid.py <unpacked_dir> <slideN.xml> --shape-id <id> --rows R --cols C
        [--area-in "x,y,w,h"]   # grid bounding box in inches; default = slide minus margins
        [--margin-in 0.5] [--gap-in 0.25]
        [--no-resize]           # keep each clone the source's size (place top-left only)

Print: the new cells' names/ids, so the next step can fill them.
"""

import argparse
import sys
from pathlib import Path

import defusedxml.minidom as minidom

EMU_PER_INCH = 914400

# Top-level shape tags and where their transform (a:xfrm) lives.
SHAPE_TAGS = ("p:sp", "p:grpSp", "p:pic", "p:graphicFrame", "p:cxnSp")


def _emu(inches: float) -> int:
    return int(round(inches * EMU_PER_INCH))


def _slide_size(unpacked: Path) -> tuple[int, int]:
    pres = minidom.parse(str(unpacked / "ppt" / "presentation.xml"))
    sz = pres.getElementsByTagName("p:sldSz")[0]
    return int(sz.getAttribute("cx")), int(sz.getAttribute("cy"))


def _first_child(el, tag):
    for c in el.childNodes:
        if c.nodeType == c.ELEMENT_NODE and c.tagName == tag:
            return c
    return None


def _cnvpr_id(shape):
    """The shape's own id = the first cNvPr descendant (its nv*Pr/cNvPr)."""
    ids = shape.getElementsByTagName("p:cNvPr")
    return ids[0] if ids else None


def _all_ids(spTree):
    return [
        int(c.getAttribute("id"))
        for c in spTree.getElementsByTagName("p:cNvPr")
        if c.getAttribute("id").isdigit()
    ]


def _get_xfrm(shape, dom):
    """Return (off, ext, chOff, chExt) elements, creating the xfrm scaffold if
    absent. Handles the three transform homes: p:spPr (sp/pic/cxnSp),
    p:grpSpPr (grpSp), and a direct p:xfrm child (graphicFrame)."""
    tag = shape.tagName
    a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"

    def make(name):
        return dom.createElementNS(a_ns, name)

    if tag == "p:graphicFrame":
        xfrm = _first_child(shape, "p:xfrm")
        if xfrm is None:
            xfrm = dom.createElementNS(
                "http://schemas.openxmlformats.org/presentationml/2006/main", "p:xfrm"
            )
            shape.insertBefore(xfrm, shape.firstChild)
        off = _first_child(xfrm, "a:off") or xfrm.appendChild(make("a:off"))
        ext = _first_child(xfrm, "a:ext") or xfrm.appendChild(make("a:ext"))
        return off, ext, None, None

    holder_tag = "p:grpSpPr" if tag == "p:grpSp" else "p:spPr"
    holder = _first_child(shape, holder_tag)
    if holder is None:
        raise SystemExit(f"Error: <{tag}> has no <{holder_tag}>; cannot place it.")
    xfrm = _first_child(holder, "a:xfrm")
    if xfrm is None:
        xfrm = make("a:xfrm")
        holder.insertBefore(xfrm, holder.firstChild)
    off = _first_child(xfrm, "a:off") or xfrm.appendChild(make("a:off"))
    ext = _first_child(xfrm, "a:ext") or xfrm.appendChild(make("a:ext"))
    choff = _first_child(xfrm, "a:chOff")
    chext = _first_child(xfrm, "a:chExt")
    return off, ext, choff, chext


def _place(shape, dom, x, y, w, h, resize):
    off, ext, choff, chext = _get_xfrm(shape, dom)
    off.setAttribute("x", str(int(x)))
    off.setAttribute("y", str(int(y)))
    if resize:
        ext.setAttribute("cx", str(int(w)))
        ext.setAttribute("cy", str(int(h)))
        # For a group, leave chOff/chExt untouched: PowerPoint maps the child
        # coordinate box (chOff..chExt) onto (off..ext), so changing only ext
        # scales the children proportionally — no per-child math needed.


def main():
    ap = argparse.ArgumentParser(description="Clone a styled shape into an R x C grid.")
    ap.add_argument("unpacked_dir")
    ap.add_argument("slide", help="slide file name, e.g. slide5.xml")
    ap.add_argument("--shape-id", type=int, required=True,
                    help="cNvPr id of the source shape to replicate")
    ap.add_argument("--rows", type=int, required=True)
    ap.add_argument("--cols", type=int, required=True)
    ap.add_argument("--area-in", default=None,
                    help='grid box "x,y,w,h" in inches; default = slide minus margins')
    ap.add_argument("--margin-in", type=float, default=0.5)
    ap.add_argument("--gap-in", type=float, default=0.25)
    ap.add_argument("--no-resize", action="store_true",
                    help="keep each clone the source size; only reposition")
    args = ap.parse_args()

    unpacked = Path(args.unpacked_dir)
    slide_path = unpacked / "ppt" / "slides" / args.slide
    if not slide_path.exists():
        raise SystemExit(f"Error: {slide_path} not found")

    rows, cols = args.rows, args.cols
    if rows < 1 or cols < 1:
        raise SystemExit("Error: rows and cols must be >= 1")

    sld_w, sld_h = _slide_size(unpacked)
    if args.area_in:
        try:
            ax, ay, aw, ah = (_emu(float(v)) for v in args.area_in.split(","))
        except ValueError:
            raise SystemExit('Error: --area-in must be "x,y,w,h" in inches')
    else:
        m = _emu(args.margin_in)
        ax, ay, aw, ah = m, m, sld_w - 2 * m, sld_h - 2 * m

    gap = _emu(args.gap_in)
    cell_w = (aw - (cols - 1) * gap) / cols
    cell_h = (ah - (rows - 1) * gap) / rows
    if cell_w <= 0 or cell_h <= 0:
        raise SystemExit("Error: area too small for the requested grid + gaps")

    dom = minidom.parse(str(slide_path))
    spTrees = dom.getElementsByTagName("p:spTree")
    if not spTrees:
        raise SystemExit("Error: no <p:spTree> in slide")
    spTree = spTrees[0]

    # Locate the source shape (a direct child of spTree whose own id matches).
    source = None
    for child in spTree.childNodes:
        if child.nodeType != child.ELEMENT_NODE or child.tagName not in SHAPE_TAGS:
            continue
        cid = _cnvpr_id(child)
        if cid is not None and cid.getAttribute("id") == str(args.shape_id):
            source = child
            break
    if source is None:
        raise SystemExit(f"Error: no top-level shape with cNvPr id={args.shape_id}")

    next_id = max(_all_ids(spTree), default=1) + 1

    made = []
    for r in range(rows):
        for c in range(cols):
            clone = source.cloneNode(deep=True)
            x = ax + c * (cell_w + gap)
            y = ay + r * (cell_h + gap)
            _place(clone, dom, x, y, cell_w, cell_h, resize=not args.no_resize)
            cid = _cnvpr_id(clone)
            name = f"gridcell_r{r}c{c}"
            cid.setAttribute("id", str(next_id))
            cid.setAttribute("name", name)
            made.append((next_id, name))
            next_id += 1
            spTree.appendChild(clone)

    spTree.removeChild(source)

    slide_path.write_bytes(dom.toxml(encoding="utf-8"))

    print(f"Cloned shape {args.shape_id} into a {rows}x{cols} grid on {args.slide}:")
    for cid, name in made:
        print(f"  id={cid} name={name}")
    print("Next: fill each cell's text (find it by its name above), via the Edit tool.")


if __name__ == "__main__":
    main()
