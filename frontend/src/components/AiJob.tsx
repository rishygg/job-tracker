import { useEffect, useRef, useState } from "react";
import { Loader2, Sparkles, X } from "lucide-react";
import { api, type Dict } from "../api";
import { useApp } from "../store";

const ACTIVE = new Set(["queued", "running"]);
export const isActive = (j?: Dict | null) => !!j && ACTIVE.has(j.status);

/** Poll a background AI job until it ends. Calls onPartial when part of the result is saved, onEnd when it stops. */
export function useJob(initial: Dict | null | undefined, onPartial?: () => void, onEnd?: (j: Dict) => void) {
  const [job, setJob] = useState<Dict | null>(initial ?? null);
  const partialSeen = useRef(0);
  const cb = useRef({ onPartial, onEnd });
  cb.current = { onPartial, onEnd };
  useEffect(() => { if (initial) { setJob(initial); partialSeen.current = initial.partial ?? 0; } }, [initial?.id, initial?.status]);
  useEffect(() => {
    if (!isActive(job)) return;
    let live = true;
    const t = setInterval(async () => {
      try {
        const j = await api.get(`/api/ai/jobs/${job!.id}`);
        if (!live) return;
        setJob(j);
        if ((j.partial ?? 0) > partialSeen.current) { partialSeen.current = j.partial; cb.current.onPartial?.(); }
        if (!ACTIVE.has(j.status)) cb.current.onEnd?.(j);
      } catch { /* app restarting */ }
    }, 1200);
    return () => { live = false; clearInterval(t); };
  }, [job?.id, job?.status]);
  return [job, setJob] as const;
}

function fmt(s: number) {
  s = Math.max(0, Math.round(s));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
}

export function jobText(j: Dict, speed?: Dict | null): { line: string; pct: number | null; eta: string | null } {
  const tps = speed?.gen_tps as number | undefined;
  if (j.status === "queued") {
    return { line: j.ahead > 0 ? `Waiting for ${j.ahead} other AI task${j.ahead > 1 ? "s" : ""} to finish (Ollama does one at a time)` : "Starting…", pct: null, eta: null };
  }
  const step = j.steps > 1 ? `Part ${j.step_index} of ${j.steps}: ${j.step}` : j.step || "Working";
  if (j.phase === "loading model") return { line: `${step} · loading the model into memory (first run after a break: up to a minute)`, pct: null, eta: null };
  if (j.phase === "reading" || !j.tokens) return { line: `${step} · reading the job and your CV`, pct: null, eta: null };
  const exp = j.expected_tokens as number | null;
  const pct = exp ? Math.min(0.97, j.tokens / exp) : null;
  let eta: string | null = null;
  if (tps && exp) {
    const rest = Math.max(0, exp - j.tokens) / tps + (j.steps > j.step_index ? (exp * (j.steps - j.step_index)) / tps : 0);
    eta = rest > 3 ? `about ${fmt(rest)} left` : "almost done";
  }
  return { line: `${step} · writing (${j.tokens} tokens${tps ? `, ~${tps.toFixed(1)}/s` : ""})`, pct, eta };
}

/** Progress card for one AI job. */
export function JobProgress({ job, onCancel, speed }: { job: Dict; onCancel?: () => void; speed?: Dict | null }) {
  const { toast } = useApp();
  const t = jobText(job, speed);
  async function cancel() {
    try { await api.del(`/api/ai/jobs/${job.id}`); onCancel?.(); } catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <div className="rounded-xl border border-brand/25 bg-brand-soft/60 p-3.5" role="status" aria-live="polite">
      <div className="flex items-start gap-2.5">
        <Loader2 className="animate-spin text-brand mt-0.5 shrink-0" size={15} />
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-medium text-ink">{job.label}</div>
          <div className="text-[12px] text-ink-soft mt-0.5">{t.line}</div>
          <div className="h-1.5 rounded-full bg-white mt-2 overflow-hidden">
            {t.pct === null
              ? <div className="h-full w-1/3 bg-brand/50 rounded-full animate-[slide_1.4s_ease-in-out_infinite]" />
              : <div className="h-full bg-brand rounded-full transition-all duration-700" style={{ width: `${Math.max(4, t.pct * 100)}%` }} />}
          </div>
          <div className="flex justify-between text-[11px] text-ink-muted mt-1 num">
            <span>{job.status === "running" ? `Running for ${fmt(job.elapsed)}` : `Queued ${fmt(job.waited)} ago`}</span>
            <span>{t.eta ?? (job.steps > 1 && job.partial ? "first part ready below" : "")}</span>
          </div>
        </div>
        <button className="btn-ghost btn-sm text-[12px]" onClick={cancel} title="Stop this AI task"><X size={13} /> Stop</button>
      </div>
    </div>
  );
}

/** Small sidebar indicator for whatever the AI is doing in the background. */
export function AiActivity() {
  const { version, refresh } = useApp();
  const [jobs, setJobs] = useState<Dict[]>([]);
  const [speed, setSpeed] = useState<Dict | null>(null);
  const wasActive = useRef(false);
  useEffect(() => {
    let live = true;
    const tick = () => api.get("/api/ai/jobs?active=true").then((d) => {
      if (!live) return;
      setJobs(d.jobs); setSpeed(d.speed);
      if (wasActive.current && !d.jobs.length) refresh(); // something finished: refresh the page's data
      wasActive.current = d.jobs.length > 0;
    }).catch(() => {});
    tick();
    const t = setInterval(tick, jobs.length ? 2000 : 6000);
    return () => { live = false; clearInterval(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version, jobs.length > 0]);
  if (!jobs.length) return null;
  const run = jobs.find((j) => j.status === "running") ?? jobs[0];
  const t = jobText(run, speed);
  return (
    <div className="hidden lg:block mx-3 mb-3 rounded-lg border border-line bg-canvas p-2.5 text-[11.5px]" title={t.line}>
      <div className="flex items-center gap-1.5 font-medium text-ink"><Sparkles size={12} className="text-brand" />AI working{jobs.length > 1 ? ` · ${jobs.length} tasks` : ""}</div>
      <div className="text-ink-soft truncate mt-0.5">{run.label}</div>
      <div className="h-1 rounded-full bg-white mt-1.5 overflow-hidden">
        {t.pct === null ? <div className="h-full w-1/3 bg-brand/50 rounded-full animate-[slide_1.4s_ease-in-out_infinite]" />
          : <div className="h-full bg-brand rounded-full transition-all duration-700" style={{ width: `${Math.max(4, t.pct * 100)}%` }} />}
      </div>
      {t.eta && <div className="text-ink-muted mt-1 num">{t.eta}</div>}
    </div>
  );
}
