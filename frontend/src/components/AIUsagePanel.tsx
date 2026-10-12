import { useEffect, useState } from "react";
import { api, type AiUsageAssessment } from "../api";

interface Props {
  studentId: number;
  moduleId: number;
}

export default function AIUsagePanel({ studentId, moduleId }: Props) {
  const [assessment, setAssessment] = useState<AiUsageAssessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [assessing, setAssessing] = useState(false);

  useEffect(() => {
    setLoading(true);
    api
      .aiUsage(studentId, moduleId)
      .then(setAssessment)
      .finally(() => setLoading(false));
  }, [studentId, moduleId]);

  async function runAssessment() {
    setAssessing(true);
    try {
      const res = await api.assessAiUsage(studentId, moduleId);
      setAssessment(res);
    } finally {
      setAssessing(false);
    }
  }

  if (loading) return null;

  return (
    <div className="rounded-xl border p-4" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}>
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-medium">AI Usage Coaching</h4>
        {assessment?.has_declaration !== false && (
          <button
            onClick={runAssessment}
            disabled={assessing}
            className="text-xs rounded-md border px-2 py-1 disabled:opacity-50"
            style={{ borderColor: "var(--dsa-border)" }}
          >
            {assessing ? "Assessing…" : assessment?.coaching_note ? "Re-assess" : "Assess"}
          </button>
        )}
      </div>

      {assessment?.has_declaration === false && (
        <p className="text-xs" style={{ color: "var(--dsa-muted)" }}>
          No AI Usage Disclosure was filed by this student — no assessment shown (not penalized, not flagged).
        </p>
      )}

      {assessment?.has_declaration === null && (
        <p className="text-xs" style={{ color: "var(--dsa-muted)" }}>
          Not checked yet — click Assess to look for a filed AI Usage Disclosure.
        </p>
      )}

      {assessment?.has_declaration && (
        <div className="space-y-2 text-sm">
          {assessment.declared_tools && assessment.declared_tools.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {assessment.declared_tools.map((t) => (
                <span
                  key={t}
                  className="text-xs px-2 py-0.5 rounded-full border"
                  style={{ borderColor: "var(--dsa-border)" }}
                >
                  {t}
                </span>
              ))}
            </div>
          )}
          {assessment.integration_quality && (
            <p>
              <span className="font-medium">Integration: </span>
              {assessment.integration_quality}
            </p>
          )}
          {assessment.coaching_note && (
            <p style={{ color: "var(--dsa-muted)" }}>{assessment.coaching_note}</p>
          )}
          {assessment.prompting_suggestions && assessment.prompting_suggestions.length > 0 && (
            <div>
              <div className="font-medium text-xs mb-1">Prompting tips for next time:</div>
              <ul className="list-disc list-inside space-y-1 text-xs" style={{ color: "var(--dsa-muted)" }}>
                {assessment.prompting_suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
