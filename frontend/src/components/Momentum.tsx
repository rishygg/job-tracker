import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, BookOpen, Flag, Flame, GraduationCap, Lock, Mail, MessagesSquare, Mic, NotebookPen, Plus, Repeat, Search, Send, Star, Trophy, Zap } from "lucide-react";
import { type Dict } from "../api";
import { useApi, useApp } from "../store";
import { cls, fmtDate, relDays, tok } from "../lib";
import { Modal } from "./ui";

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? "Working late" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export function GoalRing({ value, goal, size = 112 }: { value: number; goal: number; size?: number }) {
  const r = size / 2 - 8;
  const c = 2 * Math.PI * r;
  const p = Math.min(1, value / Math.max(1, goal));
  const done = value >= goal;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={`${value} of ${goal} applications this week`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={tok("line")} strokeWidth={9} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={done ? tok("ok-bright") : tok("brand")} strokeWidth={9} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - p)} style={{ transition: "stroke-dashoffset .8s cubic-bezier(.2,.8,.2,1)" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="num text-[24px] font-semibold leading-none tracking-tight">{value}<span className="text-ink-faint text-[15px]">/{goal}</span></div>
        <div className="text-[11px] text-ink-muted mt-1">{done ? "goal reached" : "this week"}</div>
      </div>
    </div>
  );
}

/** The top of the Overview: greeting, quick actions, this week's goal ring and streak. */
export function Hero({ data, mom, onReminder }: { data: Dict; mom: Dict | null; onReminder: () => void }) {
  const { setPalette, setQuickAdd } = useApp();
  const navigate = useNavigate();
  const goal = mom?.goal ?? data.weekly.goal;
  const thisWeek = mom?.this_week ?? data.totals.this_week;
  const pri = data.priorities.length;
  const next = data.upcoming_interviews[0];
  const status = [
    pri ? `${pri} thing${pri > 1 ? "s" : ""} to do today` : "Nothing urgent today",
    next ? `${next.stage.toLowerCase()} with ${next.company} ${relDays(next.date)}` : null,
  ].filter(Boolean).join(" · ");
  const streak = mom?.streak_weeks ? `${mom.streak_weeks}-week streak` : mom?.streak_days ? `${mom.streak_days}-day streak` : null;
  return (
    <section className="card relative overflow-hidden mb-6">
      <div aria-hidden="true" className="pointer-events-none absolute -top-24 -right-16 w-[420px] h-[260px] rounded-full opacity-70 blur-3xl"
        style={{ background: "radial-gradient(closest-side, rgb(var(--brand) / .18), transparent)" }} />
      <div className="relative grid lg:grid-cols-[1fr_auto] gap-6 p-5 lg:p-6 items-center">
        <div className="min-w-0">
          <p className="text-ink-muted text-[13px]">{new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</p>
          <h1 className="text-[26px] font-semibold tracking-[-0.015em] leading-tight mt-0.5">{greeting()}{data.name ? `, ${data.name}` : ""}</h1>
          <p className="text-[13.5px] text-ink-soft mt-1.5">{status}.</p>
          <div className="flex flex-wrap gap-2 mt-4">
            <button className="btn-primary btn-sm" onClick={() => setQuickAdd(true)}><Plus size={13} /> Add a job <kbd className="text-[10px] font-mono ml-1 opacity-70">N</kbd></button>
            <button className="btn-secondary btn-sm" onClick={() => navigate("/applications?rank=1")}><MessagesSquare size={13} /> Rank my Inbox with chat</button>
            <button className="btn-secondary btn-sm" onClick={onReminder}><Bell size={13} /> Reminder</button>
            <button className="btn-ghost btn-sm" onClick={() => setPalette(true)}><Search size={13} /> Search <kbd className="text-[10px] font-mono ml-1 opacity-70">Ctrl K</kbd></button>
          </div>
        </div>
        <div className="flex items-center gap-4 lg:pl-6 lg:border-l border-line">
          <GoalRing value={thisWeek} goal={goal} />
          <div className="space-y-2 min-w-[118px]">
            {streak ? <div className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full bg-warn-soft text-warn text-[12.5px] font-semibold"><Flame size={14} />{streak}</div>
              : <div className="text-[12px] text-ink-muted">Hit your goal to start a streak</div>}
            <div className="text-[12px] text-ink-muted leading-snug">{thisWeek >= goal ? "Weekly goal done. Anything more is a bonus." : `${goal - thisWeek} more to reach your weekly goal.`}</div>
            {mom?.best_week ? <div className="text-[11.5px] text-ink-faint num">Best week: {mom.best_week}</div> : null}
          </div>
        </div>
      </div>
    </section>
  );
}

const LEVELS = [0, 1, 3, 5];

/** A GitHub-style calendar of everything you did for your search. */
export function MomentumCard({ mom }: { mom: Dict }) {
  const weeks = useMemo(() => {
    const out: Dict[][] = [];
    for (let i = 0; i < mom.cells.length; i += 7) out.push(mom.cells.slice(i, i + 7));
    return out;
  }, [mom]);
  const shade = (n: number) => n === 0 ? "rgb(var(--line) / .7)" : `rgb(var(--brand) / ${[0.3, 0.5, 0.75, 1][LEVELS.filter((l) => n >= l).length - 1]})`;
  const months = weeks.map((w, i) => {
    const d = new Date(w[0].date + "T00:00:00");
    const prev = i ? new Date(weeks[i - 1][0].date + "T00:00:00") : null;
    return !prev || prev.getMonth() !== d.getMonth() ? d.toLocaleDateString("en-GB", { month: "short" }) : "";
  });
  const describe = (c: Dict) => {
    const parts = [["applied", "applied"], ["updates", "updates"], ["journal", "interviews logged"], ["practice", "practice"], ["stories", "stories"]]
      .filter(([k]) => c[k]).map(([k, l]) => `${c[k]} ${l}`);
    return `${fmtDate(c.date)}: ${parts.length ? parts.join(", ") : "nothing logged"}`;
  };
  return (
    <section className="card p-5">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="text-[15px] font-semibold">Momentum</h2>
        <span className="text-[11.5px] text-ink-muted num">{mom.active_days} active days · last 6 months</span>
      </div>
      <div className="overflow-x-auto scroll-thin -mx-1 px-1">
        <div className="inline-grid gap-[2px]" style={{ gridTemplateColumns: `repeat(${weeks.length}, 10px)` }}>
          {months.map((m, i) => <div key={`m${i}`} className="text-[9.5px] text-ink-faint h-3 leading-3 whitespace-nowrap overflow-visible">{m}</div>)}
          {Array.from({ length: 7 }).map((_, day) => weeks.map((w, wi) => {
            const c = w[day];
            return c ? <div key={`${wi}-${day}`} title={describe(c)} className="w-[10px] h-[10px] rounded-[2.5px]" style={{ background: shade(c.total) }} />
              : <div key={`${wi}-${day}`} />;
          }))}
        </div>
      </div>
      <div className="flex items-center justify-between mt-3 text-[11px] text-ink-muted">
        <span className="inline-flex items-center gap-1">Less {[0, 1, 3, 5, 8].map((n) => <span key={n} className="w-[10px] h-[10px] rounded-[3px] inline-block" style={{ background: shade(n) }} />)} More</span>
        {mom.streak_days > 1 && <span className="inline-flex items-center gap-1 text-warn font-medium"><Flame size={12} />{mom.streak_days} days in a row</span>}
      </div>
    </section>
  );
}

const ICONS: Record<string, typeof Send> = { send: Send, mail: Mail, mic: Mic, flag: Flag, trophy: Trophy, flame: Flame, zap: Zap,
  notebook: NotebookPen, book: BookOpen, repeat: Repeat, graduation: GraduationCap, star: Star };

export function MilestonesCard({ onOpen }: { onOpen: () => void }) {
  const { data } = useApi<Dict>("/api/milestones");
  if (!data) return null;
  const items: Dict[] = data.items;
  const got = items.filter((m) => m.achieved);
  const next = items.filter((m) => !m.achieved).sort((a, b) => b.progress[0] / b.progress[1] - a.progress[0] / a.progress[1])[0];
  return (
    <section className="card p-5">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="text-[15px] font-semibold">Milestones</h2>
        <button className="text-[12px] text-brand font-medium hover:underline" onClick={onOpen}>{got.length} of {items.length}</button>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((m) => {
          const Icon = ICONS[m.icon] ?? Star;
          return (
            <button key={m.id} onClick={onOpen} title={`${m.title}: ${m.detail}${m.achieved ? "" : ` (${m.progress[0]}/${m.progress[1]})`}`}
              className={cls("w-8 h-8 rounded-full flex items-center justify-center transition hover:scale-105",
                m.achieved ? "bg-warn-soft text-warn ring-1 ring-warn-line" : "bg-canvas text-ink-faint ring-1 ring-line")}>
              <Icon size={14} />
            </button>
          );
        })}
      </div>
      {next && (
        <div className="mt-3 text-[12px]">
          <div className="flex justify-between text-ink-soft"><span>Next: <b className="font-medium text-ink">{next.title}</b></span><span className="num text-ink-muted">{next.progress[0]}/{next.progress[1]}</span></div>
          <div className="h-1.5 rounded-full bg-canvas mt-1 overflow-hidden"><div className="h-full rounded-full bg-amber" style={{ width: `${(next.progress[0] / next.progress[1]) * 100}%` }} /></div>
        </div>
      )}
    </section>
  );
}

