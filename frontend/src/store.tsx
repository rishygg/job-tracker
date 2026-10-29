import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, qs, type Dict, type Meta } from "./api";

export interface Filters {
  role_area: string[];
  industry: string[];
  seniority: string[];
  region: string[];
  source: string[];
  status: string[];
  reached: string;
  date_from: string;
  date_to: string;
}

export const EMPTY_FILTERS: Filters = {
  role_area: [], industry: [], seniority: [], region: [], source: [], status: [], reached: "", date_from: "", date_to: "",
};

interface Toast { id: number; text: string; tone: "ok" | "error"; action?: { label: string; run: () => void } }
export type Theme = "system" | "light" | "dark";

function applyTheme(t: Theme) {
  const dark = t === "dark" || (t === "system" && window.matchMedia?.("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", !!dark);
}

interface Ctx {
  meta: Meta | null;
  version: number;
  refresh: () => void;
  filters: Filters;
  setFilters: (f: Filters) => void;
  filterQuery: (extra?: Dict) => string;
  activeFilterCount: number;
  toast: (text: string, tone?: "ok" | "error", action?: { label: string; run: () => void }) => void;
  /** Toast with an Undo button that deletes the stage events the action created. */
  undoable: (text: string, eventIds: number[]) => void;
  openApp: (id: number | null) => void;
  openAppId: number | null;
  openSaved: (id: number | null) => void;
  openSavedId: number | null;
  palette: boolean;
  setPalette: (v: boolean) => void;
  theme: Theme;
  setTheme: (t: Theme) => void;
  quickAdd: boolean;
  setQuickAdd: (v: boolean) => void;
  /** Values to pre-fill the next time Quick add opens (e.g. a posting sent from the browser bookmark). */
  prefill: Dict | null;
  setPrefill: (d: Dict | null) => void;
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
  const [openSavedId, setOpenSavedId] = useState<number | null>(null);
  const [quickAdd, setQuickAdd] = useState(false);
  const [palette, setPalette] = useState(false);
  const [prefill, setPrefill] = useState<Dict | null>(null);
  const [theme, setThemeState] = useState<Theme>(() => { try { return (localStorage.getItem("jt.theme") as Theme) || "system"; } catch { return "system"; } });
  useEffect(() => {
    applyTheme(theme);
    if (theme !== "system") return;
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const h = () => { applyTheme("system"); setVersion((v) => v + 1); };
    mq?.addEventListener?.("change", h);
    return () => mq?.removeEventListener?.("change", h);
  }, [theme]);
  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    try { localStorage.setItem("jt.theme", t); } catch { /* ignore */ }
    applyTheme(t);
    setVersion((v) => v + 1); // charts read colours at render time
  }, []);
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

  const toast = useCallback((text: string, tone: "ok" | "error" = "ok", action?: { label: string; run: () => void }) => {
    const id = ++tid.current;
    setToasts((t) => [...t, { id, text, tone, action }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), action ? 6500 : 3200);
  }, []);
  const undoable = useCallback((text: string, eventIds: number[]) => {
    toast(text, "ok", eventIds.length ? {
      label: "Undo",
      run: () => api.post("/api/events/undo", { event_ids: eventIds }).then(() => { setVersion((v) => v + 1); toast("Undone"); }).catch(() => toast("Couldn't undo", "error")),
    } : undefined);
  }, [toast]);
  const openApp = useCallback((id: number | null) => { setOpenSavedId(null); setOpenAppId(id); }, []);
  const openSaved = useCallback((id: number | null) => { setOpenAppId(null); setOpenSavedId(id); }, []);

  const value: Ctx = {
    meta, version, refresh, filters, setFilters, filterQuery, activeFilterCount, toast, undoable,
    openApp, openAppId, openSaved, openSavedId, quickAdd, setQuickAdd, prefill, setPrefill, palette, setPalette, theme, setTheme,
  };
  return (
    <AppCtx.Provider value={value}>
      {children}
      <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-[80] flex flex-col gap-2 items-center pointer-events-none">
        {toasts.map((t) => (
          <div key={t.id} role="status"
            className={`anim-in pointer-events-auto pl-4 ${t.action ? "pr-1.5" : "pr-4"} py-1.5 min-h-[40px] rounded-lg shadow-pop text-[13px] font-medium flex items-center gap-3 ${t.tone === "error" ? "bg-danger text-white" : "bg-ink text-canvas"}`}>
            {t.text}
            {t.action && (
              <button className="h-7 px-2.5 rounded-md text-[12.5px] font-semibold bg-white/15 hover:bg-white/25 dark:bg-black/10"
                onClick={() => { t.action!.run(); setToasts((x) => x.filter((y) => y.id !== t.id)); }}>{t.action.label}</button>
            )}
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
