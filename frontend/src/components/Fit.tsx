import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Check, ChevronDown, CircleDashed, Languages, Loader2, MessagesSquare, RefreshCw, ShieldAlert, Sparkles, X } from "lucide-react";
import { api, type Dict } from "../api";
import { useApp } from "../store";
import { cls, pct, tok } from "../lib";
import { EmptyState } from "./ui";
import { RankChip, RankExtras } from "./Chat";

export const ACTION_STYLE: Record<string, { color: string; bg: string; ring: string }> = {
  Apply: { color: tok("ok"), bg: tok("ok-soft"), ring: tok("ok-line") },
  "Apply with caveats": { color: tok("warn"), bg: tok("warn-soft"), ring: tok("warn-line") },
  Deprioritise: { color: tok("ink-muted"), bg: tok("neutral-soft"), ring: tok("line-strong") },
  "Not scored": { color: tok("info"), bg: tok("info-soft"), ring: tok("info-line") },
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
  const color = score === null || score === undefined ? tok("line-strong") : v >= 0.7 ? "#0e9a69" : v >= 0.45 ? "#d97f06" : "#8f97a6";
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} aria-label={`Fit score ${pct(score)}`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke={tok("line")} strokeWidth={size > 50 ? 6 : 4} fill="none" />
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
  met: <span className="w-5 h-5 rounded-full bg-ok-soft text-ok flex items-center justify-center shrink-0"><Check size={12} strokeWidth={3} /></span>,
  partial: <span className="w-5 h-5 rounded-full bg-warn-soft text-warn flex items-center justify-center shrink-0"><CircleDashed size={12} strokeWidth={2.5} /></span>,
  missing: <span className="w-5 h-5 rounded-full bg-neutral-soft text-ink-faint flex items-center justify-center shrink-0"><X size={12} strokeWidth={3} /></span>,
};

function Requirement({ r }: { r: Dict }) {
  const fromProfile = typeof r.evidence === "string" && r.evidence.startsWith("Profile:");
  return (
    <li className="flex gap-2.5 py-2">
      {STATUS_ICON[r.status]}
      <div className="min-w-0">
        <div className="text-[13px] leading-snug">{r.text}</div>
        {r.evidence && (
          <div className={cls("mt-1 text-[12px] leading-snug pl-2.5 border-l-2", r.evidence_verified === false ? "border-warn-line text-ink-muted" : "border-brand/30 text-ink-soft")}>
            {fromProfile ? <span className="text-ink-muted">{r.evidence}</span> : <>“{r.evidence}”</>}
            {!fromProfile && <span className="block text-[10.5px] text-ink-faint mt-0.5">{r.evidence_verified === false ? "Couldn't verify in your profile" : r.evidence_section ? `From your profile · ${r.evidence_section}` : "From your profile"}</span>}
          </div>
        )}
        {r.note && <div className="text-[11.5px] text-ink-muted mt-1">{r.note}</div>}
      </div>
    </li>
  );
}

const SEV: Record<string, string> = { high: tok("danger"), medium: tok("warn"), low: tok("ink-faint") };

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
            <span className="text-[11.5px] text-ink-muted">Rules · instant</span></div>
          <p className="text-[13.5px] mt-1.5 leading-snug">{res.recommendation.why}</p>
          {res.summary && <p className="text-[12.5px] text-ink-muted mt-1">{res.summary}</p>}
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

      {res.posting_language === "de" ? (
        <div className="flex gap-2 p-3 rounded-lg bg-info-soft text-[12.5px] text-ink-soft"><Languages size={15} className="mt-0.5 shrink-0 text-info" />
          <span>{res.note} Use <b>Rank with chat</b> on the board, or the prompts below, and paste the result back.</span></div>
      ) : (
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
      )}

      {res.soft_skills?.length > 0 && (
        <section>
          <div className="eyebrow mb-1.5">Soft skills they mention <span className="normal-case tracking-normal font-normal text-ink-faint">· not scored; show them in your letter and interview</span></div>
          <div className="flex flex-wrap gap-1.5">{res.soft_skills.map((x: string, i: number) => <span key={i} className="chip h-auto py-1 whitespace-normal leading-snug max-w-full">{x}</span>)}</div>
        </section>
      )}

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
    </div>
  );
}

