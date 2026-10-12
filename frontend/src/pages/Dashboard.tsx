import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Label,
  LabelList,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type AssessAllProgress, type CohortOverview, type ModuleStatistics, type StudentSummary } from "../api";
import { bandColor, STATUS_COLORS } from "../bands";
import CourseManager from "../components/CourseManager";
import { useModuleContext } from "../context/ModuleContext";

function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="metric-card">
      <div className="text-2xl font-bold" style={{ letterSpacing: "-0.03em" }}>
        {value}
      </div>
      <div className="text-[10px] font-bold uppercase tracking-wide mt-1" style={{ color: "var(--dsa-muted)" }}>
        {label}
      </div>
      {sub && (
        <div className="text-xs mt-1" style={{ color: "var(--dsa-faint)" }}>
          {sub}
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const { cohortId, moduleId } = useModuleContext();
  const [students, setStudents] = useState<StudentSummary[]>([]);
  const [stats, setStats] = useState<ModuleStatistics | null>(null);
  const [overview, setOverview] = useState<CohortOverview | null>(null);
  const [assessProgress, setAssessProgress] = useState<AssessAllProgress | null>(null);
  const assessPollRef = useRef<number | null>(null);

  function refreshRoster(mid: number) {
    api.students(mid).then(setStudents);
    api.statistics(mid).then(setStats);
  }

  function watchAssessProgress(mid: number, initial: AssessAllProgress) {
    setAssessProgress(initial);
    if (!initial.running) return;
    if (assessPollRef.current) window.clearInterval(assessPollRef.current);
    assessPollRef.current = window.setInterval(async () => {
      const s = await api.assessAllStatus(mid);
      setAssessProgress(s);
      refreshRoster(mid);
      if (!s.running && assessPollRef.current) {
        window.clearInterval(assessPollRef.current);
        assessPollRef.current = null;
      }
    }, 2500);
  }

  useEffect(() => {
    if (moduleId === null) return;
    refreshRoster(moduleId);
    setAssessProgress(null);
    if (assessPollRef.current) {
      window.clearInterval(assessPollRef.current);
      assessPollRef.current = null;
    }
    // A batch may already be running (e.g. kicked off from the upload modal, or from
    // before a page refresh) - resume showing/polling its progress instead of looking idle.
    api.assessAllStatus(moduleId).then((status) => watchAssessProgress(moduleId, status));
  }, [moduleId]);

  useEffect(() => {
    if (cohortId === null) return;
    api.cohortOverview(cohortId).then(setOverview);
  }, [cohortId, moduleId]);

  useEffect(() => {
    return () => {
      if (assessPollRef.current) window.clearInterval(assessPollRef.current);
    };
  }, []);

  async function startAssessment() {
    if (moduleId === null) return;
    const started = await api.startAssessAll(moduleId);
    watchAssessProgress(moduleId, started);
  }

  if (moduleId === null) {
    return <p style={{ color: "var(--dsa-muted)" }}>No module imported yet.</p>;
  }

  const completionData = stats
    ? [
        { name: "Not started", value: stats.completion.not_started, color: STATUS_COLORS.not_started },
        { name: "In progress", value: stats.completion.in_progress, color: STATUS_COLORS.in_progress },
        { name: "Completed", value: stats.completion.completed, color: STATUS_COLORS.completed },
        { name: "Not submitted", value: stats.completion.not_submitted, color: STATUS_COLORS.not_submitted },
      ].filter((d) => d.value > 0)
    : [];

  const completionPct =
    stats && stats.completion.total_students
      ? Math.round((stats.completion.completed / stats.completion.total_students) * 100)
      : 0;

  const scoreHistogram = (() => {
    const buckets = [
      { range: "0-20", min: 0, max: 20, count: 0 },
      { range: "20-40", min: 20, max: 40, count: 0 },
      { range: "40-60", min: 40, max: 60, count: 0 },
      { range: "60-80", min: 60, max: 80, count: 0 },
      { range: "80-100", min: 80, max: 101, count: 0 },
    ];
    for (const score of stats?.weighted_score_distribution ?? []) {
      const bucket = buckets.find((b) => score >= b.min && score < b.max);
      if (bucket) bucket.count += 1;
    }
    return buckets;
  })();

  const tooltipStyle = {
    background: "var(--dsa-surface)",
    borderColor: "var(--dsa-border)",
    borderRadius: 10,
    color: "var(--dsa-text)",
    fontSize: 12,
  };

  return (
    <div className="space-y-8">
      {overview && overview.modules.length > 1 && (
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--dsa-accent)", background: "var(--dsa-surface)" }}>
          <h3 className="text-sm font-medium mb-3">Overall (all modules in this cohort)</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">
            <StatTile label="Overall avg score" value={overview.overall_avg_score !== null ? `${overview.overall_avg_score}%` : "-"} />
            <StatTile label="Modules" value={String(overview.modules.length)} />
            <StatTile label="AI-usage coached" value={String(overview.ai_usage_coached_students)} />
            <StatTile label="Total AI tokens" value={overview.ai_usage.total_tokens.toLocaleString()} />
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left" style={{ color: "var(--dsa-muted)" }}>
                <th className="font-normal py-1">Module</th>
                <th className="font-normal py-1">Students</th>
                <th className="font-normal py-1">Completed</th>
                <th className="font-normal py-1">Avg score</th>
              </tr>
            </thead>
            <tbody>
              {overview.modules.map((m) => (
                <tr key={m.module_id} className="border-t" style={{ borderColor: "var(--dsa-border)" }}>
                  <td className="py-1">{m.module}</td>
                  <td className="py-1">{m.total_students}</td>
                  <td className="py-1">{m.completed}</td>
                  <td className="py-1">{m.avg_score !== null ? `${m.avg_score}%` : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile
          label="Students"
          value={String(stats?.completion.total_students ?? "-")}
          sub={`${stats?.completion.completed ?? 0} graded`}
        />
        <StatTile
          label="Avg weighted score"
          value={
            stats && stats.weighted_score_distribution.length
              ? `${(
                  stats.weighted_score_distribution.reduce((a, b) => a + b, 0) /
                  stats.weighted_score_distribution.length
                ).toFixed(1)}%`
              : "-"
          }
        />
        <StatTile
          label="AI calls"
          value={String(stats?.ai_usage.calls ?? 0)}
          sub={
            stats
              ? `${(stats.ai_usage.total_prompt_tokens + stats.ai_usage.total_completion_tokens).toLocaleString()} tokens`
              : undefined
          }
        />
        <StatTile
          label="Completion"
          value={
            stats && stats.completion.total_students
              ? `${Math.round((stats.completion.completed / stats.completion.total_students) * 100)}%`
              : "0%"
          }
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div
          className="lg:col-span-2 rounded-xl border p-4"
          style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}
        >
          <h3 className="text-sm font-medium mb-3">Average level by rubric trait</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={stats?.traits ?? []} layout="vertical" margin={{ left: 24, right: 28 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--dsa-border)" horizontal={false} />
              <XAxis type="number" domain={[0, 4]} stroke="var(--dsa-muted)" fontSize={12} />
              <YAxis type="category" dataKey="name" width={220} stroke="var(--dsa-muted)" fontSize={11} />
              <Tooltip formatter={(v) => (typeof v === "number" ? v.toFixed(2) : v)} contentStyle={tooltipStyle} cursor={{ fill: "var(--dsa-soft)" }} />
              <Bar dataKey="avg_level" radius={[0, 4, 4, 0]} maxBarSize={22}>
                <LabelList dataKey="avg_level" position="right" formatter={(v) => (typeof v === "number" ? v.toFixed(1) : v)} style={{ fill: "var(--dsa-muted)", fontSize: 11 }} />
                {(stats?.traits ?? []).map((t) => (
                  <Cell key={t.trait_id} fill="var(--dsa-accent)" fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border p-4" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}>
          <h3 className="text-sm font-medium mb-3">Review completion</h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={completionData} dataKey="value" nameKey="name" innerRadius={58} outerRadius={90} paddingAngle={2} stroke="none">
                {completionData.map((d) => (
                  <Cell key={d.name} fill={d.color} />
                ))}
                <Label
                  position="center"
                  content={() => (
                    <text x="50%" y="48%" textAnchor="middle" dominantBaseline="middle">
                      <tspan x="50%" dy="-0.3em" style={{ fontSize: 22, fontWeight: 700, fill: "var(--dsa-text)" }}>
                        {completionPct}%
                      </tspan>
                      <tspan x="50%" dy="1.4em" style={{ fontSize: 10, fill: "var(--dsa-muted)" }}>
                        graded
                      </tspan>
                    </text>
                  )}
                />
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend
                verticalAlign="bottom"
                height={24}
                formatter={(value) => <span style={{ color: "var(--dsa-muted)", fontSize: 11 }}>{value}</span>}
                iconSize={8}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="lg:col-span-3 rounded-xl border p-4" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}>
          <h3 className="text-sm font-medium mb-3">Weighted score distribution</h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={scoreHistogram} margin={{ left: 0, right: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--dsa-border)" vertical={false} />
              <XAxis dataKey="range" stroke="var(--dsa-muted)" fontSize={11} tickLine={false} />
              <YAxis allowDecimals={false} stroke="var(--dsa-muted)" fontSize={11} width={28} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--dsa-soft)" }} formatter={(v) => [`${v} student(s)`, "Count"]} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={48} fill="var(--dsa-green)" fillOpacity={0.75} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border overflow-hidden" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}>
        <div className="flex items-center justify-between px-4 pt-4 pb-2">
          <h3 className="text-sm font-medium">Roster</h3>
          {moduleId !== null && (
            <div className="flex gap-2">
              <button
                onClick={startAssessment}
                disabled={!!assessProgress?.running || !stats?.completion.not_started}
                className="text-xs rounded-md px-2.5 py-1 disabled:opacity-50"
                style={{ background: "var(--dsa-accent)", color: "var(--dsa-bg)" }}
                title={stats?.completion.not_started ? `${stats.completion.not_started} student(s) not yet graded` : "All students already graded"}
              >
                {assessProgress?.running ? "Assessing…" : "Start Assessment"}
              </button>
              <a
                href={api.gradebookDownloadUrl(moduleId)}
                className="text-xs rounded-md border px-2.5 py-1 hover:underline"
                style={{ borderColor: "var(--dsa-border)", color: "var(--dsa-accent)" }}
              >
                Export gradebook (.xlsx)
              </a>
              <a
                href={api.allReportsDownloadUrl(moduleId, "pdf")}
                className="text-xs rounded-md border px-2.5 py-1 hover:underline"
                style={{ borderColor: "var(--dsa-border)", color: "var(--dsa-accent)" }}
                title="Downloads a zip with every graded student's report as a PDF"
              >
                Download all reports (.zip)
              </a>
            </div>
          )}
        </div>
        {assessProgress && (assessProgress.running || assessProgress.done > 0) && (
          <div className="px-4 pb-2 text-xs" style={{ color: assessProgress.running ? "var(--dsa-muted)" : "var(--dsa-accent)" }}>
            {assessProgress.running
              ? `Assessing… ${assessProgress.done}/${assessProgress.total}${assessProgress.current ? ` — ${assessProgress.current}` : ""}`
              : `Done: ${assessProgress.done}/${assessProgress.total} graded${assessProgress.errors.length ? `, ${assessProgress.errors.length} failed` : ""}.`}
          </div>
        )}
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left" style={{ color: "var(--dsa-muted)" }}>
              <th className="px-4 py-2 font-normal">Student</th>
              <th className="px-4 py-2 font-normal">Status</th>
              <th className="px-4 py-2 font-normal">Weighted score</th>
              <th className="px-4 py-2 font-normal">Band</th>
            </tr>
          </thead>
          <tbody>
            {students.map((s) => {
              const initials = s.name
                .split(/\s+/)
                .map((p) => p[0])
                .slice(0, 2)
                .join("")
                .toUpperCase();
              return (
                <tr
                  key={s.id}
                  className="border-t"
                  style={{ borderColor: "var(--dsa-border)", transition: "background 0.16s ease" }}
                >
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2.5">
                      <div
                        className="w-[29px] h-[29px] rounded-full flex items-center justify-center text-[11px] font-semibold shrink-0"
                        style={{ background: "var(--dsa-soft)", color: "var(--dsa-muted)" }}
                      >
                        {initials}
                      </div>
                      <div>
                        <Link to={`/students/${s.id}`} className="hover:underline font-medium" style={{ color: "var(--dsa-text)" }}>
                          {s.name}
                        </Link>
                        <Link to={`/students/${s.id}/profile`} className="ml-2 text-xs hover:underline" style={{ color: "var(--dsa-muted)" }}>
                          profile
                        </Link>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-2 capitalize">{s.status.replace("_", " ")}</td>
                  <td className="px-4 py-2">{s.total_weighted_score !== null ? `${s.total_weighted_score}%` : "-"}</td>
                  <td className="px-4 py-2">
                    {s.band && (
                      <span className="tag" style={{ background: bandColor(s.band), color: "var(--dsa-bg)", border: "none" }}>
                        {s.band}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <CourseManager />
    </div>
  );
}
