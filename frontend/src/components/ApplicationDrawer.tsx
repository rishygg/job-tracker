import { useEffect, useMemo, useState } from "react";
import { Bell, Check, ExternalLink, FileText, Pencil, Sparkles, Star, Trash2, X } from "lucide-react";
import { api, type Dict } from "../api";
import { useApp } from "../store";
import { cls, fmtDate, pct, relDays, stageStyle, today } from "../lib";
import { Drawer, Field, Select, Skeleton, StatusPill, Tabs } from "./ui";
import { FitPanel } from "./Fit";

type Tab = "overview" | "timeline" | "jd" | "reminders" | "fit";
const DIMS: [string, string][] = [
  ["role_area", "Job family"], ["seniority", "Seniority"], ["industry", "Industry"], ["region", "Location group"],
  ["company_size", "Company size"], ["work_authorization", "Work permit"], ["language", "Language"], ["work_mode", "Work mode"],
];
const STEPS = ["Applied", "Screening", "Interview", "Final interview", "Offer"];

export function ApplicationDrawer({ id, onClose }: { id: number | null; onClose: () => void }) {
  const { refresh, toast, version } = useApp();
  const [app, setApp] = useState<Dict | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [staging, setStaging] = useState<string | null>(null);

  const load = () => id && api.get(`/api/applications/${id}`).then(setApp).catch((e) => toast(e.message, "error"));
  useEffect(() => { setApp(null); setTab("overview"); setStaging(null); if (id) load(); }, [id]);
  useEffect(() => { if (id && app) load(); }, [version]);

  async function recordStage(stage: string, date: string, note: string) {
    try {
      const a = await api.post(`/api/applications/${id}/stages`, { stage, date, note });
      setApp(a); setStaging(null); refresh(); toast(`Recorded: ${stage}`);
    } catch (e: any) { toast(e.message, "error"); }
  }

  async function remove() {
    try { await api.del(`/api/applications/${id}`); refresh(); onClose(); toast("Application deleted"); }
    catch (e: any) { toast(e.message, "error"); }
  }

  const furthestIdx = app ? STEPS.indexOf(app.furthest_stage) : -1;
  const closed = app && ["Rejected", "Ghosted", "Withdrawn"].includes(app.status);

  return (
    <Drawer open={id !== null} onClose={onClose}>
      {!app ? (
        <div className="p-6 space-y-3"><Skeleton className="h-5 w-40" /><Skeleton className="h-8 w-72" /><Skeleton className="h-40 w-full" /></div>
      ) : (
        <>
          <header className="px-6 pt-5 pb-4 border-b border-line">
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <div className="text-[13px] text-ink-muted font-medium flex items-center gap-2">
                  {app.company}
                  {app.location && <span className="text-ink-faint">· {app.location}</span>}
                </div>
                <h2 className="text-[20px] font-semibold tracking-[-0.01em] leading-snug mt-0.5">{app.position}</h2>
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  <StatusPill stage={app.status} />
                  <span className="chip">{app.role_area}</span>
                  <span className="chip">{app.seniority}</span>
                  <span className="text-[12px] text-ink-muted num">Applied {fmtDate(app.date_applied)}</span>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {app.url && <a className="btn-ghost btn-sm" href={app.url} target="_blank" rel="noreferrer" title="Open posting"><ExternalLink size={15} /></a>}
                <DeleteButton onConfirm={remove} />
                <button className="btn-ghost btn-sm" onClick={onClose} aria-label="Close"><X size={17} /></button>
              </div>
            </div>

            {/* Stage stepper: click a stage to record it with a date. */}
            <div className="mt-4">
              <div className="flex items-center gap-1">
                {STEPS.map((s, i) => {
                  const reached = i <= furthestIdx;
                  const current = app.status === s || (s === "Offer" && app.status === "Accepted");
                  const st = stageStyle(s);
                  return (
                    <button key={s} onClick={() => setStaging(s)}
                      className={cls("flex-1 min-w-0 group text-left rounded-md px-2 py-1.5 transition border",
                        current ? "border-transparent" : "border-transparent hover:bg-canvas")}
                      style={current ? { background: st.bg, boxShadow: `inset 0 0 0 1px ${st.ring}` } : undefined}>
                      <div className="h-1 rounded-full mb-1.5" style={{ background: reached ? st.dot : "#e4e7ec" }} />
                      <div className={cls("text-[11.5px] font-medium truncate", reached ? "text-ink" : "text-ink-faint")}>{s}</div>
                    </button>
                  );
                })}
                <div className="w-px h-8 bg-line mx-1" />
                {["Rejected", "Ghosted", "Withdrawn"].map((s) => (
                  <button key={s} onClick={() => setStaging(s)}
                    className={cls("px-2 py-1 rounded-md text-[11.5px] font-medium border transition",
                      app.status === s ? "bg-[#f2f3f5] border-line-strong text-ink" : "border-transparent text-ink-muted hover:bg-canvas")}>
                    {s}
                  </button>
                ))}
              </div>
              {staging && <StageForm stage={staging} onCancel={() => setStaging(null)} onSave={recordStage} />}
              {closed && !staging && app.furthest_stage !== "Applied" && (
                <p className="text-[12px] text-ink-muted mt-1.5">Reached <b>{app.furthest_stage}</b> before closing; it still counts in your interview stats.</p>
              )}
            </div>
          </header>

          <div className="px-6">
            <Tabs value={tab} onChange={setTab} tabs={[
              { id: "overview", label: "Details" },
              { id: "timeline", label: <>Timeline <span className="num text-ink-faint">{app.events.length}</span></> },
              { id: "jd", label: "Job description" },
              { id: "reminders", label: <>Reminders {app.reminders.filter((r: Dict) => !r.done).length > 0 && <span className="num text-alert">{app.reminders.filter((r: Dict) => !r.done).length}</span>}</> },
              { id: "fit", label: <span className="inline-flex items-center gap-1"><Sparkles size={13} /> CV fit & documents</span> },
            ]} />
          </div>
          <div className="flex-1 overflow-y-auto scroll-thin px-6 py-5">
            {tab === "overview" && <DetailsForm app={app} onSaved={(a) => { setApp(a); refresh(); }} />}
            {tab === "timeline" && <Timeline app={app} onChanged={() => { load(); refresh(); }} onAdd={() => setStaging(app.status)} />}
            {tab === "jd" && <JobDescription app={app} onSaved={(a) => { setApp(a); refresh(); }} />}
            {tab === "reminders" && <Reminders app={app} onChanged={() => { load(); refresh(); }} />}
            {tab === "fit" && <FitPanel kind="application" refId={app.id} hasJd={(app.job_description ?? "").trim().length >= 80} />}
          </div>
        </>
      )}
    </Drawer>
  );
}

