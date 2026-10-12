import json
import re
import subprocess
from pathlib import Path
from typing import Any


def _inlines_to_text(inlines: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for inline in inlines:
        t = inline.get("t")
        if t in ("Str",):
            parts.append(inline["c"])
        elif t in ("Space", "SoftBreak"):
            parts.append(" ")
        elif t == "LineBreak":
            parts.append(" ")
        elif t in ("Strong", "Emph", "Underline", "SmallCaps"):
            parts.append(_inlines_to_text(inline["c"]))
        elif t == "Quoted":
            parts.append(_inlines_to_text(inline["c"][1]))
        elif t in ("Superscript", "Subscript"):
            parts.append(_inlines_to_text(inline["c"]))
    return "".join(parts)


def _blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    chunks = []
    for block in blocks:
        t = block.get("t")
        if t in ("Plain", "Para"):
            chunks.append(_inlines_to_text(block["c"]))
        elif t == "BulletList":
            for item in block["c"]:
                chunks.append(_blocks_to_text(item))
    return " ".join(c for c in chunks if c).strip()


def _cell_text(cell: list[Any]) -> str:
    # Cell = [Attr, Alignment, RowSpan, ColSpan, [Block]]
    return _blocks_to_text(cell[4])


def _rows_from_table_part(part) -> list[list[str]]:
    # part = [Attr, [Row...]] ; Row = [Attr, [Cell...]]
    rows = part[1]
    return [[_cell_text(cell) for cell in row[1]] for row in rows]


def _find_rubric_table(ast_blocks: list[dict[str, Any]]) -> dict[str, Any] | None:
    for block in ast_blocks:
        if block.get("t") != "Table":
            continue
        thead = block["c"][3]
        header_rows = _rows_from_table_part(thead)
        if header_rows and header_rows[0] and header_rows[0][0].strip().lower() == "trait":
            return block
    return None


def parse_rubric_from_docx(path: Path) -> list[dict[str, Any]]:
    """Returns a list of trait dicts: {name, weight_pct, sort_order, levels: [{level,label,descriptor}]}"""
    result = subprocess.run(
        ["pandoc", str(path), "-t", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    ast = json.loads(result.stdout)
    table = _find_rubric_table(ast["blocks"])
    if table is None:
        raise ValueError(f"Could not locate rubric table (header starting with 'Trait') in {path}")

    thead = table["c"][3]
    head_rows = _rows_from_table_part(thead)
    header = head_rows[0]
    # header: ["Trait", "Wt.", "Beginning (1)", "Developing (2)", "Competent (3)", "Accomplished (4)"]
    level_headers = header[2:]

    tbodies = table["c"][4]
    body_rows: list[list[str]] = []
    for tbody in tbodies:
        # TableBody = [Attr, RowHeadColumns, [Row(intermediate head)...], [Row(body)...]]
        body_rows.extend([[_cell_text(cell) for cell in row[1]] for row in tbody[3]])

    # Some docx tables (depending on how the author formatted them in Word) get parsed by
    # pandoc with every row inside the table's "head" section rather than split head/body -
    # in that case thead has the trait rows too, right after the real header row.
    if len(head_rows) > 1:
        body_rows = head_rows[1:] + body_rows

    traits = []
    sort_order = 0
    for row in body_rows:
        if not row or not row[0].strip():
            continue
        name = row[0].strip()
        if name.lower() == "total":
            continue
        weight_match = re.search(r"([\d.]+)\s*%", row[1]) if len(row) > 1 else None
        weight_pct = float(weight_match.group(1)) if weight_match else 0.0
        levels = []
        for idx, descriptor in enumerate(row[2:]):
            level_num = idx + 1
            label_match = re.match(r"(\w+)", level_headers[idx]) if idx < len(level_headers) else None
            label = label_match.group(1) if label_match else str(level_num)
            levels.append({"level": level_num, "label": label, "descriptor": descriptor.strip()})
        sort_order += 1
        traits.append(
            {
                "name": name,
                "weight_pct": weight_pct,
                "sort_order": sort_order,
                "levels": levels,
            }
        )
    return traits
