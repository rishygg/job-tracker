import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, BookOpen, CalendarCheck, GraduationCap, Lightbulb, MessagesSquare, NotebookPen, Plus, Repeat, Target, Trash2, TrendingDown, TrendingUp, X } from "lucide-react";
import { api, type Dict } from "../api";
import { useApi, useApp } from "../store";
import { cls, fmtDate, today } from "../lib";
import { EmptyState, Field, Modal, PageHeader, Select, Skeleton, Tabs } from "../components/ui";
import { PracticeTab } from "../components/Practice";
import { NotesTab, SkillsTab } from "../components/CareerExtras";
import { CAT_COLOR, Rating, useCareerMeta } from "../components/careerShared";

type Tab = "journal" | "practice" | "skills" | "notes";
const TABS: { id: Tab; label: string; icon: typeof BookOpen }[] = [
  { id: "journal", label: "Interview journal", icon: MessagesSquare },
  { id: "practice", label: "Practice", icon: GraduationCap },
  { id: "skills", label: "Skills report", icon: Target },
  { id: "notes", label: "Industry notes", icon: Lightbulb },
];

export default function Career() {
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab");
  const tab = (raw as Tab) || "journal";
  const setTab = (t: Tab) => { const p = new URLSearchParams(params); p.set("tab", t); p.delete("log"); p.delete("date"); setParams(p, { replace: true }); };
  if (raw === "stories") return <Navigate to="/me?tab=stories" replace />;
  return (
    <div className="max-w-[1180px]">
      <PageHeader title="Career development" subtitle="Learn from every interview, practise what you find hardest, and close the skill gaps that matter for the roles you want." />
      <Tabs value={tab} onChange={setTab} tabs={TABS.map((t) => ({ id: t.id, label: <span className="inline-flex items-center gap-1.5"><t.icon size={14} />{t.label}</span> }))} />
      <div className="mt-5">
        {tab === "journal" && <Journal />}
        {tab === "practice" && <PracticeTab />}
        {tab === "skills" && <SkillsTab />}
        {tab === "notes" && <NotesTab />}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ journal
function Journal() {
  const { data, loading } = useApi<Dict>("/api/career/interviews");
  const [params, setParams] = useSearchParams();
  const [editing, setEditing] = useState<Dict | null>(null);
  useEffect(() => {
    const log = params.get("log");
    if (log) setEditing({ application_id: Number(log), date: params.get("date") || today(), questions: [] });
  }, []);
  const close = () => {
    setEditing(null);
    if (params.get("log")) { const p = new URLSearchParams(params); p.delete("log"); p.delete("date"); setParams(p, { replace: true }); }
  };

  if (loading && !data) return <div className="grid lg:grid-cols-[1fr_360px] gap-5"><Skeleton className="h-96" /><Skeleton className="h-96" /></div>;
  const ivs: Dict[] = data?.interviews ?? [];
  const th = data?.themes;
  return (
    <div className="grid lg:grid-cols-[1fr_360px] gap-5 items-start">
      <div className="space-y-4 min-w-0">
        {data?.to_log?.length > 0 && (
          <section className="card p-4 border-info-line bg-info-soft">
            <div className="flex items-center gap-2 text-[13px] font-semibold"><NotebookPen size={15} className="text-info-bright" />Not in your journal yet</div>
            <ul className="mt-2 space-y-1.5">
              {data!.to_log.map((x: Dict) => (
                <li key={`${x.application_id}-${x.date}`} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
                  <span><b>{x.company}</b> · {x.position} <span className="text-ink-muted">· {x.stage} on {fmtDate(x.date)}</span></span>
                  <button className="btn-primary btn-sm" onClick={() => setEditing({ application_id: x.application_id, date: x.date, round: x.stage === "Final interview" ? "Final interview" : "First interview", questions: [] })}>Log it</button>
                </li>
              ))}
            </ul>
          </section>
        )}
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold">Your interviews <span className="text-ink-muted font-normal num">{ivs.length || ""}</span></h2>
          <button className="btn-primary" onClick={() => setEditing({ date: today(), questions: [] })}><Plus size={15} /> Log interview</button>
        </div>
        {!ivs.length ? (
          <div className="card"><EmptyState art="chat" title="Log your first interview"
            action={<button className="btn-primary" onClick={() => setEditing({ date: today(), questions: [] })}><Plus size={15} /> Log interview</button>}>
            Right after an interview, note the questions, how you think each answer went, what was hard and any feedback. After a few, recurring themes appear here and your practice plan adapts to them.
          </EmptyState></div>
        ) : (
          <ul className="space-y-2">
            {ivs.map((i) => <InterviewCard key={i.id} iv={i} onOpen={() => setEditing(i)} />)}
          </ul>
        )}
      </div>
      <Themes th={th} />
      {editing && <InterviewEditor initial={editing} onClose={close} />}
    </div>
  );
}

function InterviewCard({ iv, onOpen }: { iv: Dict; onOpen: () => void }) {
  const low = iv.questions.filter((q: Dict) => q.rating && q.rating <= 2).length;
  return (
    <li>
      <button className="card w-full text-left p-4 hover:border-line-strong transition" onClick={onOpen}>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-[14px] font-semibold">{iv.company}<span className="font-normal text-ink-muted"> · {iv.position}</span></div>
            <div className="text-[12px] text-ink-muted mt-0.5">{fmtDate(iv.date)}{iv.round ? ` · ${iv.round}` : ""}{iv.format ? ` · ${iv.format}` : ""}</div>
          </div>
          <div className="flex items-center gap-2 text-[12px]">
            {iv.rating && <span className="num text-ink-soft">Felt <b>{iv.rating}/5</b></span>}
            {iv.outcome && <span className={cls("chip h-5 text-[10.5px]", iv.outcome === "Passed" && "bg-ok-soft text-ok border-ok-line", iv.outcome === "Rejected" && "bg-neutral-soft")}>{iv.outcome}</span>}
          </div>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[12px] text-ink-soft">
          <span>{iv.questions.length} question{iv.questions.length === 1 ? "" : "s"}</span>
          {low > 0 && <span className="text-warn">{low} rated weak</span>}
          {iv.struggled && <span className="truncate max-w-[420px]">Hard: {iv.struggled}</span>}
        </div>
      </button>
    </li>
  );
}

function Themes({ th }: { th?: Dict }) {
  if (!th || !th.interviews) {
    return (
      <aside className="card p-5">
        <h3 className="text-[14px] font-semibold">Recurring themes</h3>
        <p className="text-[12.5px] text-ink-muted mt-1">Once you've logged a couple of interviews, this shows the question types you get most, where your answers are weakest, questions that keep coming back, and skills you get asked about but have no story for.</p>
      </aside>
    );
  }
  const maxCat = Math.max(1, ...th.categories.map((c: Dict) => c.count));
  return (
    <aside className="space-y-4">
      {th.focus?.length > 0 && (
        <section className="card p-4">
          <div className="eyebrow mb-2 flex items-center gap-1.5"><Target size={12} />Work on next</div>
          <ol className="space-y-1.5">
            {th.focus.map((f: Dict, i: number) => (
              <li key={f.area} className="flex items-center gap-2 text-[13px]"><span className="num w-5 h-5 rounded-full bg-canvas border border-line text-[11px] flex items-center justify-center shrink-0">{i + 1}</span>{f.area}</li>
            ))}
          </ol>
          <p className="text-[11.5px] text-ink-muted mt-2">From questions you rated 1–2, what you said was hard, and feedback. Your practice plan uses this.</p>
        </section>
      )}
      <section className="card p-4">
        <div className="flex items-baseline justify-between mb-2">
          <div className="eyebrow">Question types</div>
          <span className="text-[11.5px] text-ink-muted num">{th.questions} questions · {th.interviews} interviews</span>
        </div>
        <ul className="space-y-1.5">
          {th.categories.map((c: Dict) => (
            <li key={c.category} className="text-[12.5px]">
              <div className="flex justify-between"><span>{c.category}</span><span className="num text-ink-muted">{c.count}{c.avg_rating !== null ? <> · avg <b className={cls(c.avg_rating < 3 ? "text-warn" : "text-ink-soft")}>{c.avg_rating}</b>/5</> : null}</span></div>
              <div className="h-1.5 rounded-full bg-canvas mt-1 overflow-hidden"><div className="h-full rounded-full" style={{ width: `${(c.count / maxCat) * 100}%`, background: CAT_COLOR[c.category] ?? "rgb(var(--ink-faint))" }} /></div>
            </li>
          ))}
        </ul>
        {th.rating_trend !== null && (
          <div className="mt-3 text-[12px] flex items-center gap-1.5 text-ink-soft">
            {th.rating_trend >= 0 ? <TrendingUp size={13} className="text-ok-bright" /> : <TrendingDown size={13} className="text-warn" />}
            How interviews feel: {th.rating_trend >= 0 ? "+" : ""}{th.rating_trend} points, recent half vs earlier half
          </div>
        )}
      </section>
      {th.repeated?.length > 0 && (
        <section className="card p-4">
          <div className="eyebrow mb-2 flex items-center gap-1.5"><Repeat size={12} />Asked more than once</div>
          <ul className="space-y-2">
            {th.repeated.map((r: Dict, i: number) => (
              <li key={i} className="text-[12.5px]"><div>“{r.question}”</div><div className="text-ink-muted text-[11.5px] mt-0.5">{r.times}× · {r.companies.join(", ")}{r.avg_rating ? ` · avg ${r.avg_rating}/5` : ""}</div></li>
            ))}
          </ul>
        </section>
      )}
      {th.story_gaps?.length > 0 && (
        <section className="card p-4">
          <div className="eyebrow mb-2 flex items-center gap-1.5"><AlertTriangle size={12} />Asked about, no story yet</div>
          <div className="flex flex-wrap gap-1">{th.story_gaps.map((g: Dict) => <span key={g.competency} className="chip h-6 border-dashed border-line-strong">{g.competency} <span className="num text-ink-faint">{g.asked}×</span></span>)}</div>
          <p className="text-[11.5px] text-ink-muted mt-2">Add a story for these in your <Link to="/me?tab=stories" className="text-brand hover:underline">story bank</Link> so you're not improvising.</p>
        </section>
      )}
      {th.feedback?.length > 0 && (
        <section className="card p-4">
          <div className="eyebrow mb-2">Feedback you've received</div>
          <ul className="space-y-2">{th.feedback.map((f: Dict, i: number) => <li key={i} className="text-[12.5px]"><span className="text-ink-muted">{f.company} · {fmtDate(f.date, false)}:</span> {f.text}</li>)}</ul>
        </section>
      )}
    </aside>
  );
}

// ------------------------------------------------------------------ editor
function InterviewEditor({ initial, onClose }: { initial: Dict; onClose: () => void }) {
  const { toast, refresh } = useApp();
  const meta = useCareerMeta();
  const stories = useApi<Dict>("/api/career/stories").data?.stories ?? [];
  const [iv, setIv] = useState<Dict>({ questions: [], ...initial });
  const [paste, setPaste] = useState("");
  const [saving, setSaving] = useState(false);
  const set = (k: string, v: unknown) => setIv((x) => ({ ...x, [k]: v }));
  const setQ = (i: number, patch: Dict) => setIv((x) => ({ ...x, questions: x.questions.map((q: Dict, j: number) => (j === i ? { ...q, ...patch } : q)) }));
  const apps = meta?.applications ?? [];
  const appOptions = useMemo(() => apps.map((a: Dict) => ({ value: String(a.id), label: `${a.company} · ${a.position}` })), [apps]);

  async function autoCategory(i: number) {
    const q = iv.questions[i];
    if (!q.question?.trim() || q.category_set) return;
    try { const r = await api.post("/api/career/categorise", { question: q.question }); setQ(i, { category: r.category, competencies: r.competencies }); } catch { /* ignore */ }
  }
  function addPasted() {
    const lines = paste.split(/\n+/).map((l) => l.replace(/^\s*([-•*]|\d+[.)])\s*/, "").trim()).filter((l) => l.length > 3);
    if (!lines.length) return;
    setIv((x) => ({ ...x, questions: [...x.questions, ...lines.map((question) => ({ question }))] }));
    setPaste("");
    Promise.all(lines.map((question) => api.post("/api/career/categorise", { question }).catch(() => null))).then((rs) =>
      setIv((x) => {
        const start = x.questions.length - lines.length;
        return { ...x, questions: x.questions.map((q: Dict, j: number) => (j >= start && rs[j - start] ? { ...q, ...rs[j - start] } : q)) };
      }));
  }
  async function save() {
    setSaving(true);
    const { id: _id, ...rest } = iv;
    const body = { ...rest, application_id: iv.application_id || null, questions: iv.questions.filter((q: Dict) => q.question?.trim()) };
    try {
      if (iv.id) await api.patch(`/api/career/interviews/${iv.id}`, body);
      else await api.post("/api/career/interviews", body);
      refresh(); toast("Interview saved"); onClose();
    } catch (e: any) { toast(e.message, "error"); } finally { setSaving(false); }
  }
  async function remove() {
    try { await api.del(`/api/career/interviews/${iv.id}`); refresh(); toast("Interview removed"); onClose(); } catch (e: any) { toast(e.message, "error"); }
  }

  return (
    <Modal open onClose={onClose} title={iv.id ? `${iv.company} · ${fmtDate(iv.date)}` : "Log an interview"} width="max-w-4xl"
      footer={<>
        {iv.id && <button className="btn-ghost mr-auto text-danger" onClick={remove}><Trash2 size={14} /> Delete</button>}
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={saving || (!iv.application_id && !iv.company?.trim())} onClick={save}>{saving ? "Saving…" : "Save interview"}</button>
      </>}>
      <div className="space-y-5">
        <div className="grid sm:grid-cols-[1.4fr_1fr_1fr] gap-3">
          <Field label="Application">
            <Select value={iv.application_id ? String(iv.application_id) : ""} placeholder="Not in my tracker"
              onChange={(v) => setIv((x) => ({ ...x, application_id: v ? Number(v) : null, company: v ? undefined : x.company }))} options={appOptions} />
          </Field>
          <Field label="Date"><input type="date" className="input num" value={iv.date ?? ""} onChange={(e) => set("date", e.target.value)} /></Field>
          <Field label="Round"><Select value={iv.round ?? ""} placeholder="Choose" onChange={(v) => set("round", v || null)} options={meta?.rounds ?? []} /></Field>
        </div>
        {!iv.application_id && (
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Company"><input className="input" value={iv.company ?? ""} onChange={(e) => set("company", e.target.value)} /></Field>
            <Field label="Position"><input className="input" value={iv.position ?? ""} onChange={(e) => set("position", e.target.value)} /></Field>
          </div>
        )}
        <div className="grid sm:grid-cols-[1fr_1fr_auto_1fr] gap-3 items-end">
          <Field label="Format"><Select value={iv.format ?? ""} placeholder="Choose" onChange={(v) => set("format", v || null)} options={meta?.formats ?? []} /></Field>
          <Field label="Interviewers"><input className="input" value={iv.interviewers ?? ""} onChange={(e) => set("interviewers", e.target.value)} placeholder="Names or roles" /></Field>
          <div><span className="label">How it felt overall</span><Rating label="Overall" value={iv.rating} onChange={(v) => set("rating", v)} /></div>
          <Field label="Outcome"><Select value={iv.outcome ?? ""} placeholder="Not known yet" onChange={(v) => set("outcome", v || null)} options={meta?.outcomes ?? []} /></Field>
        </div>

        <section>
          <div className="flex items-baseline justify-between mb-2">
            <div className="eyebrow">Questions asked</div>
            <span className="text-[11.5px] text-ink-muted">Rate each answer 1–5. The type is detected for you; change it if it's wrong.</span>
          </div>
          <ul className="space-y-2">
            {iv.questions.map((q: Dict, i: number) => (
              <li key={q.id ?? `n${i}`} className="rounded-lg border border-line p-3">
                <div className="flex gap-2">
                  <textarea className="textarea h-[38px] min-h-[38px] flex-1 text-[13px]" rows={1} value={q.question ?? ""} placeholder="The question, as close to their wording as you remember"
                    onChange={(e) => setQ(i, { question: e.target.value })} onBlur={() => autoCategory(i)} />
                  <button className="btn-ghost btn-sm self-start" aria-label="Remove question" onClick={() => setIv((x) => ({ ...x, questions: x.questions.filter((_: Dict, j: number) => j !== i) }))}><X size={14} /></button>
                </div>
                <div className="grid sm:grid-cols-[180px_auto_1fr_200px] gap-2 mt-2 items-center">
                  <Select className="h-8 text-[12px]" value={q.category ?? ""} placeholder="Type" onChange={(v) => setQ(i, { category: v || null, category_set: true })} options={meta?.categories ?? []} />
                  <Rating label="How your answer went" value={q.rating} onChange={(v) => setQ(i, { rating: v })} />
                  <input className="input h-8 text-[12.5px]" value={q.answer_notes ?? ""} placeholder="What you said / should have said" onChange={(e) => setQ(i, { answer_notes: e.target.value })} />
                  <Select className="h-8 text-[12px]" value={q.story_id ? String(q.story_id) : ""} placeholder="Story used (optional)"
                    onChange={(v) => setQ(i, { story_id: v ? Number(v) : null })} options={stories.map((s: Dict) => ({ value: String(s.id), label: s.title }))} />
                </div>
              </li>
            ))}
          </ul>
          <div className="grid sm:grid-cols-[1fr_auto] gap-2 mt-2">
            <textarea className="textarea h-16 text-[12.5px]" value={paste} onChange={(e) => setPaste(e.target.value)} placeholder="Type or paste questions, one per line, then click Add" />
            <div className="flex sm:flex-col gap-2">
              <button className="btn-secondary btn-sm" disabled={!paste.trim()} onClick={addPasted}><Plus size={13} /> Add</button>
              <button className="btn-ghost btn-sm" onClick={() => setIv((x) => ({ ...x, questions: [...x.questions, { question: "" }] }))}>Blank row</button>
            </div>
          </div>
        </section>

        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="What went well"><textarea className="textarea h-20" value={iv.went_well ?? ""} onChange={(e) => set("went_well", e.target.value)} /></Field>
          <Field label="What you struggled with"><textarea className="textarea h-20" value={iv.struggled ?? ""} onChange={(e) => set("struggled", e.target.value)} placeholder="e.g. Explaining my thesis simply; a SQL question" /></Field>
          <Field label="Feedback received"><textarea className="textarea h-20" value={iv.feedback ?? ""} onChange={(e) => set("feedback", e.target.value)} /></Field>
          <Field label="Next steps"><textarea className="textarea h-20" value={iv.next_steps ?? ""} onChange={(e) => set("next_steps", e.target.value)} placeholder="e.g. Case study due Friday; send thank-you" /></Field>
        </div>
        <p className="text-[11.5px] text-ink-muted flex items-center gap-1.5"><CalendarCheck size={12} />Tip: log it the same day, while you still remember the wording.</p>
      </div>
    </Modal>
  );
}
