import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, BookOpen, BriefcaseBusiness, CalendarClock, Check, ClipboardCheck, ExternalLink, Gauge, GraduationCap, Loader2, NotebookPen, Plus } from "lucide-react";
import { api, type Dict } from "../api";
import { useApp } from "../store";
import { cls, fmtDate, pct, relDays, today } from "../lib";
import { EmptyState } from "./ui";
import { FitPanel } from "./Fit";
import { AskAssistant, PromptButton } from "./Chat";
import { PracticeModal } from "./Practice";
import { CategoryChip } from "./careerShared";

type StepId = "fit" | "apply" | "interview" | "journal";
const ICON: Record<StepId, typeof Gauge> = { fit: Gauge, apply: BriefcaseBusiness, interview: GraduationCap, journal: NotebookPen };

/** One checklist per job: fit → apply → interview prep → journal. */
export function PreparePanel({ kind, refId, hasJd, onApply, info }:
  { kind: "application" | "opportunity"; refId: number; hasJd: boolean; onApply?: () => void; info?: Dict }) {
  const { version } = useApp();
  const [st, setSt] = useState<Dict | null>(null);
  const [step, setStep] = useState<StepId | null>(null);
  const load = () => api.get(`/api/prepare/${kind}/${refId}`).then(setSt).catch(() => {});
  useEffect(() => { setSt(null); setStep(null); load(); }, [kind, refId]);
  useEffect(() => { if (st) load(); }, [version]);

  const steps: Dict[] = st?.steps ?? [];
  // Saved jobs open on the fit check (the point is deciding); applications on the next thing to do.
  const current: StepId = step ?? (kind === "opportunity" ? "fit" : (steps.find((s) => s.relevant !== false && !s.done)?.id as StepId) ?? "fit");
  if (!st) return <div className="py-10 flex justify-center text-ink-muted"><Loader2 className="animate-spin" size={20} /></div>;
  return (
    <div className="space-y-5">
      <ol className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 rounded-xl border border-line bg-canvas/60 p-2">
        {steps.map((s, i) => <Step key={s.id} s={s} n={i + 1} active={current === s.id} onClick={() => setStep(s.id)} />)}
      </ol>
      <div key={current} className="anim-fade">
        {current === "fit" && (
          <div className="space-y-5">
            <FitPanel kind={kind} refId={refId} hasJd={hasJd} />
            {hasJd && st.has_profile && <AskAssistant kind={kind} refId={refId} />}
          </div>
        )}
        {current === "apply" && <ApplyStep kind={kind} s={steps.find((x) => x.id === "apply")!} onApply={onApply} info={info} />}
        {current === "interview" && <InterviewPrep kind={kind} refId={refId} relevant={steps.find((x) => x.id === "interview")?.relevant} />}
        {current === "journal" && <JournalStep kind={kind} refId={refId} />}
      </div>
    </div>
  );
}

function Step({ s, n, active, onClick }: { s: Dict; n: number; active: boolean; onClick: () => void }) {
  const Icon = ICON[s.id as StepId];
  const dim = s.relevant === false && !s.done;
  let sub = "To do";
  if (s.id === "fit") sub = s.rank ? `Chat: ${s.rank.score ?? "–"}/10` : s.done ? (s.score !== null && s.score !== undefined ? `Match ${pct(s.score)}` : s.action ?? "Checked") : "To do";
  else if (s.id === "apply") sub = s.done ? `Applied ${fmtDate(s.date, false)}` : s.deadline ? `Due ${relDays(s.deadline)}` : "Not yet";
  else if (s.id === "interview") sub = s.done ? `${s.practised} practised` : s.relevant ? "Get ready" : "When invited";
  else if (s.id === "journal") sub = s.done ? `${s.count} logged` : s.relevant ? "After interviews" : "Later";
  return (
    <li>
      <button onClick={onClick} aria-current={active ? "step" : undefined}
        className={cls("w-full h-full text-left rounded-lg px-2.5 py-2 border transition",
          active ? "bg-surface border-brand/50 shadow-card" : "border-transparent hover:bg-surface/70", dim && "opacity-60")}>
        <div className="flex items-center gap-1.5">
          <span className={cls("w-5 h-5 rounded-full flex items-center justify-center text-[10.5px] font-bold shrink-0",
            s.done && !s.stale ? "bg-ok-bright text-white" : s.stale ? "bg-warn-soft text-warn ring-1 ring-warn-line" : "bg-surface text-ink-muted ring-1 ring-line-strong")}>
            {s.done && !s.stale ? <Check size={11} strokeWidth={3} /> : s.stale ? "!" : n}
          </span>
          <Icon size={13} className="text-ink-muted shrink-0" />
          <span className="text-[12.5px] font-medium truncate">{s.label}</span>
        </div>
        <div className={cls("text-[11px] mt-0.5 pl-[26px] truncate", s.stale ? "text-warn" : "text-ink-muted")}>{s.stale ? "Profile or job changed" : sub}</div>
      </button>
    </li>
  );
}

