from fastapi import APIRouter

from app.db import db_cursor

router = APIRouter(prefix="/api", tags=["statistics"])


@router.get("/cohorts/{cohort_id}/overview")
def cohort_overview(cohort_id: int):
    with db_cursor() as cur:
        cur.execute(
            """SELECT m.id AS module_id, m.name AS module,
                      COUNT(DISTINCT s.id) AS total_students,
                      SUM(CASE WHEN rs.status = 'completed' THEN 1 ELSE 0 END) AS completed,
                      AVG(rs.total_weighted_score) AS avg_score
               FROM modules m
               JOIN students s ON s.cohort_id = m.cohort_id
               LEFT JOIN review_status rs ON rs.student_id = s.id AND rs.module_id = m.id
               WHERE m.cohort_id = ?
               GROUP BY m.id ORDER BY m.imported_at""",
            (cohort_id,),
        )
        modules = [dict(r) for r in cur.fetchall()]
        for m in modules:
            m["avg_score"] = round(m["avg_score"], 1) if m["avg_score"] is not None else None

        cur.execute(
            """SELECT COALESCE(SUM(tokens_prompt),0) + COALESCE(SUM(tokens_completion),0) AS total_tokens, COUNT(*) AS calls
               FROM ai_usage_log l JOIN modules m ON m.id = l.module_id WHERE m.cohort_id = ?""",
            (cohort_id,),
        )
        usage = dict(cur.fetchone())

        cur.execute(
            """SELECT COUNT(*) AS n FROM ai_usage_assessments a
               JOIN modules m ON m.id = a.module_id WHERE m.cohort_id = ? AND a.has_declaration = 1""",
            (cohort_id,),
        )
        ai_usage_coached = cur.fetchone()["n"]

        scores = [m["avg_score"] for m in modules if m["avg_score"] is not None]
        return {
            "modules": modules,
            "overall_avg_score": round(sum(scores) / len(scores), 1) if scores else None,
            "ai_usage": usage,
            "ai_usage_coached_students": ai_usage_coached,
        }


@router.get("/modules/{module_id}/statistics")
def module_statistics(module_id: int):
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, name, weight_pct, sort_order FROM rubric_traits WHERE module_id = ? ORDER BY sort_order",
            (module_id,),
        )
        traits = [dict(r) for r in cur.fetchall()]

        trait_stats = []
        for t in traits:
            cur.execute(
                "SELECT AVG(level) AS avg_level, COUNT(*) AS n FROM reviews WHERE trait_id = ? AND level IS NOT NULL",
                (t["id"],),
            )
            row = cur.fetchone()
            cur.execute(
                """SELECT AVG(ABS(s.suggested_level - r.level)) AS avg_delta,
                          SUM(CASE WHEN r.source = 'ai_accepted' THEN 1 ELSE 0 END) AS accepted,
                          COUNT(*) AS compared
                   FROM reviews r
                   JOIN ai_suggestions s ON s.student_id = r.student_id AND s.module_id = r.module_id AND s.trait_id = r.trait_id
                   WHERE r.trait_id = ? AND r.level IS NOT NULL""",
                (t["id"],),
            )
            divergence = cur.fetchone()
            trait_stats.append({
                "trait_id": t["id"],
                "name": t["name"],
                "weight_pct": t["weight_pct"],
                "avg_level": round(row["avg_level"], 2) if row["avg_level"] is not None else None,
                "scored_count": row["n"],
                "ai_avg_abs_delta": round(divergence["avg_delta"], 2) if divergence["avg_delta"] is not None else None,
                "ai_accept_rate": (
                    round(divergence["accepted"] / divergence["compared"], 2)
                    if divergence["compared"] else None
                ),
            })

        cur.execute(
            """SELECT status, COUNT(*) AS n FROM review_status rs
               JOIN students s ON s.id = rs.student_id
               JOIN modules m ON m.id = rs.module_id AND m.id = ?
               GROUP BY status""",
            (module_id,),
        )
        completion = {r["status"]: r["n"] for r in cur.fetchall()}
        cur.execute(
            """SELECT COUNT(*) AS n FROM students s
               JOIN modules m ON m.cohort_id = s.cohort_id WHERE m.id = ?""",
            (module_id,),
        )
        total_students = cur.fetchone()["n"]

        cur.execute(
            """SELECT total_weighted_score FROM review_status
               WHERE module_id = ? AND total_weighted_score IS NOT NULL""",
            (module_id,),
        )
        scores = [r["total_weighted_score"] for r in cur.fetchall()]

        cur.execute(
            """SELECT COALESCE(SUM(tokens_prompt),0) AS p, COALESCE(SUM(tokens_completion),0) AS c, COUNT(*) AS calls
               FROM ai_usage_log WHERE module_id = ?""",
            (module_id,),
        )
        usage_row = cur.fetchone()

        return {
            "traits": trait_stats,
            "completion": {
                "total_students": total_students,
                "not_started": completion.get("not_started", 0),
                "in_progress": completion.get("in_progress", 0),
                "completed": completion.get("completed", 0),
                "not_submitted": completion.get("not_submitted", 0),
            },
            "weighted_score_distribution": scores,
            "ai_usage": {
                "total_prompt_tokens": usage_row["p"],
                "total_completion_tokens": usage_row["c"],
                "calls": usage_row["calls"],
            },
        }
