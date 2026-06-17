"""Shared slide-deck YAML extraction for the build scripts.

Why this exists: the build scripts (`set_chart_data.py`, `fill_table.py`,
`set_notes.py`) consume one slide entry / one `data:` entry. Previously that
entry was hand-written into a temp JSON file before each call — and that manual
transcription is exactly where cell values get altered (e.g. `↑` rewritten as
`up`, an en-dash flattened to a hyphen) and body content gets dropped.

This module lets those scripts read the slide-deck YAML **directly** (via their
`--yaml/--index` mode), so categories, series, rows, cell values and prose come
straight from the single source of truth with no retyping. All knowledge of the
YAML schema (the top-level `slides:` list, the per-slide `data:` map) lives here,
in one place, rather than being spread across the three scripts.
"""

from pathlib import Path

import yaml


def _load_slides(yaml_path):
    doc = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or "slides" not in doc:
        raise SystemExit(f"Error: {yaml_path} has no top-level 'slides:' list")
    slides = doc["slides"]
    if not isinstance(slides, list):
        raise SystemExit(f"Error: 'slides' in {yaml_path} is not a list")
    return slides


def load_slide_entry(yaml_path, index):
    """Return the whole slide entry (dict) at 0-based presentation `index`.

    Used by set_notes.py, which assembles notes from the entry's
    `speaker_notes` / `prose_sources` / `data`.
    """
    slides = _load_slides(yaml_path)
    if index < 0 or index >= len(slides):
        raise SystemExit(
            f"Error: slide index {index} out of range (0..{len(slides) - 1}) "
            f"in {yaml_path}"
        )
    entry = slides[index]
    if not isinstance(entry, dict):
        raise SystemExit(f"Error: slide {index} in {yaml_path} is not a mapping")
    return entry


def load_data_entry(yaml_path, index, key=None):
    """Return one `data:` sub-entry of slide `index`.

    With `key`, returns `slides[index]['data'][key]`. Without `key`, auto-selects
    when the slide has exactly one `data:` entry; otherwise errors and lists the
    available keys (so the caller picks one with --data). Used by set_chart_data.py
    and fill_table.py, which each fill a single chart/table.
    """
    entry = load_slide_entry(yaml_path, index)
    data = entry.get("data") or {}
    if not data:
        raise SystemExit(f"Error: slide {index} in {yaml_path} has no 'data:' block")
    if key is None:
        if len(data) == 1:
            return next(iter(data.values()))
        raise SystemExit(
            f"Error: slide {index} has multiple data entries "
            f"({', '.join(data)}); pass --data <key> to choose one"
        )
    if key not in data:
        raise SystemExit(
            f"Error: slide {index} has no data entry '{key}' "
            f"(available: {', '.join(data)})"
        )
    return data[key]