function DeleteButton({ onConfirm }: { onConfirm: () => void }) {
  const [ask, setAsk] = useState(false);
  if (ask) return (
    <span className="flex items-center gap-1 text-[12px]">
      <span className="text-danger font-medium">Delete?</span>
      <button className="btn-sm btn bg-danger text-white hover:opacity-90" onClick={onConfirm}>Yes</button>
      <button className="btn-ghost btn-sm" onClick={() => setAsk(false)}>No</button>
    </span>
  );
  return <button className="btn-ghost btn-sm" title="Delete application" onClick={() => setAsk(true)}><Trash2 size={15} /></button>;
}

function StageForm({ stage, onSave, onCancel, initial }:
  { stage: string; onSave: (stage: string, date: string, note: string) => void; onCancel: () => void; initial?: { date: string; note: string } }) {
  const [date, setDate] = useState(initial?.date ?? today());
  const [note, setNote] = useState(initial?.note ?? "");
  const st = stageStyle(stage);
  const future = date > today();
  return (
    <div className="anim-in mt-2 p-3 rounded-lg border flex flex-wrap items-end gap-2" style={{ borderColor: st.ring, background: st.bg }}>
      <div className="text-[13px] font-semibold w-full" style={{ color: st.text }}>
        {future && (stage === "Interview" || stage === "Final interview") ? `Schedule ${stage.toLowerCase()}` : `Move to ${stage}`}
      </div>
      <Field label={future ? "Scheduled for" : "When"} className="w-[150px]">
        <input type="date" className="input num h-8" value={date} onChange={(e) => setDate(e.target.value)} />
      </Field>
      <Field label="Note (optional)" className="flex-1 min-w-[180px]">
        <input className="input h-8" value={note} onChange={(e) => setNote(e.target.value)}
          placeholder={stage.includes("nterview") ? "e.g. 45 min video call with hiring manager" : "e.g. Recruiter call"} />
      </Field>
      <button className="btn-primary btn-sm h-8" onClick={() => onSave(stage, date, note)}>Save</button>
      <button className="btn-ghost btn-sm h-8" onClick={onCancel}>Cancel</button>
    </div>
  );
}

