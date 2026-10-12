"""Import a Moodle assignment-export zip into the review SQLite database.

Usage:
    python -m app.ingest.import_zip <path-to-zip> --cohort "CADS-F Batch 1" --module "Module 1"
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.db import db_cursor, init_db
from app.ingest.docx_parser import docx_to_html, docx_to_plain
from app.ingest.rubric_parser import parse_rubric_from_docx
from app.ingest.structure_detection import (
    SUBMISSION_DIR_RE,
    classify_case_study_docs,
    find_docx_files,
    find_submissions_root,
)
from app.ingest.xlsx_parser import xlsx_to_html, xlsx_to_plain
from app.review_status import recompute_status
from app.storage import put_file

IMPORTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "imports"

AMBIGUOUS_KINDS = {"combined", "other"}


def _kind_from_filename(filename: str, folder_kind: str) -> str:
    lower = filename.lower()
    if folder_kind == "onlinetext":
        return "onlinetext"
    if "ai usage" in lower or "ai_usage" in lower or "declaration" in lower:
        return "ai_declaration"
    if "control note" in lower or "control_note" in lower:
        return "control_note"
    if "worksheet" in lower or "governance" in lower:
        return "worksheet"
    return "combined" if folder_kind == "file" else "other"


KNOWN_SUFFIXES = {".docx", ".xlsx", ".html", ".htm"}


def _convert_known_file(path: Path) -> tuple[str, str, str]:
    """Returns (source_format, html, text) for a file type we have a dedicated parser for."""
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return "docx", docx_to_html(path), docx_to_plain(path)
    if suffix == ".xlsx":
        return "xlsx", xlsx_to_html(path), xlsx_to_plain(path)
    if suffix in (".html", ".htm"):
        raw = path.read_text(errors="ignore")
        soup = BeautifulSoup(raw, "html.parser")
        body = soup.body
        html = body.decode_contents() if body else raw
        text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
        return "html", html, text
    raise ValueError(f"{path.suffix} is not a known type")


def _safe_object_key(*parts: str) -> str:
    cleaned = [re.sub(r"[^A-Za-z0-9._ -]", "_", p).strip() for p in parts]
    return "/".join(cleaned)


def import_zip(
    zip_path: Path,
    cohort_name: str,
    module_name: str,
    use_ai_classification: bool = True,
) -> dict:
    init_db()
    extract_root = IMPORTS_DIR / cohort_name / module_name
    extract_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_root)

    try:
        put_file(_safe_object_key(cohort_name, module_name, "source.zip"), zip_path)
    except Exception as e:  # object storage is best-effort; local extraction already succeeded
        print(f"Warning: could not upload source zip to object storage: {e}")

    # Search the whole extracted tree recursively rather than assuming a fixed nesting depth -
    # real zips vary (some double-nest a "Module N" folder inside itself, some don't).
    case_study_path, sample_answer_path = classify_case_study_docs(find_docx_files(extract_root))

    if sample_answer_path is None:
        raise FileNotFoundError(f"No sample-answer/evaluator-key docx found anywhere under {extract_root}")

    case_study_html = docx_to_html(case_study_path) if case_study_path else ""
    traits = parse_rubric_from_docx(sample_answer_path)

    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO cohorts (name) VALUES (?) ON CONFLICT(name) DO UPDATE SET name=excluded.name",
            (cohort_name,),
        )
        cur.execute("SELECT id FROM cohorts WHERE name = ?", (cohort_name,))
        cohort_id = cur.fetchone()["id"]

        cur.execute(
            """INSERT INTO modules (cohort_id, name, case_study_path, case_study_html, sample_answer_path)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(cohort_id, name) DO UPDATE SET
                 case_study_path=excluded.case_study_path,
                 case_study_html=excluded.case_study_html,
                 sample_answer_path=excluded.sample_answer_path""",
            (cohort_id, module_name, str(case_study_path) if case_study_path else None, case_study_html, str(sample_answer_path)),
        )
        cur.execute("SELECT id FROM modules WHERE cohort_id = ? AND name = ?", (cohort_id, module_name))
        module_id = cur.fetchone()["id"]

        # Upsert traits by (module_id, name) rather than delete-all-and-reinsert: a fresh
        # autoincrement id on every re-import would cascade-delete any reviews/ai_suggestions
        # already recorded against the old trait_id (both have ON DELETE CASCADE on trait_id).
        for trait in traits:
            cur.execute(
                """INSERT INTO rubric_traits (module_id, name, weight_pct, sort_order) VALUES (?, ?, ?, ?)
                   ON CONFLICT(module_id, name) DO UPDATE SET
                     weight_pct=excluded.weight_pct, sort_order=excluded.sort_order""",
                (module_id, trait["name"], trait["weight_pct"], trait["sort_order"]),
            )
            cur.execute(
                "SELECT id FROM rubric_traits WHERE module_id = ? AND name = ?", (module_id, trait["name"])
            )
            trait_id = cur.fetchone()["id"]
            cur.execute("DELETE FROM rubric_levels WHERE trait_id = ?", (trait_id,))
            for level in trait["levels"]:
                cur.execute(
                    "INSERT INTO rubric_levels (trait_id, level, label, descriptor) VALUES (?, ?, ?, ?)",
                    (trait_id, level["level"], level["label"], level["descriptor"]),
                )

        submissions_root = find_submissions_root(extract_root)
        student_dirs = sorted(p for p in submissions_root.iterdir() if p.is_dir())

        # Phase 1: walk the tree, convert known formats inline (fast, no LLM), and collect
        # every unrecognized file for a single parallel dispatch to the file-parser agent -
        # a submission folder can contain literally anything, so we don't hardcode formats.
        pending: list[dict] = []
        unknown_paths: list[Path] = []
        for student_dir in student_dirs:
            m = SUBMISSION_DIR_RE.match(student_dir.name)
            if not m:
                continue
            folder_kind = m.group("kind")
            for f in sorted(student_dir.iterdir()):
                if not f.is_file():
                    continue
                record = {"student_dir": student_dir, "folder_kind": folder_kind, "path": f}
                if f.suffix.lower() in KNOWN_SUFFIXES:
                    source_format, html, text = _convert_known_file(f)
                    record.update(source_format=source_format, html=html, text=text)
                else:
                    unknown_paths.append(f)
                pending.append(record)

        if unknown_paths:
            print(f"Dispatching {len(unknown_paths)} unrecognized file(s) to the file-parser agent in parallel...")
            from app.ai.file_parser_agent import parse_unknown_files_parallel

            parsed_unknown = parse_unknown_files_parallel(unknown_paths)
            for record in pending:
                if record["path"] in parsed_unknown:
                    result = parsed_unknown[record["path"]]
                    record.update(
                        source_format=f"auto:{record['path'].suffix.lstrip('.') or 'unknown'}",
                        html=result["html"] or f"<p><em>{result['description']}</em></p>",
                        text=result["text"] or result["description"],
                    )

        # Phase 2: classify, upload, and write to the DB.
        seen_student_ids: set[int] = set()
        n_files = 0
        n_ai_classified = 0
        student_id_by_dir: dict[Path, int] = {}
        for record in pending:
            student_dir = record["student_dir"]
            if student_dir not in student_id_by_dir:
                m = SUBMISSION_DIR_RE.match(student_dir.name)
                name = m.group("name").strip()
                pid = m.group("pid")
                cur.execute(
                    """INSERT INTO students (cohort_id, name, moodle_participant_id) VALUES (?, ?, ?)
                       ON CONFLICT(cohort_id, name, moodle_participant_id) DO UPDATE SET name=excluded.name""",
                    (cohort_id, name, pid),
                )
                cur.execute(
                    "SELECT id FROM students WHERE cohort_id = ? AND name = ? AND moodle_participant_id = ?",
                    (cohort_id, name, pid),
                )
                student_id_by_dir[student_dir] = cur.fetchone()["id"]
            student_id = student_id_by_dir[student_dir]
            seen_student_ids.add(student_id)

            f = record["path"]
            source_format, html, text = record["source_format"], record["html"], record["text"]
            kind = _kind_from_filename(f.name, record["folder_kind"])
            kind_source = "heuristic"

            if use_ai_classification and kind in AMBIGUOUS_KINDS and text.strip():
                try:
                    from app.ai.classifier import classify_file_kind

                    ai_kind = classify_file_kind(f.name, text)
                    if ai_kind != "other":
                        kind = ai_kind
                        kind_source = "ai"
                        n_ai_classified += 1
                except Exception as e:
                    print(f"Warning: AI classification failed for {f.name}: {e}")

            object_key = _safe_object_key(cohort_name, module_name, student_dir.name, f.name)
            try:
                put_file(object_key, f)
            except Exception as e:
                print(f"Warning: could not upload {f.name} to object storage: {e}")
                object_key = None

            cur.execute(
                """INSERT INTO submission_files
                     (student_id, module_id, kind, kind_source, original_filename, storage_path, object_key, source_format, extracted_html, extracted_text)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(student_id, module_id, original_filename) DO UPDATE SET
                     kind=excluded.kind, kind_source=excluded.kind_source, storage_path=excluded.storage_path,
                     object_key=excluded.object_key, source_format=excluded.source_format,
                     extracted_html=excluded.extracted_html, extracted_text=excluded.extracted_text""",
                (student_id, module_id, kind, kind_source, f.name, str(f), object_key, source_format, html, text),
            )
            n_files += 1

        for student_id in seen_student_ids:
            recompute_status(cur, student_id, module_id)

    summary = {
        "cohort": cohort_name,
        "module": module_name,
        "module_id": module_id,
        "rubric_traits": len(traits),
        "students": len(seen_student_ids),
        "files": n_files,
        "ai_classified_files": n_ai_classified,
    }
    print(
        f"Imported cohort={cohort_name!r} module={module_name!r}: "
        f"{len(traits)} rubric traits, {len(seen_student_ids)} students, {n_files} submission files "
        f"({n_ai_classified} AI-classified)."
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--cohort", default="Default Cohort")
    parser.add_argument("--module", default="Module 1")
    parser.add_argument("--no-ai-classification", action="store_true")
    args = parser.parse_args()
    import_zip(args.zip_path, args.cohort, args.module, use_ai_classification=not args.no_ai_classification)


if __name__ == "__main__":
    main()
