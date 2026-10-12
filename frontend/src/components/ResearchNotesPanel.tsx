import { useEffect, useState } from "react";
import { api, type Dossier } from "../api";

export default function ResearchNotesPanel({ studentId, moduleId }: { studentId: number; moduleId: number }) {
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    api.dossier(studentId, moduleId).then(setDossier);
  }, [studentId, moduleId]);

  if (!dossier) return null;

  return (
    <div className="rounded-xl border p-4" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}>
      <button
        className="flex items-center justify-between w-full text-sm font-medium"
        onClick={() => setExpanded((e) => !e)}
      >
        <span>Research notes ({dossier.files_read_count} file{dossier.files_read_count === 1 ? "" : "s"} reviewed)</span>
        <span style={{ color: "var(--dsa-muted)" }}>{expanded ? "▲" : "▼"}</span>
      </button>

      {expanded && (
        <div className="mt-3 space-y-3 text-xs">
          {dossier.dossier.overall_impression && (
            <p style={{ color: "var(--dsa-muted)" }}>{dossier.dossier.overall_impression}</p>
          )}

          {dossier.dossier.per_task_evidence && dossier.dossier.per_task_evidence.length > 0 && (
            <div className="space-y-2">
              {dossier.dossier.per_task_evidence.map((t, i) => (
                <div key={i} className="rounded-md border p-2" style={{ borderColor: "var(--dsa-border)" }}>
                  <div className="flex items-center gap-2 font-medium">
                    <span>{t.task}</span>
                    <span
                      className="px-1.5 py-0.5 rounded text-[10px] text-white"
                      style={{ background: t.found ? "#16a34a" : "#e11d48" }}
                    >
                      {t.found ? "addressed" : "missing"}
                    </span>
                  </div>
                  <p className="mt-1" style={{ color: "var(--dsa-muted)" }}>
                    {t.evidence}
                  </p>
                  {t.gaps && (
                    <p className="mt-1 italic" style={{ color: "var(--dsa-muted)" }}>
                      Gap: {t.gaps}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {dossier.review_draft?.traits && dossier.review_draft.traits.length > 0 && (
            <div>
              <div className="font-medium mb-1">Parallel per-trait verdicts:</div>
              <div className="space-y-1.5">
                {dossier.review_draft.traits.map((t, i) => (
                  <div key={i} className="rounded-md border p-2" style={{ borderColor: "var(--dsa-border)" }}>
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{t.trait}</span>
                      <span style={{ color: "var(--dsa-muted)" }}>
                        L{t.level} ({t.level_label}) · {t.earned_pct}% of {t.weight_pct}%
                      </span>
                    </div>
                    <p className="mt-1 italic" style={{ color: "var(--dsa-muted)" }}>
                      "{t.reasoning_verbatim}"
                    </p>
                    {t.open_question && (
                      <p className="mt-1" style={{ color: "var(--dsa-accent)" }}>
                        Flagged for review: {t.open_question}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
