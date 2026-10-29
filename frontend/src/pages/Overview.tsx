import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Bell, CalendarClock, CalendarX2, Clock, Ghost, Mail, MessageSquareHeart, Plus, NotebookPen } from "lucide-react";
import { api, type Dict } from "../api";
import { useApi, useApp } from "../store";
import { cls, relDays } from "../lib";
import { EmptyState, Field, Modal, Select, Skeleton } from "../components/ui";
import { Hero, MilestonesCard, MilestonesModal, MomentumCard } from "../components/Momentum";

const KIND: Record<string, { icon: typeof Bell; color: string; label: string }> = {
  interview: { icon: CalendarClock, color: "#d97f06", label: "Interview" },
  deadline: { icon: CalendarX2, color: "#c2410c", label: "Deadline" },
  reminder: { icon: Bell, color: "#3d6fd6", label: "Reminder" },
  thank_you: { icon: MessageSquareHeart, color: "#7f5bd1", label: "After interview" },
  follow_up: { icon: Mail, color: "#0e7a5c", label: "Follow up" },
  ghost: { icon: Ghost, color: "#8f97a6", label: "No reply" },
  journal: { icon: NotebookPen, color: "#3d6fd6", label: "Journal" },
};
const ACTION_LABEL: Record<string, string> = {
  done: "Done", open_opportunity: "Open", snooze: "Snooze 7d", dismiss: "Dismiss", mark_ghosted: "Mark ghosted", followed_up: "Followed up", open: "Open", log_interview: "Log it",
};