function ApplyStep({ kind, s, onApply, info }: { kind: string; s: Dict; onApply?: () => void; info?: Dict }) {
  if (kind === "application") return (
    <div className="rounded-xl border border-line p-5">
      <div className="flex items-center gap-2 text-[14px] font-semibold"><Check size={16} className="text-ok-bright" />Applied on {fmtDate(s.date)}</div>
      <p className="text-[12.5px] text-ink-muted mt-1">{s.cv_version ? <>CV version used: <b className="text-ink">{s.cv_version}</b>.</> : "Tip: record which CV version you sent in Details, so the Analytics page can compare versions."}</p>
    </div>
  );
  return (
    <div className="rounded-xl border border-line p-5 space-y-4">
      <div>
        <div className="text-[14px] font-semibold">Ready to apply?</div>
        <p className="text-[12.5px] text-ink-muted mt-0.5">Tailor your CV and letter (the Fit step has prompts for your chat assistant), send the application, then mark it here.</p>
      </div>
      {s.deadline && <div className="text-[12.5px] flex items-center gap-1.5 text-ink-soft"><CalendarClock size={13} />Deadline {fmtDate(s.deadline)} · {relDays(s.deadline)}</div>}
      <div className="flex flex-wrap gap-2">
        {info?.url && <a className="btn-secondary" href={info.url} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Open posting</a>}
        {onApply && <button className="btn-primary" onClick={onApply}><BriefcaseBusiness size={14} /> I've applied</button>}
      </div>
    </div>
  );
}

function InterviewPrep({ kind, refId, relevant }: { kind: string; refId: number; relevant?: boolean }) {
  const { version, refresh } = useApp();
  const [d, setD] = useState<Dict | null>(null);
  const [open, setOpen] = useState<Dict | null>(null);
  const load = () => api.get(`/api/prepare/${kind}/${refId}/interview`).then(setD).catch(() => {});
  useEffect(() => { load(); }, [kind, refId, version]);
  if (!d) return <div className="py-8 flex justify-center"><Loader2 className="animate-spin text-ink-muted" /></div>;
  const ref = `${kind}:${refId}`;
  const done = new Set((d.practised ?? []).map((p: Dict) => p.question.toLowerCase()));
  return (
    <div className="space-y-4">
      {!relevant && <p className="text-[12.5px] text-ink-muted">No interview yet, but it's never too early: these come from the job's requirements and your own interview history.</p>}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="eyebrow">Likely questions</div>
        <PromptButton kind={kind} refId={refId} ptype="interview" label="More questions from your chat assistant" />
      </div>
      <ul className="divide-y divide-line rounded-xl border border-line">
        {d.suggested.map((q: Dict, i: number) => (
          <li key={i} className="px-4 py-2.5 flex items-start gap-3">
            <GraduationCap size={13} className="text-ink-muted mt-1 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-medium leading-snug">{q.question}</div>
              <div className="flex flex-wrap items-center gap-1.5 mt-0.5 text-[11.5px] text-ink-muted"><CategoryChip category={q.category} />{q.reason}
                {q.story && <span className="inline-flex items-center gap-1 text-violet"><BookOpen size={11} />{q.story.title}</span>}</div>
            </div>
            {done.has(q.question.toLowerCase()) ? <span className="text-[11.5px] text-ok inline-flex items-center gap-1"><Check size={12} />Practised</span>
              : <button className="btn-secondary btn-sm" onClick={() => setOpen({ ...q, ref })}>Practise</button>}
          </li>
        ))}
      </ul>
      {d.practised?.length > 0 && (
        <div>
          <div className="eyebrow mb-1.5">Your answers for this job</div>
          <ul className="space-y-1">{d.practised.map((p: Dict) => (
            <li key={p.id}><button className="w-full text-left text-[12.5px] rounded-md px-2 py-1 hover:bg-canvas" onClick={() => setOpen(p)}>
              {p.question}<span className="text-ink-muted num">{p.feedback?.score ? ` · ${p.feedback.score}/5` : ""}</span></button></li>
          ))}</ul>
        </div>
      )}
      {open && <PracticeModal item={open} onClose={() => { setOpen(null); load(); refresh(); }} />}
    </div>
  );
}

function JournalStep({ kind, refId }: { kind: string; refId: number }) {
  const navigate = useNavigate();
  const [d, setD] = useState<Dict | null>(null);
  const { version } = useApp();
  useEffect(() => { api.get(`/api/prepare/${kind}/${refId}/interview`).then(setD).catch(() => {}); }, [kind, refId, version]);
  const ivs: Dict[] = useMemo(() => d?.interviews ?? [], [d]);
  if (kind !== "application") return <EmptyState art="chat" title="Nothing to log yet">Once you've applied and had an interview, log it here: questions, how it went and feedback.</EmptyState>;
  return (
    <div className="space-y-3">
      {!ivs.length ? (
        <EmptyState art="chat" title="No interviews logged for this job"
          action={<button className="btn-primary" onClick={() => navigate(`/career?log=${refId}&date=${today()}`)}><Plus size={15} /> Log an interview</button>}>
          Right after an interview, note the questions and how each answer went. It feeds your practice plan.
        </EmptyState>
      ) : (
        <>
          <ul className="space-y-2">
            {ivs.map((i) => (
              <li key={i.id} className="rounded-xl border border-line px-4 py-3">
                <div className="flex flex-wrap justify-between gap-2 text-[13px]"><b>{i.round || "Interview"}</b><span className="text-ink-muted num">{fmtDate(i.date)}{i.rating ? ` · felt ${i.rating}/5` : ""}</span></div>
                <div className="text-[12px] text-ink-muted mt-0.5">{i.questions.length} questions{i.struggled ? ` · Hard: ${i.struggled}` : ""}</div>
                {i.next_steps && <div className="text-[12px] text-ink-soft mt-1 flex gap-1"><ClipboardCheck size={12} className="mt-0.5" />{i.next_steps}</div>}
              </li>
            ))}
          </ul>
          <button className="btn-secondary btn-sm" onClick={() => navigate(`/career?log=${refId}&date=${today()}`)}><Plus size={13} /> Log another</button>
        </>
      )}
      {ivs.some((i) => i.questions.some((q: Dict) => q.rating && q.rating <= 2)) && (
        <p className="text-[12px] text-warn flex gap-1.5"><AlertTriangle size={13} className="mt-0.5" />Some answers were rated weak; they're at the top of your practice plan.</p>
      )}
    </div>
  );
}
