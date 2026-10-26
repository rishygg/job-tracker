import { useEffect, useMemo, useState } from "react";
import { Check, EyeOff, Eye, Loader2, Plus, RefreshCw, Sparkles, Trash2 } from "lucide-react";
import { api, type Dict } from "../api";
import { useApi, useApp } from "../store";
import { cls } from "../lib";
import { Field, Select } from "./ui";
import { JobProgress, isActive, useJob } from "./AiJob";

const KINDS = ["achievement", "responsibility", "project", "publication", "qualification", "coursework", "skill", "summary", "personal"];
const KIND_STYLE: Record<string, string> = {
  achievement: "bg-[#e8f6f0] text-[#0a7a53] border-[#bfe6d6]", responsibility: "bg-[#edf2fc] text-[#2a55b0] border-[#c9d7f4]",
  project: "bg-[#f2eefb] text-[#6442b4] border-[#dcd0f3]", publication: "bg-[#fdf4e6] text-[#a35f00] border-[#f5dcb1]",
  qualification: "bg-canvas text-ink-soft border-line", coursework: "bg-canvas text-ink-soft border-line", personal: "bg-canvas text-ink-faint border-line", skill: "bg-canvas text-ink-soft border-line", summary: "bg-canvas text-ink-soft border-line",
};

