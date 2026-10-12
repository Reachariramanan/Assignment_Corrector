from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.ai.report_builder import render_report
from app.db import db_cursor

router = APIRouter(prefix="/api", tags=["report"])

MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


@router.get("/students/{student_id}/report/download")
def download_report(student_id: int, module_id: int, format: str = "docx"):
    if format not in MEDIA_TYPES:
        raise HTTPException(400, "format must be 'docx' or 'pdf'")

    with db_cursor() as cur:
        cur.execute("SELECT name FROM students WHERE id = ?", (student_id,))
        student = cur.fetchone()
        if not student:
            raise HTTPException(404, "Student not found")
        cur.execute(
            "SELECT status FROM review_status WHERE student_id = ? AND module_id = ?", (student_id, module_id)
        )
        status_row = cur.fetchone()
        if not status_row or status_row["status"] != "completed":
            raise HTTPException(400, "This student's review isn't complete yet - finish scoring before generating a report")

    try:
        path = render_report(student_id, module_id, format)
    except Exception as e:
        raise HTTPException(502, f"Report generation failed: {e}")

    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in student["name"])
    return FileResponse(
        path,
        media_type=MEDIA_TYPES[format],
        filename=f"{safe_name} - Review Report.{format}",
    )