export function MilestonesModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data } = useApi<Dict>(open ? "/api/milestones" : null, [open]);
  return (
    <Modal open={open} onClose={onClose} title="Milestones" width="max-w-2xl">
      <p className="text-[12.5px] text-ink-muted mb-4">Small wins along the way. A job search is long; these are worth noticing.</p>
      <ul className="grid sm:grid-cols-2 gap-2.5">
        {(data?.items ?? []).map((m: Dict) => {
          const Icon = ICONS[m.icon] ?? Star;
          return (
            <li key={m.id} className={cls("rounded-xl border p-3 flex gap-3", m.achieved ? "border-warn-line bg-warn-soft/50" : "border-line")}>
              <span className={cls("w-9 h-9 rounded-full flex items-center justify-center shrink-0", m.achieved ? "bg-warn-soft text-warn ring-1 ring-warn-line" : "bg-canvas text-ink-faint ring-1 ring-line")}>
                {m.achieved ? <Icon size={16} /> : <Lock size={14} />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[13.5px] font-semibold">{m.title}</div>
                <div className="text-[12px] text-ink-muted">{m.detail}</div>
                {m.achieved ? (m.date && <div className="text-[11px] text-warn mt-0.5 num">{fmtDate(m.date)}</div>)
                  : <div className="h-1 rounded-full bg-canvas mt-1.5 overflow-hidden"><div className="h-full bg-amber rounded-full" style={{ width: `${(m.progress[0] / m.progress[1]) * 100}%` }} /></div>}
              </div>
            </li>
          );
        })}
      </ul>
    </Modal>
  );
}
