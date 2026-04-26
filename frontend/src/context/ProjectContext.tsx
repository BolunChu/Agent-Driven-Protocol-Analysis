import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

interface ProjectContextValue {
  projectId: number | null;
  setProjectId: (projectId: number | null) => void;
}

const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projectId, setProjectIdState] = useState<number | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem("protoanalyzer.projectId");
    if (!stored) return;
    const parsed = Number(stored);
    if (!Number.isNaN(parsed) && parsed > 0) {
      setProjectIdState(parsed);
    }
  }, []);

  const setProjectId = (nextProjectId: number | null) => {
    setProjectIdState(nextProjectId);
    if (nextProjectId == null) {
      window.localStorage.removeItem("protoanalyzer.projectId");
      return;
    }
    window.localStorage.setItem("protoanalyzer.projectId", String(nextProjectId));
  };

  const value = useMemo(() => ({ projectId, setProjectId }), [projectId]);

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProjectContext() {
  const value = useContext(ProjectContext);
  if (!value) {
    throw new Error("useProjectContext must be used within ProjectProvider");
  }
  return value;
}
