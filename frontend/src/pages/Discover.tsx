import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Bookmark, BriefcaseBusiness, CalendarClock, ExternalLink, FileText, Gauge, Loader2, MapPin, Send, Sparkles, Trash2 } from "lucide-react";
import { api, type Dict } from "../api";
import { useApi, useApp } from "../store";
import { cls, fmtDate, pct, relDays, today } from "../lib";
import { ActionPill, FitPanel, FitResultView, ScoreRing } from "../components/Fit";
import { EmptyState, Field, Modal, PageHeader, SectionTitle, Skeleton, StatusPill, Tabs } from "../components/ui";

export default function Discover() {
  const { refresh, toast, meta, openApp } = useApp();
  const { data, loading } = useApi<Dict>("/api/discover");
  const { data: ai } = useApi<Dict>("/api/ai/status");
  const [params, setParams] = useSearchParams();
  const openId = params.get("open") ? Number(params.get("open")) : null;
  const [scoring, setScoring] = useState(false);
  const [queue, setQueue] = useState<Dict | null>(null);
  const busyQueue = !!queue && (queue.pending > 0 || !!queue.running);
  useEffect(() => { api.get("/api/ai/queue").then(setQueue).catch(() => {}); }, []);
  useEffect(() => {
    if (!busyQueue) return;
    const t = setInterval(() => api.get("/api/ai/queue").then((q) => {
      setQueue((prev) => { if (prev && q.done > prev.done) refresh(); return q; });
    }).catch(() => {}), 2000);
    return () => clearInterval(t);
  }, [busyQueue, refresh]);

  async function queueAi(items: Dict[]) {
    try { setQueue(await api.post("/api/ai/queue", { items })); toast(`${items.length} job${items.length === 1 ? "" : "s"} queued for AI analysis`); }
    catch (e: any) { toast(e.message, "error"); }
  }
  const aiTargets = (data?.opportunities ?? []).filter((o: Dict) => o.has_jd && o.fit?.method !== "ollama").slice(0, 5);

  async function scoreAll(kind: "opportunity" | "application") {
    setScoring(true);
    try {
      const r = await api.post("/api/fit/batch", { kind, engine: "keywords" });
      toast(r.analysed ? `Scored ${r.analysed} job${r.analysed === 1 ? "" : "s"}` : r.errors?.[0] ?? "Nothing new to score");
      refresh();
    } catch (e: any) { toast(e.message, "error"); }
    finally { setScoring(false); }
  }

  const hasCv = (meta?.settings?.cv_chars ?? 0) >= 50;
  return (
    <div>
      <PageHeader title="Discover" subtitle="Check a job against your CV before you apply, and keep a ranked list of jobs worth applying to." />
      <AiBanner ai={ai} hasCv={hasCv} />
      <div className="grid xl:grid-cols-[1.1fr_1fr] gap-5 items-start">
        <CheckJob hasCv={hasCv} />
        <div className="space-y-5 min-w-0">
          <section className="card">
            <div className="px-5 pt-4 pb-3 flex items-center justify-between gap-2">
              <div>
                <h2 className="text-[15px] font-semibold">Saved jobs, best fit first</h2>
                <p className="text-[12.5px] text-ink-muted">Jobs you haven't applied to yet. Deadlines show up in today's priorities.</p>
              </div>
              <div className="flex gap-1">
                <button className="btn-secondary btn-sm" disabled={scoring || !hasCv} onClick={() => scoreAll("opportunity")} title="Instant keyword scoring">
                  {scoring ? <Loader2 className="animate-spin" size={13} /> : <Gauge size={13} />} Quick score all
                </button>
                {ai?.available && aiTargets.length > 0 && (
                  <button className="btn-primary btn-sm" disabled={busyQueue || !hasCv}
                    onClick={() => queueAi(aiTargets.map((o: Dict) => ({ kind: "opportunity", ref_id: o.id, label: o.position })))}>
                    <Sparkles size={13} /> AI-analyse top {aiTargets.length}
                  </button>
                )}
              </div>
            </div>
            {busyQueue && (
              <div className="mx-5 mb-3 p-3 rounded-lg bg-brand-soft/70 text-[12.5px]">
                <div className="flex items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-1.5"><Loader2 className="animate-spin" size={13} />
                    AI analysing {queue?.running?.label ? `“${queue?.running.label}”` : "…"} · {queue?.done} of {queue?.total} done</span>
                  <button className="btn-ghost btn-sm" onClick={async () => setQueue(await api.del("/api/ai/queue"))}>Stop after this one</button>
                </div>
                <div className="h-1.5 rounded-full bg-white mt-2 overflow-hidden"><div className="h-full bg-brand rounded-full transition-all" style={{ width: `${((queue?.done ?? 0) / Math.max(1, queue?.total ?? 1)) * 100}%` }} /></div>
                <div className="text-[11.5px] text-ink-muted mt-1.5">Runs in the background; keep browsing. Results replace the quick scores as they finish.</div>
              </div>
            )}
            {queue?.errors?.length > 0 && !busyQueue && <p className="mx-5 mb-3 text-[12px] text-danger">{queue?.errors[(queue?.errors?.length ?? 1) - 1].error}</p>}
            {loading && !data ? <div className="p-5"><Skeleton className="h-40" /></div>
              : !data?.opportunities.length ? (
                <EmptyState icon={<Bookmark size={20} />} title="No saved jobs yet">Paste a job on the left and choose "Save for later" to build a ranked shortlist.</EmptyState>
              ) : (
                <ul className="divide-y divide-line border-t border-line">
                  {data.opportunities.map((o: Dict) => <OppRow key={o.id} o={o} queued={queue?.queued_ids?.includes(`opportunity:${o.id}`)}
                    canAi={!!ai?.available && o.has_jd && !busyQueue} onAi={() => queueAi([{ kind: "opportunity", ref_id: o.id, label: o.position }])}
                    onOpen={() => setParams({ open: String(o.id) })} />)}
                </ul>
              )}
          </section>
          <section className="card">
            <div className="px-5 pt-4 pb-3 flex items-center justify-between gap-2">
              <div>
                <h2 className="text-[15px] font-semibold">Open applications by fit</h2>
                <p className="text-[12.5px] text-ink-muted">Where your CV is strongest among applications still in progress.</p>
              </div>
              {data?.unscored_applications > 0 && (
                <button className="btn-secondary btn-sm" disabled={scoring || !hasCv} onClick={() => scoreAll("application")}>
                  <Gauge size={13} /> Score {data?.unscored_applications}
                </button>
              )}
            </div>
            {!data?.applications.length ? (
              <p className="px-5 pb-5 text-[13px] text-ink-muted">No scored applications yet. Applications need a saved job description to be scored.</p>
            ) : (
              <ul className="divide-y divide-line border-t border-line">
                {data.applications.slice(0, 12).map((a: Dict) => (
                  <li key={a.id}>
                    <button onClick={() => openApp(a.id)} className="w-full flex items-center gap-3 px-5 py-2.5 text-left hover:bg-canvas/70">
                      <ScoreRing score={a.fit?.score} size={36} />
                      <div className="flex-1 min-w-0">
                        <div className="text-[13.5px] font-medium truncate">{a.position}</div>
                        <div className="text-[12px] text-ink-muted truncate">{a.company}</div>
                      </div>
                      <StatusPill stage={a.status} size="sm" />
                      <ActionPill action={a.fit.action} size="sm" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
      <OpportunityModal id={openId} onClose={() => setParams({})} />
    </div>
  );
}

function AiBanner({ ai, hasCv }: { ai: Dict | null; hasCv: boolean }) {
  if (!ai) return null;
  if (!hasCv) return (
    <div className="mb-5 flex flex-wrap items-center gap-3 p-3.5 rounded-xl border border-[#f5dcb1] bg-[#fffaf1] text-[13px]">
      <FileText size={16} className="text-[#a35f00]" />
      <span className="flex-1 min-w-[200px]"><b>Add your CV to get started.</b> Fit analysis compares each job with your CV and profile (languages, degree, work permits).</span>
      <Link to="/settings" className="btn-primary btn-sm">Add CV</Link>
    </div>
  );
  return (
    <div className="mb-5 flex flex-wrap items-center gap-2 text-[12.5px] text-ink-muted">
      <span className={cls("w-2 h-2 rounded-full", ai.available ? "bg-[#0e9a69]" : "bg-[#c9ced8]")} />
      {ai.available ? <>AI analysis on: <b className="text-ink">{ai.model}</b> via Ollama (runs on your computer).</>
        : <>Using keyword analysis. <Link to="/settings" className="text-brand font-medium hover:underline">Set up Ollama</Link> for AI-written analyses, target CVs and cover letters.</>}
    </div>
  );
}

function OppRow({ o, onOpen, queued, canAi, onAi }: { o: Dict; onOpen: () => void; queued?: boolean; canAi?: boolean; onAi?: () => void }) {
  const dl = o.deadline;
  const soon = dl && dl >= today() && (new Date(dl).getTime() - Date.now()) / 86400000 <= 7;
  return (
    <li>
      <button onClick={onOpen} className="w-full flex items-start gap-3 px-5 py-3 text-left hover:bg-canvas/70">
        <ScoreRing score={o.fit?.score} size={40} />
        <div className="flex-1 min-w-0">
          <div className="text-[13.5px] font-medium truncate">{o.position}</div>
          <div className="text-[12px] text-ink-muted truncate">{o.company}{o.location ? ` · ${o.location}` : ""}</div>
          <div className="flex flex-wrap gap-1 mt-1.5">
            {dl && <span className={cls("chip h-5 text-[10.5px]", soon && "bg-alert-soft text-alert border-[#f6d3bd]")}><CalendarClock size={10} /> {fmtDate(dl, false)} · {relDays(dl)}</span>}
            {o.fit?.blockers?.map((b: Dict, i: number) => <span key={i} className="chip h-5 text-[10.5px]">{b.type}</span>)}
            {o.fit?.stale && <span className="chip h-5 text-[10.5px]">Outdated, re-run</span>}
            {!o.has_jd && <span className="chip h-5 text-[10.5px]">No description</span>}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          {o.fit ? <ActionPill action={o.fit.action} size="sm" /> : <span className="text-[11.5px] text-ink-faint">Not scored</span>}
          {queued ? <span className="text-[10.5px] text-brand inline-flex items-center gap-1"><Loader2 className="animate-spin" size={10} /> AI queued</span>
            : o.fit && <span className="text-[10.5px] text-ink-faint">{o.fit.method === "ollama" ? "AI analysis" : "Quick score"}</span>}
        </div>
      </button>
      {canAi && o.fit?.method !== "ollama" && !queued && (
        <div className="px-5 -mt-2 pb-2 pl-[72px]"><button className="text-[11.5px] text-brand font-medium hover:underline inline-flex items-center gap-1" onClick={onAi}><Sparkles size={11} /> Deep-analyse with AI</button></div>
      )}
    </li>
  );
}

function CheckJob({ hasCv }: { hasCv: boolean }) {
  const { toast, refresh, openApp } = useApp();
  const [f, setF] = useState({ job_description: "", position: "", company: "", location: "", url: "", deadline: "" });
  const [res, setRes] = useState<Dict | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => setF((c) => ({ ...c, [k]: v }));

  // Guess title and company from the pasted posting.
  useEffect(() => {
    if (f.job_description.length < 40 || (f.position && f.company)) return;
    const t = setTimeout(() => api.post("/api/parse", { job_description: f.job_description }).then((p) => {
      setF((c) => ({ ...c, position: c.position || p.guess?.position || "", company: c.company || p.guess?.company || "" }));
    }).catch(() => {}), 400);
    return () => clearTimeout(t);
  }, [f.job_description]);

  const [ai, setAi] = useState<Dict | null>(null);
  useEffect(() => { api.get("/api/ai/status").then(setAi).catch(() => {}); }, []);
  async function analyse(engine = "keywords") {
    setBusy(true); if (engine === "keywords") setRes(null);
    try { setRes(await api.post("/api/fit/check", { ...f, engine })); }
    catch (e: any) { toast(e.message, "error"); }
    finally { setBusy(false); }
  }
  async function save() {
    try { await api.post("/api/opportunities", { ...f, fit: res }); toast("Saved to Discover"); refresh(); reset(); }
    catch (e: any) { toast(e.message, "error"); }
  }
  async function applyNow() {
    try {
      const r = await api.post("/api/applications", { ...f, deadline: undefined });
      toast("Added as an application"); refresh(); reset(); openApp(r.id);
    } catch (e: any) { toast(e.message, "error"); }
  }
  const reset = () => { setF({ job_description: "", position: "", company: "", location: "", url: "", deadline: "" }); setRes(null); };
  const canSave = f.position.trim() && f.company.trim();

  return (
    <section className="card p-5 min-w-0">
      <SectionTitle>Check a job</SectionTitle>
      <div className="space-y-3">
        <textarea className="textarea h-44 text-[13px]" placeholder="Paste a job description to see how well your CV fits…" value={f.job_description}
          onChange={(e) => set("job_description")(e.target.value)} />
        <div className="grid sm:grid-cols-3 gap-3">
          <Field label="Position"><input className="input" value={f.position} onChange={(e) => set("position")(e.target.value)} /></Field>
          <Field label="Company"><input className="input" value={f.company} onChange={(e) => set("company")(e.target.value)} /></Field>
          <Field label="Location"><input className="input" value={f.location} onChange={(e) => set("location")(e.target.value)} placeholder="Used for permit checks" /></Field>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-primary" disabled={busy || !hasCv || f.job_description.trim().length < 80} onClick={() => analyse()}>
            <Gauge size={15} /> Check fit
          </button>
          {res && ai?.available && res.method !== "ollama" && (
            <button className="btn-secondary" disabled={busy} onClick={() => analyse("ollama")}>
              {busy ? <><Loader2 className="animate-spin" size={15} /> AI is reading… (~20–40 s)</> : <><Sparkles size={15} /> Deep analysis with AI</>}
            </button>
          )}
          {!hasCv && <span className="text-[12px] text-ink-muted">Add your CV in Settings first.</span>}
          {hasCv && f.job_description.trim().length > 0 && f.job_description.trim().length < 80 && <span className="text-[12px] text-ink-muted">Paste the full posting.</span>}
        </div>
      </div>
      {res && (
        <div className="mt-6 pt-5 border-t border-line anim-in">
          <FitResultView res={res} />
          <div className="mt-5 p-3.5 rounded-xl bg-canvas flex flex-wrap items-end gap-3">
            <Field label="Link" className="flex-1 min-w-[180px]"><input className="input h-8" value={f.url} onChange={(e) => set("url")(e.target.value)} placeholder="https://…" /></Field>
            <Field label="Deadline (optional)" className="w-[160px]"><input type="date" className="input h-8 num" value={f.deadline} onChange={(e) => set("deadline")(e.target.value)} /></Field>
            <button className="btn-secondary h-8" disabled={!canSave} onClick={save}><Bookmark size={14} /> Save for later</button>
            <button className="btn-primary h-8" disabled={!canSave} onClick={applyNow}><Send size={14} /> I've applied</button>
          </div>
          {!canSave && <p className="text-[12px] text-ink-muted mt-2">Add the position and company to save it.</p>}
        </div>
      )}
    </section>
  );
}

function OpportunityModal({ id, onClose }: { id: number | null; onClose: () => void }) {
  const { refresh, toast, openApp, version } = useApp();
  const [o, setO] = useState<Dict | null>(null);
  const [tab, setTab] = useState<"fit" | "details">("fit");
  const [edit, setEdit] = useState<Dict>({});
  useEffect(() => {
    if (!id) { setO(null); return; }
    api.get(`/api/opportunities/${id}`).then((x) => { setO(x); setEdit({ job_description: x.job_description ?? "", deadline: x.deadline ?? "", url: x.url ?? "", notes: x.notes ?? "", location: x.location ?? "" }); })
      .catch(() => onClose());
  }, [id, version]);
  if (!id) return null;
  async function saveEdit() {
    try { await api.patch(`/api/opportunities/${id}`, edit); toast("Saved"); refresh(); } catch (e: any) { toast(e.message, "error"); }
  }
  async function markApplied() {
    try { const r = await api.post(`/api/opportunities/${id}/apply`); toast("Moved to your applications"); refresh(); onClose(); openApp(r.application_id); }
    catch (e: any) { toast(e.message, "error"); }
  }
  async function remove() {
    try { await api.del(`/api/opportunities/${id}`); toast("Removed"); refresh(); onClose(); } catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <Modal open={!!id} onClose={onClose} width="max-w-4xl"
      title={o ? <span>{o.position} <span className="text-ink-muted font-normal">· {o.company}</span></span> : "Loading…"}
      footer={o && <>
        <button className="btn-ghost mr-auto text-danger" onClick={remove}><Trash2 size={15} /> Remove</button>
        {o.url && <a className="btn-secondary" href={o.url} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Posting</a>}
        <button className="btn-primary" onClick={markApplied}><BriefcaseBusiness size={15} /> I've applied</button>
      </>}>
      {!o ? <Skeleton className="h-64" /> : (
        <div>
          <div className="flex flex-wrap gap-2 mb-3 text-[12.5px] text-ink-muted">
            {o.location && <span className="inline-flex items-center gap-1"><MapPin size={13} />{o.location}</span>}
            {o.deadline && <span className="inline-flex items-center gap-1"><CalendarClock size={13} />Deadline {fmtDate(o.deadline)} · {relDays(o.deadline)}</span>}
          </div>
          <Tabs value={tab} onChange={setTab} tabs={[{ id: "fit", label: "Fit & documents" }, { id: "details", label: "Details & description" }]} />
          <div className="pt-5">
            {tab === "fit" && <FitPanel kind="opportunity" refId={o.id} hasJd={(o.job_description ?? "").trim().length >= 80} />}
            {tab === "details" && (
              <div className="space-y-3">
                <div className="grid sm:grid-cols-3 gap-3">
                  <Field label="Location"><input className="input" value={edit.location} onChange={(e) => setEdit({ ...edit, location: e.target.value })} /></Field>
                  <Field label="Deadline"><input type="date" className="input num" value={edit.deadline} onChange={(e) => setEdit({ ...edit, deadline: e.target.value })} /></Field>
                  <Field label="Link"><input className="input" value={edit.url} onChange={(e) => setEdit({ ...edit, url: e.target.value })} /></Field>
                </div>
                <Field label="Notes"><input className="input" value={edit.notes} onChange={(e) => setEdit({ ...edit, notes: e.target.value })} /></Field>
                <Field label="Job description"><textarea className="textarea h-72 text-[13px]" value={edit.job_description} onChange={(e) => setEdit({ ...edit, job_description: e.target.value })} /></Field>
                <div className="flex justify-end"><button className="btn-primary" onClick={saveEdit}>Save</button></div>
              </div>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}

export { pct };
