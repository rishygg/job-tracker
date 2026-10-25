import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Bell, CalendarClock, CheckCircle2, Clock, Ghost, Lightbulb, Mail, MessageSquareHeart, Plus, TrendingUp } from "lucide-react";
import { api, type Dict } from "../api";
import { useApi, useApp } from "../store";
import { cls, fmtDate, pct, relDays, STAGE_STYLE } from "../lib";
import { EmptyState, Field, Modal, Select, Skeleton, StatusPill } from "../components/ui";

const KIND: Record<string, { icon: typeof Bell; color: string; label: string }> = {
  interview: { icon: CalendarClock, color: "#d97f06", label: "Interview" },
  reminder: { icon: Bell, color: "#3d6fd6", label: "Reminder" },
  thank_you: { icon: MessageSquareHeart, color: "#7f5bd1", label: "After interview" },
  follow_up: { icon: Mail, color: "#0e7a5c", label: "Follow up" },
  ghost: { icon: Ghost, color: "#8f97a6", label: "No reply" },
};
const ACTION_LABEL: Record<string, string> = {
  done: "Done", snooze: "Snooze 7d", dismiss: "Dismiss", mark_ghosted: "Mark ghosted", followed_up: "Followed up", open: "Open",
};

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export default function Overview() {
  const { filterQuery, openApp, refresh, toast, activeFilterCount } = useApp();
  const { data, loading } = useApi<Dict>(`/api/overview${filterQuery()}`);
  const [remOpen, setRemOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);

  async function act(item: Dict, action: string) {
    if (action === "open") { openApp(item.application_id); return; }
    try { await api.post("/api/priorities/act", { key: item.key, action, days: 7 }); refresh(); toast(ACTION_LABEL[action] ?? "Done"); }
    catch (e: any) { toast(e.message, "error"); }
  }

  if (loading && !data) return <div className="space-y-4"><Skeleton className="h-10 w-80" /><Skeleton className="h-24" /><Skeleton className="h-96" /></div>;
  if (!data) return null;
  const t = data.totals;
  const pri: Dict[] = data.priorities;
  const shown = showAll ? pri : pri.slice(0, 7);
  const pipe = data.pipeline as Record<string, number>;
  const pipeTotal = Object.values(pipe).reduce((a, b) => a + b, 0) || 1;
  const maxWeek = Math.max(data.weekly.goal, ...data.weekly.counts, 1);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-6">
        <div>
          <p className="text-ink-muted text-[13px]">{new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</p>
          <h1 className="text-[26px] font-semibold tracking-[-0.015em]">{greeting()}{data.name ? `, ${data.name}` : ""}</h1>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => setRemOpen(true)}><Bell size={15} /> Add reminder</button>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <Tile label="Active applications" value={t.active} sub={`${t.applications} in total`} />
        <Tile label="Interviews coming up" value={data.upcoming_interviews.length} sub={data.upcoming_interviews[0] ? `Next ${relDays(data.upcoming_interviews[0].date)}` : "None scheduled"} />
        <Tile label="Applied this week" value={`${t.this_week}`} suffix={` / ${data.weekly.goal}`} sub={t.this_week >= data.weekly.goal ? "Goal reached" : `${data.weekly.goal - t.this_week} to go`}
          bar={Math.min(1, t.this_week / Math.max(1, data.weekly.goal))} />
        <Tile label="Reached interview" value={t.interviews} sub={t.applications ? `${pct(t.interviews / t.applications, 1)} of applications` : ""} />
      </div>

      <div className="grid lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-5 min-w-0">
          <section className="card">
            <div className="flex items-center justify-between px-5 pt-4 pb-3">
              <div>
                <h2 className="text-[15px] font-semibold">Today's priorities</h2>
                <p className="text-[12.5px] text-ink-muted">Follow-ups, reminders and interviews that need you. Snooze or dismiss what isn't relevant.</p>
              </div>
              {pri.length > 0 && <span className="num text-[12px] text-ink-muted">{pri.length} open</span>}
            </div>
            {pri.length === 0 ? (
              <EmptyState icon={<CheckCircle2 size={20} />} title="You're all caught up">Nothing needs a follow-up and no reminders are due. Nice.</EmptyState>
            ) : (
              <ul className="divide-y divide-line border-t border-line">
                {shown.map((item) => {
                  const k = KIND[item.kind] ?? KIND.reminder;
                  return (
                    <li key={item.key} className="flex items-start gap-3 px-5 py-3 anim-in">
                      <span className="mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${k.color}14`, color: k.color }}>
                        <k.icon size={16} />
                      </span>
                      <div className="flex-1 min-w-0">
                        <button className="text-left font-medium text-[13.5px] hover:underline decoration-line-strong underline-offset-2"
                          onClick={() => item.application_id && openApp(item.application_id)}>{item.title}</button>
                        <div className="text-[12.5px] text-ink-muted">{item.detail}</div>
                      </div>
                      {item.severity === "high" && <span className="chip h-5 text-[10.5px] bg-alert-soft text-alert border-[#f6d3bd] mt-1">Urgent</span>}
                      <div className="flex gap-1 shrink-0">
                        {item.actions.map((a: string, i: number) => (
                          <button key={a} onClick={() => act(item, a)} className={i === 0 ? "btn-secondary btn-sm" : "btn-ghost btn-sm"}>{ACTION_LABEL[a]}</button>
                        ))}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
            {pri.length > 7 && (
              <div className="border-t border-line px-5 py-2"><button className="btn-ghost btn-sm" onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer" : `Show all ${pri.length}`}</button></div>
            )}
          </section>

          <section className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[15px] font-semibold">Active pipeline</h2>
              <Link to="/applications" className="text-[12.5px] font-medium text-brand inline-flex items-center gap-1 hover:underline">Open board <ArrowRight size={13} /></Link>
            </div>
            <div className="flex h-2.5 rounded-full overflow-hidden bg-canvas mb-2">
              {Object.entries(pipe).map(([k, v]) => v > 0 && <div key={k} style={{ width: `${(v / pipeTotal) * 100}%`, background: STAGE_STYLE[k].dot }} title={`${k}: ${v}`} />)}
            </div>
            <div className="flex flex-wrap gap-x-5 gap-y-1 mb-4">
              {Object.entries(pipe).map(([k, v]) => (
                <span key={k} className="text-[12.5px] text-ink-soft inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full" style={{ background: STAGE_STYLE[k].dot }} />
                  {k[0].toUpperCase() + k.slice(1)} <b className="num text-ink">{v}</b>
                </span>
              ))}
            </div>
            {data.active.length === 0 ? <p className="text-ink-muted text-[13px]">No open applications.</p> : (
              <div className="divide-y divide-line border border-line rounded-lg">
                {data.active.map((a: Dict) => (
                  <button key={a.id} onClick={() => openApp(a.id)} className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-canvas/70">
                    <div className="flex-1 min-w-0">
                      <div className="text-[13.5px] font-medium truncate">{a.position}</div>
                      <div className="text-[12px] text-ink-muted truncate">{a.company} · {a.role_area}</div>
                    </div>
                    <span className="text-[12px] text-ink-muted num whitespace-nowrap hidden sm:inline">{a.days_since_activity < 0 ? `next step in ${-a.days_since_activity}d` : a.days_since_activity === 0 ? "updated today" : `${a.days_since_activity}d since update`}</span>
                    <StatusPill stage={a.status} size="sm" />
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>

        <div className="space-y-5 min-w-0">
          <section className="card p-5">
            <h2 className="text-[15px] font-semibold mb-3 flex items-center gap-2"><CalendarClock size={16} className="text-ink-muted" /> Upcoming interviews</h2>
            {data.upcoming_interviews.length === 0 ? (
              <p className="text-[13px] text-ink-muted">None scheduled. Record an interview with a future date on an application to see it here.</p>
            ) : (
              <div className="space-y-2.5">
                {data.upcoming_interviews.map((u: Dict) => (
                  <button key={u.event_id} onClick={() => openApp(u.application_id)} className="w-full flex gap-3 text-left group">
                    <div className="w-11 shrink-0 rounded-lg border border-line text-center py-1">
                      <div className="text-[10px] uppercase font-semibold text-alert">{new Date(u.date + "T00:00:00").toLocaleDateString("en-GB", { month: "short" })}</div>
                      <div className="num text-[16px] font-semibold leading-none mt-0.5">{new Date(u.date + "T00:00:00").getDate()}</div>
                    </div>
                    <div className="min-w-0">
                      <div className="text-[13.5px] font-medium truncate group-hover:underline">{u.company}</div>
                      <div className="text-[12px] text-ink-muted truncate">{u.stage} · {u.position}</div>
                      <div className="text-[12px] text-ink-faint">{relDays(u.date)}{u.note ? ` · ${u.note}` : ""}</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </section>

          <section className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[15px] font-semibold flex items-center gap-2"><Clock size={16} className="text-ink-muted" /> Coming up</h2>
              <button className="btn-ghost btn-sm" onClick={() => setRemOpen(true)}><Plus size={14} /> Reminder</button>
            </div>
            {data.upcoming_reminders.length === 0 ? (
              <p className="text-[13px] text-ink-muted">No future reminders. Use them for applications that open on a certain day or deadlines.</p>
            ) : (
              <div className="space-y-2">
                {data.upcoming_reminders.map((r: Dict) => (
                  <div key={r.id} className="flex items-start gap-2.5">
                    <Bell size={14} className="text-ink-faint mt-1 shrink-0" />
                    <div className="min-w-0">
                      <div className="text-[13px] font-medium">{r.title}</div>
                      <div className="text-[12px] text-ink-muted num">{fmtDate(r.due_date)} · {relDays(r.due_date)}{r.company ? ` · ${r.company}` : ""}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="card p-5">
            <h2 className="text-[15px] font-semibold mb-3 flex items-center gap-2"><Lightbulb size={16} className="text-ink-muted" /> Key insights</h2>
            {activeFilterCount > 0 && <p className="text-[11.5px] text-ink-muted -mt-2 mb-2">Using your current filters.</p>}
            <ul className="space-y-2.5">
              {data.insights.map((i: Dict, n: number) => (
                <li key={n} className="flex gap-2 text-[13px] leading-snug">
                  <span className={cls("mt-1.5 w-1.5 h-1.5 rounded-full shrink-0",
                    i.tone === "good" ? "bg-[#0e9a69]" : i.tone === "warn" ? "bg-[#d97f06]" : i.tone === "hint" ? "bg-[#7f5bd1]" : "bg-[#3d6fd6]")} />
                  <span className="text-ink-soft">{i.text}</span>
                </li>
              ))}
            </ul>
            <Link to="/analytics" className="mt-3 text-[12.5px] font-medium text-brand inline-flex items-center gap-1 hover:underline">See analytics <ArrowRight size={13} /></Link>
          </section>

          <section className="card p-5">
            <h2 className="text-[15px] font-semibold mb-3 flex items-center gap-2"><TrendingUp size={16} className="text-ink-muted" /> Weekly pace</h2>
            <div className="relative h-24 flex items-end gap-1.5">
              <div className="absolute left-0 right-0 border-t border-dashed border-ink-faint/60" style={{ bottom: `${(data.weekly.goal / maxWeek) * 100}%` }}>
                <span className="absolute right-0 -top-4 text-[10.5px] text-ink-muted">goal {data.weekly.goal}</span>
              </div>
              {data.weekly.counts.map((c: number, i: number) => (
                <div key={i} className="flex-1 flex flex-col items-center justify-end h-full" title={`Week of ${fmtDate(data.weekly.weeks[i], false)}: ${c}`}>
                  <div className="w-full rounded-t-[4px]" style={{ height: `${(c / maxWeek) * 100}%`, minHeight: c ? 3 : 0, background: i === data.weekly.counts.length - 1 ? "#0e7a5c" : "#c4d4f2" }} />
                </div>
              ))}
            </div>
            <div className="flex justify-between text-[10.5px] text-ink-faint num mt-1">
              <span>{fmtDate(data.weekly.weeks[0], false)}</span><span>This week</span>
            </div>
          </section>
        </div>
      </div>
      <ReminderModal open={remOpen} onClose={() => setRemOpen(false)} />
    </div>
  );
}

function Tile({ label, value, sub, suffix, bar }: { label: string; value: number | string; sub?: string; suffix?: string; bar?: number }) {
  return (
    <div className="card px-4 py-3.5">
      <div className="text-[12px] text-ink-muted font-medium">{label}</div>
      <div className="mt-1 flex items-baseline gap-0.5">
        <span className="num text-[26px] font-semibold tracking-tight">{value}</span>
        {suffix && <span className="num text-ink-faint text-[14px]">{suffix}</span>}
      </div>
      {bar !== undefined && <div className="h-1 rounded-full bg-canvas mt-1.5 overflow-hidden"><div className="h-full bg-brand rounded-full" style={{ width: `${bar * 100}%` }} /></div>}
      {sub && <div className="text-[12px] text-ink-muted mt-1">{sub}</div>}
    </div>
  );
}

export function ReminderModal({ open, onClose, applicationId }: { open: boolean; onClose: () => void; applicationId?: number }) {
  const { refresh, toast } = useApp();
  const { data } = useApi<{ items: Dict[] }>(open ? "/api/applications?active=1" : null, [open]);
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [app, setApp] = useState(applicationId ? String(applicationId) : "");
  async function save() {
    try {
      await api.post("/api/reminders", { title, due_date: date, application_id: app ? Number(app) : null });
      toast("Reminder added"); refresh(); setTitle(""); setDate(""); setApp(""); onClose();
    } catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <Modal open={open} onClose={onClose} title="Add reminder" width="max-w-lg"
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!title || !date} onClick={save}>Add reminder</button></>}>
      <div className="space-y-3">
        <Field label="What"><input autoFocus className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Roche graduate programme opens, apply then" /></Field>
        <Field label="When"><input type="date" className="input num" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
        <Field label="Application (optional)">
          <Select value={app} onChange={setApp} placeholder="Not linked to an application"
            options={(data?.items ?? []).map((a) => ({ value: String(a.id), label: `${a.company} · ${a.position}` }))} />
        </Field>
      </div>
    </Modal>
  );
}
