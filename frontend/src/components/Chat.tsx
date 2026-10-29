import { useEffect, useState } from "react";
import { Check, ClipboardCopy, Loader2, MessageSquareText, Sparkles } from "lucide-react";
import { api, type Dict } from "../api";
import { useApp } from "../store";
import { cls } from "../lib";
import { Modal } from "./ui";

export async function copyText(text: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(text); return true; }
  catch {
    // Fallback for browsers that block the clipboard API on http://localhost.
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    const ok = document.execCommand("copy"); ta.remove();
    return ok;
  }
}

const VERDICT_STYLE: Record<string, string> = {
  Apply: "bg-ok-soft text-ok border-ok-line", "Apply with caveats": "bg-warn-soft text-warn border-warn-line", Skip: "bg-neutral-soft text-ink-muted border-line",
};

// ------------------------------------------------------------ configurable ranking fields
let rankCfg: Promise<Dict> | null = null;
/** The extra ranking fields from config/ranking.yaml (fetched once; reset after editing them in Settings). */
export function useRankConfig(): Dict | null {
  const [cfg, setCfg] = useState<Dict | null>(null);
  useEffect(() => {
    rankCfg = rankCfg ?? api.get("/api/rank/config").catch(() => ({ fields: [] }));
    rankCfg.then(setCfg);
  }, []);
  return cfg;
}
export function resetRankConfig() { rankCfg = null; }

function fmtExtra(f: Dict, v: any) {
  return f.type === "number" ? `${v}${f.suffix ?? ""}` : String(v);
}
const LEVEL: Record<string, string> = {
  high: "bg-ok-soft text-ok border-ok-line", "very high": "bg-alert-soft text-alert border-alert/30",
  medium: "bg-warn-soft text-warn border-warn-line", low: "bg-neutral-soft text-ink-muted border-line",
};

/** The extra things your chat assistant filled in (salary, ATS match…). "card" shows compact chips; "detail" a full list. */
export function RankExtras({ rank, mode }: { rank?: Dict | null; mode: "card" | "detail" }) {
  const cfg = useRankConfig();
  const extra = rank?.extra;
  if (!extra || !cfg?.fields?.length) return null;
  const fields: Dict[] = cfg.fields.filter((f: Dict) => extra[f.key] !== undefined && (mode === "detail" || f.show === "card"));
  if (!fields.length) return null;
  if (mode === "card") return <>{fields.map((f) => (
    <span key={f.key} title={f.label} className={cls("chip h-5 text-[10.5px] max-w-full truncate", f.type === "choice" && f.key.includes("chance") ? LEVEL[String(extra[f.key]).toLowerCase()] : "")}>
      {f.type === "number" ? `${f.label.split(" ")[0]} ${fmtExtra(f, extra[f.key])}` : f.type === "choice" ? `${f.label}: ${extra[f.key]}` : fmtExtra(f, extra[f.key])}
    </span>))}</>;
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12.5px] mt-2">
      {fields.map((f) => <div key={f.key} className="contents"><dt className="text-ink-muted">{f.label}</dt><dd className="text-ink-soft min-w-0">{fmtExtra(f, extra[f.key])}</dd></div>)}
    </dl>
  );
}

/** The ranking your chat assistant gave a job. */
export function RankChip({ rank, size = "sm" }: { rank?: Dict | null; size?: "sm" | "md" }) {
  if (!rank) return null;
  return (
    <span title={`Chat assistant ranking${rank.at ? ` (${rank.at.slice(0, 10)})` : ""}: ${rank.reason ?? ""}${rank.missing ? ` · Missing: ${rank.missing}` : ""}`}
      className={cls("chip", size === "sm" ? "h-5 text-[10.5px]" : "h-6", VERDICT_STYLE[rank.verdict] ?? "")}>
      <MessageSquareText size={size === "sm" ? 10 : 12} />{rank.score ? `${rank.score}/10` : ""}{rank.verdict ? ` · ${rank.verdict}` : ""}
    </span>
  );
}

