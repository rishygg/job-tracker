import { useEffect, useRef, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { BarChart3, Briefcase, GraduationCap, Home, Monitor, Moon, Plus, Search, Settings, Sun, UserRound } from "lucide-react";
import { api } from "../api";
import { useApi, useApp } from "../store";
import { cls } from "../lib";
import { AiActivity } from "./AiJob";
import { CommandPalette } from "./CommandPalette";
import { celebrate } from "./Confetti";

const NAV = [
  { to: "/", label: "Overview", icon: Home, end: true },
  { to: "/applications", label: "Applications", icon: Briefcase },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/career", label: "Career development", icon: GraduationCap },
];

/** Opens Quick add with a posting sent from the browser bookmark (?inbox=…). */
function InboxHandler() {
  const [params, setParams] = useSearchParams();
  const { setPrefill, setQuickAdd, toast } = useApp();
  useEffect(() => {
    const id = params.get("inbox");
    if (!id) return;
    api.get(`/api/inbox/${id}`).then((x) => {
      setPrefill({ position: x.guess?.position ?? "", company: x.guess?.company ?? "", url: x.url ?? "", job_description: x.text ?? "" });
      setQuickAdd(true);
    }).catch((e) => toast(e.message, "error"));
    const p = new URLSearchParams(params); p.delete("inbox"); setParams(p, { replace: true });
  }, [params]);
  return null;
}

/** Celebrates milestones you've just reached. */
function MilestoneWatcher() {
  const { version, toast } = useApp();
  const navigate = useNavigate();
  const last = useRef(0);
  useEffect(() => {
    const t = setTimeout(() => {
      if (Date.now() - last.current < 1500) return;
      last.current = Date.now();
      api.get("/api/milestones").then((m) => {
        if (!m.new?.length) return;
        celebrate(m.new.some((x: { id: string }) => x.id === "offer") ? 1.6 : 0.8);
        const first = m.new[0];
        toast(`Milestone: ${first.title}${m.new.length > 1 ? ` (+${m.new.length - 1} more)` : ""}`, "ok", { label: "See all", run: () => navigate("/?milestones=1") });
        api.post("/api/milestones/seen", { ids: m.new.map((x: { id: string }) => x.id) }).catch(() => {});
      }).catch(() => {});
    }, 900);
    return () => clearTimeout(t);
  }, [version]);
  return null;
}

function ThemeButton() {
  const { theme, setTheme } = useApp();
  const next = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";
  const Icon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;
  const label = theme === "light" ? "Light" : theme === "dark" ? "Dark" : "Auto";
  return (
    <button onClick={() => setTheme(next)} title={`Theme: ${label}. Click for ${next}.`} aria-label={`Theme: ${label}`}
      className="h-9 px-2.5 rounded-lg text-ink-soft hover:bg-canvas hover:text-ink inline-flex items-center gap-2 text-[13px] font-medium">
      <Icon size={16} /><span className="hidden lg:inline">{label}</span>
    </button>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { setQuickAdd, meta, setPalette } = useApp();
  const { data: ov } = useApi<{ priorities: unknown[] }>("/api/overview");
  const loc = useLocation();

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable) return;
      if (e.key === "n" && !e.metaKey && !e.ctrlKey && !e.altKey && !document.querySelector('[role="dialog"]')) { e.preventDefault(); setQuickAdd(true); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [setQuickAdd]);

  const pri = ov?.priorities?.length ?? 0;
  const link = (n: (typeof NAV)[number] | { to: string; label: string; icon: typeof Home; end?: boolean; soon?: boolean }) => (
    <NavLink key={n.to} to={n.to} end={"end" in n ? n.end : false}
      className={({ isActive }) => cls(
        "group flex items-center gap-2.5 h-9 px-2.5 rounded-lg text-[13.5px] font-medium transition-colors",
        isActive ? "bg-brand-soft text-brand-strong" : "text-ink-soft hover:bg-canvas hover:text-ink")}>
      <n.icon size={17} strokeWidth={2} className="shrink-0" />
      <span className="truncate">{n.label}</span>
      {n.to === "/" && pri > 0 && (
        <span className="ml-auto num text-[11px] min-w-[20px] h-5 px-1.5 rounded-full bg-alert text-white inline-flex items-center justify-center">{pri}</span>
      )}
      {"soon" in n && n.soon && <span className="ml-auto text-[10px] font-semibold uppercase tracking-wide text-ink-faint">Soon</span>}
    </NavLink>
  );

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      <aside className="lg:w-[244px] lg:shrink-0 lg:h-screen lg:sticky lg:top-0 bg-surface border-b lg:border-b-0 lg:border-r border-line flex lg:flex-col overflow-x-auto lg:overflow-visible scroll-thin">
        <div className="flex items-center gap-2.5 px-4 lg:px-5 h-16 shrink-0">
          <div className="w-8 h-8 rounded-lg bg-brand flex items-center justify-center">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="white" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M5 13l4 4 10-10" /></svg>
          </div>
          <div className="leading-tight">
            <div className="font-semibold text-[15px] tracking-[-0.01em]">Job Tracker</div>
            <div className="text-[11px] text-ink-muted num">{meta ? `${meta.count} applications` : " "}</div>
          </div>
        </div>
        <div className="px-3 pb-3 hidden lg:block space-y-2">
          <button className="btn-primary w-full justify-between" onClick={() => setQuickAdd(true)}>
            <span className="inline-flex items-center gap-1.5"><Plus size={16} /> Add application</span>
            <kbd className="text-[10.5px] font-mono px-1.5 py-0.5 rounded bg-white/15">N</kbd>
          </button>
          <button className="w-full h-9 px-3 rounded-lg border border-line bg-canvas text-ink-muted hover:text-ink hover:border-line-strong text-[13px] flex items-center justify-between transition"
            onClick={() => setPalette(true)}>
            <span className="inline-flex items-center gap-2"><Search size={14} /> Search…</span>
            <kbd className="text-[10.5px] font-mono px-1.5 py-0.5 rounded border border-line">Ctrl K</kbd>
          </button>
        </div>
        <nav className="flex lg:flex-col gap-0.5 px-3 shrink-0 items-center lg:items-stretch">
          {NAV.map(link)}
        </nav>
        <div className="lg:mt-auto" />
        <AiActivity />
        <div className="px-3 lg:pb-4 flex lg:flex-col items-center lg:items-stretch gap-0.5 shrink-0">
          {link({ to: "/me", label: "Me", icon: UserRound })}
          {link({ to: "/settings", label: "Settings", icon: Settings })}
          <div className="flex items-center gap-1 lg:mt-1 lg:pt-2 lg:border-t border-line">
            <ThemeButton />
            <button className="lg:hidden h-9 px-2.5 rounded-lg text-ink-soft hover:bg-canvas" aria-label="Search" onClick={() => setPalette(true)}><Search size={16} /></button>
          </div>
        </div>
      </aside>
      <main className="flex-1 min-w-0" key={loc.pathname}>
        <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8 py-6 lg:py-8">{children}</div>
      </main>
      <CommandPalette />
      <InboxHandler />
      <MilestoneWatcher />
      <button onClick={() => setQuickAdd(true)} aria-label="Add application"
        className="lg:hidden fixed bottom-5 right-5 z-30 w-12 h-12 rounded-full bg-brand text-white shadow-pop flex items-center justify-center">
        <Plus size={22} />
      </button>
    </div>
  );
}
