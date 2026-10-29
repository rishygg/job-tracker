import { Ghost, Hourglass, Zap } from "lucide-react";
import { type Dict } from "../api";
import { useApi, useApp } from "../store";
import { EmptyState, Monogram, Skeleton } from "./ui";

/** Which companies reply fast, which take ages, and which never reply. */
export function Companies() {
  const { filterQuery } = useApp();
  const { data, loading } = useApi<Dict>(`/api/analytics/companies${filterQuery()}`);
  if (loading && !data) return <Skeleton className="h-80" />;
  if (!data || (!data.fastest.length && !data.ghosts.length && !data.responsive.length)) return <div className="card"><EmptyState art="chart" title="Not enough replies yet">Once companies start replying (record the stage with its date), you'll see who answers quickly and who doesn't.</EmptyState></div>;
  const max = Math.max(1, ...data.slowest.map((r: Dict) => r.median_days));
  return (
    <div className="space-y-5">
      <p className="text-[12.5px] text-ink-muted max-w-3xl">Who replies, how fast, and who goes quiet. Useful for knowing when a follow-up is worth sending, and when silence probably means no.
        {data.dated_replies < 5 && " Reply times need stages recorded with their real date (imported history doesn't have them), so they'll fill in as you go."}</p>
      <div className="grid lg:grid-cols-3 gap-5 items-start">
        {data.fastest.length >= 3 ? <>
          <Board title="Quickest to reply" icon={<Zap size={14} className="text-ok-bright" />} rows={data.fastest} max={max} tone="ok" />
          <Board title="Slowest to reply" icon={<Hourglass size={14} className="text-warn" />} rows={data.slowest} max={max} tone="warn" />
        </> : <>
          <RateBoard title="Most responsive" icon={<Zap size={14} className="text-ok-bright" />} rows={data.responsive} />
          <Board title="Reply times so far" icon={<Hourglass size={14} className="text-warn" />} rows={data.fastest} max={max} tone="ok" />
        </>}
        <section className="card p-5">
          <h3 className="text-[14px] font-semibold flex items-center gap-2 mb-1"><Ghost size={14} className="text-ink-muted" />The ghost list</h3>
          <p className="text-[11.5px] text-ink-muted mb-3">Share of applications with no reply at all, among those old enough to judge.</p>
          {!data.ghosts.length ? <p className="text-[12.5px] text-ink-muted">Nobody yet. Lucky you.</p> : (
            <ol className="space-y-2">
              {data.ghosts.map((r: Dict, i: number) => (
                <li key={r.company} className="flex items-center gap-2.5 text-[13px]">
                  <span className="num w-4 text-ink-faint text-[11.5px]">{i + 1}</span>
                  <Monogram name={r.company} size={24} />
                  <span className="flex-1 min-w-0 truncate">{r.company}</span>
                  <span className="num text-[12px]"><b>{Math.round(r.ghost_rate * 100)}%</b><span className="text-ink-muted"> · {r.ghosted} of {r.judged}</span></span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}

function Board({ title, icon, rows, max, tone }: { title: string; icon: React.ReactNode; rows: Dict[]; max: number; tone: "ok" | "warn" }) {
  return (
    <section className="card p-5">
      <h3 className="text-[14px] font-semibold flex items-center gap-2 mb-3">{icon}{title}</h3>
      {!rows.length ? <p className="text-[12.5px] text-ink-muted">No replies with dates yet.</p> : (
        <ol className="space-y-2.5">
          {rows.map((r) => (
            <li key={r.company} className="text-[13px]">
              <div className="flex items-center gap-2.5">
                <Monogram name={r.company} size={24} />
                <span className="flex-1 min-w-0 truncate">{r.company}</span>
                <span className="num font-semibold">{Math.round(r.median_days)}<span className="text-ink-muted font-normal"> days</span></span>
              </div>
              <div className="ml-[34px] h-1.5 rounded-full bg-canvas mt-1 overflow-hidden">
                <div className={tone === "ok" ? "h-full rounded-full bg-ok-bright" : "h-full rounded-full bg-amber"} style={{ width: `${Math.max(4, (r.median_days / max) * 100)}%` }} />
              </div>
              <div className="ml-[34px] text-[11px] text-ink-faint mt-0.5 num">{r.replied} repl{r.replied === 1 ? "y" : "ies"} from {r.applications} application{r.applications === 1 ? "" : "s"}</div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function RateBoard({ title, icon, rows }: { title: string; icon: React.ReactNode; rows: Dict[] }) {
  return (
    <section className="card p-5">
      <h3 className="text-[14px] font-semibold flex items-center gap-2 mb-1">{icon}{title}</h3>
      <p className="text-[11.5px] text-ink-muted mb-3">Reply rate, companies with at least two applications.</p>
      {!rows.length ? <p className="text-[12.5px] text-ink-muted">Not enough applications per company yet.</p> : (
        <ol className="space-y-2.5">
          {rows.map((r) => (
            <li key={r.company} className="text-[13px]">
              <div className="flex items-center gap-2.5">
                <Monogram name={r.company} size={24} />
                <span className="flex-1 min-w-0 truncate">{r.company}</span>
                <span className="num font-semibold">{Math.round(r.reply_rate * 100)}%</span>
              </div>
              <div className="ml-[34px] h-1.5 rounded-full bg-canvas mt-1 overflow-hidden"><div className="h-full rounded-full bg-ok-bright" style={{ width: `${Math.max(4, r.reply_rate * 100)}%` }} /></div>
              <div className="ml-[34px] text-[11px] text-ink-faint mt-0.5 num">{r.replied} of {r.judged} replied</div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
