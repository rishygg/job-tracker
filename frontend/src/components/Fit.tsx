import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Check, ChevronDown, CircleDashed, Copy, FileText, Loader2, Mail, RefreshCw, ShieldAlert, Sparkles, X } from "lucide-react";
import { api, type Dict } from "../api";
import { useApp } from "../store";
import { cls, pct } from "../lib";
import { EmptyState, Segmented } from "./ui";
import { BuilderPanel } from "./Builder";
import { JobProgress, isActive, useJob } from "./AiJob";

export const ACTION_STYLE: Record<string, { color: string; bg: string; ring: string }> = {
  Apply: { color: "#0a7a53", bg: "#e8f6f0", ring: "#bfe6d6" },
  "Apply with caveats": { color: "#a35f00", bg: "#fdf4e6", ring: "#f5dcb1" },
  Deprioritise: { color: "#5d6676", bg: "#f2f3f5", ring: "#dde0e6" },
};

export function ActionPill({ action, size = "md" }: { action: string; size?: "sm" | "md" }) {
  const s = ACTION_STYLE[action] ?? ACTION_STYLE.Deprioritise;
  return (
    <span className={cls("inline-flex items-center rounded-full font-semibold whitespace-nowrap", size === "sm" ? "h-5 px-2 text-[11px]" : "h-7 px-3 text-[12.5px]")}
      style={{ color: s.color, background: s.bg, boxShadow: `inset 0 0 0 1px ${s.ring}` }}>{action}</span>
  );
}

export function ScoreRing({ score, size = 64 }: { score: number | null | undefined; size?: number }) {
  const r = size / 2 - 5, c = 2 * Math.PI * r, v = score ?? 0;
  const color = score === null || score === undefined ? "#c9ced8" : v >= 0.7 ? "#0e9a69" : v >= 0.45 ? "#d97f06" : "#8f97a6";
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} aria-label={`Fit score ${pct(score)}`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#eef0f3" strokeWidth={size > 50 ? 6 : 4} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={size > 50 ? 6 : 4} fill="none" strokeLinecap="round"
          strokeDasharray={`${c * v} ${c}`} />
      </svg>
      <div className={cls("absolute inset-0 flex items-center justify-center num font-semibold", size > 50 ? "text-[16px]" : "text-[11px]")}>
        {score === null || score === undefined ? "—" : Math.round(v * 100)}
      </div>
    </div>
  );
}

const STATUS_ICON: Record<string, ReactNode> = {
  met: <span className="w-5 h-5 rounded-full bg-[#e8f6f0] text-[#0a7a53] flex items-center justify-center shrink-0"><Check size={12} strokeWidth={3} /></span>,
  partial: <span className="w-5 h-5 rounded-full bg-[#fdf4e6] text-[#a35f00] flex items-center justify-center shrink-0"><CircleDashed size={12} strokeWidth={2.5} /></span>,
  missing: <span className="w-5 h-5 rounded-full bg-[#f2f3f5] text-[#8f97a6] flex items-center justify-center shrink-0"><X size={12} strokeWidth={3} /></span>,
};

function Requirement({ r }: { r: Dict }) {
  const fromProfile = typeof r.evidence === "string" && r.evidence.startsWith("Profile:");
  return (
    <li className="flex gap-2.5 py-2">
      {STATUS_ICON[r.status]}
      <div className="min-w-0">
        <div className="text-[13px] leading-snug">{r.text}</div>
        {r.evidence && (
          <div className={cls("mt-1 text-[12px] leading-snug pl-2.5 border-l-2", r.evidence_verified === false ? "border-[#f5dcb1] text-ink-muted" : "border-brand/30 text-ink-soft")}>
            {fromProfile ? <span className="text-ink-muted">{r.evidence}</span> : <>“{r.evidence}”</>}
            {!fromProfile && <span className="block text-[10.5px] text-ink-faint mt-0.5">{r.evidence_verified === false ? "Couldn't verify in your CV" : r.evidence_section ? `From your CV · ${r.evidence_section}` : "From your CV"}</span>}
          </div>
        )}
        {r.note && <div className="text-[11.5px] text-ink-muted mt-1">{r.note}</div>}
      </div>
    </li>
  );
}

