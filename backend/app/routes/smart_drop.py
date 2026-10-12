import shutil
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.ai.zip_dispatch import process_dropped_zip
from app.db import db_cursor

router = APIRouter(prefix="/api", tags=["smart-drop"])


@router.post("/uploads/smart-drop")
async def smart_drop(file: UploadFile = File(...), cohort_id: int = Form(...)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Expected a .zip file")

    with db_cursor() as cur:
        cur.execute("SELECT name FROM cohorts WHERE id = ?", (cohort_id,))
        cohort = cur.fetchone()
        if not cohort:
            raise HTTPException(404, "Course not found")

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / file.filename
        with zip_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        try:
            with zipfile.ZipFile(zip_path):
                pass
        except zipfile.BadZipFile:
            raise HTTPException(400, "Not a valid zip file")

        try:
            result = process_dropped_zip(zip_path, cohort_id, cohort["name"])
        except Exception as e:
            raise HTTPException(502, f"Processing the zip failed: {e}")

    return result
