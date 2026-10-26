import { useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, ArrowRight, ClipboardCopy, HelpCircle, Loader2, Quote, RefreshCw, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { api, type Dict } from "../api";
import { useApp } from "../store";
import { cls } from "../lib";
import { JobProgress, isActive, useJob } from "./AiJob";

/** CV builder / cover letter builder: prioritised findings, not a rewritten document. */
export function BuilderPanel({ kind, refId, doc }: { kind: string; refId: number; doc: "cv_builder" | "letter_builder" }) {
  const { toast } = useApp();
  const [state, setState] = useState<Dict | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [ai, setAi] = useState<Dict | null>(null);
  const url = `/api/docs/${kind}/${refId}/${doc}`;
  const reload = () => api.get(url).then((s) => s.result && setState(s)).catch(() => {});
  const [job, setJob] = useJob(state?.job, reload, (j) => {
    reload();
    if (j.status === "error") toast(j.error ?? "The AI review failed", "error");
    else if (j.status === "done") toast("AI review ready");
  });
  useEffect(() => { api.get("/api/ai/status").then(setAi).catch(() => {}); }, []);

  async function run(engine: "keywords" | "ollama") {
    setBusy(engine);
    try {
      const s = await api.post(url, { engine });
      setState(s);
      if (s.job) setJob(s.job);
    } catch (e: any) { toast(e.message, "error"); }
    finally { setBusy(null); }
  }
  useEffect(() => {
    setState(null);
    api.get(url).then((s) => {
      if (s.result) setState(s);
      else run("keywords"); // rule-based version is instant, so show it straight away
    }).catch(() => setState({ result: null }));
  }, [kind, refId, doc]);

  function copyBrief() {
    const text = state?.result?.brief;
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => toast("Brief copied. Paste it into your chat assistant."))
      .catch(() => toast("Couldn't copy; select the text instead", "error"));
  }
  const working = isActive(job);
  const failed = job?.status === "error" && job.error;
  const estimate = ai?.speed?.gen_tps ? Math.round((doc === "cv_builder" ? 810 : 710) / ai.speed.gen_tps / 60 + 0.5) : null;

  if (!state?.result) return <div className="py-10 flex justify-center text-ink-muted"><Loader2 className="animate-spin" size={20} /></div>;
  const r = state.result;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[11.5px] text-ink-muted">
          {r.method === "ollama" ? <>Recruiter review by <b className="text-ink-soft">{r.model}</b></> : "Rule-based review (instant)"}
          {" · "}<Link to="/settings?tab=evidence" className="text-brand hover:underline">Evidence bank</Link>
        </span>
        <div className="flex gap-1">
          {ai?.available && !working && (
            <button className="btn-primary btn-sm" disabled={!!busy} onClick={() => run("ollama")}
              title={estimate ? `Runs in the background; about ${estimate} min on this computer` : "Runs in the background; you can keep using the app"}>
              {busy === "ollama" ? <><Loader2 className="animate-spin" size={13} /> Starting…</> : <><Sparkles size={13} /> {r.method === "ollama" ? "Re-run AI review" : "Recruiter review with AI"}{estimate ? <span className="opacity-75 font-normal">· ~{estimate} min</span> : null}</>}
            </button>
          )}
          <button className="btn-secondary btn-sm" disabled={!!busy || working} onClick={() => run("keywords")} title="Instant rule-based review"><RefreshCw size={13} /> Refresh</button>
          <button className="btn-secondary btn-sm" onClick={copyBrief} title="A ready-made prompt for ChatGPT, Claude etc. to write your version"><ClipboardCopy size={13} /> Copy brief</button>
        </div>
      </div>
      {working && <JobProgress job={job!} speed={ai?.speed} onCancel={() => setJob({ ...job!, status: "cancelled" })} />}
      {failed && !working && <div className="flex gap-2 p-2.5 rounded-lg bg-[#fdecea] text-[#8a1c12] text-[12.5px]"><AlertTriangle size={14} className="mt-0.5 shrink-0" /><span>AI review failed: {job!.error} The rule-based review is shown.</span></div>}
      {r.ai_note && !working && <div className="flex gap-2 p-2.5 rounded-lg bg-canvas text-ink-soft text-[12.5px]"><AlertTriangle size={14} className="mt-0.5 shrink-0 text-[#a35f00]" />{r.ai_note}</div>}
      {state.stale && <div className="flex gap-2 p-2.5 rounded-lg bg-[#fdf4e6] text-[#7a4a00] text-[12.5px]"><AlertTriangle size={14} className="mt-0.5 shrink-0" />Your CV, evidence bank or this job changed since this review. Refresh it.</div>}
      {r.priorities?.length > 0 && (
        <section className="rounded-xl bg-canvas p-3.5">
          <div className="eyebrow mb-1.5">What this role prioritises</div>
          <ol className="list-decimal pl-5 space-y-0.5 text-[13px] text-ink-soft">{r.priorities.map((p: string, i: number) => <li key={i}>{p}</li>)}</ol>
          {r.themes?.length > 0 && <div className="flex flex-wrap gap-1 mt-2">{r.themes.map((t: string) => <span key={t} className="chip h-5 text-[10.5px] bg-white">{t}</span>)}</div>}
        </section>
      )}
      {doc === "cv_builder" ? <CvBuilder r={r} /> : <LetterBuilder r={r} />}
      {r.fallback_reason && <p className="text-[11.5px] text-ink-muted">{r.fallback_reason}</p>}
      <p className="text-[11.5px] text-ink-muted">Use these findings to write your own version, or click "Copy brief" and paste it into a chat assistant to draft it for you.</p>
    </div>
  );
}

