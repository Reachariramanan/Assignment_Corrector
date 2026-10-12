import shutil
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.ai.module_naming import suggest_module_name
from app.ingest.import_zip import import_zip
from app.ingest.structure_detection import classify_case_study_docs, find_docx_files

router = APIRouter(prefix="/api", tags=["uploads"])


@router.post("/uploads/module")
async def upload_module(
    file: UploadFile = File(...),
    cohort_name: str = Form(...),
    module_name: str = Form(...),
    use_ai_classification: bool = Form(True),
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Expected a .zip Moodle assignment export")

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / file.filename
        with zip_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        try:
            summary = import_zip(zip_path, cohort_name, module_name, use_ai_classification=use_ai_classification)
        except FileNotFoundError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(500, f"Import failed: {e}")

    return summary


@router.post("/uploads/suggest-module-name")
async def suggest_module_name_route(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Expected a .zip Moodle assignment export")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / file.filename
        with zip_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        try:
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise HTTPException(400, "Not a valid zip file")

        case_study_path, sample_answer_path = classify_case_study_docs(find_docx_files(extract_dir))
        doc_path = case_study_path or sample_answer_path
        if doc_path is None:
            return {"suggested_name": ""}

        return {"suggested_name": suggest_module_name(doc_path)}
