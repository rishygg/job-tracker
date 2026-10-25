import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, qs, type Dict, type Meta } from "./api";

export interface Filters {
  role_area: string[];
  industry: string[];
  seniority: string[];
  region: string[];
  source: string[];
  date_from: string;
  date_to: string;
}

export const EMPTY_FILTERS: Filters = {
  role_area: [], industry: [], seniority: [], region: [], source: [], date_from: "", date_to: "",
};

interface Toast { id: number; text: string; tone: "ok" | "error" }

interface Ctx {
  meta: Meta | null;
  version: number;
  refresh: () => void;
  filters: Filters;
  setFilters: (f: Filters) => void;
  filterQuery: (extra?: Dict) => string;
  activeFilterCount: number;
  toast: (text: string, tone?: "ok" | "error") => void;
  openApp: (id: number | null) => void;
  openAppId: number | null;
  quickAdd: boolean;
  setQuickAdd: (v: boolean) => void;
}

const AppCtx = createContext<Ctx>(null as unknown as Ctx);

function loadFilters(): Filters {
  try {
    const raw = localStorage.getItem("jt.filters");
    if (raw) return { ...EMPTY_FILTERS, ...JSON.parse(raw) };
  } catch { /* storage unavailable */ }
  return EMPTY_FILTERS;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [version, setVersion] = useState(0);
  const [filters, setFiltersState] = useState<Filters>(loadFilters);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [openAppId, setOpenAppId] = useState<number | null>(null);
  const [quickAdd, setQuickAdd] = useState(false);
  const tid = useRef(0);

  const refresh = useCallback(() => setVersion((v) => v + 1), []);
  useEffect(() => { api.get<Meta>("/api/meta").then(setMeta).catch(() => {}); }, [version]);

  const setFilters = useCallback((f: Filters) => {
    setFiltersState(f);
    try { localStorage.setItem("jt.filters", JSON.stringify(f)); } catch { /* ignore */ }
  }, []);

  const filterQuery = useCallback((extra: Dict = {}) => qs({ ...filters, ...extra }), [filters]);
  const activeFilterCount = useMemo(
    () => (Object.entries(filters) as [string, string | string[]][]).filter(([, v]) => (Array.isArray(v) ? v.length : v)).length,
    [filters],
  );

  const toast = useCallback((text: string, tone: "ok" | "error" = "ok") => {
    const id = ++tid.current;
    setToasts((t) => [...t, { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);

  const value: Ctx = {
    meta, version, refresh, filters, setFilters, filterQuery, activeFilterCount, toast,
    openApp: setOpenAppId, openAppId, quickAdd, setQuickAdd,
  };
  return (
    <AppCtx.Provider value={value}>
      {children}
      <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-[80] flex flex-col gap-2 items-center pointer-events-none">
        {toasts.map((t) => (
          <div key={t.id} role="status"
            className={`anim-in pointer-events-auto px-4 py-2.5 rounded-lg shadow-pop text-[13px] font-medium ${t.tone === "error" ? "bg-danger text-white" : "bg-ink text-white"}`}>
            {t.text}
          </div>
        ))}
      </div>
    </AppCtx.Provider>
  );
}

export const useApp = () => useContext(AppCtx);

/** Fetch JSON and refetch whenever the app's data version or `deps` change. */
export function useApi<T = any>(url: string | null, deps: unknown[] = []) {
  const { version } = useApp();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!url) return;
    let live = true;
    setLoading(true);
    api.get<T>(url)
      .then((d) => { if (live) { setData(d); setError(null); } })
      .catch((e) => { if (live) setError(e.message); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, version, ...deps]);
  return { data, error, loading, setData };
}
