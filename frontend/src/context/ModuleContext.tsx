import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type Cohort, type ModuleSummary } from "../api";

interface ModuleContextValue {
  cohorts: Cohort[];
  modules: ModuleSummary[];
  cohortId: number | null;
  moduleId: number | null;
  setCohortId: (id: number) => void;
  setModuleId: (id: number) => void;
  loading: boolean;
  refresh: () => void;
}

const ModuleContext = createContext<ModuleContextValue | null>(null);

const LS_COHORT = "dsa.cohortId";
const LS_MODULE = "dsa.moduleId";

export function ModuleProvider({ children }: { children: ReactNode }) {
  const [cohorts, setCohorts] = useState<Cohort[]>([]);
  const [modules, setModules] = useState<ModuleSummary[]>([]);
  const [cohortId, setCohortIdState] = useState<number | null>(() => {
    const v = localStorage.getItem(LS_COHORT);
    return v ? Number(v) : null;
  });
  const [moduleId, setModuleIdState] = useState<number | null>(() => {
    const v = localStorage.getItem(LS_MODULE);
    return v ? Number(v) : null;
  });
  const [loading, setLoading] = useState(true);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    api.cohorts().then((cs) => {
      setCohorts(cs);
      if (cs.length && (cohortId === null || !cs.some((c) => c.id === cohortId))) {
        setCohortIdState(cs[0].id);
      } else if (cs.length === 0) {
        setCohortIdState(null);
        setModuleIdState(null);
      }
    });
  }, [refreshTick]);

  useEffect(() => {
    if (cohortId === null) return;
    localStorage.setItem(LS_COHORT, String(cohortId));
    api.modules(cohortId).then((ms) => {
      setModules(ms);
      if (ms.length && (moduleId === null || !ms.some((m) => m.id === moduleId))) {
        setModuleIdState(ms[ms.length - 1].id);
      }
      setLoading(false);
    });
  }, [cohortId, refreshTick]);

  useEffect(() => {
    if (moduleId !== null) localStorage.setItem(LS_MODULE, String(moduleId));
  }, [moduleId]);

  return (
    <ModuleContext.Provider
      value={{
        cohorts,
        modules,
        cohortId,
        moduleId,
        setCohortId: setCohortIdState,
        setModuleId: setModuleIdState,
        loading,
        refresh: () => setRefreshTick((t) => t + 1),
      }}
    >
      {children}
    </ModuleContext.Provider>
  );
}

export function useModuleContext() {
  const ctx = useContext(ModuleContext);
  if (!ctx) throw new Error("useModuleContext must be used within ModuleProvider");
  return ctx;
}
