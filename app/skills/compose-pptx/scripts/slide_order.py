"""Print the unpacked deck's slides in presentation order (pure XML).

The unpacked slide*.xml filenames are NOT in display order — order lives in
ppt/presentation.xml's <p:sldIdLst> (r:id -> presentation.xml.rels -> file).
The matching step's mapping.json uses 0-based *presentation order*
(`template_index`), so the build needs this index -> file resolution to know
which slideN.xml to duplicate. This keeps the build free of python-pptx.

Usage:
    python slide_order.py <unpacked_dir>            # "idx<TAB>slideN.xml" per line
    python slide_order.py <unpacked_dir> --index 2  # just the file at that index
"""

import argparse
import re
from pathlib import Path

import defusedxml.minidom as minidom


def slide_order(unpacked: Path):
    pres = unpacked / "ppt" / "presentation.xml"
    rels = unpacked / "ppt" / "_rels" / "presentation.xml.rels"

    rid_to_file = {}
    rdom = minidom.parse(str(rels))
    for rel in rdom.getElementsByTagName("Relationship"):
        if rel.getAttribute("Type").endswith("/slide"):
            tgt = rel.getAttribute("Target")
            rid_to_file[rel.getAttribute("Id")] = tgt.split("/")[-1]

    content = pres.read_text(encoding="utf-8")
    order = []
    for rid in re.findall(r'<p:sldId[^>]*r:id="([^"]+)"', content):
        if rid in rid_to_file:
            order.append(rid_to_file[rid])
    return order


def main():
    ap = argparse.ArgumentParser(description="List unpacked slides in presentation order.")
    ap.add_argument("unpacked_dir")
    ap.add_argument("--index", type=int, default=None)
    args = ap.parse_args()

    order = slide_order(Path(args.unpacked_dir))
    if args.index is not None:
        if args.index < 0 or args.index >= len(order):
            raise SystemExit(f"Error: index {args.index} out of range (0..{len(order)-1})")
        print(order[args.index])
    else:
        for i, f in enumerate(order):
            print(f"{i}\t{f}")


if __name__ == "__main__":
    main()
