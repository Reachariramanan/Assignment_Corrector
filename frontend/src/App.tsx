import { useEffect, useState } from "react";
import { Route, HashRouter as Router, Routes, Link, useLocation } from "react-router-dom";
import ChatPane from "./components/ChatPane";
import ErrorBoundary from "./components/ErrorBoundary";
import UploadModal from "./components/UploadModal";
import { ModuleProvider, useModuleContext } from "./context/ModuleContext";
import Dashboard from "./pages/Dashboard";
import Review from "./pages/Review";
import StudentProfilePage from "./pages/StudentProfile";
import { applyTheme, resolvedTheme, type Theme } from "./theme";

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(resolvedTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  return (
    <button
      onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
      className="w-7 h-7 rounded-full border flex items-center justify-center text-xs"
      style={{ borderColor: "var(--dsa-border)" }}
      title="Toggle dark/light mode"
    >
      {theme === "dark" ? "☀" : "☾"}
    </button>
  );
}

function ModulePicker() {
  const { cohorts, modules, cohortId, moduleId, setCohortId, setModuleId, refresh } = useModuleContext();
  const [uploadOpen, setUploadOpen] = useState(false);

  return (
    <div className="flex items-center gap-2 text-sm">
      {cohorts.length > 0 && (
        <>
          <select
            className="rounded-md border px-2 py-1 bg-transparent"
            style={{ borderColor: "var(--dsa-border)" }}
            value={cohortId ?? ""}
            onChange={(e) => setCohortId(Number(e.target.value))}
          >
            {cohorts.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            className="rounded-md border px-2 py-1 bg-transparent"
            style={{ borderColor: "var(--dsa-border)" }}
            value={moduleId ?? ""}
            onChange={(e) => setModuleId(Number(e.target.value))}
          >
            {modules.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </>
      )}
      <button
        onClick={() => setUploadOpen(true)}
        className="rounded-md px-3 py-1.5 text-sm"
        style={{ background: "var(--dsa-accent)", color: "var(--dsa-bg)" }}
      >
        Upload
      </button>
      {uploadOpen && <UploadModal onClose={() => setUploadOpen(false)} onImported={() => refresh()} />}
    </div>
  );
}

function Shell() {
  const location = useLocation();
  return (
    <div className="h-screen flex flex-col">
      <header
        className="border-b shrink-0"
        style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}
      >
        <div className="px-6 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-baseline gap-3">
            <span className="text-lg font-semibold tracking-tight">Submission Review Interface</span>
            <span className="text-xs" style={{ color: "var(--dsa-muted)" }}>
              By Digital Skills Academy
            </span>
          </Link>
          <div className="flex items-center gap-3">
            <ModulePicker />
            <ThemeToggle />
          </div>
        </div>
      </header>
      <div className="flex-1 flex min-h-0">
        <ChatPane />
        <main className="flex-1 min-w-0 overflow-y-auto px-6 py-8">
          <ErrorBoundary key={location.pathname}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/students/:studentId" element={<Review />} />
              <Route path="/students/:studentId/profile" element={<StudentProfilePage />} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ModuleProvider>
      <Router>
        <Shell />
      </Router>
    </ModuleProvider>
  );
}
