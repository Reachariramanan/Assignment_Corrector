import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { api, type StudentProfile } from "../api";
import { bandColor } from "../bands";

export default function StudentProfilePage() {
  const { studentId } = useParams();
  const [profile, setProfile] = useState<StudentProfile | null>(null);

  useEffect(() => {
    if (!studentId) return;
    api.studentProfile(Number(studentId)).then(setProfile);
  }, [studentId]);

  if (!profile) return <p style={{ color: "var(--dsa-muted)" }}>Loading…</p>;

  const chartData = profile.modules.map((m) => ({ module: m.module, score: m.total_weighted_score }));

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-xs" style={{ color: "var(--dsa-muted)" }}>
          ← Dashboard
        </Link>
        <h2 className="text-xl font-semibold mt-1">{profile.student.name}</h2>
        <p className="text-xs" style={{ color: "var(--dsa-muted)" }}>
          Moodle ID {profile.student.moodle_participant_id ?? "—"}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}>
          <div className="text-xs uppercase" style={{ color: "var(--dsa-muted)" }}>
            Average across modules
          </div>
          <div className="text-2xl font-semibold mt-1">
            {profile.average_weighted_score !== null ? `${profile.average_weighted_score}%` : "—"}
          </div>
        </div>
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}>
          <div className="text-xs uppercase" style={{ color: "var(--dsa-muted)" }}>
            Modules
          </div>
          <div className="text-2xl font-semibold mt-1">{profile.modules.length}</div>
        </div>
      </div>

      {profile.modules.length > 1 && (
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}>
          <h3 className="text-sm font-medium mb-3">Score trend across modules</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--dsa-border)" />
              <XAxis dataKey="module" stroke="var(--dsa-muted)" fontSize={12} />
              <YAxis domain={[0, 100]} stroke="var(--dsa-muted)" fontSize={12} />
              <Tooltip contentStyle={{ background: "var(--dsa-surface)", borderColor: "var(--dsa-border)" }} />
              <Line type="monotone" dataKey="score" stroke="var(--dsa-accent)" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="rounded-xl border overflow-hidden" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}>
        <h3 className="text-sm font-medium px-4 pt-4 pb-2">Per-module results</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left" style={{ color: "var(--dsa-muted)" }}>
              <th className="px-4 py-2 font-normal">Module</th>
              <th className="px-4 py-2 font-normal">Status</th>
              <th className="px-4 py-2 font-normal">Score</th>
              <th className="px-4 py-2 font-normal">Band</th>
              <th className="px-4 py-2 font-normal"></th>
            </tr>
          </thead>
          <tbody>
            {profile.modules.map((m) => (
              <tr key={m.module_id} className="border-t" style={{ borderColor: "var(--dsa-border)" }}>
                <td className="px-4 py-2">{m.module}</td>
                <td className="px-4 py-2 capitalize">{m.status.replace("_", " ")}</td>
                <td className="px-4 py-2">{m.total_weighted_score !== null ? `${m.total_weighted_score}%` : "-"}</td>
                <td className="px-4 py-2">
                  {m.band && (
                    <span className="px-2 py-0.5 rounded-full text-xs text-white" style={{ background: bandColor(m.band) }}>
                      {m.band}
                    </span>
                  )}
                </td>
                <td className="px-4 py-2">
                  <Link to={`/students/${studentId}`} className="text-xs hover:underline" style={{ color: "var(--dsa-accent)" }}>
                    Review →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {profile.trait_history.length > 0 && (
        <div className="rounded-xl border overflow-hidden" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}>
          <h3 className="text-sm font-medium px-4 pt-4 pb-2">Trait history</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left" style={{ color: "var(--dsa-muted)" }}>
                <th className="px-4 py-2 font-normal">Module</th>
                <th className="px-4 py-2 font-normal">Trait</th>
                <th className="px-4 py-2 font-normal">Level</th>
              </tr>
            </thead>
            <tbody>
              {profile.trait_history.map((t, i) => (
                <tr key={i} className="border-t" style={{ borderColor: "var(--dsa-border)" }}>
                  <td className="px-4 py-2">{t.module}</td>
                  <td className="px-4 py-2">{t.trait}</td>
                  <td className="px-4 py-2">{t.level}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
