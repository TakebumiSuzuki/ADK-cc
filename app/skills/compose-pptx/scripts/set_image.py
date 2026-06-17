"""Replace a slide picture's image with a file from disk (raw-XML).

Reuses the sample `<p:pic>`'s position, size and crop — only the image bits and
its alt text change. The new image is copied into ppt/media, a Content_Types
Default is added for its extension if missing, and the picture's `<a:blip>`
r:embed is repointed to a fresh relationship.

Usage:
    python set_image.py <unpacked_dir> <slideN.xml> --path <image> [--pic-index 0] [--alt "..."]
"""

import argparse
import re
import shutil
from pathlib import Path

import defusedxml.minidom as minidom

R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _next_media_index(media_dir: Path) -> int:
    media_dir.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for f in media_dir.glob("image*")
            if (m := re.match(r"image(\d+)\.", f.name))]
    return max(nums, default=0) + 1


def _ensure_content_type(unpacked: Path, ext: str) -> None:
    ct_path = unpacked / "[Content_Types].xml"
    ct = ct_path.read_text(encoding="utf-8")
    ext = ext.lower().lstrip(".")
    if re.search(rf'Default Extension="{ext}"', ct, re.IGNORECASE):
        return
    mime = {
        "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "gif": "image/gif", "bmp": "image/bmp", "tiff": "image/tiff",
        "svg": "image/svg+xml", "webp": "image/webp",
    }.get(ext, f"image/{ext}")
    default = f'<Default Extension="{ext}" ContentType="{mime}"/>'
    ct = ct.replace("<Types ", "<Types ").replace(
        "</Types>", f"  {default}\n</Types>", 1)
    # Insert Defaults near the top is conventional but not required; appended is valid.
    ct_path.write_text(ct, encoding="utf-8")


def _add_image_rel(unpacked: Path, slide_name: str, media_name: str) -> str:
    rels_path = unpacked / "ppt" / "slides" / "_rels" / f"{slide_name}.rels"
    dom = minidom.parse(str(rels_path))
    root = dom.documentElement
    rids = [int(m) for m in re.findall(r'Id="rId(\d+)"', rels_path.read_text(encoding="utf-8"))]
    rid = f"rId{max(rids, default=0) + 1}"
    rel = dom.createElement("Relationship")
    rel.setAttribute("Id", rid)
    rel.setAttribute("Type", f"{R_NS}/image")
    rel.setAttribute("Target", f"../media/{media_name}")
    root.appendChild(rel)
    rels_path.write_bytes(dom.toxml(encoding="utf-8"))
    return rid


def main():
    ap = argparse.ArgumentParser(description="Replace a slide picture's image.")
    ap.add_argument("unpacked_dir")
    ap.add_argument("slide")
    ap.add_argument("--path", required=True, help="image file to insert")
    ap.add_argument("--pic-index", type=int, default=0)
    ap.add_argument("--alt", default=None)
    args = ap.parse_args()

    unpacked = Path(args.unpacked_dir)
    img = Path(args.path)
    if not img.exists():
        raise SystemExit(f"Error: image not found: {img}")

    slide_path = unpacked / "ppt" / "slides" / args.slide
    dom = minidom.parse(str(slide_path))
    pics = dom.getElementsByTagName("p:pic")
    if not pics:
        raise SystemExit(f"Error: no <p:pic> on {args.slide}")
    if args.pic_index >= len(pics):
        raise SystemExit(f"Error: pic-index {args.pic_index} out of range ({len(pics)} pics)")
    pic = pics[args.pic_index]

    # Copy image into ppt/media with a fresh name.
    media_dir = unpacked / "ppt" / "media"
    ext = img.suffix.lower().lstrip(".")
    media_name = f"image{_next_media_index(media_dir)}.{ext}"
    shutil.copy2(img, media_dir / media_name)
    _ensure_content_type(unpacked, ext)
    rid = _add_image_rel(unpacked, args.slide, media_name)

    # Repoint the blip's embed.
    blips = pic.getElementsByTagName("a:blip")
    if not blips:
        raise SystemExit("Error: <p:pic> has no <a:blip> to repoint")
    blips[0].setAttributeNS(R_NS, "r:embed", rid)

    if args.alt is not None:
        cnvpr = pic.getElementsByTagName("p:cNvPr")
        if cnvpr:
            cnvpr[0].setAttribute("descr", args.alt)

    slide_path.write_bytes(dom.toxml(encoding="utf-8"))
    print(f"Replaced pic[{args.pic_index}] on {args.slide} with {media_name} (rId={rid}).")


if __name__ == "__main__":
    main()
