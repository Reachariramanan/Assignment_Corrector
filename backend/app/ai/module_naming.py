"""Suggests a module name from a case-study/assignment docx's own content - shared by the
upload-preview endpoint and the smart zip-drop dispatcher so there's one place this logic
lives rather than a route importing from a dispatcher or vice versa."""

from pathlib import Path

from app.ai.common import extract_json, run_oneshot
from app.ingest.docx_parser import docx_to_plain

SUGGEST_NAME_SYSTEM = """You are helping an instructor import a Moodle assignment export. Below is the \
start of the case-study/assignment document. Suggest a short module name for this assignment (e.g. \
"Module 1" if the document names itself that way, or a short descriptive title drawn from its own heading \
if it doesn't). Keep it under 6 words.

Respond with ONLY a JSON object: {"suggested_name": "<name>"}
"""


def suggest_module_name(doc_path: Path) -> str:
    try:
        text = docx_to_plain(doc_path)[:2000]
        response, _usage = run_oneshot("module-name-suggester", SUGGEST_NAME_SYSTEM, text, temperature=0.1)
        return extract_json(response).get("suggested_name", "") or ""
    except Exception:
        return ""
