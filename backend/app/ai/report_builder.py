"""Builds a per-student Markdown report from everything the pipeline produced
(scores, research evidence, AI-usage coaching, gap analysis), then renders it to
DOCX or PDF via pandoc."""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.ai.gap_analysis_agent import analyze_gaps
from app.db import db_cursor


def _get_or_create_gap_analysis(student_id: int, module_id: int) -> dict[str, Any]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT problem_solving_style, strengths_json, growth_areas_json, overall_narrative "
            "FROM gap_analyses WHERE student_id = ? AND module_id = ?",
            (student_id, module_id),
        )
        row = cur.fetchone()
        if row:
            return {
                "problem_solving_style": row["problem_solving_style"],
                "strengths": json.loads(row["strengths_json"] or "[]"),
                "growth_areas": json.loads(row["growth_areas_json"] or "[]"),
                "overall_narrative": row["overall_narrative"],
            }

        cur.execute("SELECT briefing_json FROM modules WHERE id = ?", (module_id,))
        briefing = json.loads(cur.fetchone()["briefing_json"] or "{}")
        cur.execute(
            "SELECT dossier_json, review_draft_json FROM research_dossiers WHERE student_id = ? AND module_id = ?",
            (student_id, module_id),
        )
        dossier_row = cur.fetchone()
        if not dossier_row:
            raise ValueError("No research dossier for this student yet - run AI-assist first")
        dossier = json.loads(dossier_row["dossier_json"])
        review_draft = json.loads(dossier_row["review_draft_json"] or "{}")

        cur.execute(
            """SELECT rt.name AS trait, r.level, r.comment FROM reviews r
               JOIN rubric_traits rt ON rt.id = r.trait_id
               WHERE r.student_id = ? AND r.module_id = ?""",
            (student_id, module_id),
        )
        final_grades = {"traits": [dict(r) for r in cur.fetchall()]}

    analysis, usage = analyze_gaps(briefing, dossier, review_draft, final_grades)

    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO gap_analyses (student_id, module_id, problem_solving_style, strengths_json, growth_areas_json, overall_narrative, model)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(student_id, module_id) DO UPDATE SET
                 problem_solving_style=excluded.problem_solving_style, strengths_json=excluded.strengths_json,
                 growth_areas_json=excluded.growth_areas_json, overall_narrative=excluded.overall_narrative,
                 model=excluded.model, created_at=datetime('now')""",
            (
                student_id, module_id,
                analysis.get("problem_solving_style"),
                json.dumps(analysis.get("strengths", [])),
                json.dumps(analysis.get("growth_areas", [])),
                analysis.get("overall_narrative"),
                "gemma-4-26b-a4b-it",
            ),
        )
        cur.execute(
            """INSERT INTO ai_usage_log (student_id, module_id, yukta_session_id, kind, tokens_prompt, tokens_completion, iterations)
               VALUES (?, ?, ?, 'gap_analysis', ?, ?, ?)""",
            (student_id, module_id, f"{student_id}:{module_id}", usage.get("tokens_prompt", 0), usage.get("tokens_completion", 0), usage.get("iterations", 1)),
        )
    return analysis


def build_report_markdown(student_id: int, module_id: int) -> str:
    with db_cursor() as cur:
        cur.execute("SELECT name, moodle_participant_id, cohort_id FROM students WHERE id = ?", (student_id,))
        student = cur.fetchone()
        cur.execute("SELECT name FROM cohorts WHERE id = ?", (student["cohort_id"],))
        cohort = cur.fetchone()
        cur.execute("SELECT name FROM modules WHERE id = ?", (module_id,))
        module = cur.fetchone()
        cur.execute(
            "SELECT framing_note, total_weighted_score, band FROM review_status WHERE student_id = ? AND module_id = ?",
            (student_id, module_id),
        )
        summary = cur.fetchone()
        cur.execute(
            """SELECT rt.id AS trait_id, rt.name AS trait, rt.weight_pct, r.level, r.comment FROM rubric_traits rt
               LEFT JOIN reviews r ON r.trait_id = rt.id AND r.student_id = ? AND r.module_id = ?
               WHERE rt.module_id = ? ORDER BY rt.sort_order""",
            (student_id, module_id, module_id),
        )
        traits = [dict(r) for r in cur.fetchall()]
        for t in traits:
            cur.execute("SELECT label FROM rubric_levels WHERE trait_id = ? AND level = ?", (t["trait_id"], t["level"]))
            row = cur.fetchone()
            t["level_label"] = row["label"] if row else None
            t["earned_pct"] = round(t["weight_pct"] * t["level"] / 4, 1) if t["level"] else None
        cur.execute(
            "SELECT dossier_json, review_draft_json FROM research_dossiers WHERE student_id = ? AND module_id = ?",
            (student_id, module_id),
        )
        dossier_row = cur.fetchone()
        dossier = json.loads(dossier_row["dossier_json"]) if dossier_row else {}
        review_draft = json.loads(dossier_row["review_draft_json"]) if dossier_row and dossier_row["review_draft_json"] else {}
        open_questions_by_trait = {
            rv["trait"]: rv.get("open_question") for rv in review_draft.get("traits", []) if rv.get("open_question")
        }
        cur.execute(
            "SELECT has_declaration, declared_tools, integration_quality, coaching_note, prompting_suggestions "
            "FROM ai_usage_assessments WHERE student_id = ? AND module_id = ?",
            (student_id, module_id),
        )
        ai_usage_row = cur.fetchone()

    gap = _get_or_create_gap_analysis(student_id, module_id)

    lines = [
        f"# Submission Review Report",
        f"**Student:** {student['name']}  ",
        f"**Cohort:** {cohort['name']}  ",
        f"**Module:** {module['name']}  ",
        "",
        "## Summary",
        f"**Weighted score:** {summary['total_weighted_score']}%  ",
        f"**Band:** {summary['band']}  ",
        "",
        f"> {summary['framing_note'] or ''}",
        "",
        "## Rubric Scores",
        "",
        "| Trait | Weight | Level | Earned |",
        "|---|---|---|---|",
    ]
    for t in traits:
        level_display = f"{t['level']} ({t['level_label']})" if t["level"] else "-"
        earned_display = f"{t['earned_pct']}%" if t["earned_pct"] is not None else "-"
        lines.append(f"| {t['trait']} | {t['weight_pct']}% | {level_display} | {earned_display} |")

    lines += ["", "## Trait-by-Trait Detail", ""]
    for t in traits:
        level_display = f"Level {t['level']} — {t['level_label']}" if t["level"] else "Not scored"
        earned_display = f"{t['earned_pct']}% of {t['weight_pct']}%" if t["earned_pct"] is not None else "-"
        lines.append(f"### {t['trait']} ({t['weight_pct']}% weight)")
        lines.append(f"**{level_display} · earned {earned_display}**")
        lines.append("")
        if t["comment"]:
            lines.append(f"> {t['comment']}")
            lines.append("")
        open_q = open_questions_by_trait.get(t["trait"])
        if open_q:
            lines.append(f"*Reviewer follow-up: {open_q}*")
            lines.append("")

    lines += ["", "## Problem-Solving Analysis", ""]
    if gap.get("problem_solving_style"):
        lines += [gap["problem_solving_style"], ""]
    if gap.get("strengths"):
        lines += ["**Strengths:**", ""]
        lines += [f"- {s}" for s in gap["strengths"]]
        lines.append("")
    if gap.get("growth_areas"):
        lines += ["**Growth areas:**", ""]
        for g in gap["growth_areas"]:
            lines.append(f"- **{g.get('area', '')}** — {g.get('pattern', '')} *Recommendation: {g.get('recommendation', '')}*")
        lines.append("")
    if gap.get("overall_narrative"):
        lines += ["**Overall:** " + gap["overall_narrative"], ""]

    if dossier.get("per_task_evidence"):
        lines += ["## Evidence Found Per Task", ""]
        for t in dossier["per_task_evidence"]:
            status = "✅" if t.get("found") else "⚠️"
            lines.append(f"- {status} **{t.get('task', '')}**: {t.get('evidence', '')}")
            if t.get("gaps"):
                lines.append(f"  - Gap: {t['gaps']}")
        lines.append("")

    if ai_usage_row and ai_usage_row["has_declaration"]:
        lines += ["## AI Usage Coaching", ""]
        tools = json.loads(ai_usage_row["declared_tools"] or "[]")
        if tools:
            lines.append(f"**Declared tools:** {', '.join(tools)}  ")
        if ai_usage_row["integration_quality"]:
            lines.append(f"**Integration quality:** {ai_usage_row['integration_quality']}  ")
        if ai_usage_row["coaching_note"]:
            lines += ["", ai_usage_row["coaching_note"]]
        suggestions = json.loads(ai_usage_row["prompting_suggestions"] or "[]")
        if suggestions:
            lines += ["", "**Prompting tips for next time:**", ""]
            lines += [f"- {s}" for s in suggestions]
        lines.append("")

    lines.append("*Generated by the Submission Review Interface — Digital Skills Academy*")
    return "\n".join(lines)


def render_report(student_id: int, module_id: int, fmt: str) -> Path:
    if fmt not in ("docx", "pdf"):
        raise ValueError("format must be 'docx' or 'pdf'")
    markdown = build_report_markdown(student_id, module_id)
    tmp_dir = Path(tempfile.mkdtemp(prefix="dsa_report_"))
    md_path = tmp_dir / "report.md"
    out_path = tmp_dir / f"report.{fmt}"
    md_path.write_text(markdown)

    args = ["pandoc", str(md_path), "-o", str(out_path), "--metadata", "title=Submission Review Report"]
    if fmt == "pdf":
        args += ["--pdf-engine=wkhtmltopdf"]
    subprocess.run(args, check=True, capture_output=True, text=True)
    return out_path