const SEV: Record<string, string> = { high: "#b42318", medium: "#a35f00", low: "#8f97a6" };

export function FitResultView({ res }: { res: Dict }) {
  const [showAll, setShowAll] = useState(false);
  const ess = res.requirements.filter((r: Dict) => r.type === "essential");
  const pref = res.requirements.filter((r: Dict) => r.type === "preferred");
  return (
    <div className="space-y-5">
      <div className="flex items-start gap-4 p-4 rounded-xl border" style={{ borderColor: ACTION_STYLE[res.recommendation.action]?.ring, background: `${ACTION_STYLE[res.recommendation.action]?.bg}80` }}>
        <ScoreRing score={res.score} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><ActionPill action={res.recommendation.action} />
            <span className="text-[11.5px] text-ink-muted">{res.method === "ollama" ? `AI analysis · ${res.model}` : "Keyword analysis"}</span></div>
          <p className="text-[13.5px] mt-1.5 leading-snug">{res.recommendation.why}</p>
          <p className="text-[12.5px] text-ink-muted mt-1">{res.summary}</p>
        </div>
      </div>

      {res.blockers.length > 0 && (
        <section>
          <div className="eyebrow mb-2 flex items-center gap-1.5"><ShieldAlert size={13} /> Potential blockers</div>
          <ul className="space-y-1.5">
            {res.blockers.map((b: Dict, i: number) => (
              <li key={i} className="flex gap-2 text-[13px]">
                <span className="mt-1.5 w-2 h-2 rounded-full shrink-0" style={{ background: SEV[b.severity] }} />
                <span><b className="font-medium">{b.type}:</b> <span className="text-ink-soft">{b.detail}</span></span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="grid md:grid-cols-2 gap-5">
        <section>
          <div className="eyebrow mb-1">Essential · {res.counts.essential_met}/{res.counts.essential} met</div>
          {ess.length ? <ul className="divide-y divide-line">{ess.map((r: Dict, i: number) => <Requirement key={i} r={r} />)}</ul>
            : <p className="text-[12.5px] text-ink-muted py-2">No essential requirements found.</p>}
        </section>
        <section>
          <div className="eyebrow mb-1">Preferred · {res.counts.preferred_met}/{res.counts.preferred} met</div>
          {pref.length ? <ul className="divide-y divide-line">{(showAll ? pref : pref.slice(0, 8)).map((r: Dict, i: number) => <Requirement key={i} r={r} />)}</ul>
            : <p className="text-[12.5px] text-ink-muted py-2">None listed as preferred.</p>}
          {pref.length > 8 && <button className="btn-ghost btn-sm" onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer" : `Show all ${pref.length}`}</button>}
        </section>
      </div>

      {res.gaps.length > 0 && (
        <section>
          <div className="eyebrow mb-2">Gaps to address</div>
          <div className="flex flex-wrap gap-1.5">
            {res.gaps.map((g: Dict, i: number) => (
              <span key={i} className="chip h-auto py-1 max-w-full whitespace-normal leading-snug" title={g.note ?? ""}>
                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: SEV[g.severity] }} />{g.point}
              </span>
            ))}
          </div>
        </section>
      )}
      {res.fallback_reason && <p className="text-[11.5px] text-ink-muted">Used keyword matching because Ollama wasn't available: {res.fallback_reason}</p>}
    </div>
  );
}

/** Fit analysis for a saved application or opportunity, with the target CV and cover letter. */
export function FitPanel({ kind, refId, hasJd }: { kind: "application" | "opportunity"; refId: number; hasJd: boolean }) {
  const { toast, meta } = useApp();
  const [state, setState] = useState<Dict | null>(null);
  const [busy, setBusy] = useState(false);
  const [doc, setDoc] = useState<"fit" | "cv_builder" | "letter_builder">("fit");
  const [ai, setAi] = useState<Dict | null>(null);
  useEffect(() => { api.get("/api/ai/status").then(setAi).catch(() => {}); }, []);
  const load = () => api.get(`/api/fit/${kind}/${refId}`).then(setState).catch(() => setState({ result: null }));
  useEffect(() => { load(); }, [kind, refId]);
  const hasCv = (meta?.settings?.cv_chars ?? 0) >= 50;
  const [job, setJob] = useJob(state?.job, undefined, (j) => {
    load();
    if (j.status === "error") toast(j.error ?? "The AI analysis failed", "error");
  });
  const working = isActive(job);

  async function run(engine?: string) {
    setBusy(true);
    try {
      const s = await api.post(`/api/fit/${kind}/${refId}`, engine ? { engine } : { engine: "keywords" });
      if (s.job) { setJob(s.job); setState((old) => ({ ...(old ?? {}), ...s, result: s.result ?? old?.result ?? null })); }
      else setState(s);
    }
    catch (e: any) { toast(e.message, "error"); }
    finally { setBusy(false); }
  }

  if (!hasCv) return (
    <EmptyState icon={<FileText size={20} />} title="Add your CV first" action={<Link to="/settings" className="btn-primary">Go to Settings</Link>}>
      Upload your CV and fill in your languages, degree and work permits in Settings → Profile. Then every job gets a fit analysis.
    </EmptyState>
  );
  if (!hasJd) return <EmptyState icon={<FileText size={20} />} title="No job description yet">Paste the full posting in the Job description tab, then come back here.</EmptyState>;
  if (!state) return <div className="py-10 flex justify-center text-ink-muted"><Loader2 className="animate-spin" size={20} /></div>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Segmented value={doc} onChange={setDoc} options={[
          { id: "fit", label: <><Sparkles size={13} /> Fit analysis</> }, { id: "cv_builder", label: <><FileText size={13} /> CV builder</> },
          { id: "letter_builder", label: <><Mail size={13} /> Cover letter builder</> }]} />
        {doc === "fit" && state.result && (
          <div className="flex gap-1">
            {ai?.available && !working && (
              <button className="btn-primary btn-sm" disabled={busy} onClick={() => run("ollama")}>
                {busy ? <><Loader2 className="animate-spin" size={13} /> Starting…</> : <><Sparkles size={13} /> {state.result.method === "ollama" ? "Re-run AI analysis" : "Deep analysis with AI"}</>}
              </button>
            )}
            <button className="btn-secondary btn-sm" disabled={busy || working} onClick={() => run()} title="Instant keyword analysis"><RefreshCw size={13} /> Quick re-score</button>
          </div>
        )}
      </div>
      {doc === "fit" && (
        <>
          {working && <JobProgress job={job!} speed={ai?.speed} onCancel={() => setJob({ ...job!, status: "cancelled" })} />}
          {state.stale && <div className="flex gap-2 p-2.5 rounded-lg bg-[#fdf4e6] text-[#7a4a00] text-[12.5px]"><AlertTriangle size={14} className="mt-0.5 shrink-0" />Your CV, profile or this job description changed since this analysis. Re-run it to update.</div>}
          {!state.result ? (
            <EmptyState icon={<Sparkles size={20} />} title="Check how well your CV fits"
              action={<button className="btn-primary" disabled={busy} onClick={() => run()}>{busy ? <><Loader2 className="animate-spin" size={15} /> Analysing…</> : <><Sparkles size={15} /> Analyse fit</>}</button>}>
              Essential and preferred requirements, evidence from your CV, gaps, blockers like language or permits, and a recommendation.
            </EmptyState>
          ) : <FitResultView res={state.result} />}
        </>
      )}
      {doc !== "fit" && <BuilderPanel kind={kind} refId={refId} doc={doc} />}
    </div>
  );
}

const SUPPORT: Record<string, { label: string; color: string; bg: string; border: string }> = {
  backed: { label: "Backed by your CV", color: "#0a7a53", bg: "#ffffff", border: "#bfe6d6" },
  partial: { label: "Needs your input", color: "#a35f00", bg: "#fffbf3", border: "#f5dcb1" },
  gap: { label: "Not in your CV, only use if true", color: "#5d6676", bg: "#f6f7f9", border: "#dde0e6" },
};

function SupportTag({ support }: { support: string }) {
  const s = SUPPORT[support] ?? SUPPORT.partial;
  return <span className="text-[10.5px] font-semibold uppercase tracking-wide" style={{ color: s.color }}>{s.label}</span>;
}

export function DocPanel({ kind, refId, doc }: { kind: string; refId: number; doc: "target_cv" | "cover_letter" | "cv_tips" }) {
  const { toast } = useApp();
  const [state, setState] = useState<Dict | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setState(null); api.get(`/api/docs/${kind}/${refId}/${doc}`).then(setState).catch(() => setState({ result: null })); }, [kind, refId, doc]);
  async function run() {
    setBusy(true);
    try { setState(await api.post(`/api/docs/${kind}/${refId}/${doc}`, {})); }
    catch (e: any) { toast(e.message, "error"); }
    finally { setBusy(false); }
  }
  const label = doc === "target_cv" ? "target CV" : doc === "cv_tips" ? "list of CV suggestions" : "cover letter";
  if (!state) return <div className="py-10 flex justify-center text-ink-muted"><Loader2 className="animate-spin" size={20} /></div>;
  if (!state.result) return (
    <EmptyState icon={doc === "target_cv" ? <FileText size={20} /> : <Mail size={20} />} title={`Generate a ${label}`}
      action={<button className="btn-primary" disabled={busy} onClick={run}>{busy ? <><Loader2 className="animate-spin" size={15} /> Writing…</> : <><Sparkles size={15} /> Generate</>}</button>}>
      {doc === "cv_tips"
        ? "Which of your CV lines to emphasise, reword or shorten for this job, what to add if it's true, and which keywords to mirror."
        : "A draft built only from facts in your CV, with [placeholders] where your own words are needed."}
      <span className="block mt-1 text-[12px]">{doc === "cv_tips" ? "Instant without AI; about 15–30 seconds with Ollama." : "Uses Ollama when it's running (about a minute); otherwise a template."}</span>
    </EmptyState>
  );
  const r = state.result;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11.5px] text-ink-muted">{r.method === "ollama" ? `By ${r.model}` : r.method === "template" ? "Template (install Ollama for a full draft)" : "From keyword matching (Ollama adds rewording ideas)"}</span>
        <div className="flex gap-1">
          <button className="btn-secondary btn-sm" onClick={() => copy(r, doc, toast)}><Copy size={13} /> Copy</button>
          <button className="btn-ghost btn-sm" disabled={busy} onClick={run}>{busy ? <Loader2 className="animate-spin" size={13} /> : <RefreshCw size={13} />} Regenerate</button>
        </div>
      </div>
      {state.stale && <div className="flex gap-2 p-2.5 rounded-lg bg-[#fdf4e6] text-[#7a4a00] text-[12.5px]"><AlertTriangle size={14} className="mt-0.5 shrink-0" />Your CV or the job description changed since this was generated.</div>}
      {doc !== "cv_tips" && <div className="flex flex-wrap gap-3 text-[11.5px]">
        {Object.entries(SUPPORT).filter(([k]) => doc === "target_cv" || k !== "gap").map(([k, s]) => (
          <span key={k} className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm border" style={{ background: s.bg, borderColor: s.border }} />{s.label}</span>
        ))}
      </div>}
      {doc === "cv_tips" ? <CvTips r={r} /> : doc === "target_cv" ? <TargetCv r={r} /> : <Letter r={r} />}
    </div>
  );
}

