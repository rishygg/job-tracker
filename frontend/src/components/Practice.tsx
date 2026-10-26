import { useState } from "react";
import { BookOpen, CalendarClock, Check, GraduationCap, History, Loader2, Plus, Sparkles, Target, Trash2, X } from "lucide-react";
import { api, type Dict } from "../api";
import { useApi, useApp } from "../store";
import { cls, fmtDate } from "../lib";
import { EmptyState, Modal, Skeleton } from "./ui";
import { JobProgress, isActive, useJob } from "./AiJob";
import { CategoryChip, Rating } from "./careerShared";

const SOURCE: Record<string, { label: string; icon: typeof Target }> = {
  history: { label: "From your interviews", icon: History },
  upcoming: { label: "For your next interview", icon: CalendarClock },
  focus: { label: "Weak spot", icon: Target },
  common: { label: "Common question", icon: GraduationCap },
  ai: { label: "Predicted by AI", icon: Sparkles },
  custom: { label: "Your question", icon: Plus },
};

export function PracticeTab() {
  const { data, loading } = useApi<Dict>("/api/career/practice");
  const { data: ai } = useApi<Dict>("/api/ai/status");
  const [open, setOpen] = useState<Dict | null>(null);
  const [own, setOwn] = useState("");
  if (loading && !data) return <Skeleton className="h-96" />;
  const s: Dict[] = data?.suggested ?? [];
  return (
    <div className="grid lg:grid-cols-[1fr_340px] gap-5 items-start">
      <div className="space-y-4 min-w-0">
        {data?.upcoming?.length > 0 && (
          <section className="space-y-2">
            {data!.upcoming.map((u: Dict) => <UpcomingCard key={u.application_id} u={u} ai={ai} set={data!.ai_sets?.[u.application_id]}
              job={data!.jobs?.[u.application_id]} onPractise={(q) => setOpen({ ...q, ref: `application:${u.application_id}` })} />)}
          </section>
        )}
        <section className="card">
          <div className="px-5 py-3.5 border-b border-line flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-[15px] font-semibold">Your practice plan</h2>
            <span className="text-[11.5px] text-ink-muted">Your own interviews first, then your next interviews, then your weak spots.</span>
          </div>
          {!s.length ? <EmptyState icon={<GraduationCap size={20} />} title="Nothing to practise yet">Log an interview or move an application to an interview stage.</EmptyState> : (
            <ul className="divide-y divide-line">
              {s.map((q, i) => {
                const src = SOURCE[q.source] ?? SOURCE.common;
                return (
                  <li key={i} className="px-5 py-3 flex items-start gap-3">
                    <src.icon size={15} className="text-ink-muted mt-0.5 shrink-0" aria-label={src.label} />
                    <div className="flex-1 min-w-0">
                      <div className="text-[13.5px] font-medium leading-snug">{q.question}</div>
                      <div className="flex flex-wrap items-center gap-1.5 mt-1 text-[11.5px] text-ink-muted">
                        <CategoryChip category={q.category} /><span>{q.reason}</span>
                        {q.story && <span className="inline-flex items-center gap-1 text-[#6442b4]"><BookOpen size={11} />Story: {q.story.title}</span>}
                      </div>
                    </div>
                    <button className="btn-secondary btn-sm shrink-0" onClick={() => setOpen(q)}>Practise</button>
                  </li>
                );
              })}
            </ul>
          )}
          <div className="px-5 py-3 border-t border-line flex gap-2">
            <input className="input" value={own} onChange={(e) => setOwn(e.target.value)} placeholder="Practise your own question…"
              onKeyDown={(e) => e.key === "Enter" && own.trim() && (setOpen({ question: own.trim(), source: "custom" }), setOwn(""))} />
            <button className="btn-secondary" disabled={!own.trim()} onClick={() => { setOpen({ question: own.trim(), source: "custom" }); setOwn(""); }}>Practise</button>
          </div>
        </section>
      </div>
      <aside className="space-y-4">
        {data?.focus?.length > 0 && (
          <section className="card p-4">
            <div className="eyebrow mb-2">Focus areas from your journal</div>
            <div className="flex flex-wrap gap-1">{data!.focus.map((f: Dict) => <span key={f.area} className="chip h-6">{f.area}</span>)}</div>
          </section>
        )}
        <section className="card p-4">
          <div className="eyebrow mb-2 flex items-center gap-1.5"><History size={12} />Practised</div>
          {!data?.history?.length ? <p className="text-[12.5px] text-ink-muted">Answers you write are kept here with their feedback, so you can see yourself improve.</p> : (
            <ul className="space-y-1.5">
              {data!.history.map((p: Dict) => (
                <li key={p.id}>
                  <button className="w-full text-left rounded-lg px-2 py-1.5 hover:bg-canvas" onClick={() => setOpen(p)}>
                    <div className="text-[12.5px] leading-snug line-clamp-2">{p.question}</div>
                    <div className="text-[11px] text-ink-muted mt-0.5 num">{fmtDate(p.updated_at?.slice(0, 10), false)}
                      {p.feedback?.score ? ` · feedback ${p.feedback.score}/5` : ""}{p.rating ? ` · you: ${p.rating}/5` : ""}</div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </aside>
      {open && <PracticeModal item={open} onClose={() => setOpen(null)} ai={ai} />}
    </div>
  );
}

function UpcomingCard({ u, ai, set, job: initialJob, onPractise }: { u: Dict; ai?: Dict | null; set?: Dict; job?: Dict; onPractise: (q: Dict) => void }) {
  const { toast, refresh } = useApp();
  const [job, setJob] = useJob(isActive(initialJob) ? initialJob : null, undefined, (j) => {
    refresh();
    if (j.status === "error") toast(j.error ?? "Couldn't predict questions", "error");
  });
  async function predict() {
    try { setJob((await api.post("/api/career/practice/questions", { application_id: u.application_id })).job); } catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-[13.5px]"><CalendarClock size={14} className="inline -mt-0.5 mr-1.5 text-[#3d6fd6]" /><b>{u.stage}</b> with <b>{u.company}</b> <span className="text-ink-muted">· {u.position} · {u.when}</span></div>
        {ai?.available && !isActive(job) && <button className="btn-secondary btn-sm" onClick={predict}><Sparkles size={13} /> {set ? "Predict again" : "Predict questions with AI"}</button>}
      </div>
      {isActive(job) && <div className="mt-3"><JobProgress job={job!} speed={ai?.speed} /></div>}
      {set?.questions?.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {set!.questions.map((q: Dict, i: number) => (
            <li key={i} className="flex items-start gap-2 text-[13px]">
              <Sparkles size={12} className="text-brand mt-1 shrink-0" />
              <div className="flex-1"><div>{q.question}</div>{q.reason && <div className="text-[11.5px] text-ink-muted">{q.reason}</div>}</div>
              <button className="btn-ghost btn-sm" onClick={() => onPractise(q)}>Practise</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PracticeModal({ item, onClose, ai }: { item: Dict; onClose: () => void; ai?: Dict | null }) {
  const { toast, refresh } = useApp();
  const [p, setP] = useState<Dict>({ ...item });
  const [busy, setBusy] = useState<string | null>(null);
  const reload = (id: number) => api.get(`/api/career/practice/${id}`).then((x) => setP((o) => ({ ...o, ...x }))).catch(() => {});
  const [job, setJob] = useJob(null, undefined, (j) => { if (p.id) reload(p.id); refresh(); if (j.status === "error") toast(j.error ?? "AI feedback failed", "error"); });

  async function feedback(engine: "keywords" | "ollama") {
    if (!p.answer?.trim()) return;
    setBusy(engine);
    try {
      const body = { question: p.question, category: p.category, source: p.source, ref: p.ref, answer: p.answer, rating: p.rating, engine };
      const r = p.id ? await api.patch(`/api/career/practice/${p.id}`, body) : await api.post("/api/career/practice", body);
      setP((o) => ({ ...o, id: r.id, feedback: r.feedback ?? o.feedback }));
      if (r.job) setJob(r.job);
      refresh();
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(null); }
  }
  async function saveRating(v: number | null) {
    setP((o) => ({ ...o, rating: v }));
    if (p.id) await api.patch(`/api/career/practice/${p.id}`, { rating: v }).catch(() => {});
  }
  async function remove() {
    if (!p.id) return onClose();
    await api.del(`/api/career/practice/${p.id}`); refresh(); onClose();
  }
  const fb = p.feedback;
  const words = (p.answer ?? "").trim().split(/\s+/).filter(Boolean).length;
  return (
    <Modal open onClose={onClose} title="Practise" width="max-w-3xl"
      footer={<>
        {p.id && <button className="btn-ghost mr-auto text-danger" onClick={remove}><Trash2 size={14} /> Delete</button>}
        <button className="btn-secondary" onClick={onClose}>Close</button>
        <button className="btn-secondary" disabled={!p.answer?.trim() || !!busy} onClick={() => feedback("keywords")}>{busy === "keywords" ? "Checking…" : "Quick check"}</button>
        {ai?.available && <button className="btn-primary" disabled={!p.answer?.trim() || !!busy || isActive(job)} onClick={() => feedback("ollama")}><Sparkles size={14} /> AI feedback</button>}
      </>}>
      <div className="space-y-4">
        <div>
          <div className="text-[15px] font-semibold leading-snug">{p.question}</div>
          <div className="flex flex-wrap items-center gap-2 mt-1 text-[12px] text-ink-muted"><CategoryChip category={p.category} />{p.reason}</div>
          {p.story && <div className="text-[12px] text-[#6442b4] mt-1.5 flex items-center gap-1"><BookOpen size={12} />Story that fits: {p.story.title}</div>}
        </div>
        <div>
          <textarea className="textarea h-48 text-[13.5px]" value={p.answer ?? ""} onChange={(e) => setP({ ...p, answer: e.target.value })}
            placeholder="Write your answer as you'd say it. For 'tell me about a time' questions: situation, your task, what you did, and the result." />
          <div className="flex justify-between text-[11.5px] text-ink-muted mt-1 num"><span>{words} words · about {Math.max(0, Math.round(words / 140 * 10) / 10)} min spoken</span><span>Aim for 150–250 words</span></div>
        </div>
        {isActive(job) && <JobProgress job={job!} speed={ai?.speed} />}
        {fb && (
          <section className="rounded-xl border border-line p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="eyebrow flex items-center gap-1.5">{fb.method === "ollama" ? <><Sparkles size={11} className="text-brand" />AI feedback · {fb.model}</> : "Quick check (rules)"}</div>
              <div className="text-[13px] num">Score <b>{fb.score}/5</b></div>
            </div>
            {fb.star && (
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(fb.star).map(([k, v]) => (
                  <span key={k} className={cls("chip h-6 capitalize", v ? "bg-[#e8f6f0] text-[#0a7a53] border-[#bfe6d6]" : "border-dashed border-line-strong text-ink-muted")}>
                    {v ? <Check size={11} /> : <X size={11} />}{k}
                  </span>
                ))}
              </div>
            )}
            {fb.strengths?.length > 0 && <div><div className="text-[12px] font-semibold text-[#0a7a53] mb-1">Working</div><ul className="space-y-1 text-[13px]">{fb.strengths.map((x: string, i: number) => <li key={i} className="flex gap-1.5"><Check size={13} className="mt-0.5 text-[#0e9a69] shrink-0" />{x}</li>)}</ul></div>}
            {fb.improve?.length > 0 && <div><div className="text-[12px] font-semibold text-[#a35f00] mb-1">Improve</div><ul className="space-y-1 text-[13px]">{fb.improve.map((x: string, i: number) => <li key={i} className="flex gap-1.5"><span className="text-[#a35f00] shrink-0">→</span>{x}</li>)}</ul></div>}
            {fb.better_opening && <div className="text-[13px]"><span className="text-[12px] font-semibold text-ink-soft">Stronger opening: </span>“{fb.better_opening}”</div>}
            {fb.follow_up && <div className="text-[13px] text-ink-soft"><span className="text-[12px] font-semibold">Likely follow-up: </span>{fb.follow_up}</div>}
          </section>
        )}
        <div className="flex items-center gap-3"><span className="label mb-0">How ready do you feel?</span><Rating label="Readiness" value={p.rating} onChange={saveRating} />
          {!p.id && <span className="text-[11.5px] text-ink-muted">Saved once you check your answer.</span>}</div>
        {busy && <Loader2 className="animate-spin text-ink-muted" size={14} />}
      </div>
    </Modal>
  );
}
