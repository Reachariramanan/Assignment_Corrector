import { useEffect, useRef, useState } from "react";
import { api, type AssessAllProgress, type Cohort, type ModuleSummary } from "../api";

interface Props {
  onClose: () => void;
  onImported: () => void;
}

const NEW_OPTION = "__new__";

export default function UploadModal({ onClose, onImported }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [cohorts, setCohorts] = useState<Cohort[]>([]);
  const [modules, setModules] = useState<ModuleSummary[]>([]);

  const [cohortChoice, setCohortChoice] = useState<string>(NEW_OPTION);
  const [newCohortName, setNewCohortName] = useState("");
  const [moduleChoice, setModuleChoice] = useState<string>(NEW_OPTION);
  const [newModuleName, setNewModuleName] = useState("");
  const [suggesting, setSuggesting] = useState(false);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [importedModuleId, setImportedModuleId] = useState<number | null>(null);
  const [assessProgress, setAssessProgress] = useState<AssessAllProgress | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  async function startAssessment() {
    if (importedModuleId === null) return;
    const started = await api.startAssessAll(importedModuleId);
    setAssessProgress(started);
    if (!started.running) return; // nothing_to_grade or already finished synchronously
    pollRef.current = window.setInterval(async () => {
      const status = await api.assessAllStatus(importedModuleId);
      setAssessProgress(status);
      if (!status.running && pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }, 2500);
  }

  useEffect(() => {
    api.cohorts().then((cs) => {
      setCohorts(cs);
      if (cs.length > 0) setCohortChoice(String(cs[0].id));
    });
  }, []);

  useEffect(() => {
    if (cohortChoice === NEW_OPTION) {
      setModules([]);
      setModuleChoice(NEW_OPTION);
      return;
    }
    api.modules(Number(cohortChoice)).then((ms) => {
      setModules(ms);
      setModuleChoice(ms.length > 0 ? String(ms[0].id) : NEW_OPTION);
    });
  }, [cohortChoice]);

  async function handleFileChange(f: File | null) {
    setFile(f);
    if (f && moduleChoice === NEW_OPTION && !newModuleName) {
      setSuggesting(true);
      try {
        const suggested = await api.suggestModuleName(f);
        if (suggested) setNewModuleName(suggested);
      } finally {
        setSuggesting(false);
      }
    }
  }

  const cohortName =
    cohortChoice === NEW_OPTION ? newCohortName.trim() : cohorts.find((c) => String(c.id) === cohortChoice)?.name ?? "";
  const moduleName =
    moduleChoice === NEW_OPTION ? newModuleName.trim() : modules.find((m) => String(m.id) === moduleChoice)?.name ?? "";

  async function submit() {
    if (!file || !cohortName || !moduleName) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.uploadModule(file, cohortName, moduleName);
      setResult(
        `Imported ${res.students} students, ${res.files} files, ${res.rubric_traits} rubric traits` +
          (res.ai_classified_files ? ` (${res.ai_classified_files} file kinds auto-classified by AI)` : ""),
      );
      setImportedModuleId(res.module_id);
      onImported();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 px-4">
      <div
        className="w-full max-w-md rounded-xl border p-5 space-y-3"
        style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-medium">Import a Moodle assignment export</h3>
          <button onClick={onClose} className="text-sm" style={{ color: "var(--dsa-muted)" }}>
            ✕
          </button>
        </div>

        <div>
          <label className="text-xs" style={{ color: "var(--dsa-muted)" }}>
            Course
          </label>
          <select
            className="w-full rounded-md border px-2 py-1.5 text-sm bg-transparent mt-1"
            style={{ borderColor: "var(--dsa-border)" }}
            value={cohortChoice}
            onChange={(e) => setCohortChoice(e.target.value)}
          >
            {cohorts.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
            <option value={NEW_OPTION}>+ New course…</option>
          </select>
          {cohortChoice === NEW_OPTION && (
            <input
              type="text"
              placeholder="New course name (e.g. CADS-F Batch 2)"
              className="w-full rounded-md border px-2 py-1.5 text-sm bg-transparent mt-1.5"
              style={{ borderColor: "var(--dsa-border)" }}
              value={newCohortName}
              onChange={(e) => setNewCohortName(e.target.value)}
            />
          )}
        </div>

        <div>
          <label className="text-xs" style={{ color: "var(--dsa-muted)" }}>
            Module
          </label>
          <select
            className="w-full rounded-md border px-2 py-1.5 text-sm bg-transparent mt-1"
            style={{ borderColor: "var(--dsa-border)" }}
            value={moduleChoice}
            onChange={(e) => setModuleChoice(e.target.value)}
          >
            {modules.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
            <option value={NEW_OPTION}>+ New module…</option>
          </select>
          {moduleChoice === NEW_OPTION && (
            <input
              type="text"
              placeholder={suggesting ? "Suggesting a name from the zip…" : "New module name (e.g. Module 2)"}
              className="w-full rounded-md border px-2 py-1.5 text-sm bg-transparent mt-1.5"
              style={{ borderColor: "var(--dsa-border)" }}
              value={newModuleName}
              onChange={(e) => setNewModuleName(e.target.value)}
            />
          )}
          {moduleChoice !== NEW_OPTION && (
            <p className="text-xs mt-1" style={{ color: "var(--dsa-muted)" }}>
              Re-importing into an existing module updates it in place (students/scores already
              reviewed are preserved).
            </p>
          )}
        </div>

        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const dropped = e.dataTransfer.files?.[0];
            if (dropped && dropped.name.toLowerCase().endsWith(".zip")) handleFileChange(dropped);
          }}
          className="flex flex-col items-center justify-center rounded-lg border border-dashed px-3 py-5 text-xs cursor-pointer text-center"
          style={{
            borderColor: dragOver ? "var(--dsa-accent)" : "var(--dsa-border)",
            background: dragOver ? "var(--dsa-accent-soft)" : "var(--dsa-soft)",
            color: "var(--dsa-muted)",
          }}
        >
          {file ? (
            <span style={{ color: "var(--dsa-text)" }}>{file.name}</span>
          ) : (
            <span>Drag a .zip here, or click to browse</span>
          )}
          <input
            type="file"
            accept=".zip"
            onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
            className="hidden"
          />
        </label>
        <p className="text-xs" style={{ color: "var(--dsa-muted)" }}>
          Expects the standard Moodle export shape: a case-study docx, an evaluator-key/sample-answer docx
          with the rubric table, and a student-submissions folder. Folder names and nesting can vary -
          this is auto-detected. File kinds that can't be inferred from filename are auto-classified by
          the model. This can take a minute for larger batches.
        </p>

        {error && <p className="text-xs text-red-500">{error}</p>}
        {result && (
          <p className="text-xs" style={{ color: "var(--dsa-accent)" }}>
            {result}
          </p>
        )}

        {result && assessProgress && (
          <div className="rounded-md border px-3 py-2 text-xs space-y-1" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-soft)" }}>
            {assessProgress.reason === "nothing_to_grade" ? (
              <p style={{ color: "var(--dsa-muted)" }}>Nothing to assess - all students already graded.</p>
            ) : assessProgress.running ? (
              <p>
                Assessing… {assessProgress.done}/{assessProgress.total}
                {assessProgress.current ? ` — ${assessProgress.current}` : ""}
              </p>
            ) : (
              <p style={{ color: "var(--dsa-accent)" }}>
                Done: {assessProgress.done}/{assessProgress.total} graded
                {assessProgress.errors.length > 0 ? `, ${assessProgress.errors.length} failed` : ""}.
              </p>
            )}
            {assessProgress.errors.length > 0 && (
              <ul style={{ color: "var(--dsa-muted)" }}>
                {assessProgress.errors.map((e, i) => (
                  <li key={i}>
                    {e.student}: {e.error}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="rounded-md border px-3 py-1.5 text-sm" style={{ borderColor: "var(--dsa-border)" }}>
            {result ? "Close" : "Cancel"}
          </button>
          {!result && (
            <button
              onClick={submit}
              disabled={busy || !file || !cohortName || !moduleName}
              className="rounded-md px-3 py-1.5 text-sm disabled:opacity-50"
              style={{ background: "var(--dsa-accent)", color: "var(--dsa-bg)" }}
            >
              {busy ? "Importing…" : "Import"}
            </button>
          )}
          {result && !assessProgress && (
            <button
              onClick={startAssessment}
              className="rounded-md px-3 py-1.5 text-sm"
              style={{ background: "var(--dsa-accent)", color: "var(--dsa-bg)" }}
            >
              Start Assessment
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