function TipGroup({ title, hint, color, items, render }: { title: string; hint: string; color: string; items: Dict[]; render: (x: Dict) => ReactNode }) {
  if (!items?.length) return null;
  return (
    <section>
      <div className="flex items-baseline gap-2 mb-2"><span className="w-2 h-2 rounded-full" style={{ background: color }} /><span className="eyebrow">{title}</span><span className="text-[11.5px] text-ink-muted">{hint}</span></div>
      <ul className="space-y-1.5">{items.map((x, i) => <li key={i} className="rounded-lg border border-line bg-white px-3 py-2 text-[13px] leading-snug">{render(x)}</li>)}</ul>
    </section>
  );
}

function CvTips({ r }: { r: Dict }) {
  const nothing = !r.emphasise?.length && !r.reword?.length && !r.cut?.length && !r.add?.length;
  return (
    <div className="space-y-5">
      {nothing && <p className="text-[13px] text-ink-muted">No specific suggestions. Run the fit analysis first for better results.</p>}
      <TipGroup title="Emphasise" hint="move up, expand" color="#0e9a69" items={r.emphasise} render={(x) => <>
        <div>“{x.text}”</div><div className="text-[12px] text-ink-muted mt-0.5">{x.why}</div></>} />
      <TipGroup title="Reword" hint="same facts, the job's vocabulary" color="#3d6fd6" items={r.reword} render={(x) => <>
        <div className="text-ink-muted line-through decoration-ink-faint/60">“{x.text}”</div><div className="mt-0.5">→ {x.suggestion}</div></>} />
      <TipGroup title="Add, if true" hint="what they want that your CV doesn't show" color="#d97f06" items={r.add} render={(x) => <>
        <div>{x.what}</div><div className="text-[12px] text-ink-muted mt-0.5">{x.why}</div></>} />
      <TipGroup title="Shorten or move down" hint="least relevant for this job" color="#8f97a6" items={r.cut} render={(x) => <>
        <div className="text-ink-soft">“{x.text}”</div><div className="text-[12px] text-ink-muted mt-0.5">{x.why}</div></>} />
      {(r.keywords?.length > 0 || r.missing_keywords?.length > 0) && (
        <section>
          <div className="eyebrow mb-2">Keywords</div>
          <div className="flex flex-wrap gap-1.5">
            {r.keywords?.map((k: string) => <span key={k} className="chip bg-brand-soft text-brand-strong border-brand/20">{k}</span>)}
            {r.missing_keywords?.map((k: string) => <span key={k} className="chip border-dashed">{k}</span>)}
          </div>
          <p className="text-[11.5px] text-ink-muted mt-1.5">Green: already in your CV, use the same wording. Dashed: the job mentions it but your CV doesn't. Add only if true.</p>
        </section>
      )}
    </div>
  );
}

