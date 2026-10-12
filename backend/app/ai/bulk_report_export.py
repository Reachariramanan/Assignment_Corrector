"""Bulk-download all of a module's student reports (whoever has a completed review)
as a single zip - the Dashboard's "download everyone's report" button."""

import re
import tempfile
import zipfile
from pathlib import Path

from app.ai.report_builder import render_report
from app.db import db_cursor


def _safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9 _-]", "_", name).strip()


def build_reports_zip(module_id: int, fmt: str = "pdf") -> tuple[Path, list[str]]:
    """Returns (zip_path, skipped_student_names) - students without a completed review
    are skipped (nothing to report yet) rather than failing the whole export."""
    if fmt not in ("docx", "pdf"):
        raise ValueError("format must be 'docx' or 'pdf'")

    with db_cursor() as cur:
        cur.execute("SELECT name FROM modules WHERE id = ?", (module_id,))
        module_row = cur.fetchone()
        if not module_row:
            raise ValueError(f"Module {module_id} not found")
        cur.execute(
            """SELECT s.id, s.name, rs.status FROM students s
               JOIN modules m ON m.cohort_id = s.cohort_id AND m.id = ?
               LEFT JOIN review_status rs ON rs.student_id = s.id AND rs.module_id = m.id
               ORDER BY s.name""",
            (module_id,),
        )
        students = [dict(r) for r in cur.fetchall()]

    tmp_dir = Path(tempfile.mkdtemp(prefix="dsa_reports_zip_"))
    zip_path = tmp_dir / f"{_safe_filename(module_row['name'])}_reports.zip"

    skipped = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for s in students:
            if s["status"] != "completed":
                skipped.append(s["name"])
                continue
            try:
                report_path = render_report(s["id"], module_id, fmt)
                zf.write(report_path, arcname=f"{_safe_filename(s['name'])}.{fmt}")
            except Exception as e:
                print(f"Warning: report generation failed for student {s['id']} ({s['name']}): {e}")
                skipped.append(s["name"])

    return zip_path, skipped