function SourceTag({ source }: { source?: string }) {
  if (!source) return null;
  if (source === "pending") return <span className="text-[10px] font-semibold uppercase tracking-wide text-brand inline-flex items-center gap-1"><Loader2 size={10} className="animate-spin" />AI working · rules for now</span>;
  return source === "ai"
    ? <span className="text-[10px] font-semibold uppercase tracking-wide text-brand inline-flex items-center gap-0.5"><Sparkles size={10} />AI</span>
    : <span className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">rules</span>;
}

function Group({ title, hint, color, children, empty, source }: { title: string; hint?: string; color: string; children: ReactNode; empty?: boolean; source?: string }) {
  if (empty) return null;
  return (
    <section>
      <div className="flex items-baseline gap-2 mb-2">
        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
        <span className="eyebrow">{title}</span>
        {hint && <span className="text-[11.5px] text-ink-muted">{hint}</span>}
        <span className="ml-auto"><SourceTag source={source} /></span>
      </div>
      <ul className="space-y-1.5">{children}</ul>
    </section>
  );
}

function Item({ children, tone }: { children: ReactNode; tone?: string }) {
  return <li className={cls("rounded-lg border bg-white px-3 py-2.5 text-[13px] leading-snug", tone ?? "border-line")}>{children}</li>;
}

const Bullet = ({ text }: { text: string }) => <div className="text-ink">“{text}”</div>;
const PRI: Record<string, string> = { high: "#b42318", medium: "#a35f00", low: "#8f97a6" };

function CvBuilder({ r }: { r: Dict }) {
  return (
    <div className="space-y-5">
      <Group source={r.sources?.critique} title="Recruiter critique" hint="what a screener would question, and one fix each" color="#b42318" empty={!r.critique?.length}>
        {r.critique?.map((c: Dict, i: number) => (
          <Item key={i}>
            <div className="flex items-start gap-2">
              <span className="text-[10px] font-bold uppercase tracking-wide mt-0.5 shrink-0" style={{ color: PRI[c.priority] ?? PRI.medium }}>{c.priority}</span>
              <div className="min-w-0 flex-1">
                <Bullet text={c.text} />
                <div className="mt-1.5 grid sm:grid-cols-[auto_1fr] gap-x-2 gap-y-1 text-[12.5px]">
                  <span className="text-ink-muted font-medium">Why it's weak</span><span className="text-ink-soft">{c.issue}</span>
                  <span className="text-ink-muted font-medium">Improve it</span><span className="text-ink">{c.fix}</span>
                </div>
              </div>
            </div>
          </Item>
        ))}
      </Group>
      {!r.critique?.length && <p className="text-[12.5px] text-ink-muted">No obvious weaknesses in your most relevant bullets. Try the AI review for a stricter read.</p>}
      <Group source={r.sources?.emphasise} title="Emphasise" hint="move up, give more space" color="#0e9a69" empty={!r.emphasise?.length}>
        {r.emphasise?.map((x: Dict, i: number) => <Item key={i}><Bullet text={x.text} /><div className="text-[12px] text-ink-muted mt-1">{x.why}</div></Item>)}
      </Group>
      <Group source={r.sources?.reword} title="Reword" hint="same facts, the job's vocabulary" color="#3d6fd6" empty={!r.reword?.length}>
        {r.reword?.map((x: Dict, i: number) => <Item key={i}><Bullet text={x.text} /><div className="text-[12.5px] mt-1 flex gap-1.5"><ArrowRight size={13} className="mt-0.5 text-[#3d6fd6] shrink-0" />{x.suggestion}</div></Item>)}
      </Group>
      <Group source={r.sources?.questions} title="Questions a recruiter would ask" color="#7f5bd1" empty={!r.questions?.length}>
        {r.questions?.map((q: Dict, i: number) => (
          <Item key={i}><div className="flex gap-2"><HelpCircle size={14} className="text-[#7f5bd1] mt-0.5 shrink-0" /><div>
            <div className="font-medium">{q.question}</div>{q.how_to_answer && <div className="text-[12px] text-ink-muted mt-0.5">{q.how_to_answer}</div>}</div></div></Item>
        ))}
      </Group>
      <Group source={r.sources?.add_if_true} title="Add, if true" hint="the job wants it; your CV doesn't show it" color="#d97f06" empty={!r.add_if_true?.length}>
        {r.add_if_true?.map((x: Dict, i: number) => <Item key={i} tone="border-dashed border-line-strong"><div>{x.what}</div>{x.why && <div className="text-[12px] text-ink-muted mt-0.5">{x.why}</div>}</Item>)}
      </Group>
      <Group title="Shorten or move down" hint="least relevant for this job" color="#8f97a6" empty={!r.cut?.length}>
        {r.cut?.map((x: Dict, i: number) => <Item key={i}><div className="text-ink-soft">“{x.text}”</div></Item>)}
      </Group>
      {(r.keywords?.length > 0 || r.missing_keywords?.length > 0) && (
        <section>
          <div className="eyebrow mb-2">Keywords</div>
          <div className="flex flex-wrap gap-1.5">
            {r.keywords?.map((k: string) => <span key={k} className="chip bg-brand-soft text-brand-strong border-brand/20">{k}</span>)}
            {r.missing_keywords?.map((k: string) => <span key={k} className="chip border-dashed border-line-strong">{k}</span>)}
          </div>
          <p className="text-[11.5px] text-ink-muted mt-1.5">Green: in your CV, keep the job's wording. Dashed: in the job but not your CV; add only if true.</p>
        </section>
      )}
    </div>
  );
}