function TargetCv({ r }: { r: Dict }) {
  return (
    <div className="space-y-4">
      {r.headline && <div className="text-[17px] font-semibold">{r.headline}</div>}
      {r.summary && <p className="text-[13.5px] text-ink-soft leading-relaxed">{r.summary}</p>}
      {r.sections.map((s: Dict, i: number) => (
        <section key={i}>
          <div className="eyebrow mb-2">{s.title}</div>
          <ul className="space-y-2">
            {s.bullets.map((b: Dict, j: number) => <Bullet key={j} b={b} />)}
          </ul>
        </section>
      ))}
      {r.skills?.length > 0 && (
        <section>
          <div className="eyebrow mb-2">Skills the job asks for</div>
          <div className="flex flex-wrap gap-1.5">
            {r.skills.map((s: Dict) => <span key={s.skill} className={cls("chip", s.support === "backed" ? "bg-brand-soft text-brand-strong border-brand/20" : "border-dashed")}>{s.skill}</span>)}
          </div>
          <p className="text-[11.5px] text-ink-muted mt-1.5">Green: in your CV. Dashed: not in your CV.</p>
        </section>
      )}
      {r.advice?.length > 0 && (
        <section>
          <div className="eyebrow mb-2">Advice</div>
          <ul className="list-disc pl-5 space-y-1 text-[13px] text-ink-soft">{r.advice.map((a: string, i: number) => <li key={i}>{a}</li>)}</ul>
        </section>
      )}
    </div>
  );
}

