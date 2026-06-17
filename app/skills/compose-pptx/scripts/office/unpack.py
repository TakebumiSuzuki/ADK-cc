"""Unpack a PPTX for raw-XML editing.

PPTX-only, so it has no dependency beyond `defusedxml`.

It does three things, in order:
  1. Extract the .pptx ZIP into <output_dir>.
  2. Pretty-print every .xml / .rels part (so the Edit tool can target lines).
  3. Escape smart quotes to XML entities (&#x201C; etc.) so the Edit tool — which
     normalizes curly quotes to ASCII — cannot silently corrupt them. pack.py
     leaves the entities as-is (they are valid XML and render correctly).

Usage:
    python unpack.py <presentation.pptx> <output_dir>
"""

import argparse
import sys
import zipfile
from pathlib import Path

import defusedxml.minidom

SMART_QUOTE_REPLACEMENTS = {
    "“": "&#x201C;",
    "”": "&#x201D;",
    "‘": "&#x2018;",
    "’": "&#x2019;",
}


def unpack(input_file: str, output_directory: str) -> str:
    input_path = Path(input_file)
    output_path = Path(output_directory)

    if not input_path.exists():
        return f"Error: {input_file} does not exist"
    if input_path.suffix.lower() != ".pptx":
        return f"Error: {input_file} must be a .pptx file"

    try:
        output_path.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(input_path, "r") as zf:
            zf.extractall(output_path)

        xml_files = list(output_path.rglob("*.xml")) + list(output_path.rglob("*.rels"))
        for xml_file in xml_files:
            _pretty_print_xml(xml_file)
        for xml_file in xml_files:
            _escape_smart_quotes(xml_file)

        return f"Unpacked {input_file} ({len(xml_files)} XML parts) -> {output_directory}"
    except zipfile.BadZipFile:
        return f"Error: {input_file} is not a valid PPTX (ZIP) file"
    except Exception as e:  # noqa: BLE001
        return f"Error unpacking: {e}"


def _pretty_print_xml(xml_file: Path) -> None:
    try:
        content = xml_file.read_text(encoding="utf-8")
        dom = defusedxml.minidom.parseString(content)
        xml_file.write_bytes(dom.toprettyxml(indent="  ", encoding="utf-8"))
    except Exception:  # noqa: BLE001 - leave unparseable parts untouched
        pass


def _escape_smart_quotes(xml_file: Path) -> None:
    try:
        content = xml_file.read_text(encoding="utf-8")
        for char, entity in SMART_QUOTE_REPLACEMENTS.items():
            content = content.replace(char, entity)
        xml_file.write_text(content, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unpack a PPTX for raw-XML editing")
    parser.add_argument("input_file", help="PPTX file to unpack")
    parser.add_argument("output_directory", help="Output directory")
    args = parser.parse_args()

    message = unpack(args.input_file, args.output_directory)
    print(message)
    if message.startswith("Error"):
        sys.exit(1)