function Card({ label, color, children, source }: { label: string; color: string; children: ReactNode; source?: string }) {
  return (
    <div className="rounded-xl border border-line bg-white p-3.5">
      <div className="flex items-center justify-between gap-2 mb-1.5"><span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color }}>{label}</span><SourceTag source={source} /></div>
      {children}
    </div>
  );
}

function LetterBuilder({ r }: { r: Dict }) {
  return (
    <div className="space-y-5">
      <div className="grid md:grid-cols-3 gap-3">
        <Card source={r.sources?.connection} label="Strongest connection" color="#0a7a53">
          {r.connection ? <>
            <div className="text-[13px] leading-snug">“{r.connection.text}”</div>
            {r.connection.requirement && <div className="text-[12px] text-ink-muted mt-1.5">↔ {r.connection.requirement}</div>}
            {r.connection.why && <div className="text-[12px] text-ink-soft mt-1">{r.connection.why}</div>}
          </> : <div className="text-[12.5px] text-ink-muted">No clear link found yet. Check your evidence bank.</div>}
        </Card>
        <Card source={r.sources?.interest} label="Most credible reason to be interested" color="#3d6fd6">
          <div className="text-[13px] leading-snug">{r.interest?.reason}</div>
          {r.interest?.basis && <div className="text-[12px] text-ink-muted mt-1.5 flex gap-1"><Quote size={11} className="mt-0.5 shrink-0" />{r.interest.basis}</div>}
        </Card>
        <Card source={r.sources?.highlight} label="Example worth highlighting" color="#d97f06">
          {r.highlight ? <>
            <div className="text-[13px] leading-snug">“{r.highlight.text}”</div>
            {r.highlight.why && <div className="text-[12px] text-ink-soft mt-1.5">{r.highlight.why}</div>}
          </> : <div className="text-[12.5px] text-ink-muted">No standout example yet. Add one with a result to your evidence bank.</div>}
        </Card>
      </div>
      <Group source={r.sources?.missing} title="Missing from the story" hint="what a hiring manager would notice" color="#b42318" empty={!r.missing?.length}>
        {r.missing?.map((m: string, i: number) => <Item key={i}>{m}</Item>)}
      </Group>
      <Group source={r.sources?.avoid} title="Generic statements to avoid" color="#8f97a6" empty={!r.avoid?.length}>
        {r.avoid?.map((a: Dict, i: number) => (
          <Item key={i}><div className="text-ink-muted line-through decoration-ink-faint/60">“{a.phrase}”</div><div className="text-[12.5px] mt-0.5 flex gap-1.5"><ArrowRight size={13} className="mt-0.5 text-brand shrink-0" />{a.instead}</div></Item>
        ))}
      </Group>
      {r.outline?.length > 0 && (
        <section>
          <div className="eyebrow mb-2">Suggested structure</div>
          <ol className="space-y-1.5">
            {r.outline.map((o: string, i: number) => (
              <li key={i} className="flex gap-2.5 text-[13px]"><span className="num w-5 h-5 rounded-full bg-canvas border border-line text-[11px] flex items-center justify-center shrink-0">{i + 1}</span><span className="text-ink-soft">{o}</span></li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