function DetailsForm({ app, onSaved }: { app: Dict; onSaved: (a: Dict) => void }) {
  const { meta, toast } = useApp();
  const initial = useMemo(() => ({
    company: app.company ?? "", position: app.position ?? "", location: app.location ?? "",
    date_applied: app.date_applied ?? "", date_posted: app.date_posted ?? "", source: app.source ?? "",
    contact: app.contact ?? "", url: app.url ?? "", cv_version: app.cv_version ?? "", fit_rating: app.fit_rating ?? 0,
    salary: app.salary ?? "", notes: app.notes ?? "",
    ...Object.fromEntries(DIMS.map(([d]) => [d, app.overrides?.[d] ?? ""])),
  }), [app]);
  const [f, setF] = useState<Dict>(initial);
  useEffect(() => setF(initial), [initial]);
  const dirty = JSON.stringify(f) !== JSON.stringify(initial);
  const set = (k: string) => (v: any) => setF((c) => ({ ...c, [k]: v }));

  async function save() {
    try {
      const body: Dict = { ...f, fit_rating: f.fit_rating || null };
      const a = await api.patch(`/api/applications/${app.id}`, body);
      onSaved(a); toast("Saved");
    } catch (e: any) { toast(e.message, "error"); }
  }
  if (!meta) return null;
  return (
    <div className="space-y-5">
      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="Position"><input className="input" value={f.position} onChange={(e) => set("position")(e.target.value)} /></Field>
        <Field label="Company"><input className="input" value={f.company} onChange={(e) => set("company")(e.target.value)} /></Field>
        <Field label="Location"><input className="input" value={f.location} onChange={(e) => set("location")(e.target.value)} /></Field>
        <Field label="Channel"><Select value={f.source} onChange={set("source")} options={meta.sources} placeholder="Not recorded" /></Field>
        <Field label="Date applied"><input type="date" className="input num" value={f.date_applied} onChange={(e) => set("date_applied")(e.target.value)} /></Field>
        <Field label="Date posted"><input type="date" className="input num" value={f.date_posted} onChange={(e) => set("date_posted")(e.target.value)} /></Field>
        <Field label="Contact / hiring manager"><input className="input" value={f.contact} onChange={(e) => set("contact")(e.target.value)} /></Field>
        <Field label="Link"><input className="input" value={f.url} onChange={(e) => set("url")(e.target.value)} /></Field>
        <Field label="CV version">
          <input className="input" list="cv-versions-d" value={f.cv_version} onChange={(e) => set("cv_version")(e.target.value)} />
          <datalist id="cv-versions-d">{meta.cv_versions.map((v) => <option key={v} value={v} />)}</datalist>
        </Field>
        <Field label="Your fit">
          <div className="flex items-center gap-0.5 h-9">
            {[1, 2, 3, 4, 5].map((n) => (
              <button key={n} type="button" aria-label={`${n} of 5`} onClick={() => set("fit_rating")(f.fit_rating === n ? 0 : n)}
                className={cls("p-1 rounded", n <= f.fit_rating ? "text-[#d97f06]" : "text-line-strong hover:text-ink-faint")}>
                <Star size={17} fill={n <= f.fit_rating ? "currentColor" : "none"} />
              </button>
            ))}
          </div>
        </Field>
        <Field label="Salary"><input className="input" value={f.salary} onChange={(e) => set("salary")(e.target.value)} /></Field>
      </div>
      <Field label="Notes"><textarea className="textarea h-24" value={f.notes} onChange={(e) => set("notes")(e.target.value)} /></Field>

      <div>
        <div className="eyebrow mb-1">Role dimensions</div>
        <p className="text-[12px] text-ink-muted mb-3">"Auto" is worked out from the title, company and job description and keeps updating. Pick a value to set it yourself.</p>
        <div className="grid sm:grid-cols-2 gap-3">
          {DIMS.map(([d, label]) => (
            <Field key={d} label={label}>
              <Select value={f[d]} onChange={set(d)} options={meta.options[d] ?? []} placeholder={`Auto: ${app.auto?.[d] ?? "—"}`}
                className={f[d] ? "border-brand/40" : ""} />
            </Field>
          ))}
        </div>
      </div>

      <div className="sticky bottom-0 -mx-6 px-6 py-3 bg-white/95 backdrop-blur border-t border-line flex justify-end gap-2">
        <button className="btn-secondary" disabled={!dirty} onClick={() => setF(initial)}>Discard</button>
        <button className="btn-primary" disabled={!dirty} onClick={save}><Check size={15} /> Save changes</button>
      </div>
    </div>
  );
}

