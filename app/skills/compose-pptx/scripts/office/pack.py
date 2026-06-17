"""Pack an unpacked directory back into a .pptx.

Packing never validates — it condenses whitespace and zips. (Validation belongs to
the separate, out-of-scope QA stage.) It strips only inter-element whitespace while
preserving text inside `<a:t>` runs.

Usage:
    python pack.py <input_directory> <output.pptx>
"""

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import defusedxml.minidom


def pack(input_directory: str, output_file: str) -> str:
    input_dir = Path(input_directory)
    output_path = Path(output_file)

    if not input_dir.is_dir():
        return f"Error: {input_dir} is not a directory"
    if output_path.suffix.lower() != ".pptx":
        return f"Error: {output_file} must be a .pptx file"

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_content = Path(temp_dir) / "content"
            shutil.copytree(input_dir, temp_content)

            for pattern in ("*.xml", "*.rels"):
                for xml_file in temp_content.rglob(pattern):
                    _condense_xml(xml_file)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in temp_content.rglob("*"):
                    if f.is_file():
                        zf.write(f, f.relative_to(temp_content))

        return f"Packed {input_directory} -> {output_file}"
    except Exception as e:  # noqa: BLE001
        return f"Error packing: {e}"


def _condense_xml(xml_file: Path) -> None:
    """Remove the indentation whitespace unpack.py added, but never touch text
    inside `<*:t>` elements (slide text, where whitespace is significant)."""
    try:
        with open(xml_file, encoding="utf-8") as f:
            dom = defusedxml.minidom.parse(f)

        for element in dom.getElementsByTagName("*"):
            if element.tagName.endswith(":t"):
                continue
            for child in list(element.childNodes):
                if (
                    child.nodeType == child.TEXT_NODE
                    and child.nodeValue
                    and child.nodeValue.strip() == ""
                ) or child.nodeType == child.COMMENT_NODE:
                    element.removeChild(child)

        xml_file.write_bytes(dom.toxml(encoding="UTF-8"))
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: Failed to condense {xml_file.name}: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pack a directory into a .pptx")
    parser.add_argument("input_directory", help="Unpacked PPTX directory")
    parser.add_argument("output_file", help="Output .pptx file")
    args = parser.parse_args()

    message = pack(args.input_directory, args.output_file)
    print(message)
    if message.startswith("Error"):
        sys.exit(1)