/** Explainable rule-based fit for a saved job or application, plus the chat assistant's ranking if you imported one. */
export function FitPanel({ kind, refId, hasJd }: { kind: "application" | "opportunity"; refId: number; hasJd: boolean }) {
  const { toast, version } = useApp();
  const [state, setState] = useState<Dict | null>(null);
  const [busy, setBusy] = useState(false);
  const [ai, setAi] = useState<Dict | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => { setOpen(false); }, [kind, refId]);
  useEffect(() => { api.get("/api/ai/status").then(setAi).catch(() => {}); }, []);
  const load = () => api.get(`/api/fit/${kind}/${refId}`).then(setState).catch(() => setState({ result: null }));
  useEffect(() => { load(); }, [kind, refId, version]);

  async function run() {
    setBusy(true);
    try { setState(await api.post(`/api/fit/${kind}/${refId}`, {})); }
    catch (e: any) { toast(e.message, "error"); }
    finally { setBusy(false); }
  }

  if (ai && !ai.has_profile) return (
    <EmptyState art="inbox" title="Add your experience first" action={<Link to="/me" className="btn-primary">Go to Me</Link>}>
      Add your education, experience and projects, and your languages, degree and work permits. Then every job gets an instant fit check.
    </EmptyState>
  );
  if (!hasJd) return <EmptyState art="notes" title="No job description yet">Paste the full posting in the Job description tab, then come back here.</EmptyState>;
  if (!state) return <div className="py-10 flex justify-center text-ink-muted"><Loader2 className="animate-spin" size={20} /></div>;

  return (
    <div className="space-y-4">
      {state.rank && (
        <div className="flex items-start gap-3 p-3 rounded-xl border border-violet/30 bg-violet/5">
          <MessagesSquare size={16} className="text-violet mt-0.5 shrink-0" />
          <div className="min-w-0 flex-1 text-[13px]">
            <div className="flex flex-wrap items-center gap-2"><span className="font-medium">Your chat assistant's ranking</span><RankChip rank={state.rank} />
              {state.rank.at && <span className="text-[11px] text-ink-faint">{String(state.rank.at).slice(0, 10)}</span>}</div>
            {state.rank.reason && <p className="mt-1 text-ink-soft leading-snug">{state.rank.reason}</p>}
            {state.rank.missing && state.rank.missing.toLowerCase() !== "none" && <p className="mt-0.5 text-[12px] text-ink-muted">Main gap: {state.rank.missing}</p>}
            <RankExtras rank={state.rank} mode="detail" />
          </div>
        </div>
      )}
      {!state.result ? (
        <EmptyState art="target" title="Check how well you fit"
          action={<button className="btn-primary" disabled={busy} onClick={run}>{busy ? <><Loader2 className="animate-spin" size={15} /> Checking…</> : <><Sparkles size={15} /> Check fit</>}</button>}>
          Essential and preferred requirements, the line in your profile that shows each one, blockers like language or permits, and a recommendation.
        </EmptyState>
      ) : (
        <>
          {/* With a chat ranking the rule-based check is the backup: one line, details on demand. */}
          {state.rank && (
            <button className="w-full flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-left text-[12.5px] hover:bg-canvas" aria-expanded={open}
              onClick={() => setOpen(!open)}>
              <span className="text-ink-muted">Rule-based check:</span>
              <ActionPill action={state.result.recommendation.action} size="sm" />
              {state.result.score !== null && state.result.score !== undefined && <b className="num">{pct(state.result.score)}</b>}
              {state.stale && <span className="text-warn">· out of date</span>}
              <span className="ml-auto inline-flex items-center gap-1 text-ink-muted">{open ? "hide details" : "show details"}<ChevronDown size={14} className={cls("transition", open && "rotate-180")} /></span>
            </button>
          )}
          {(!state.rank || open) && (
            <div className="space-y-4">
              <div className="flex justify-end">
                <button className="btn-secondary btn-sm" disabled={busy} onClick={run} title="Re-run the instant rule check"><RefreshCw size={13} /> Re-check</button>
              </div>
              {state.stale && <div className="flex gap-2 p-2.5 rounded-lg bg-warn-soft text-warn-strong text-[12.5px]"><AlertTriangle size={14} className="mt-0.5 shrink-0" />Your profile or this job description changed since this check. Re-check to update.</div>}
              <div className="anim-fade"><FitResultView res={state.result} /></div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
