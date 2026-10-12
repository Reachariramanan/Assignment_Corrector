import { useEffect, useState } from "react";
import { api, type Cohort, type ModuleSummary } from "../api";
import { useModuleContext } from "../context/ModuleContext";
import ConfirmDialog from "./ConfirmDialog";

type PendingDelete = { kind: "cohort"; id: number; name: string } | { kind: "module"; id: number; name: string };

export default function CourseManager() {
  const { refresh } = useModuleContext();
  const [cohorts, setCohorts] = useState<Cohort[]>([]);
  const [modulesByCohort, setModulesByCohort] = useState<Record<number, ModuleSummary[]>>({});
  const [editing, setEditing] = useState<{ kind: "cohort" | "module"; id: number; value: string } | null>(null);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const cs = await api.cohorts();
    setCohorts(cs);
    const entries = await Promise.all(cs.map(async (c) => [c.id, await api.modules(c.id)] as const));
    setModulesByCohort(Object.fromEntries(entries));
  }

  useEffect(() => {
    load();
  }, []);

  async function saveEdit() {
    if (!editing) return;
    setBusy(true);
    try {
      if (editing.kind === "cohort") await api.renameCohort(editing.id, editing.value);
      else await api.renameModule(editing.id, editing.value);
      setEditing(null);
      await load();
      refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setBusy(true);
    try {
      if (pendingDelete.kind === "cohort") await api.deleteCohort(pendingDelete.id);
      else await api.deleteModule(pendingDelete.id);
      setPendingDelete(null);
      await load();
      refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border overflow-hidden" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}>
      <h3 className="text-sm font-medium px-4 pt-4 pb-2">Courses &amp; Modules</h3>
      <div className="divide-y" style={{ borderColor: "var(--dsa-border)" }}>
        {cohorts.map((c) => (
          <div key={c.id} className="px-4 py-3" style={{ borderColor: "var(--dsa-border)" }}>
            <div className="flex items-center justify-between">
              {editing?.kind === "cohort" && editing.id === c.id ? (
                <div className="flex items-center gap-2 flex-1">
                  <input
                    autoFocus
                    className="flex-1 rounded-md border px-2 py-1 text-sm bg-transparent"
                    style={{ borderColor: "var(--dsa-border)" }}
                    value={editing.value}
                    onChange={(e) => setEditing({ ...editing, value: e.target.value })}
                    onKeyDown={(e) => e.key === "Enter" && saveEdit()}
                  />
                  <button onClick={saveEdit} disabled={busy} className="text-xs" style={{ color: "var(--dsa-green)" }}>
                    Save
                  </button>
                  <button onClick={() => setEditing(null)} className="text-xs" style={{ color: "var(--dsa-muted)" }}>
                    Cancel
                  </button>
                </div>
              ) : (
                <>
                  <span className="font-medium text-sm">{c.name}</span>
                  <div className="flex gap-3 text-xs" style={{ color: "var(--dsa-muted)" }}>
                    <button onClick={() => setEditing({ kind: "cohort", id: c.id, value: c.name })} className="hover:underline">
                      Rename
                    </button>
                    <button
                      onClick={() => setPendingDelete({ kind: "cohort", id: c.id, name: c.name })}
                      className="hover:underline"
                      style={{ color: "#e11d48" }}
                    >
                      Delete
                    </button>
                  </div>
                </>
              )}
            </div>
            <div className="mt-2 pl-3 space-y-1.5">
              {(modulesByCohort[c.id] ?? []).map((m) => (
                <div key={m.id} className="flex items-center justify-between text-sm">
                  {editing?.kind === "module" && editing.id === m.id ? (
                    <div className="flex items-center gap-2 flex-1">
                      <input
                        autoFocus
                        className="flex-1 rounded-md border px-2 py-1 text-xs bg-transparent"
                        style={{ borderColor: "var(--dsa-border)" }}
                        value={editing.value}
                        onChange={(e) => setEditing({ ...editing, value: e.target.value })}
                        onKeyDown={(e) => e.key === "Enter" && saveEdit()}
                      />
                      <button onClick={saveEdit} disabled={busy} className="text-xs" style={{ color: "var(--dsa-green)" }}>
                        Save
                      </button>
                      <button onClick={() => setEditing(null)} className="text-xs" style={{ color: "var(--dsa-muted)" }}>
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <>
                      <span style={{ color: "var(--dsa-muted)" }}>· {m.name}</span>
                      <div className="flex gap-3 text-xs" style={{ color: "var(--dsa-faint)" }}>
                        <button onClick={() => setEditing({ kind: "module", id: m.id, value: m.name })} className="hover:underline">
                          Rename
                        </button>
                        <button
                          onClick={() => setPendingDelete({ kind: "module", id: m.id, name: m.name })}
                          className="hover:underline"
                          style={{ color: "#e11d48" }}
                        >
                          Delete
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
              {(modulesByCohort[c.id] ?? []).length === 0 && (
                <div className="text-xs" style={{ color: "var(--dsa-faint)" }}>
                  No modules yet
                </div>
              )}
            </div>
          </div>
        ))}
        {cohorts.length === 0 && (
          <div className="px-4 py-6 text-sm text-center" style={{ color: "var(--dsa-muted)" }}>
            No courses yet - use Upload to create one.
          </div>
        )}
      </div>

      {pendingDelete && (
        <ConfirmDialog
          title={`Delete ${pendingDelete.kind === "cohort" ? "course" : "module"} "${pendingDelete.name}"?`}
          message={
            pendingDelete.kind === "cohort"
              ? "This permanently deletes the course and every module, student, submission, review, and report in it. This cannot be undone."
              : "This permanently deletes this module and every submission, review, and report for it. Students with no other modules in this course will also be removed. This cannot be undone."
          }
          confirmLabel="Delete"
          danger
          busy={busy}
          onConfirm={confirmDelete}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </div>
  );
}
