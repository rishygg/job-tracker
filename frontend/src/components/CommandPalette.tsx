import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BarChart3, BookOpen, Bookmark, Briefcase, CornerDownLeft, GraduationCap, Home, Layers, Lightbulb, Map, MessagesSquare,
  Moon, NotebookPen, PenLine, Plus, Search, Settings, Sun, Target, UserRound } from "lucide-react";
import { api, type Dict } from "../api";
import { useApp } from "../store";
import { cls } from "../lib";
import { Monogram, StatusPill } from "./ui";

interface Item { id: string; group: string; label: string; hint?: string; icon?: typeof Home; company?: string; status?: string; keywords?: string; run: () => void }

/** Ctrl+K: jump to any application, saved job, page or action. */
export function CommandPalette() {
  const { palette, setPalette, setQuickAdd, openApp, openSaved, theme, setTheme } = useApp();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const [apps, setApps] = useState<Dict[]>([]);
  const [saved, setSaved] = useState<Dict[]>([]);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette(!palette); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [palette, setPalette]);

  useEffect(() => {
    if (!palette) return;
    setQ(""); setIdx(0);
    api.get("/api/applications").then((d) => setApps(d.items ?? [])).catch(() => {});
    api.get("/api/opportunities").then(setSaved).catch(() => {});
  }, [palette]);

  const close = () => setPalette(false);
  const go = (path: string) => () => { navigate(path); close(); };
  const dark = document.documentElement.classList.contains("dark");

  const base: Item[] = useMemo(() => [
    { id: "a-add", group: "Actions", label: "Add an application", hint: "N", icon: Plus, keywords: "new quick add job", run: () => { close(); setQuickAdd(true); } },
    { id: "a-check", group: "Actions", label: "Check a job against your profile", icon: Target, keywords: "fit paste discover", run: () => { close(); setQuickAdd(true); } },
    { id: "a-log", group: "Actions", label: "Log an interview", icon: NotebookPen, keywords: "journal record", run: go("/career?tab=journal&log=0") },
    { id: "a-practise", group: "Actions", label: "Practise interview questions", icon: GraduationCap, keywords: "mock prepare", run: go("/career?tab=practice") },
    { id: "a-theme", group: "Actions", label: dark ? "Switch to light mode" : "Switch to dark mode", icon: dark ? Sun : Moon, keywords: "theme appearance dark light",
      run: () => { setTheme(dark ? "light" : "dark"); close(); } },
    { id: "p-overview", group: "Pages", label: "Overview", icon: Home, run: go("/") },
    { id: "p-apps", group: "Pages", label: "Applications", icon: Briefcase, keywords: "board table pipeline", run: go("/applications") },
    { id: "p-analytics", group: "Pages", label: "Analytics", icon: BarChart3, keywords: "stats funnel scorecard", run: go("/analytics") },
    { id: "p-map", group: "Pages", label: "Map of your applications", icon: Map, keywords: "where locations cities", run: go("/analytics?tab=map") },
    { id: "p-journal", group: "Pages", label: "Interview journal", icon: MessagesSquare, run: go("/career?tab=journal") },
    { id: "p-skills", group: "Pages", label: "Skills report", icon: Target, keywords: "gaps market", run: go("/career?tab=skills") },
    { id: "p-notes", group: "Pages", label: "Industry notes", icon: Lightbulb, run: go("/career?tab=notes") },
    { id: "p-me", group: "Pages", label: "Me: experience & education", icon: UserRound, keywords: "profile cv entries", run: go("/me") },
    { id: "p-elig", group: "Pages", label: "Me: eligibility & skills", icon: UserRound, keywords: "languages permit degree", run: go("/me?tab=eligibility") },
    { id: "a-rank", group: "Actions", label: "Rank your Inbox with your chat assistant", icon: Layers, keywords: "chatgpt claude ranking", run: go("/applications?rank=1") },
    { id: "p-stories", group: "Pages", label: "Me: Story bank", icon: BookOpen, keywords: "star", run: go("/me?tab=stories") },
    { id: "p-writing", group: "Pages", label: "Me: How you write", icon: PenLine, run: go("/me?tab=writing") },
    { id: "p-settings", group: "Pages", label: "Settings", icon: Settings, keywords: "ollama ai goals import export bookmark", run: go("/settings") },
    // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [dark, theme]);

  const items: Item[] = useMemo(() => {
    const t = q.trim().toLowerCase();
    const score = (s: string) => {
      const x = s.toLowerCase();
      if (!t) return 1;
      if (x.startsWith(t)) return 3;
      if (x.split(/\s+/).some((w) => w.startsWith(t))) return 2;
      return t.split(/\s+/).every((w) => x.includes(w)) ? 1 : 0;
    };
    const rank = (arr: Item[]) => arr.map((i) => ({ i, s: score(`${i.label} ${i.hint ?? ""} ${i.keywords ?? ""} ${i.company ?? ""}`) })).filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s).map((x) => x.i);
    const appItems: Item[] = apps.map((a) => ({ id: `app-${a.id}`, group: "Applications", label: a.position, company: a.company, status: a.status,
      keywords: `${a.company} ${a.location ?? ""}`, run: () => { openApp(a.id); close(); } }));
    const savedItems: Item[] = saved.map((o) => ({ id: `s-${o.id}`, group: "Inbox", label: o.position, company: o.company, status: "Saved",
      keywords: `${o.company} ${o.location ?? ""}`, run: () => { openSaved(o.id); close(); } }));
    if (!t) return [...base.slice(0, 7), ...appItems.slice(0, 5)];
    return [...rank(appItems).slice(0, 8), ...rank(savedItems).slice(0, 5), ...rank(base).slice(0, 8)];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, apps, saved, base]);

  useEffect(() => { setIdx(0); }, [q]);
  useEffect(() => { list.current?.querySelector(`[data-idx="${idx}"]`)?.scrollIntoView({ block: "nearest" }); }, [idx]);

  if (!palette) return null;
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") close();
    else if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(items.length - 1, i + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setIdx((i) => Math.max(0, i - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); items[idx]?.run(); }
  };
  let lastGroup = "";
  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[12vh] px-4 bg-ink/30 backdrop-blur-[2px]" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div role="dialog" aria-modal="true" aria-label="Search and commands" className="anim-in w-full max-w-[600px] card shadow-pop overflow-hidden" onKeyDown={onKey}>
        <div className="flex items-center gap-2.5 px-4 h-13 border-b border-line">
          <Search size={17} className="text-ink-faint shrink-0" />
          <input ref={input} autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search applications, Inbox jobs, pages or actions…"
            className="flex-1 h-12 bg-transparent outline-none text-[14.5px] placeholder:text-ink-faint" role="combobox" aria-expanded="true" aria-controls="palette-list"
            aria-activedescendant={items[idx] ? `pal-${items[idx].id}` : undefined} />
          <kbd className="text-[10.5px] font-mono px-1.5 py-0.5 rounded border border-line text-ink-muted">Esc</kbd>
        </div>
        <ul ref={list} id="palette-list" role="listbox" className="max-h-[56vh] overflow-y-auto scroll-thin py-1.5">
          {!items.length && <li className="px-4 py-6 text-center text-[13px] text-ink-muted">Nothing matches “{q}”.</li>}
          {items.map((it, i) => {
            const header = it.group !== lastGroup ? it.group : null;
            lastGroup = it.group;
            const Icon = it.icon;
            return (
              <li key={it.id} role="presentation">
                {header && <div className="px-4 pt-2 pb-1 eyebrow">{header}</div>}
                <button id={`pal-${it.id}`} role="option" aria-selected={i === idx} data-idx={i} onMouseMove={() => setIdx(i)} onClick={it.run}
                  className={cls("w-full flex items-center gap-3 px-4 py-2 text-left text-[13.5px]", i === idx ? "bg-brand-soft text-ink" : "text-ink-soft")}>
                  {it.company ? <Monogram name={it.company} size={24} /> : Icon ? <span className="w-6 h-6 rounded-md bg-canvas border border-line flex items-center justify-center shrink-0"><Icon size={13} /></span> : null}
                  <span className="flex-1 min-w-0 truncate">{it.label}{it.company && <span className="text-ink-muted"> · {it.company}</span>}</span>
                  {it.status && (it.status === "Saved" ? <span className="chip h-5 text-[10.5px]"><Bookmark size={10} />Saved</span> : <StatusPill stage={it.status} size="sm" />)}
                  {it.hint && <kbd className="text-[10.5px] font-mono px-1.5 py-0.5 rounded border border-line text-ink-muted">{it.hint}</kbd>}
                  {i === idx && <CornerDownLeft size={13} className="text-ink-faint" />}
                </button>
              </li>
            );
          })}
        </ul>
        <div className="px-4 py-2 border-t border-line text-[11px] text-ink-muted flex gap-4">
          <span><kbd className="font-mono">↑↓</kbd> move</span><span><kbd className="font-mono">Enter</kbd> open</span><span><kbd className="font-mono">Ctrl K</kbd> toggle</span>
        </div>
      </div>
    </div>
  );
}