export function PromptButton({ kind, refId, ptype, label, primary }: { kind: string; refId: number; ptype: string; label: string; primary?: boolean }) {
  const { toast } = useApp();
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  async function go() {
    setState("busy");
    try {
      const r = await api.get(`/api/prompts/${kind}/${refId}/${ptype}`);
      if (await copyText(r.prompt)) { setState("done"); toast("Prompt copied. Paste it into ChatGPT or Claude."); setTimeout(() => setState("idle"), 2500); }
      else { setState("idle"); toast("Couldn't copy to the clipboard", "error"); }
    } catch (e: any) { setState("idle"); toast(e.message, "error"); }
  }
  return (
    <button className={cls(primary ? "btn-primary" : "btn-secondary", "btn-sm justify-start")} onClick={go} disabled={state === "busy"}>
      {state === "busy" ? <Loader2 size={13} className="animate-spin" /> : state === "done" ? <Check size={13} /> : <ClipboardCopy size={13} />}{label}
    </button>
  );
}

/** Ready-made prompts for one job: the tracker collects the context, your chat assistant does the thinking. */
export function AskAssistant({ kind, refId }: { kind: string; refId: number }) {
  return (
    <section className="rounded-xl border border-line p-4">
      <div className="flex items-center gap-2 text-[13.5px] font-semibold"><Sparkles size={14} className="text-brand" />Ask your chat assistant</div>
      <p className="text-[12px] text-ink-muted mt-0.5 mb-3">Each button copies a prompt with this job, your profile and eligibility. Paste it into ChatGPT, Claude or similar.</p>
      <div className="grid sm:grid-cols-3 gap-2">
        <div className="space-y-1.5">
          <div className="eyebrow">Critique</div>
          <PromptButton kind={kind} refId={refId} ptype="weakness" label="Biggest weakness" />
          <PromptButton kind={kind} refId={refId} ptype="evidence" label="Claims needing evidence" />
          <PromptButton kind={kind} refId={refId} ptype="hesitate" label="Why a recruiter might hesitate" />
        </div>
        <div className="space-y-1.5">
          <div className="eyebrow">Write</div>
          <PromptButton kind={kind} refId={refId} ptype="cv" label="Tailor my CV" />
          <PromptButton kind={kind} refId={refId} ptype="letter" label="Draft a cover letter" />
        </div>
        <div className="space-y-1.5">
          <div className="eyebrow">Interview</div>
          <PromptButton kind={kind} refId={refId} ptype="interview" label="Likely questions & stories" />
        </div>
      </div>
    </section>
  );
}