export default function Overview() {
  const { filterQuery, openApp, openSaved, refresh, toast, undoable } = useApp();
  const { data: mom } = useApi<Dict>("/api/momentum");
  const [params, setParams] = useSearchParams();
  const showMilestones = params.get("milestones") === "1";
  const { data, loading } = useApi<Dict>(`/api/overview${filterQuery()}`);
  const [remOpen, setRemOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const navigate = useNavigate();

  async function act(item: Dict, action: string) {
    if (action === "open") { openApp(item.application_id); return; }
    if (action === "open_opportunity") { openSaved(item.opportunity_id); return; }
    if (action === "log_interview") { navigate(`/career?log=${item.application_id}&date=${item.log_date}`); return; }
    try {
      const r = await api.post("/api/priorities/act", { key: item.key, action, days: 7 });
      refresh();
      if (r.event_ids?.length) undoable(`${ACTION_LABEL[action]}: ${item.title.replace(/^No reply from |^Follow up with /, "")}`, r.event_ids);
      else toast(ACTION_LABEL[action] ?? "Done");
    }
    catch (e: any) { toast(e.message, "error"); }
  }
  async function ghostAll() {
    try { const r = await api.post("/api/priorities/ghost-all"); refresh(); undoable(`Marked ${r.count} as ghosted`, r.event_ids); }
    catch (e: any) { toast(e.message, "error"); }
  }

  if (loading && !data) return <div className="space-y-4"><Skeleton className="h-10 w-80" /><Skeleton className="h-24" /><Skeleton className="h-96" /></div>;
  if (!data) return null;
  const pri: Dict[] = data.priorities;
  const shown = showAll ? pri : pri.slice(0, 7);
  const upcoming = [
    ...data.upcoming_interviews.map((u: Dict) => ({ key: `i${u.event_id}`, date: u.date, interview: true, application_id: u.application_id,
      title: u.company, sub: `${u.stage} · ${u.position}${u.note ? ` · ${u.note}` : ""}` })),
    ...data.upcoming_reminders.map((r: Dict) => ({ key: `r${r.id}`, date: r.due_date, interview: false, application_id: r.application_id,
      title: r.title, sub: r.company ?? "Reminder" })),
  ].sort((a, b) => a.date.localeCompare(b.date)).slice(0, 8);
  const ghosts = pri.filter((p) => p.kind === "ghost").length;

  return (
    <div>
      <Hero data={data} mom={mom} onReminder={() => setRemOpen(true)} />

      <div className="grid lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-5 min-w-0">
          <section className="card">
            <div className="flex items-center justify-between px-5 pt-4 pb-3">
              <div>
                <h2 className="text-[15px] font-semibold">Today's priorities</h2>
                <p className="text-[12.5px] text-ink-muted">Follow-ups, reminders and interviews that need you. Snooze or dismiss what isn't relevant.</p>
              </div>
              <div className="flex items-center gap-2">
                {ghosts >= 2 && <button className="btn-ghost btn-sm" onClick={ghostAll} title="Mark every application with no reply in a long time as ghosted"><Ghost size={13} /> Mark all {ghosts} ghosted</button>}
                {pri.length > 0 && <span className="num text-[12px] text-ink-muted">{pri.length} open</span>}
              </div>
            </div>
            {pri.length === 0 ? (
              <EmptyState art="spark" title="You're all caught up">Nothing needs a follow-up and no reminders are due. Nice.</EmptyState>
            ) : (
              <ul className="divide-y divide-line border-t border-line">
                {shown.map((item) => {
                  const k = KIND[item.kind] ?? KIND.reminder;
                  return (
                    <li key={item.key} className="flex flex-wrap sm:flex-nowrap items-start gap-x-3 gap-y-2 px-4 sm:px-5 py-3 anim-in">
                      <span className="mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${k.color}14`, color: k.color }}>
                        <k.icon size={16} />
                      </span>
                      <div className="flex-1 min-w-0">
                        <button className="text-left font-medium text-[13.5px] hover:underline decoration-line-strong underline-offset-2"
                          onClick={() => item.application_id ? openApp(item.application_id) : item.opportunity_id && openSaved(item.opportunity_id)}>{item.title}</button>
                        <div className="text-[12.5px] text-ink-muted">{item.detail}</div>
                      </div>
                      {item.severity === "high" && <span className="chip h-5 text-[10.5px] bg-alert-soft text-alert border-alert/30 mt-1">Urgent</span>}
                      <div className="flex flex-wrap gap-1 shrink-0 w-full sm:w-auto pl-11 sm:pl-0">
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
        </div>

        <div className="space-y-5 min-w-0">
          {mom && <MomentumCard mom={mom} />}
          <MilestonesCard onOpen={() => setParams({ milestones: "1" })} />
          <section className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[15px] font-semibold flex items-center gap-2"><Clock size={16} className="text-ink-muted" /> Coming up</h2>
              <button className="btn-ghost btn-sm" onClick={() => setRemOpen(true)}><Plus size={14} /> Reminder</button>
            </div>
            {!upcoming.length ? (
              <p className="text-[13px] text-ink-muted">Nothing scheduled. Interviews with a future date and reminders (for example when applications open) show up here.</p>
            ) : (
              <div className="space-y-2.5">
                {upcoming.map((u) => (
                  <button key={u.key} onClick={() => u.application_id && openApp(u.application_id)} className="w-full flex gap-3 text-left group">
                    <div className={cls("w-11 shrink-0 rounded-lg border text-center py-1", u.interview ? "border-warn-line bg-warn-soft/50" : "border-line")}>
                      <div className={cls("text-[10px] uppercase font-semibold", u.interview ? "text-warn" : "text-info")}>{new Date(u.date + "T00:00:00").toLocaleDateString("en-GB", { month: "short" })}</div>
                      <div className="num text-[16px] font-semibold leading-none mt-0.5">{new Date(u.date + "T00:00:00").getDate()}</div>
                    </div>
                    <div className="min-w-0">
                      <div className="text-[13.5px] font-medium truncate group-hover:underline flex items-center gap-1.5">
                        {u.interview ? <CalendarClock size={12} className="text-warn shrink-0" /> : <Bell size={12} className="text-info shrink-0" />}{u.title}</div>
                      <div className="text-[12px] text-ink-muted truncate">{u.sub}</div>
                      <div className="text-[12px] text-ink-faint">{relDays(u.date)}</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
      <ReminderModal open={remOpen} onClose={() => setRemOpen(false)} />
      <MilestonesModal open={showMilestones} onClose={() => setParams({})} />
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
