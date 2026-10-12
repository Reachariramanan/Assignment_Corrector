"""Smart zip drop: given an arbitrary zip someone drags into the chat, figure out what it
actually is and do the right thing - no manual "what is this" step from the user.

Two paths:
- It looks like a Moodle assignment-export (has a folder of per-student
  "..._assignsubmission_{file,onlinetext}" folders plus a case-study-shaped docx) -> hand it
  straight to the normal import pipeline for the given course.
- Anything else -> walk every file and build a cumulative summary via a SLIDING WINDOW: each
  batch of files only ever gets summarized together with the running summary so far, never
  the full raw content of everything already processed - so this never blows the context
  window no matter how large the zip is.
"""

import tempfile
import zipfile
from pathlib import Path
from typing import Any

from app.ai.common import extract_json, run_oneshot
from app.ai.file_parser_agent import parse_unknown_files_parallel
from app.ai.module_naming import suggest_module_name
from app.ingest.docx_parser import docx_to_plain
from app.ingest.import_zip import KNOWN_SUFFIXES, import_zip
from app.ingest.structure_detection import classify_case_study_docs, find_docx_files, find_submissions_root
from app.ingest.xlsx_parser import xlsx_to_plain

BATCH_CHAR_BUDGET = 8000

SUMMARY_UPDATE_SYSTEM = """You are building a cumulative summary of the contents of a zip file, one batch \
of files at a time - you never see the whole zip's content at once, only the running summary so far plus \
the next batch, so you must FOLD the new batch's information into the summary rather than just appending \
to it.

## Running summary so far (empty if this is the first batch)
{running_summary}

## New batch of files (filename + extracted content)
{batch_text}

Respond with ONLY a JSON object: {{"summary": "<the updated cumulative summary - a few concise paragraphs \
covering everything seen so far, old and new, organized by theme/topic rather than by file>"}}
"""


def _looks_like_module_export(extract_dir: Path) -> tuple[Path | None, Path | None, Path | None]:
    """Returns (case_study_path, sample_answer_path, submissions_root) if this looks like a
    Moodle assignment export, each None/missing otherwise."""
    case_study_path, sample_answer_path = classify_case_study_docs(find_docx_files(extract_dir))
    if sample_answer_path is None:
        return None, None, None
    try:
        submissions_root = find_submissions_root(extract_dir)
    except Exception:
        return case_study_path, sample_answer_path, None
    return case_study_path, sample_answer_path, submissions_root


def _extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix == ".docx":
            return docx_to_plain(path)
        if suffix == ".xlsx":
            return xlsx_to_plain(path)
        if suffix in (".html", ".htm"):
            return path.read_text(errors="ignore")
        if suffix in (".txt", ".md", ".csv", ".json"):
            return path.read_text(errors="ignore")
    except Exception as e:
        return f"(could not read {path.name}: {e})"
    return ""


def _all_files(extract_dir: Path) -> list[Path]:
    skip_names = {"__MACOSX", ".DS_Store", "Thumbs.db"}
    return sorted(
        p for p in extract_dir.rglob("*")
        if p.is_file() and not any(part in skip_names for part in p.parts)
    )


def summarize_zip_generic(extract_dir: Path) -> dict[str, Any]:
    files = _all_files(extract_dir)
    known = [f for f in files if f.suffix.lower() in KNOWN_SUFFIXES or f.suffix.lower() in (".txt", ".md", ".csv", ".json")]
    unknown = [f for f in files if f not in known]

    file_texts: dict[Path, str] = {f: _extract_text(f) for f in known}
    if unknown:
        parsed = parse_unknown_files_parallel(unknown)
        for f, result in parsed.items():
            file_texts[f] = result.get("text") or result.get("description", "")

    running_summary = ""
    batch: list[tuple[Path, str]] = []
    batch_chars = 0
    total_usage = {"tokens_prompt": 0, "tokens_completion": 0}

    def flush_batch():
        nonlocal running_summary, batch, batch_chars
        if not batch:
            return
        batch_text = "\n\n".join(f"--- {p.relative_to(extract_dir)} ---\n{t[:4000]}" for p, t in batch)
        system_text = SUMMARY_UPDATE_SYSTEM.format(running_summary=running_summary or "(none yet)", batch_text=batch_text)
        response, usage = run_oneshot("zip-summary-fold", system_text, "Produce the updated summary JSON.", temperature=0.2)
        total_usage["tokens_prompt"] += usage.get("tokens_prompt", 0)
        total_usage["tokens_completion"] += usage.get("tokens_completion", 0)
        running_summary = extract_json(response).get("summary", running_summary)
        batch = []
        batch_chars = 0

    for f in files:
        text = file_texts.get(f, "")
        if not text.strip():
            continue
        batch.append((f, text))
        batch_chars += len(text)
        if batch_chars >= BATCH_CHAR_BUDGET:
            flush_batch()
    flush_batch()

    return {
        "summary": running_summary or "No readable text content was found in this zip.",
        "files_processed": len(files),
        "usage": total_usage,
    }


def process_dropped_zip(zip_path: Path, cohort_id: int, cohort_name: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        extract_dir = Path(tmp) / "extracted"
        extract_dir.mkdir()
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)

        case_study_path, sample_answer_path, submissions_root = _looks_like_module_export(extract_dir)

        if sample_answer_path is not None and submissions_root is not None:
            # Looks like a real module export - figure out a module name and import it for real.
            doc_for_name = case_study_path or sample_answer_path
            module_name = suggest_module_name(doc_for_name) or "Untitled Module"

            summary = import_zip(zip_path, cohort_name, module_name, use_ai_classification=True)
            return {"kind": "module_import", "module_name": module_name, **summary}

        # Not shaped like a module export - summarize it instead of trying to grade it.
        result = summarize_zip_generic(extract_dir)
        return {"kind": "document_summary", **result}