/** The evidence bank: your CV as structured, reusable records. */
export function EvidenceBank() {
  const { toast, refresh } = useApp();
  const { data, loading } = useApi<Dict>("/api/evidence");
  const { data: ai } = useApi<Dict>("/api/ai/status");
  const [busy, setBusy] = useState<string | null>(null);
  const [showHidden, setShowHidden] = useState(false);
  const [adding, setAdding] = useState({ text: "", kind: "achievement", context: "" });
  const [job, setJob] = useJob(null, undefined, (j) => { refresh(); toast(j.status === "done" ? "Evidence enriched" : j.error ?? "Stopped", j.status === "error" ? "error" : "ok"); });

  const groups = useMemo(() => {
    const g = new Map<string, Dict[]>();
    for (const e of data?.items ?? []) {
      if (e.hidden && !showHidden) continue;
      const flat = ["qualification", "skill", "summary"].includes(e.kind) || !e.context;
      const key = flat ? (e.section ?? "Other") : `${e.section ?? "Other"} · ${e.context}`;
      g.set(key, [...(g.get(key) ?? []), e]);
    }
    return [...g.entries()];
  }, [data, showHidden]);

  async function act(label: string, fn: () => Promise<unknown>, done?: string) {
    setBusy(label);
    try { await fn(); refresh(); if (done) toast(done); } catch (e: any) { toast(e.message, "error"); } finally { setBusy(null); }
  }
  const patch = (id: number, body: Dict) => act(`p${id}`, () => api.patch(`/api/evidence/${id}`, body));

  if (loading && !data) return <div className="py-10 flex justify-center"><Loader2 className="animate-spin text-ink-muted" /></div>;
  if (!data?.has_cv) return <p className="text-[13px] text-ink-muted">Upload your CV under Profile first; it's turned into an evidence bank automatically.</p>;
  const c = data.counts;
  const hiddenCount = data.items.filter((e: Dict) => e.hidden).length;

  return (
    <div className="space-y-5">
      <section className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-2xl">
            <h2 className="text-[15px] font-semibold">Evidence bank</h2>
            <p className="text-[12.5px] text-ink-muted">Your CV split into records once, so every job can be checked quickly against the most relevant ones. Confirm records, add what you actually did, hide what's irrelevant, or add evidence that isn't on your CV.</p>
          </div>
          <div className="flex gap-1.5">
            <button className="btn-secondary btn-sm" disabled={!!busy} onClick={() => act("rebuild", () => api.post("/api/evidence/rebuild"), "Rebuilt from your CV (your edits are kept)")}>
              {busy === "rebuild" ? <Loader2 className="animate-spin" size={13} /> : <RefreshCw size={13} />} Rebuild from CV
            </button>
            {ai?.available && !isActive(job) && (
              <button className="btn-primary btn-sm" disabled={!!busy} onClick={() => act("enrich", async () => setJob((await api.post("/api/evidence/enrich")).job))}
                title="One-time pass: what you did and the outcome, for each line. Runs in the background.">
                <Sparkles size={13} /> Enrich with AI
              </button>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-x-5 gap-y-1 mt-4 text-[12.5px] text-ink-soft">
          <span><b className="num text-ink">{c.achievement}</b> achievements</span>
          <span><b className="num text-ink">{c.responsibility}</b> responsibilities</span>
          <span><b className="num text-ink">{c.qualification}</b> qualifications</span>
          <span><b className="num text-ink">{c.project + c.publication}</b> projects & publications</span>
          <span><b className="num text-ink">{data.confirmed}</b> confirmed</span>
          {hiddenCount > 0 && <button className="text-brand hover:underline" onClick={() => setShowHidden(!showHidden)}>{showHidden ? "Hide" : "Show"} {hiddenCount} hidden</button>}
        </div>
        {isActive(job) && <div className="mt-3"><JobProgress job={job!} speed={ai?.speed} /></div>}
        {c.achievement < 3 && <p className="text-[12px] text-[#a35f00] mt-2">Few achievements found. Records with a result or number make the strongest evidence; mark them as achievements or add them below.</p>}
      </section>

      {groups.map(([title, items]) => (
        <section key={title} className="card">
          <div className="px-5 py-3 border-b border-line text-[13px] font-semibold">{title}</div>
          <ul className="divide-y divide-line">
            {items.map((e) => <EvidenceRow key={e.id} e={e} onPatch={(b) => patch(e.id, b)} onDelete={() => act(`d${e.id}`, () => api.del(`/api/evidence/${e.id}`), "Removed")} />)}
          </ul>
        </section>
      ))}

      <section className="card p-5">
        <h3 className="text-[14px] font-semibold mb-1">Add evidence that isn't on your CV</h3>
        <p className="text-[12.5px] text-ink-muted mb-3">Side projects, things you cut for space, results you only remember now. Used in reviews like any other record.</p>
        <div className="grid sm:grid-cols-[1fr_170px] gap-3">
          <Field label="What you did and what came of it"><textarea className="textarea h-20" value={adding.text} onChange={(e) => setAdding({ ...adding, text: e.target.value })} placeholder="e.g. Taught a weekly Python workshop for 30 master's students; 90% rated it useful" /></Field>
          <div className="space-y-3">
            <Field label="Type"><Select value={adding.kind} onChange={(v) => setAdding({ ...adding, kind: v })} options={KINDS} /></Field>
            <Field label="Where (optional)"><input className="input" value={adding.context} onChange={(e) => setAdding({ ...adding, context: e.target.value })} placeholder="Role or project" /></Field>
          </div>
        </div>
        <button className="btn-primary mt-3" disabled={!adding.text.trim() || !!busy}
          onClick={() => act("add", () => api.post("/api/evidence", adding), "Evidence added").then(() => setAdding({ text: "", kind: "achievement", context: "" }))}>
          <Plus size={15} /> Add evidence
        </button>
      </section>
    </div>
  );
}

function EvidenceRow({ e, onPatch, onDelete }: { e: Dict; onPatch: (b: Dict) => void; onDelete: () => void }) {
  const [note, setNote] = useState(e.note ?? "");
  const [open, setOpen] = useState(false);
  useEffect(() => setNote(e.note ?? ""), [e.note]);
  return (
    <li className={cls("px-5 py-3", e.hidden && "opacity-50")}>
      <div className="flex items-start gap-3">
        <select aria-label="Type" value={e.kind} onChange={(x) => onPatch({ kind: x.target.value })}
          className={cls("h-6 px-1.5 rounded-md border text-[11px] font-medium shrink-0 mt-0.5", KIND_STYLE[e.kind] ?? KIND_STYLE.summary)}>
          {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <div className="flex-1 min-w-0">
          <div className="text-[13px] leading-snug">{e.text}</div>
          {(e.did || e.outcome) && <div className="text-[12px] text-ink-muted mt-0.5">{e.did}{e.outcome ? ` → ${e.outcome}` : ""}</div>}
          <div className="flex flex-wrap gap-1 mt-1.5">
            {e.metrics.map((m: string) => <span key={m} className="chip h-5 text-[10.5px] bg-[#fdf4e6] text-[#a35f00] border-[#f5dcb1]">{m}</span>)}
            {e.skills.slice(0, 6).map((s: string) => <span key={s} className="chip h-5 text-[10.5px]">{s}</span>)}
            {e.stakeholders.map((s: string) => <span key={s} className="chip h-5 text-[10.5px] bg-[#f2eefb] text-[#6442b4] border-[#dcd0f3]">{s}</span>)}
            {e.source === "manual" && <span className="chip h-5 text-[10.5px]">added by you</span>}
          </div>
          {(open || e.note) && (
            <input className="input h-8 mt-2 text-[12.5px]" placeholder="What you personally did, tools, outcome… (used in reviews)" value={note}
              onChange={(x) => setNote(x.target.value)} onBlur={() => note !== (e.note ?? "") && onPatch({ note })} />
          )}
        </div>
        <div className="flex items-center gap-0.5 shrink-0">
          {!open && !e.note && <button className="btn-ghost btn-sm text-[11.5px]" onClick={() => setOpen(true)}>Add note</button>}
          <button className={cls("btn-ghost btn-sm", e.confirmed && "text-brand")} title={e.confirmed ? "Confirmed" : "Confirm this is accurate"} onClick={() => onPatch({ confirmed: !e.confirmed })}>
            <Check size={14} strokeWidth={e.confirmed ? 3 : 2} />
          </button>
          <button className="btn-ghost btn-sm" title={e.hidden ? "Use in reviews again" : "Don't use in reviews"} onClick={() => onPatch({ hidden: !e.hidden })}>
            {e.hidden ? <Eye size={14} /> : <EyeOff size={14} />}
          </button>
          {e.source === "manual" && <button className="btn-ghost btn-sm" title="Delete" onClick={onDelete}><Trash2 size={13} /></button>}
        </div>
      </div>
    </li>
  );
}

export function WritingStyle() {
  const { meta, toast, refresh } = useApp();
  const [w, setW] = useState<Dict>({ spelling: "", tone: "", avoid: "", samples: "" });
  useEffect(() => { if (meta?.settings?.writing) setW({ spelling: "", tone: "", avoid: "", samples: "", ...meta.settings.writing }); }, [meta]);
  async function save() {
    try { await api.put("/api/settings", { writing: w }); refresh(); toast("Writing style saved"); } catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <section className="card p-5">
      <h2 className="text-[15px] font-semibold">How you write</h2>
      <p className="text-[12.5px] text-ink-muted mb-4">Included in AI reviews and in the brief you copy to a chat assistant, so the advice and drafts sound like you.</p>
      <div className="grid sm:grid-cols-3 gap-3">
        <Field label="Spelling"><Select value={w.spelling} onChange={(v) => setW({ ...w, spelling: v })} options={["British", "American"]} placeholder="No preference" /></Field>
        <Field label="Tone"><input className="input" value={w.tone} onChange={(e) => setW({ ...w, tone: e.target.value })} placeholder="e.g. direct, warm, no buzzwords" /></Field>
        <Field label="Words or phrases to avoid"><input className="input" value={w.avoid} onChange={(e) => setW({ ...w, avoid: e.target.value })} placeholder="e.g. passionate, leverage, synergy" /></Field>
      </div>
      <Field label="A sample of your writing (optional)" className="mt-3" hint="A paragraph from a past cover letter or email you were happy with.">
        <textarea className="textarea h-28 text-[13px]" value={w.samples} onChange={(e) => setW({ ...w, samples: e.target.value })} />
      </Field>
      <div className="flex justify-end mt-3"><button className="btn-primary" onClick={save}>Save writing style</button></div>
    </section>
  );
}