function Bullet({ b }: { b: Dict }) {
  const [open, setOpen] = useState(false);
  const s = SUPPORT[b.support] ?? SUPPORT.partial;
  return (
    <li className={cls("rounded-lg border px-3 py-2", b.support === "gap" && "border-dashed")} style={{ background: s.bg, borderColor: s.border }}>
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-[13px] leading-snug">{b.text}</div>
          <div className="flex flex-wrap items-center gap-x-3 mt-1"><SupportTag support={b.support} />
            {b.addresses && <span className="text-[11px] text-ink-muted">Addresses: {b.addresses}</span>}</div>
          {b.note && <div className="text-[11.5px] text-ink-muted mt-1">{b.note}</div>}
        </div>
        {b.source && b.source !== b.text && (
          <button className="btn-ghost btn-sm h-6 px-1.5" onClick={() => setOpen(!open)} title="Show the CV line it's based on">
            <ChevronDown size={13} className={cls("transition", open && "rotate-180")} />
          </button>
        )}
      </div>
      {open && b.source && <div className="mt-2 text-[12px] text-ink-soft pl-2.5 border-l-2 border-brand/30">Your CV: “{b.source}”</div>}
    </li>
  );
}

function Letter({ r }: { r: Dict }) {
  return (
    <div className="rounded-xl border border-line bg-white p-5 space-y-3 text-[13.5px] leading-relaxed">
      <p>{r.greeting}</p>
      {r.paragraphs.map((p: Dict, i: number) => (
        <div key={i} className={cls("rounded-md -mx-2 px-2 py-1", p.support === "partial" && "bg-[#fffbf3]")}>
          <p className="whitespace-pre-wrap">{highlightPlaceholders(p.text)}</p>
          <SupportTag support={p.support} />
        </div>
      ))}
      <p className="whitespace-pre-wrap">{r.closing}</p>
    </div>
  );
}

