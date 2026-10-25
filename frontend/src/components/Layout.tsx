import { useEffect, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { BarChart3, Briefcase, Compass, GraduationCap, Home, Plus, Settings } from "lucide-react";
import { useApi, useApp } from "../store";
import { cls } from "../lib";

const NAV = [
  { to: "/", label: "Overview", icon: Home, end: true },
  { to: "/applications", label: "Applications", icon: Briefcase },
  { to: "/discover", label: "Discover", icon: Compass, soon: true },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/career", label: "Career development", icon: GraduationCap, soon: true },
];

export function Layout({ children }: { children: ReactNode }) {
  const { setQuickAdd, meta } = useApp();
  const { data: ov } = useApi<{ priorities: unknown[] }>("/api/overview");
  const loc = useLocation();

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable) return;
      if (e.key === "n" && !e.metaKey && !e.ctrlKey) { e.preventDefault(); setQuickAdd(true); }
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
      <aside className="lg:w-[244px] lg:shrink-0 lg:h-screen lg:sticky lg:top-0 bg-white border-b lg:border-b-0 lg:border-r border-line flex lg:flex-col">
        <div className="flex items-center gap-2.5 px-5 h-16 shrink-0">
          <div className="w-8 h-8 rounded-lg bg-brand flex items-center justify-center">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="white" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M5 13l4 4 10-10" /></svg>
          </div>
          <div className="leading-tight">
            <div className="font-semibold text-[15px] tracking-[-0.01em]">Job Tracker</div>
            <div className="text-[11px] text-ink-muted num">{meta ? `${meta.count} applications` : " "}</div>
          </div>
        </div>
        <div className="px-3 pb-3 hidden lg:block">
          <button className="btn-primary w-full justify-between" onClick={() => setQuickAdd(true)}>
            <span className="inline-flex items-center gap-1.5"><Plus size={16} /> Add application</span>
            <kbd className="text-[10.5px] font-mono px-1.5 py-0.5 rounded bg-white/15">N</kbd>
          </button>
        </div>
        <nav className="flex lg:flex-col gap-0.5 px-3 overflow-x-auto lg:overflow-visible items-center lg:items-stretch">
          {NAV.map(link)}
        </nav>
        <div className="lg:mt-auto px-3 lg:pb-4 flex lg:flex-col items-center lg:items-stretch">
          {link({ to: "/settings", label: "Settings", icon: Settings })}
        </div>
      </aside>
      <main className="flex-1 min-w-0" key={loc.pathname}>
        <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8 py-6 lg:py-8">{children}</div>
      </main>
      <button onClick={() => setQuickAdd(true)} aria-label="Add application"
        className="lg:hidden fixed bottom-5 right-5 z-30 w-12 h-12 rounded-full bg-brand text-white shadow-pop flex items-center justify-center">
        <Plus size={22} />
      </button>
    </div>
  );
}
