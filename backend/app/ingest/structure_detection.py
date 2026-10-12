"""Finds the meaningful folders/files inside an extracted Moodle export zip, tolerating
real-world variation in folder naming (singular/plural, extra nesting, case differences)
instead of requiring one exact path shape. Shared by the real importer and the
upload-preview "suggest a module name" endpoint, so both see identically-detected files.

Heuristic first (fast, free, deterministic); only falls back to a small one-shot agent
when the heuristic is genuinely ambiguous (zero or multiple candidates) - mirrors the
existing "heuristic first, agent fallback" shape in app.ai.classifier.
"""

import re
from pathlib import Path

from app.ai.common import extract_json, run_oneshot

SUBMISSION_DIR_RE = re.compile(r"^(?P<name>.+)_(?P<pid>\d+)_assignsubmission_(?P<kind>file|onlinetext)$")

SUBMISSIONS_FOLDER_SYSTEM = """You are helping import a Moodle assignment-export zip. Below is the \
recursive directory listing under the extracted module folder. Exactly one of these directories holds \
the per-student submission subfolders - each of those subfolders is named like \
"<Student Name>_<id>_assignsubmission_file" or "..._assignsubmission_onlinetext" (a Moodle-generated \
pattern). Identify which listed directory is the parent of those per-student folders.

Respond with ONLY a JSON object: {"folder": "<the exact relative path from the listing that is the parent \
of the per-student submission folders>"}
"""


def _is_inside_a_student_submission_folder(path: Path, search_root: Path) -> bool:
    """A student's own uploaded filename can coincidentally match our course-doc heuristics
    (e.g. a student submission literally named "... Case Study Response.docx") - excluding
    anything inside a Moodle-pattern assignsubmission folder keeps the course-level docx
    search (case study / sample answer) from ever picking up a student's file by accident."""
    return any(SUBMISSION_DIR_RE.match(p.name) for p in path.relative_to(search_root).parents)


def find_docx_files(search_root: Path) -> list[Path]:
    return sorted(
        p for p in search_root.rglob("*.docx") if not _is_inside_a_student_submission_folder(p, search_root)
    )


def classify_case_study_docs(docx_paths: list[Path]) -> tuple[Path | None, Path | None]:
    """Returns (case_study_path, sample_answer_path)."""
    case_study_path = None
    sample_answer_path = None
    for f in docx_paths:
        lower = f.name.lower()
        if "sample answer" in lower or "evaluator" in lower:
            sample_answer_path = f
        elif "case study" in lower:
            case_study_path = f
    return case_study_path, sample_answer_path


def _looks_like_submissions_parent(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        children = list(path.iterdir())
    except OSError:
        return False
    return any(SUBMISSION_DIR_RE.match(c.name) for c in children if c.is_dir())


def find_submissions_root(search_root: Path) -> Path:
    # Fast path: any directory that actually contains assignsubmission-pattern children,
    # regardless of its own name - this is the most reliable signal there is.
    by_content = [p for p in search_root.rglob("*") if _looks_like_submissions_parent(p)]
    if len(by_content) == 1:
        return by_content[0]

    # Name-based heuristic (singular/plural/case-insensitive) as a secondary signal.
    by_name = [p for p in search_root.rglob("*") if p.is_dir() and "student submission" in p.name.lower()]

    if len(by_content) == 0 and len(by_name) == 1:
        return by_name[0]
    if len(by_content) > 1:
        # Multiple folders contain assignsubmission children (unusual) - prefer one that
        # also matches the name heuristic if there's exactly one such overlap.
        overlap = [p for p in by_content if p in by_name]
        if len(overlap) == 1:
            return overlap[0]

    candidates = by_content or by_name
    if len(candidates) == 1:
        return candidates[0]

    # Genuine ambiguity (zero or multiple candidates) - ask a small agent, giving it the
    # full recursive directory listing to reason over.
    all_dirs = sorted(p.relative_to(search_root).as_posix() for p in search_root.rglob("*") if p.is_dir())
    if not all_dirs:
        raise FileNotFoundError(f"No subdirectories found at all under {search_root}")

    listing = "\n".join(all_dirs)
    response, _usage = run_oneshot(
        "submissions-folder-detector",
        SUBMISSIONS_FOLDER_SYSTEM,
        f"Directory listing:\n{listing}",
        temperature=0.0,
    )
    parsed = extract_json(response)
    chosen = search_root / parsed["folder"]
    if not chosen.is_dir():
        raise FileNotFoundError(
            f"Could not reliably locate the student-submissions folder under {search_root} "
            f"(heuristic found {len(candidates)} candidates, agent suggested a path that doesn't exist)"
        )
    return chosen
