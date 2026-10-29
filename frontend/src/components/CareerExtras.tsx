import { useMemo, useState } from "react";
import { AlertTriangle, Check, ExternalLink, Plus, Search, ShieldAlert, Sparkles, Target, Trash2, TrendingUp } from "lucide-react";
import { api, type Dict } from "../api";
import { useApi, useApp } from "../store";
import { cls, fmtDate, pct } from "../lib";
import { EmptyState, Field, Modal, Select, Skeleton } from "./ui";
import { FilterBar } from "./FilterBar";
import { useCareerMeta } from "./careerShared";
import { DigestPanel } from "./Digest";

// ------------------------------------------------------------------ story bank
const STAR = [
  { k: "situation", label: "Situation", hint: "Where, when, what was at stake (1-2 sentences)" },
  { k: "task", label: "Task", hint: "What you specifically had to do" },
  { k: "action", label: "Action", hint: "What YOU did, step by step: the longest part" },
  { k: "result", label: "Result", hint: "What changed, with a number if you can; what you learned" },
];

export function StoriesTab() {
  const { data, loading } = useApi<Dict>("/api/career/stories");
  const { toast, refresh } = useApp();
  const [open, setOpen] = useState<Dict | null>(null);
  if (loading && !data) return <Skeleton className="h-96" />;
  const stories: Dict[] = data?.stories ?? [];
  async function fromEvidence(id: number) {
    try { const r = await api.post("/api/career/stories", { evidence_id: id }); refresh(); const d = await api.get("/api/career/stories"); setOpen(d.stories.find((s: Dict) => s.id === r.id)); }
    catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <div className="grid lg:grid-cols-[1fr_340px] gap-5 items-start">
      <div className="space-y-3 min-w-0">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold">Your stories <span className="text-ink-muted font-normal num">{stories.length || ""}</span></h2>
          <button className="btn-primary" onClick={() => setOpen({ competencies: [] })}><Plus size={15} /> New story</button>
        </div>
        {!stories.length ? (
          <div className="card"><EmptyState art="book" title="Build a few reusable stories">
            Five or six well-prepared examples cover most behavioural questions. Start from the suggestions on the right: they come from the strongest lines in your entries under Me.
          </EmptyState></div>
        ) : (
          <ul className="grid sm:grid-cols-2 gap-3">
            {stories.map((s) => {
              const filled = STAR.filter((x) => (s[x.k] || "").trim()).length;
              return (
                <li key={s.id}>
                  <button className="card w-full h-full text-left p-4 hover:border-line-strong transition flex flex-col" onClick={() => setOpen(s)}>
                    <div className="text-[13.5px] font-semibold leading-snug">{s.title}</div>
                    <div className="flex flex-wrap gap-1 mt-2">{(s.competencies ?? []).slice(0, 4).map((c: string) => <span key={c} className="chip h-5 text-[10.5px]">{c}</span>)}</div>
                    <div className="mt-auto pt-3 flex items-center justify-between text-[11.5px] text-ink-muted">
                      <span className="inline-flex items-center gap-1.5" aria-label={`${filled} of 4 STAR parts written`}>
                        {STAR.map((x) => <span key={x.k} title={x.label} className={cls("w-5 h-5 rounded text-[10px] font-bold flex items-center justify-center", (s[x.k] || "").trim() ? "bg-brand text-white" : "bg-canvas border border-dashed border-line-strong text-ink-faint")}>{x.label[0]}</span>)}
                      </span>
                      <span>{s.used?.length ? `Used in ${s.used.length} interview${s.used.length > 1 ? "s" : ""}` : "Not used yet"}</span>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <aside className="card p-4">
        <div className="eyebrow mb-1 flex items-center gap-1.5"><Sparkles size={12} />Good material from your CV</div>
        <p className="text-[11.5px] text-ink-muted mb-3">Lines with results, scale or other people involved, not yet in a story.</p>
        {!data?.suggestions?.length ? <p className="text-[12.5px] text-ink-muted">Nothing new. Add achievements to your entries (Me → Experience &amp; education).</p> : (
          <ul className="space-y-2">
            {data.suggestions.map((x: Dict) => (
              <li key={x.evidence_id} className="rounded-lg border border-line p-2.5">
                <div className="text-[12.5px] leading-snug">{x.text}</div>
                {x.context && <div className="text-[11px] text-ink-muted mt-0.5">{x.context}</div>}
                <div className="flex items-center justify-between mt-1.5">
                  <div className="flex flex-wrap gap-1">{x.competencies.slice(0, 2).map((c: string) => <span key={c} className="chip h-5 text-[10px]">{c}</span>)}</div>
                  <button className="btn-ghost btn-sm text-brand" onClick={() => fromEvidence(x.evidence_id)}>Make a story</button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </aside>
      {open && <StoryEditor initial={open} onClose={() => setOpen(null)} />}
    </div>
  );
}

function StoryEditor({ initial, onClose }: { initial: Dict; onClose: () => void }) {
  const { toast, refresh } = useApp();
  const meta = useCareerMeta();
  const [s, setS] = useState<Dict>({ competencies: [], ...initial });
  async function save() {
    const body = { title: s.title, situation: s.situation, task: s.task, action: s.action, result: s.result, competencies: s.competencies };
    try {
      if (s.id) await api.patch(`/api/career/stories/${s.id}`, body); else await api.post("/api/career/stories", body);
      refresh(); toast("Story saved"); onClose();
    } catch (e: any) { toast(e.message, "error"); }
  }
  async function remove() { await api.del(`/api/career/stories/${s.id}`); refresh(); onClose(); }
  const toggle = (c: string) => setS({ ...s, competencies: s.competencies.includes(c) ? s.competencies.filter((x: string) => x !== c) : [...s.competencies, c] });
  const words = STAR.reduce((n, x) => n + (s[x.k] || "").trim().split(/\s+/).filter(Boolean).length, 0);
  return (
    <Modal open onClose={onClose} title={s.id ? "Edit story" : "New story"} width="max-w-3xl"
      footer={<>{s.id && <button className="btn-ghost mr-auto text-danger" onClick={remove}><Trash2 size={14} /> Delete</button>}
        <button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!s.title?.trim()} onClick={save}>Save story</button></>}>
      <div className="space-y-3">
        <Field label="Short title"><input className="input" value={s.title ?? ""} onChange={(e) => setS({ ...s, title: e.target.value })} placeholder="e.g. Automating MRI quality checks" /></Field>
        {STAR.map((x) => (
          <Field key={x.k} label={x.label} hint={x.hint}>
            <textarea className={cls("textarea", x.k === "action" ? "h-28" : "h-16")} value={s[x.k] ?? ""} onChange={(e) => setS({ ...s, [x.k]: e.target.value })} />
          </Field>
        ))}
        <div>
          <span className="label">Shows (used to match stories to questions)</span>
          <div className="flex flex-wrap gap-1">{(meta?.competencies ?? []).map((c: string) => (
            <button key={c} type="button" onClick={() => toggle(c)} aria-pressed={s.competencies.includes(c)}
              className={cls("chip h-6", s.competencies.includes(c) && "bg-brand-soft text-brand-strong border-brand/30")}>{s.competencies.includes(c) && <Check size={11} />}{c}</button>
          ))}</div>
        </div>
        <div className="text-[11.5px] text-ink-muted num">{words} words · about {Math.round(words / 140 * 10) / 10} min spoken (aim for 1.5–2)</div>
        {s.tips?.length > 0 && <ul className="text-[12px] text-warn-strong space-y-0.5">{s.tips.map((t: string) => <li key={t} className="flex gap-1.5"><AlertTriangle size={12} className="mt-0.5 shrink-0" />{t}</li>)}</ul>}
        {s.used?.length > 0 && (
          <div><div className="eyebrow mb-1">Used for</div><ul className="text-[12.5px] space-y-0.5">{s.used.map((u: Dict, i: number) => <li key={i}>“{u.question}” <span className="text-ink-muted">· {u.company}{u.rating ? ` · ${u.rating}/5` : ""}</span></li>)}</ul></div>
        )}
      </div>
    </Modal>
  );
}

// ------------------------------------------------------------------ skills report
export function SkillsTab() {
  const { filterQuery } = useApp();
  const { data, loading } = useApi<Dict>(`/api/career/skills${filterQuery()}`);
  const [showAll, setShowAll] = useState(false);
  if (loading && !data) return <Skeleton className="h-96" />;
  if (!data?.jobs) return (
    <div className="space-y-4"><FilterBar />
      <div className="card"><EmptyState art="target" title="No job descriptions yet">Paste job descriptions into your applications or Inbox jobs. The report counts the skills they ask for and compares them with your CV.</EmptyState></div></div>
  );
  const rows: Dict[] = showAll ? data.skills : data.skills.slice(0, 15);
  const max = Math.max(...data.skills.map((r: Dict) => r.share), 0.01);
  return (
    <div className="space-y-4">
      <FilterBar />
      <p className="text-[12.5px] text-ink-muted">Across <b className="num text-ink">{data.jobs}</b> job descriptions (your applications and Inbox jobs){data.recent_jobs ? <>, <b className="num text-ink">{data.recent_jobs}</b> from the last 60 days</> : null}. “You have it” means it's in your entries or skills list.{data.digests ? <> Includes skills a local model found in <b className="num text-ink">{data.digests}</b> of them.</> : null}</p>
      <DigestPanel compact />
      <div className="grid lg:grid-cols-[1fr_360px] gap-5 items-start">
        <section className="card p-5">
          <h3 className="text-[14px] font-semibold mb-3">Most requested skills</h3>
          <ul className="space-y-2">
            {rows.map((r) => (
              <li key={r.skill} className="grid grid-cols-[150px_1fr_auto] items-center gap-3 text-[12.5px]">
                <span className="truncate" title={r.examples?.join("\n")}>{r.label ?? r.skill}</span>
                <div className="h-2.5 rounded-full bg-canvas overflow-hidden">
                  <div className={cls("h-full rounded-full", r.have ? "bg-brand" : "bg-[repeating-linear-gradient(45deg,#d97f06_0_4px,#f2c58a_4px_8px)]")} style={{ width: `${(r.share / max) * 100}%` }} />
                </div>
                <span className="num text-ink-muted w-[110px] text-right">{pct(r.share)} · {r.have ? <span className="text-brand inline-flex items-center gap-0.5"><Check size={11} />have</span> : <span className="text-warn">missing</span>}</span>
              </li>
            ))}
          </ul>
          {data.skills.length > 15 && <button className="btn-ghost btn-sm mt-3" onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer" : `Show all ${data.skills.length}`}</button>}
          <p className="text-[11px] text-ink-muted mt-3">Solid bar: in your profile. Striped bar: asked for but not in your profile.</p>
        </section>
        <aside className="space-y-4">
          <SkillList title="Gaps worth closing" icon={<Target size={12} />} items={data.top_gaps} hint="Asked for most often, not in your CV yet." />
          {data.emerging?.length > 0 && <SkillList title="Asked for more lately" icon={<TrendingUp size={12} />} items={data.emerging} trend hint="More common in the last 60 days than before." />}
          {data.missing_essentials?.length > 0 && (
            <section className="card p-4">
              <div className="eyebrow mb-1 flex items-center gap-1.5"><AlertTriangle size={12} />Essentials you were missing</div>
              <p className="text-[11.5px] text-ink-muted mb-2">From the fit analyses of {data.fits_counted} jobs: requirements marked essential that your CV didn't show.</p>
              <ul className="space-y-1.5">{data.missing_essentials.map((m: Dict) => (
                <li key={m.requirement} className="text-[12.5px]"><span>{m.requirement}</span> <span className="text-ink-muted num">· {m.jobs} job{m.jobs > 1 ? "s" : ""}</span>
                  {m.examples?.length > 0 && <div className="text-[11px] text-ink-faint truncate">{m.examples.join(" · ")}</div>}</li>
              ))}</ul>
            </section>
          )}
          <ResultsBy title="Where you get interviews · industry" rows={data.by_industry} />
          <ResultsBy title="Where you get interviews · seniority" rows={data.by_seniority} />
          {data.blockers?.length > 0 && (
            <section className="card p-4">
              <div className="eyebrow mb-2 flex items-center gap-1.5"><ShieldAlert size={12} />Hard blockers seen</div>
              <ul className="text-[12.5px] space-y-1">{data.blockers.map((b: Dict) => <li key={b.type} className="flex justify-between"><span>{b.type}</span><span className="num text-ink-muted">{b.jobs} job{b.jobs > 1 ? "s" : ""}</span></li>)}</ul>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}

function ResultsBy({ title, rows }: { title: string; rows?: Dict[] }) {
  if (!rows?.length) return null;
  const best = Math.max(...rows.map((r) => r.interview_rate), 0.01);
  return (
    <section className="card p-4">
      <div className="eyebrow mb-1">{title}</div>
      <p className="text-[11.5px] text-ink-muted mb-2">Applications whose description was read with Ollama. Small groups are noisy.</p>
      <ul className="space-y-1.5">
        {rows.map((r) => (
          <li key={r.label} className="grid grid-cols-[1fr_70px_auto] items-center gap-2 text-[12.5px]">
            <span className="truncate" title={r.label}>{r.label}</span>
            <div className="h-1.5 rounded-full bg-canvas overflow-hidden"><div className="h-full rounded-full bg-violet" style={{ width: `${(r.interview_rate / best) * 100}%` }} /></div>
            <span className="num text-ink-muted text-right w-[86px]" title={`${r.responses} responses`}>{r.interviews}/{r.applied} · {pct(r.interview_rate)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function SkillList({ title, icon, items, hint, trend }: { title: string; icon: React.ReactNode; items: Dict[]; hint: string; trend?: boolean }) {
  if (!items?.length) return null;
  return (
    <section className="card p-4">
      <div className="eyebrow mb-1 flex items-center gap-1.5">{icon}{title}</div>
      <p className="text-[11.5px] text-ink-muted mb-2">{hint}</p>
      <ul className="space-y-1">
        {items.map((r) => (
          <li key={r.skill} className="flex justify-between text-[12.5px]">
            <span>{r.label ?? r.skill}{r.have && <Check size={11} className="inline ml-1 text-brand" aria-label="you have it" />}</span>
            <span className="num text-ink-muted">{trend ? `+${Math.round(r.trend * 100)} pts` : `${r.jobs} job${r.jobs > 1 ? "s" : ""}`}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ------------------------------------------------------------------ industry notes
export function NotesTab() {
  const { data, loading } = useApi<Dict>("/api/career/notes");
  const meta = useCareerMeta();
  const [industry, setIndustry] = useState<string>("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Dict | null>(null);
  const notes: Dict[] = data?.notes ?? [];
  const counts = useMemo(() => {
    const c = new Map<string, number>();
    notes.forEach((n) => c.set(n.industry || "General", (c.get(n.industry || "General") ?? 0) + 1));
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [notes]);
  if (loading && !data) return <Skeleton className="h-96" />;
  const shown = notes.filter((n) => (!industry || (n.industry || "General") === industry)
    && (!q || `${n.title} ${n.body ?? ""} ${n.company ?? ""} ${(n.tags ?? []).join(" ")}`.toLowerCase().includes(q.toLowerCase())));
  const st = industry ? data?.industry_stats?.[industry] : null;
  return (
    <div className="grid lg:grid-cols-[240px_1fr] gap-5 items-start">
      <aside className="card p-3">
        <button className={cls("w-full text-left px-2.5 h-8 rounded-md text-[13px] flex justify-between items-center", !industry ? "bg-brand-soft text-brand-strong font-medium" : "hover:bg-canvas")} onClick={() => setIndustry("")}>All notes <span className="num text-[11.5px]">{notes.length}</span></button>
        {counts.map(([k, v]) => (
          <button key={k} className={cls("w-full text-left px-2.5 h-8 rounded-md text-[13px] flex justify-between items-center gap-2", industry === k ? "bg-brand-soft text-brand-strong font-medium" : "hover:bg-canvas")} onClick={() => setIndustry(k)}>
            <span className="truncate">{k}</span><span className="num text-[11.5px]">{v}</span></button>
        ))}
      </aside>
      <div className="space-y-3 min-w-0">
        <div className="flex flex-wrap gap-2">
          <div className="relative flex-1 min-w-[200px]"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
            <input className="input pl-8" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search notes" /></div>
          <button className="btn-primary" onClick={() => setOpen({ industry: industry && industry !== "General" ? industry : "", tags: [] })}><Plus size={15} /> New note</button>
        </div>
        {st && (
          <div className="rounded-lg bg-canvas px-4 py-2.5 text-[12.5px] text-ink-soft">Your record in {industry}: <b className="num">{st.applications}</b> applications · <b className="num">{st.interviews}</b> reached interview{st.response_rate !== null ? <> · <b className="num">{pct(st.response_rate)}</b> response rate</> : null}</div>
        )}
        {!shown.length ? (
          <div className="card"><EmptyState art="notes" title={notes.length ? "No notes match" : "Keep what you learn about each industry"}>
            Hiring cycles, who the big employers are, what interviewers there care about, salary ranges, people you've talked to. Notes are grouped by industry, next to your results in it.
          </EmptyState></div>
        ) : (
          <ul className="space-y-2">
            {shown.map((n) => (
              <li key={n.id}>
                <button className="card w-full text-left p-4 hover:border-line-strong transition" onClick={() => setOpen(n)}>
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="text-[14px] font-semibold">{n.title}</span>
                    <span className="text-[11.5px] text-ink-muted">{[n.industry, n.company].filter(Boolean).join(" · ")} · {fmtDate(n.updated_at?.slice(0, 10), false)}</span>
                  </div>
                  {n.body && <p className="text-[13px] text-ink-soft mt-1 line-clamp-3 whitespace-pre-line">{n.body}</p>}
                  {n.tags?.length > 0 && <div className="flex flex-wrap gap-1 mt-2">{n.tags.map((t: string) => <span key={t} className="chip h-5 text-[10.5px]">{t}</span>)}</div>}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {open && <NoteEditor initial={open} industries={meta?.industries ?? []} onClose={() => setOpen(null)} />}
    </div>
  );
}

function NoteEditor({ initial, industries, onClose }: { initial: Dict; industries: string[]; onClose: () => void }) {
  const { toast, refresh } = useApp();
  const [n, setN] = useState<Dict>({ ...initial, tagText: (initial.tags ?? []).join(", ") });
  async function save() {
    const body = { title: n.title, industry: n.industry || null, company: n.company, link: n.link, body: n.body,
      tags: (n.tagText ?? "").split(",").map((t: string) => t.trim()).filter(Boolean) };
    try { if (n.id) await api.patch(`/api/career/notes/${n.id}`, body); else await api.post("/api/career/notes", body); refresh(); onClose(); }
    catch (e: any) { toast(e.message, "error"); }
  }
  async function remove() { await api.del(`/api/career/notes/${n.id}`); refresh(); onClose(); }
  return (
    <Modal open onClose={onClose} title={n.id ? "Edit note" : "New note"} width="max-w-2xl"
      footer={<>{n.id && <button className="btn-ghost mr-auto text-danger" onClick={remove}><Trash2 size={14} /> Delete</button>}
        <button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!n.title?.trim()} onClick={save}>Save note</button></>}>
      <div className="space-y-3">
        <Field label="Title"><input className="input" value={n.title ?? ""} onChange={(e) => setN({ ...n, title: e.target.value })} placeholder="e.g. How pharma graduate programmes hire" /></Field>
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Industry"><Select value={n.industry ?? ""} placeholder="General" onChange={(v) => setN({ ...n, industry: v })} options={industries} /></Field>
          <Field label="Company (optional)"><input className="input" value={n.company ?? ""} onChange={(e) => setN({ ...n, company: e.target.value })} /></Field>
        </div>
        <Field label="Note"><textarea className="textarea h-40" value={n.body ?? ""} onChange={(e) => setN({ ...n, body: e.target.value })} /></Field>
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Tags" hint="Separate with commas"><input className="input" value={n.tagText} onChange={(e) => setN({ ...n, tagText: e.target.value })} placeholder="timing, salary, networking" /></Field>
          <Field label="Link (optional)"><div className="flex gap-1.5"><input className="input" value={n.link ?? ""} onChange={(e) => setN({ ...n, link: e.target.value })} placeholder="https://" />
            {n.link && /^https?:\/\//.test(n.link) && <a className="btn-secondary btn-sm h-9" href={n.link} target="_blank" rel="noreferrer" aria-label="Open link"><ExternalLink size={13} /></a>}</div></Field>
        </div>
      </div>
    </Modal>
  );
}
