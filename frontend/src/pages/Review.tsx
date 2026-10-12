import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type AiSuggestion, type RubricTrait, type StudentSummary, type SubmissionFile } from "../api";
import AIUsagePanel from "../components/AIUsagePanel";
import ResearchNotesPanel from "../components/ResearchNotesPanel";
import { bandColor } from "../bands";
import RubricPanel, { type TraitDraft } from "../components/RubricPanel";
import { useModuleContext } from "../context/ModuleContext";

type Tab = "scoring" | "research" | "ai_usage";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export default function Review() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const { moduleId } = useModuleContext();
  const sid = Number(studentId);

  const [students, setStudents] = useState<StudentSummary[]>([]);
  const [rubric, setRubric] = useState<RubricTrait[]>([]);
  const [files, setFiles] = useState<SubmissionFile[]>([]);
  const [activeFile, setActiveFile] = useState(0);
  const [drafts, setDrafts] = useState<Record<number, TraitDraft>>({});
  const [framingNote, setFramingNote] = useState("");
  const [suggestions, setSuggestions] = useState<Record<number, AiSuggestion>>({});
  const [saving, setSaving] = useState(false);
  const [assisting, setAssisting] = useState(false);
  const [summary, setSummary] = useState<{ total_weighted_score: number | null; band: string | null; status?: string } | null>(null);
  const [notSubmittedReason, setNotSubmittedReason] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("scoring");

  useEffect(() => {
    if (moduleId === null) return;
    api.students(moduleId).then(setStudents);
    api.rubric(moduleId).then(setRubric);
  }, [moduleId]);

  useEffect(() => {
    if (moduleId === null || !sid) return;
    api.submissions(sid, moduleId).then((fs) => {
      setFiles(fs);
      setActiveFile(0);
    });
    api.reviews(sid, moduleId).then((r) => {
      const d: Record<number, TraitDraft> = {};
      for (const t of r.traits) {
        d[t.trait_id] = { trait_id: t.trait_id, level: t.level, comment: t.comment ?? "", source: t.source ?? "manual" };
      }
      setDrafts(d);
      setFramingNote(r.summary?.framing_note ?? "");
      setSummary(r.summary);
      setNotSubmittedReason(r.summary?.status === "not_submitted" ? r.summary.framing_note : null);
    });
    setSuggestions({});
    setTab("scoring");
  }, [sid, moduleId]);

  const currentIndex = useMemo(() => students.findIndex((s) => s.id === sid), [students, sid]);
  const student = students.find((s) => s.id === sid);

  async function handleSave() {
    if (moduleId === null) return;
    setSaving(true);
    try {
      const traits = Object.values(drafts)
        .filter((d) => d.level !== null)
        .map((d) => ({ trait_id: d.trait_id, level: d.level as number, comment: d.comment || null, source: d.source }));
      const result = await api.saveReviews(sid, moduleId, { framing_note: framingNote || null, traits });
      setSummary(result);
      if (result.status !== "not_submitted") setNotSubmittedReason(null);
    } finally {
      setSaving(false);
    }
  }

  async function handleAiAssist() {
    if (moduleId === null) return;
    setAssisting(true);
    try {
      const res = await api.aiAssist(sid, moduleId);
      if (res.not_submitted) {
        setNotSubmittedReason(res.reason ?? "No genuine attempt at the assignment tasks was found.");
        const fresh = await api.reviews(sid, moduleId);
        setSummary(fresh.summary);
        return;
      }
      setNotSubmittedReason(null);
      const byTrait: Record<number, AiSuggestion> = {};
      for (const s of res.suggestions) byTrait[s.trait_id] = s;
      setSuggestions(byTrait);
      if (!framingNote && res.framing_note) setFramingNote(res.framing_note);
    } catch (e) {
      alert(`AI assist failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setAssisting(false);
    }
  }

  function goToOffset(offset: number) {
    const next = students[currentIndex + offset];
    if (next) navigate(`/students/${next.id}`);
  }

  if (moduleId === null || !rubric.length) return <p style={{ color: "var(--dsa-muted)" }}>Loading…</p>;

  const scoredCount = Object.values(drafts).filter((d) => d.level !== null).length;

  const TABS: { key: Tab; label: string }[] = [
    { key: "scoring", label: "Scoring" },
    { key: "research", label: "Research" },
    { key: "ai_usage", label: "AI Usage" },
  ];

  return (
    <div className="h-full flex flex-col gap-3">
      <div className="flex items-center justify-between shrink-0">
        <Link to="/" className="text-xs" style={{ color: "var(--dsa-muted)" }}>
          ← Dashboard
        </Link>
        <div className="flex items-center gap-2">
          <button
            className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-40"
            style={{ borderColor: "var(--dsa-border)" }}
            disabled={currentIndex <= 0}
            onClick={() => goToOffset(-1)}
          >
            ← Prev
          </button>
          <span className="text-xs tabular-nums" style={{ color: "var(--dsa-faint)" }}>
            {currentIndex >= 0 ? `${currentIndex + 1} / ${students.length}` : ""}
          </span>
          <button
            className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-40"
            style={{ borderColor: "var(--dsa-border)" }}
            disabled={currentIndex < 0 || currentIndex >= students.length - 1}
            onClick={() => goToOffset(1)}
          >
            Next →
          </button>
        </div>
      </div>

      {/* Hero */}
      <div className="rounded-2xl border p-4 shrink-0" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}>
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="flex items-center gap-3.5 min-w-0">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center text-sm font-semibold shrink-0"
              style={{ background: "var(--dsa-soft)", color: "var(--dsa-muted)" }}
            >
              {student ? initials(student.name) : "–"}
            </div>
            <div className="min-w-0">
              <h2 className="text-lg font-semibold truncate">{student?.name ?? "Student"}</h2>
              <div className="flex items-center gap-2 text-xs mt-0.5" style={{ color: "var(--dsa-muted)" }}>
                {student?.moodle_participant_id && <span>ID {student.moodle_participant_id}</span>}
                <Link to={`/students/${sid}/profile`} className="hover:underline" style={{ color: "var(--dsa-accent)" }}>
                  full profile →
                </Link>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div>
              <div className="text-[10px] uppercase tracking-wide font-bold text-right" style={{ color: "var(--dsa-muted)" }}>
                Weighted total
              </div>
              <div className="flex items-baseline gap-2 justify-end">
                <div className="text-[38px] font-bold leading-none mt-1" style={{ letterSpacing: "-0.03em" }}>
                  {summary?.total_weighted_score !== null && summary?.total_weighted_score !== undefined
                    ? `${summary.total_weighted_score}%`
                    : "—"}
                </div>
                {summary?.band && (
                  <span className="tag" style={{ background: bandColor(summary.band), color: "var(--dsa-bg)", border: "none" }}>
                    {summary.band}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="h-1.5 rounded-full mt-3 overflow-hidden" style={{ background: "var(--dsa-soft-2)" }}>
          <div
            className="h-full rounded-full"
            style={{
              width: `${summary?.total_weighted_score ?? 0}%`,
              background: "var(--dsa-accent)",
              transition: "width .55s cubic-bezier(.2,.75,.25,1)",
            }}
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 mt-3 pt-3 border-t" style={{ borderColor: "var(--dsa-border)" }}>
          <span className="text-xs" style={{ color: "var(--dsa-faint)" }}>
            {scoredCount}/{rubric.length} traits scored
          </span>
          <div className="flex items-center gap-2">
            {summary?.status === "completed" && (
              <>
                <a
                  href={api.reportDownloadUrl(sid, moduleId, "docx")}
                  className="rounded-md border px-2.5 py-1.5 text-xs hover:underline"
                  style={{ borderColor: "var(--dsa-border)", color: "var(--dsa-muted)" }}
                >
                  Report (.docx)
                </a>
                <a
                  href={api.reportDownloadUrl(sid, moduleId, "pdf")}
                  className="rounded-md border px-2.5 py-1.5 text-xs hover:underline"
                  style={{ borderColor: "var(--dsa-border)", color: "var(--dsa-muted)" }}
                >
                  Report (.pdf)
                </a>
              </>
            )}
            <button
              onClick={handleAiAssist}
              disabled={assisting}
              className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-50"
              style={{ borderColor: "var(--dsa-border)" }}
            >
              {assisting ? "Grading…" : "Get AI suggestion"}
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-md px-3.5 py-1.5 text-sm font-medium disabled:opacity-50"
              style={{ background: "var(--dsa-accent)", color: "var(--dsa-bg)" }}
            >
              {saving ? "Saving…" : "Save review"}
            </button>
          </div>
        </div>
      </div>

      {notSubmittedReason && (
        <div
          className="rounded-xl border px-4 py-2.5 text-sm flex gap-2.5 shrink-0"
          style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-soft)" }}
        >
          <span className="shrink-0">⚠</span>
          <span>
            <span className="font-medium">No genuine submission detected.</span> {notSubmittedReason} Weighted score
            defaulted to 0%. If you disagree, score the traits manually below to override this.
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0">
        <div className="h-full flex flex-col min-h-0">
          <div
            className="flex gap-0.5 mb-2.5 p-0.5 rounded-lg border w-fit flex-wrap shrink-0"
            style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-soft)" }}
          >
            {files.map((f, i) => (
              <button
                key={f.id}
                onClick={() => setActiveFile(i)}
                className="px-3 py-1 rounded-md text-xs capitalize"
                style={{
                  background: i === activeFile ? "var(--dsa-surface)" : "transparent",
                  color: i === activeFile ? "var(--dsa-text)" : "var(--dsa-muted)",
                  boxShadow: i === activeFile ? "0 1px 2px rgba(0,0,0,.06)" : "none",
                }}
              >
                {f.kind.replace("_", " ")}
              </button>
            ))}
          </div>
          <div
            className="rounded-xl border p-4 flex-1 min-h-0 overflow-y-auto submission-preview text-sm"
            style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}
          >
            {files[activeFile] ? (
              <div dangerouslySetInnerHTML={{ __html: files[activeFile].extracted_html }} />
            ) : (
              <p style={{ color: "var(--dsa-muted)" }}>No submission files.</p>
            )}
          </div>
        </div>

        <div className="h-full flex flex-col min-h-0">
          <div
            className="flex gap-0.5 mb-2.5 p-0.5 rounded-lg border w-fit shrink-0"
            style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-soft)" }}
          >
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className="px-3.5 py-1 rounded-md text-xs font-medium"
                style={{
                  background: tab === t.key ? "var(--dsa-surface)" : "transparent",
                  color: tab === t.key ? "var(--dsa-text)" : "var(--dsa-muted)",
                  boxShadow: tab === t.key ? "0 1px 2px rgba(0,0,0,.06)" : "none",
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto space-y-4 pr-1">
            {tab === "scoring" && (
              <>
                <div>
                  <label className="text-[10px] uppercase tracking-wide font-bold" style={{ color: "var(--dsa-muted)" }}>
                    Framing note
                  </label>
                  <textarea
                    className="w-full rounded-md border px-2 py-1.5 text-sm bg-transparent mt-1"
                    style={{ borderColor: "var(--dsa-border)" }}
                    rows={2}
                    placeholder="How well does the submission open by framing the core issue?"
                    value={framingNote}
                    onChange={(e) => setFramingNote(e.target.value)}
                  />
                </div>

                <div className="rounded-xl border p-4" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}>
                  <RubricPanel
                    rubric={rubric}
                    drafts={drafts}
                    suggestions={suggestions}
                    onChange={(traitId, patch) =>
                      setDrafts((prev) => ({
                        ...prev,
                        [traitId]: { ...(prev[traitId] ?? { trait_id: traitId, level: null, comment: "", source: "manual" }), ...patch },
                      }))
                    }
                  />
                </div>
              </>
            )}

            {tab === "research" && <ResearchNotesPanel studentId={sid} moduleId={moduleId} />}
            {tab === "ai_usage" && <AIUsagePanel studentId={sid} moduleId={moduleId} />}
          </div>
        </div>
      </div>
    </div>
  );
}