function highlightPlaceholders(text: string) {
  const parts = text.split(/(\[[^\]]+\])/g);
  return parts.map((p, i) => p.startsWith("[") ? <mark key={i} className="bg-[#fdf0d6] text-[#7a4a00] rounded px-0.5">{p}</mark> : <span key={i}>{p}</span>);
}

function copy(r: Dict, doc: string, toast: (t: string, tone?: "ok" | "error") => void) {
  let text = "";
  if (doc === "cv_tips") {
    const sec = (t: string, xs: string[]) => (xs.length ? [`${t}:`, ...xs.map((x) => `• ${x}`), ""] : []);
    text = [...sec("Emphasise", (r.emphasise ?? []).map((x: Dict) => `${x.text} (${x.why})`)),
      ...sec("Reword", (r.reword ?? []).map((x: Dict) => `${x.text} → ${x.suggestion}`)),
      ...sec("Add if true", (r.add ?? []).map((x: Dict) => x.what)),
      ...sec("Shorten", (r.cut ?? []).map((x: Dict) => x.text))].join("\n");
  } else if (doc === "target_cv") {
    text = [r.headline, r.summary, ...r.sections.flatMap((s: Dict) => [`\n${s.title}`, ...s.bullets.filter((b: Dict) => b.support !== "gap").map((b: Dict) => `• ${b.text}`)])]
      .filter(Boolean).join("\n");
    text += "\n\n(Gaps left out. Lines marked 'Needs your input' must be checked before use.)";
  } else {
    text = [r.greeting, ...r.paragraphs.map((p: Dict) => p.text), r.closing].join("\n\n");
  }
  navigator.clipboard.writeText(text).then(() => toast("Copied")).catch(() => toast("Couldn't copy; select the text instead", "error"));
}
