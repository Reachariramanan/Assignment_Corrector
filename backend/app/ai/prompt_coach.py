"""AI-usage coaching agent.

Deliberately NOT an "AI-detector": LLMs cannot reliably tell whether text was
AI-written, and guessing would be unfair to students. This agent only runs for
students who filed their own AI Usage Disclosure document, and only ever gives
coaching feedback (how well the disclosed AI use was integrated, and how a
different prompting approach could have produced richer output) - never a
plagiarism verdict, never a score.
"""

from app.ai.common import extract_json, run_oneshot

PROMPT_COACH_SYSTEM = """You are a writing/AI-literacy coach for an audit-training course. A participant \
has voluntarily disclosed their use of AI tools while completing a case-study assignment. Your job is \
ONLY to coach them on how to use AI tools more effectively next time - you are not grading, scoring, or \
making any claim about academic integrity. Assume the disclosure is honest and the AI use was permitted.

## Case study tasks (for context on what a strong answer covers)
{case_study_text}

## The participant's own AI Usage Disclosure
{declaration_text}

## Instructions
Read the disclosure and the participant's actual submission (given by the user). Assess:
1. How specifically they disclosed their AI use (tool names, what it was used for, how they verified/edited output)
2. Whether the final submission shows independent judgment beyond what was likely drafted by AI (or is generic/unedited)
3. Concrete ways their PROMPTING could have been better - e.g. asking the AI to cite specific data-pack \
evidence (Device IDs, clauses), asking for alternatives before picking one, asking it to challenge its own \
first answer - anything that would have produced a richer, more evidence-grounded result.

Respond with ONLY a JSON object of this shape:
{{
  "declared_tools": ["<tool names as disclosed>"],
  "integration_quality": "<1-2 sentence assessment of how well AI output was verified/integrated vs copy-pasted>",
  "coaching_note": "<2-3 sentence encouraging, specific coaching note>",
  "prompting_suggestions": ["<specific, actionable prompting tip>", "..."]
}}
"""


def assess_ai_usage(case_study_html_text: str, declaration_text: str, submission_text: str) -> tuple[dict, dict]:
    system_text = PROMPT_COACH_SYSTEM.format(
        case_study_text=case_study_html_text[:4000],
        declaration_text=declaration_text[:3000],
    )
    user_text = "Here is the participant's full submission:\n\n" + submission_text[:16000]
    response, usage = run_oneshot("prompt-coach", system_text, user_text, temperature=0.3)
    parsed = extract_json(response)
    return parsed, usage
