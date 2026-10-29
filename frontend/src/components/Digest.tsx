import { useEffect, useState } from "react";
import { BookOpenText, Loader2, Square } from "lucide-react";
import { api, type Dict } from "../api";
import { useApp } from "../store";
import { cls } from "../lib";

function eta(min?: number | null) {
  if (!min) return null;
  if (min < 2) return "about a minute";
  if (min < 90) return `about ${min} min`;
  return `about ${Math.round(min / 6) / 10} h`;
}

/** Reading job descriptions with Ollama in the background, so skill and industry statistics improve over time. */
export function DigestPanel({ compact = false }: { compact?: boolean }) {
  const { toast, version } = useApp();
  const [d, setD] = useState<Dict | null>(null);
  const [ai, setAi] = useState<Dict | null>(null);
  const load = () => api.get("/api/digest").then(setD).catch(() => {});
  useEffect(() => { load(); api.get("/api/ai/status").then(setAi).catch(() => {}); }, [version]);
  useEffect(() => {
    if (!d?.queued) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [d?.queued]);
  if (!d || !d.total) return null;
  const left = d.total - d.done;
  const running = d.queued > 0;
  const available = ai?.available;
  if (compact && !left && !running) return null;

  async function start() {
    try { const r = await api.post("/api/digest/run", {}); setD(r); if (!r.queued_now) toast("Everything is already read"); }
    catch (e: any) { toast(e.message, "error"); }
  }
  async function stop() { setD(await api.del("/api/digest/run")); }

  return (
    <div className={cls("rounded-xl border border-line p-3.5 flex flex-wrap items-center gap-3", compact ? "bg-canvas/60" : "")}>
      <BookOpenText size={17} className="text-violet shrink-0" />
      <div className="flex-1 min-w-[200px]">
        <div className="text-[13px] font-medium">
          {running ? <>Reading descriptions… <span className="num text-ink-muted font-normal">{d.done}/{d.total}</span></>
            : left ? <><span className="num">{d.done}</span> of <span className="num">{d.total}</span> descriptions read with Ollama</>
            : <>All <span className="num">{d.total}</span> descriptions read</>}
        </div>
        <div className="text-[11.5px] text-ink-muted">
          {running ? <>{d.running ? `Now: ${d.running}. ` : ""}{eta(d.eta_minutes) ? `${eta(d.eta_minutes)} left. ` : ""}You can keep using the tracker.</>
            : left ? <>Optional: a local model picks out skills, industry and seniority the keyword rules miss. {d.seconds_each ? `About ${d.seconds_each}s per description${eta(d.eta_minutes) ? `, ${eta(d.eta_minutes)} for the rest` : ""}.` : "Each takes about 30–50 s on a laptop, once."}</>
            : <>New descriptions {d.auto ? "are read automatically" : "can be read from here or Settings"}.</>}
        </div>
        {(running || (d.done > 0 && left > 0)) && (
          <div className="mt-1.5 h-1.5 rounded-full bg-line overflow-hidden"><div className="h-full bg-violet transition-all" style={{ width: `${(d.done / d.total) * 100}%` }} /></div>
        )}
      </div>
      {running ? <button className="btn-secondary btn-sm" onClick={stop}><Square size={12} /> Stop</button>
        : left > 0 && (available ? <button className="btn-secondary btn-sm" onClick={start}>Read {left} with Ollama</button>
          : <span className="text-[11.5px] text-ink-faint">Ollama isn't running</span>)}
      {running && <Loader2 size={14} className="animate-spin text-ink-muted" />}
    </div>
  );
}