function Timeline({ app, onChanged, onAdd }: { app: Dict; onChanged: () => void; onAdd: () => void }) {
  const { toast, meta } = useApp();
  const [editing, setEditing] = useState<number | null>(null);
  const [edit, setEdit] = useState<Dict>({});
  const events = [...app.events].sort((a: Dict, b: Dict) => (a.date < b.date ? 1 : a.date > b.date ? -1 : b.id - a.id));
  async function saveEdit(id: number) {
    try { await api.patch(`/api/events/${id}`, edit); setEditing(null); onChanged(); toast("Updated"); }
    catch (e: any) { toast(e.message, "error"); }
  }
  async function del(id: number) {
    try { await api.del(`/api/events/${id}`); onChanged(); toast("Removed"); }
    catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-[12.5px] text-ink-muted">Every stage with its date. Future-dated interviews show up as upcoming on the Overview.</p>
        <button className="btn-secondary btn-sm" onClick={onAdd}>Record stage</button>
      </div>
      <ol className="relative ml-2">
        {events.map((e: Dict, i: number) => {
          const st = stageStyle(e.stage);
          const isFuture = e.date > today();
          return (
            <li key={e.id} className="relative pl-7 pb-5 group">
              {i < events.length - 1 && <span className="absolute left-[5px] top-4 bottom-0 w-px bg-line" />}
              <span className="absolute left-0 top-1.5 w-[11px] h-[11px] rounded-full ring-4 ring-white" style={{ background: st.dot }} />
              {editing === e.id ? (
                <div className="flex flex-wrap items-end gap-2 p-2.5 rounded-lg bg-canvas">
                  <Field label="Stage" className="w-40"><Select value={edit.stage} onChange={(v) => setEdit({ ...edit, stage: v })} options={meta?.stages ?? []} className="h-8" /></Field>
                  <Field label="Date" className="w-[150px]"><input type="date" className="input h-8 num" value={edit.date} onChange={(x) => setEdit({ ...edit, date: x.target.value })} /></Field>
                  <Field label="Note" className="flex-1 min-w-[160px]"><input className="input h-8" value={edit.note} onChange={(x) => setEdit({ ...edit, note: x.target.value })} /></Field>
                  <button className="btn-primary btn-sm h-8" onClick={() => saveEdit(e.id)}>Save</button>
                  <button className="btn-ghost btn-sm h-8" onClick={() => setEditing(null)}>Cancel</button>
                </div>
              ) : (
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-[13.5px]">{e.stage}</span>
                      {isFuture && <span className="chip h-5 text-[10.5px]" style={{ background: st.bg, color: st.text, borderColor: st.ring }}>Upcoming</span>}
                    </div>
                    <div className="text-[12px] text-ink-muted num">{fmtDate(e.date)} · {relDays(e.date)}</div>
                    {e.note && <div className="text-[13px] text-ink-soft mt-0.5">{e.note === "imported" ? "From import" : e.note}</div>}
                  </div>
                  <div className="opacity-0 group-hover:opacity-100 focus-within:opacity-100 flex gap-0.5 transition">
                    <button className="btn-ghost btn-sm" title="Edit" onClick={() => { setEditing(e.id); setEdit({ stage: e.stage, date: e.date, note: e.note ?? "" }); }}><Pencil size={13} /></button>
                    {events.length > 1 && <button className="btn-ghost btn-sm" title="Remove" onClick={() => del(e.id)}><Trash2 size={13} /></button>}
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      {app.same_company?.length > 0 && (
        <div className="mt-2 pt-4 border-t border-line">
          <div className="eyebrow mb-2">Other applications at {app.company}</div>
          {app.same_company.map((o: Dict) => (
            <div key={o.id} className="flex items-center justify-between py-1 text-[13px]">
              <span className="truncate">{o.position} <span className="text-ink-muted num">· {fmtDate(o.date_applied)}</span></span>
              <StatusPill stage={o.status} size="sm" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function JobDescription({ app, onSaved }: { app: Dict; onSaved: (a: Dict) => void }) {
  const { toast } = useApp();
  const [jd, setJd] = useState(app.job_description ?? "");
  useEffect(() => setJd(app.job_description ?? ""), [app.job_description]);
  const a = app.jd_analysis;
  async function save() {
    try { const r = await api.patch(`/api/applications/${app.id}`, { job_description: jd }); onSaved(r); toast("Job description saved"); }
    catch (e: any) { toast(e.message, "error"); }
  }
  const have = a?.skills?.filter((s: Dict) => s.have) ?? [];
  const missing = a?.skills?.filter((s: Dict) => !s.have) ?? [];
  return (
    <div className="space-y-5">
      {a && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[["Skills match", a.has_profile ? pct(a.match) : "—"], ["Experience asked", a.min_years !== null ? `${a.min_years}+ yrs` : "Not stated"],
            ["Language", a.language ?? "None stated"], ["Work permit", a.work_authorization ?? "Not stated"]].map(([k, v]) => (
            <div key={k} className="rounded-lg border border-line p-3">
              <div className="text-[11.5px] text-ink-muted">{k}</div>
              <div className="font-semibold text-[13.5px] mt-0.5 leading-snug">{v}</div>
            </div>
          ))}
        </div>
      )}
      {a && a.skills.length > 0 && (
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <div className="eyebrow mb-2">You have</div>
            <div className="flex flex-wrap gap-1">{have.length ? have.map((s: Dict) => <span key={s.skill} className="chip bg-brand-soft text-brand-strong border-brand/20">{s.skill}</span>) : <span className="text-ink-muted text-[12.5px]">{a.has_profile ? "None of the listed skills" : "Add your skills in Settings"}</span>}</div>
          </div>
          <div>
            <div className="eyebrow mb-2">Not in your profile</div>
            <div className="flex flex-wrap gap-1">{missing.map((s: Dict) => <span key={s.skill} className="chip">{s.skill}</span>)}</div>
          </div>
        </div>
      )}
      {a?.written_in_german && <p className="text-[12.5px] text-ink-soft">This posting is written in German, which usually means German is expected.</p>}
      <Field label="Job description">
        <textarea className="textarea h-[340px] text-[13px]" value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the full posting to unlock skills match and requirement detection." />
      </Field>
      <div className="flex justify-end"><button className="btn-primary" disabled={jd === (app.job_description ?? "")} onClick={save}><FileText size={15} /> Save description</button></div>
    </div>
  );
}

function Reminders({ app, onChanged }: { app: Dict; onChanged: () => void }) {
  const { toast } = useApp();
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  async function add() {
    try { await api.post("/api/reminders", { title, due_date: date, application_id: app.id }); setTitle(""); setDate(""); onChanged(); toast("Reminder added"); }
    catch (e: any) { toast(e.message, "error"); }
  }
  async function toggle(r: Dict) { await api.patch(`/api/reminders/${r.id}`, { done: !r.done }); onChanged(); }
  async function del(r: Dict) { await api.del(`/api/reminders/${r.id}`); onChanged(); }
  return (
    <div className="space-y-4">
      <p className="text-[12.5px] text-ink-muted">For things that can only happen on a certain day: applications opening, a deadline, a call back. Due reminders appear in today's priorities.</p>
      <div className="flex flex-wrap gap-2 items-end">
        <Field label="Reminder" className="flex-1 min-w-[200px]"><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Applications open, submit then" /></Field>
        <Field label="On" className="w-[160px]"><input type="date" className="input num" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
        <button className="btn-primary" disabled={!title || !date} onClick={add}><Bell size={15} /> Add</button>
      </div>
      <div className="divide-y divide-line border border-line rounded-lg">
        {app.reminders.length === 0 && <div className="p-4 text-ink-muted text-[13px]">No reminders for this application.</div>}
        {app.reminders.map((r: Dict) => (
          <div key={r.id} className="flex items-center gap-3 px-3 py-2.5">
            <input type="checkbox" checked={!!r.done} onChange={() => toggle(r)} className="accent-[#0e7a5c] w-4 h-4" aria-label="Done" />
            <div className={cls("flex-1 min-w-0", r.done && "line-through text-ink-faint")}>
              <div className="text-[13.5px] font-medium truncate">{r.title}</div>
              <div className="text-[12px] text-ink-muted num">{fmtDate(r.due_date)} · {relDays(r.due_date)}</div>
            </div>
            <button className="btn-ghost btn-sm" onClick={() => del(r)} aria-label="Delete reminder"><Trash2 size={13} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}

