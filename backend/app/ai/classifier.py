"""AI fallback classification for submission files whose kind can't be inferred
from the filename alone (module-agnostic - a new module's students may not use
the same filename conventions as Module 1)."""

from app.ai.common import extract_json, run_oneshot

CLASSIFIER_SYSTEM = """You classify a single student-submitted file from an assignment package into \
exactly one category, based on its filename and the start of its extracted text content.

Categories:
- worksheet: a structured worksheet/table deliverable (e.g. a classification scheme, a data table, a checklist)
- control_note: a narrative memo/report/note addressed to a reviewer or committee
- ai_declaration: a disclosure of what AI tools were used and how
- combined: a single document containing multiple deliverables (e.g. worksheet AND note together)
- other: anything that doesn't fit the above (e.g. a cover page, unrelated file)

Respond with ONLY a JSON object: {"kind": "<one of the categories above>"}
"""


def classify_file_kind(filename: str, text_snippet: str) -> str:
    user_text = f"Filename: {filename}\n\nContent start:\n{text_snippet[:2000]}"
    response, _usage = run_oneshot("file-classifier", CLASSIFIER_SYSTEM, user_text, temperature=0.0)
    try:
        parsed = extract_json(response)
        kind = parsed.get("kind", "other")
    except (ValueError, KeyError):
        kind = "other"
    valid = {"worksheet", "control_note", "ai_declaration", "combined", "other"}
    return kind if kind in valid else "other"