/** Rank several jobs in one go: copy the prompt(s) to your chat assistant, paste each reply back. */
export function RankModal({ items, onClose, title, counts }:
  { items?: Dict[]; onClose: () => void; title?: string; counts?: { fresh: number; ranked: number } }) {
  const { toast, refresh } = useApp();
  const cfg = useRankConfig();
  const [goals, setGoals] = useState<string | null>(null);
  useEffect(() => { if (cfg && goals === null) setGoals(cfg.goals || cfg.default_criteria || ""); }, [cfg]);
  const [prompt, setPrompt] = useState<Dict | null>(null);
  const [copied, setCopied] = useState<Set<number>>(new Set());
  const [recorded, setRecorded] = useState<Set<string>>(new Set());
  const [again, setAgain] = useState(false);
  const [reply, setReply] = useState("");
  const [result, setResult] = useState<Dict | null>(null);
  const [busy, setBusy] = useState(false);

  async function build() {
    setBusy(true);
    try {
      const r = await api.post("/api/rank/prompt", { items: items ?? [], goals: goals ?? "", include_ranked: again });
      if (cfg) cfg.goals = goals ?? "";
      setPrompt(r); setCopied(new Set()); setRecorded(new Set());
      if (r.parts.length === 1) {
        if (await copyText(r.parts[0].prompt)) { setCopied(new Set([0])); toast(`Prompt for ${r.count} job${r.count === 1 ? "" : "s"} copied. Paste it into your chat assistant.`); }
      } else if (r.parts.length > 1) {
        if (await copyText(r.parts[0].prompt)) { setCopied(new Set([0])); toast(`Part 1 of ${r.parts.length} copied. Paste it into your chat assistant.`); }
      }
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  }
  async function copyPart(i: number) {
    if (await copyText(prompt!.parts[i].prompt)) { setCopied((c) => new Set(c).add(i)); toast(`Part ${i + 1} of ${prompt!.parts.length} copied`); }
  }
  async function importReply() {
    setBusy(true);
    try {
      const r = await api.post("/api/rank/import", { text: reply });
      setResult(r); setReply(""); refresh();
      setRecorded((s) => new Set([...s, ...r.saved.map((x: Dict) => x.code)]));
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  }
  const n = items?.length;
  const parts: Dict[] = prompt?.parts ?? [];
  const doneParts = parts.filter((p) => p.codes.every((c: string) => recorded.has(c))).length;
  const nothing = prompt && prompt.count === 0;
  return (
    <Modal open onClose={onClose} width="max-w-2xl" title={title ?? (n ? `Rank ${n} job${n === 1 ? "" : "s"} with your chat assistant` : "Rank your Inbox with your chat assistant")}
      footer={<button className="btn-secondary" onClick={onClose}>{recorded.size ? "Done" : "Close"}</button>}>
      {result ? (
        <div className="space-y-3">
          <p className="text-[13px]"><b className="num">{result.saved.length}</b> ranking{result.saved.length === 1 ? "" : "s"} recorded. They show in your Inbox, on the board and in each job's Fit step.</p>
          <ul className="divide-y divide-line border border-line rounded-xl max-h-72 overflow-y-auto scroll-thin">
            {result.saved.map((r: Dict) => (
              <li key={r.code} className="px-3 py-2 flex items-start gap-3">
                <span className="num text-[13px] font-semibold w-10 shrink-0">{r.score ?? "–"}/10</span>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium">{r.position} <span className="text-ink-muted font-normal">· {r.company}</span></div>
                  <div className="text-[12px] text-ink-muted">{r.reason}{r.missing && r.missing.toLowerCase() !== "none" ? ` · Missing: ${r.missing}` : ""}</div>
                  <div className="flex flex-wrap gap-1 mt-1"><RankExtras rank={r} mode="card" /></div>
                </div>
                <RankChip rank={r} />
              </li>
            ))}
          </ul>
          {result.unknown?.length > 0 && <p className="text-[12px] text-warn">Not found (deleted or wrong code): {result.unknown.join(", ")}</p>}
          {result.not_in_reply?.length > 0 && (
            <div className="rounded-lg bg-warn-soft text-warn-strong text-[12.5px] p-3">
              <b>{result.not_in_reply.length} job{result.not_in_reply.length === 1 ? " wasn't" : "s weren't"} in the reply</b> ({result.not_in_reply.slice(0, 12).join(", ")}{result.not_in_reply.length > 12 ? "…" : ""}).
              Long answers often get cut off. In the same chat, reply <i>"Continue with the remaining jobs, same JSON format"</i>, then paste that in too; rankings already recorded are kept.
            </div>
          )}
          {result.unscored?.length > 0 && <p className="text-[12px] text-warn">No score found for: {result.unscored.join(", ")}</p>}
          {parts.length > 1 && <p className="text-[12.5px] text-ink-soft"><b className="num">{doneParts}</b> of <b className="num">{parts.length}</b> parts recorded.</p>}
          <button className="btn-secondary" onClick={() => setResult(null)}>{parts.length > 1 || result.not_in_reply?.length ? "Paste another reply" : "Back"}</button>
        </div>
      ) : (
        <ol className="space-y-5">
          <li>
            <div className="text-[13.5px] font-semibold">1. Copy the prompt</div>
            <p className="text-[12.5px] text-ink-muted mt-0.5 mb-2">It contains your profile, eligibility and {n ? "the selected jobs'" : "the descriptions of every Inbox job that isn't ranked yet"} (cleaned of page clutter), with a fixed reply format. A long list is cut into parts the assistant can answer one at a time.</p>
            <label className="label">What you're looking for <span className="font-normal text-ink-muted">· saved for next time</span></label>
            <textarea className="textarea h-28 text-[12.5px]" value={goals ?? ""} onChange={(e) => setGoals(e.target.value)}
              placeholder="e.g. data roles in pharma in Switzerland, internship from March, salary above 40k, German up to B1" />
            {cfg && cfg.fields?.length > 0 && <p className="text-[11.5px] text-ink-muted mt-1">The assistant also fills in: {cfg.fields.map((f: Dict) => f.label).join(", ")}. Change these in Settings → Rules → Chat ranking fields.</p>}
            {cfg?.error && <p className="text-[11.5px] text-warn mt-1">Your ranking fields file has an error ({cfg.error}), so only the built-in fields are used.</p>}
            {!n && (counts?.ranked ?? prompt?.ranked ?? 0) > 0 && (
              <label className="flex items-center gap-2 mt-2 text-[12.5px] text-ink-soft cursor-pointer">
                <input type="checkbox" className="accent-brand w-4 h-4" checked={again} onChange={(e) => { setAgain(e.target.checked); setPrompt(null); }} />
                Also rank the {counts?.ranked ?? prompt?.ranked} I've already ranked (e.g. after changing my criteria)
              </label>
            )}
            <div className="flex items-center gap-3 mt-2 flex-wrap">
              <button className="btn-primary" disabled={busy || (!n && !again && counts?.fresh === 0)} onClick={build}>
                {busy && !prompt ? <Loader2 size={14} className="animate-spin" /> : <ClipboardCopy size={14} />}
                {!n && counts ? `Copy prompt for ${again ? counts.fresh + counts.ranked : counts.fresh} job${(again ? counts.fresh + counts.ranked : counts.fresh) === 1 ? "" : "s"}` : "Copy prompt"}
              </button>
              {prompt && !nothing && <span className="text-[12px] text-ink-muted num">{prompt.count} jobs · {Math.round(prompt.chars / 1000)}k characters{parts.length > 1 ? ` · ${parts.length} parts` : ""}</span>}
              {!n && counts?.fresh === 0 && !again && <span className="text-[12px] text-ink-muted">Nothing new to rank.</span>}
            </div>
            {nothing && <p className="text-[12.5px] text-warn mt-2">Nothing to rank{prompt.no_description ? `: ${prompt.no_description} job${prompt.no_description === 1 ? " has" : "s have"} no description` : ""}.</p>}
            {prompt && !nothing && prompt.no_description > 0 && <p className="text-[11.5px] text-ink-muted mt-1">{prompt.no_description} job{prompt.no_description === 1 ? " has" : "s have"} no description and {prompt.no_description === 1 ? "was" : "were"} left out.</p>}
            {parts.length > 1 && (
              <div className="mt-3 rounded-xl border border-line divide-y divide-line">
                {parts.map((p, i) => (
                  <div key={i} className="flex items-center gap-3 px-3 py-2">
                    <span className="num text-[12.5px] font-semibold w-16">Part {i + 1}</span>
                    <span className="text-[12px] text-ink-muted flex-1 num">{p.count} jobs · {Math.round(p.chars / 1000)}k characters</span>
                    {p.codes.every((c: string) => recorded.has(c)) ? <span className="chip h-6 text-[11px] bg-ok-soft text-ok border-ok-line"><Check size={11} />Recorded</span>
                      : <button className="btn-secondary btn-sm" onClick={() => copyPart(i)}>{copied.has(i) ? <Check size={13} /> : <ClipboardCopy size={13} />} {copied.has(i) ? "Copied, copy again" : "Copy"}</button>}
                  </div>
                ))}
                <p className="px-3 py-2 text-[11.5px] text-ink-muted">Paste each part into the same chat or a fresh one, then paste the reply in step 2. Do them one at a time, in any order.</p>
              </div>
            )}
          </li>
          <li>
            <div className="text-[13.5px] font-semibold">2. Paste the assistant's reply</div>
            <p className="text-[12.5px] text-ink-muted mt-0.5 mb-2">Paste the whole answer; the tracker finds the job codes (like S7 or A12) and records each score and reason.{parts.length > 1 ? " Replies for the other parts can follow one after another." : ""}</p>
            <textarea className="textarea h-32 text-[12.5px] font-mono" value={reply} onChange={(e) => setReply(e.target.value)} placeholder='[{"code": "S7", "score": 8, "verdict": "Apply", "reason": "…"}]' />
            <button className="btn-primary mt-2" disabled={busy || !reply.trim()} onClick={importReply}>Record rankings</button>
          </li>
        </ol>
      )}
    </Modal>
  );
}
