from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.ai.bulk_report_export import build_reports_zip

router = APIRouter(prefix="/api", tags=["bulk-reports"])


@router.get("/modules/{module_id}/reports.zip")
def download_all_reports(module_id: int, format: str = "pdf"):
    try:
        zip_path, skipped = build_reports_zip(module_id, format)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(502, f"Bulk report export failed: {e}")

    headers = {"X-Skipped-Students": ", ".join(skipped)} if skipped else {}
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=zip_path.name,
        headers=headers,
    )
