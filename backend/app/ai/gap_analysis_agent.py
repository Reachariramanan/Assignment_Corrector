"""Gap-analysis agent: a distinct pass from grading. Grading answers "what level did
they hit"; this answers "how do they actually approach the problem, and what should
they work on next". Runs on-demand (when a report is requested), cached in DB, using
the same research dossier + review draft + final grades the grading stages already
produced - it does not re-read the student's files itself."""

import json
from typing import Any

from app.ai.common import extract_json, run_oneshot

GAP_ANALYSIS_SYSTEM = """You are a learning-development coach analysing how one participant approaches audit \
case-study problems, using the grading pipeline's own findings below. Your job is different from grading: \
grading already happened - you are now diagnosing their problem-solving PATTERN across the whole submission, \
so they get a personalized, growth-oriented analysis, not just a score.

## Module briefing
{briefing}

## Research dossier (evidence found in their submission)
{dossier}

## Review draft (preliminary trait assessment)
{review_draft}

## Final grades
{final_grades}

## Your task
Look across all of this for PATTERNS, not just per-trait scores:
- How do they approach problems - systematically working through a framework, or ad hoc? Evidence-led or
  assertion-led? Do they verify/cross-check their own claims?
- Where do they consistently do well, and where do they consistently struggle, ACROSS tasks (e.g. "strong
  at classifying individual data elements, but weak at reasoning about second-order consequences" is a
  pattern; "got a 3 on trait X" is not).
- What specific, actionable thing would most improve their NEXT submission - not generic advice.

Respond with ONLY a JSON object, no prose:
{{
  "problem_solving_style": "<2-3 sentences on HOW they approach problems - not what score they got>",
  "strengths": ["<specific, evidence-grounded strength>", ...],
  "growth_areas": [{{"area": "<short name>", "pattern": "<what you observed across tasks>", "recommendation": "<specific, actionable next step>"}}],
  "overall_narrative": "<3-4 sentence holistic summary suitable for a report a student would read about their own work>"
}}
"""


def analyze_gaps(
    briefing: dict[str, Any], dossier: dict[str, Any], review_draft: dict[str, Any], final_grades: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, int]]:
    system_text = GAP_ANALYSIS_SYSTEM.format(
        briefing=json.dumps(briefing, indent=2),
        dossier=json.dumps(dossier, indent=2),
        review_draft=json.dumps(review_draft, indent=2),
        final_grades=json.dumps(final_grades, indent=2),
    )
    response, usage = run_oneshot("gap-analysis", system_text, "Produce the gap-analysis JSON.", temperature=0.3)
    return extract_json(response), usage
