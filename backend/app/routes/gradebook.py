from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.ai.gradebook_export import build_gradebook_xlsx

router = APIRouter(prefix="/api", tags=["gradebook"])


@router.get("/modules/{module_id}/gradebook.xlsx")
def download_gradebook(module_id: int):
    try:
        path = build_gradebook_xlsx(module_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(502, f"Gradebook export failed: {e}")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="gradebook.xlsx",
    )
