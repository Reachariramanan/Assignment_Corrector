from datetime import datetime, timezone

BAND_THRESHOLDS = [
    (3.25, "Accomplished"),
    (2.5, "Competent"),
    (1.75, "Developing"),
    (0, "Beginning"),
]


def band_for(weighted_level_avg: float) -> str:
    for threshold, label in BAND_THRESHOLDS:
        if weighted_level_avg >= threshold:
            return label
    return "Beginning"


def recompute_status(cur, student_id: int, module_id: int) -> None:
    """Recomputes review_status from the current state of `reviews`. Always call this after
    any change that could affect a student's reviews - including rubric-trait changes from a
    re-import, since ON DELETE CASCADE can silently invalidate review rows."""
    cur.execute(
        """SELECT rt.weight_pct, r.level FROM rubric_traits rt
           LEFT JOIN reviews r ON r.trait_id = rt.id AND r.student_id = ? AND r.module_id = ?
           WHERE rt.module_id = ?""",
        (student_id, module_id, module_id),
    )
    rows = cur.fetchall()
    total_traits = len(rows)
    scored = [r for r in rows if r["level"] is not None]

    weighted_level_avg = 0.0
    if scored:
        weight_sum = sum(r["weight_pct"] for r in scored)
        if weight_sum > 0:
            weighted_level_avg = sum(r["weight_pct"] * r["level"] for r in scored) / weight_sum

    total_weighted_score = round(weighted_level_avg / 4 * 100, 1) if scored else None
    band = band_for(weighted_level_avg) if scored else None
    if not scored:
        status = "not_started"
    elif len(scored) < total_traits:
        status = "in_progress"
    else:
        status = "completed"

    cur.execute(
        """INSERT INTO review_status (student_id, module_id, total_weighted_score, band, status, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(student_id, module_id) DO UPDATE SET
             total_weighted_score=excluded.total_weighted_score, band=excluded.band,
             status=excluded.status, updated_at=excluded.updated_at""",
        (student_id, module_id, total_weighted_score, band, status, datetime.now(timezone.utc).isoformat()),
    )


def mark_not_submitted(cur, student_id: int, module_id: int, reason: str) -> None:
    """Used when the Research agent determines the student didn't actually submit the
    assignment (e.g. only an AI Usage Declaration, no real task answers) - bypasses the
    normal trait-completion counting entirely so this can never read as 'completed'
    just because every trait happens to have been scored 1 ('Beginning')."""
    cur.execute("DELETE FROM reviews WHERE student_id = ? AND module_id = ?", (student_id, module_id))
    cur.execute(
        """INSERT INTO review_status (student_id, module_id, framing_note, total_weighted_score, band, status, updated_at)
           VALUES (?, ?, ?, 0.0, 'No Submission', 'not_submitted', ?)
           ON CONFLICT(student_id, module_id) DO UPDATE SET
             framing_note=excluded.framing_note, total_weighted_score=0.0, band='No Submission',
             status='not_submitted', updated_at=excluded.updated_at""",
        (student_id, module_id, reason, datetime.now(timezone.utc).isoformat()),
    )
