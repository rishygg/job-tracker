import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, BellPlus, Check, CircleDashed, Eraser, Gauge, Sparkles, Star, X } from "lucide-react";
import { api, type Dict } from "../api";
import { useApp } from "../store";
import { cls, fmtDate, pct, today } from "../lib";
import { Field, Modal, Select, StatusPill } from "./ui";
import { ActionPill } from "./Fit";

const DIM_LABELS: Record<string, string> = {
  role_area: "Job family", seniority: "Seniority", industry: "Industry", region: "Location group",
  company_size: "Company size", work_authorization: "Work permit", language: "Language", work_mode: "Work mode",
};

const blank = () => ({
  position: "", company: "", location: "", status: "Applied", date_applied: today(), date_posted: "",
  source: "", url: "", cv_version: "", fit_rating: 0, salary: "", notes: "", job_description: "",
  workload: "", contract: "", deadline: "",
});
type Form = ReturnType<typeof blank>;
const GUESSED = ["position", "company", "location", "workload", "contract", "deadline"] as const;
const CONTRACTS = ["Permanent", "Fixed-term", "Internship", "Freelance", "Apprenticeship"];

export function QuickAdd() {
  const { quickAdd, setQuickAdd, meta, refresh, toast, openApp, prefill, setPrefill } = useApp();
  const navigate = useNavigate();
  const [f, setF] = useState(blank());
  const [over, setOver] = useState<Dict>({});
  const [parsed, setParsed] = useState<Dict | null>(null);
  const [rem, setRem] = useState({ on: false, title: "", date: "" });
  const [busy, setBusy] = useState(false);
  const [fit, setFit] = useState<Dict | null>(null);
  const [tidied, setTidied] = useState<{ original: string; lines: number } | null>(null);
  // Fields filled in from the posting, with how sure the parser was. Editing a field clears its flag.
  const [auto, setAuto] = useState<Record<string, string>>({});
  const skipTidy = useRef<string | null>(null);
  const fRef = useRef(f);
  fRef.current = f;

  const close = () => { setQuickAdd(false); };
  const reset = () => { setF(blank()); setOver({}); setParsed(null); setFit(null); setTidied(null); setAuto({}); setRem({ on: false, title: "", date: "" }); skipTidy.current = null; };
  useEffect(() => { if (!quickAdd) reset(); }, [quickAdd]);
  useEffect(() => {
    if (!quickAdd || !prefill) return;
    setF((cur) => ({ ...cur, ...Object.fromEntries(Object.entries(prefill).filter(([, v]) => v)) }));
    setPrefill(null);
  }, [quickAdd, prefill]);

  async function saveForLater() {
    if (!canSave) return;
    setBusy(true);
    try {
      await api.post("/api/opportunities", { company: f.company, position: f.position, location: f.location || null, url: f.url || null,
        job_description: f.job_description || null, notes: f.notes || null, source: f.source || null,
        deadline: f.deadline || null, workload: f.workload || null, contract: f.contract || null });
      refresh(); toast(`${f.position} added to your Inbox.`, "ok", { label: "Open Inbox", run: () => navigate("/applications?view=inbox") }); close();
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  }

  // Live detection, debounced.
  useEffect(() => {
    if (!quickAdd) return;
    if (!f.position && !f.company && !f.job_description) { setParsed(null); return; }
    const t = setTimeout(() => {
      api.post("/api/parse", { company: f.company, position: f.position, location: f.location, job_description: f.job_description })
        .then((p) => {
          setParsed(p);
          // Fill empty fields from the posting; remember which ones so they can be highlighted for checking.
          const filled: Record<string, string> = {};
          for (const k of GUESSED) {
            const g = p.guess?.[k];
            if (g && !fRef.current[k]) filled[k] = String(g);
          }
          if (Object.keys(filled).length) {
            setF((cur) => ({ ...cur, ...Object.fromEntries(Object.entries(filled).filter(([k]) => !cur[k as keyof Form])) }));
            setAuto((a) => ({ ...a, ...Object.fromEntries(Object.keys(filled).map((k) => [k, p.confidence?.[k] ?? (["workload", "contract", "deadline"].includes(k) ? "high" : "medium")])) }));
          }
          // Strip page clutter (buttons, "Apply", AI summaries, company boilerplate) once per paste, with undo.
          if (p.cleaned && skipTidy.current !== f.job_description) {
            const removed = Object.values(p.removed ?? {}).reduce((x: number, y: any) => x + Number(y), 0) as number;
            setTidied({ original: f.job_description, lines: removed });
            skipTidy.current = p.cleaned;
            setF((cur) => ({ ...cur, job_description: p.cleaned }));
          }
        })
        .catch(() => {});
    }, 350);
    return () => clearTimeout(t);
  }, [quickAdd, f.company, f.position, f.location, f.job_description]);

  // Instant rule-based fit preview once there's a real description.
  useEffect(() => {
    if (!quickAdd || f.job_description.trim().length < 80) { setFit(null); return; }
    const t = setTimeout(() => {
      api.post("/api/fit/check", { company: f.company, position: f.position, location: f.location, job_description: f.job_description })
        .then(setFit).catch(() => setFit(null));
    }, 700);
    return () => clearTimeout(t);
  }, [quickAdd, f.job_description, f.location]);

  const set = (k: keyof Form) => (v: string | number) => {
    setF((cur) => ({ ...cur, [k]: v }));
    if (auto[k]) setAuto((a) => { const n = { ...a }; delete n[k]; return n; });
  };
  const check = (k: string) => auto[k] && auto[k] !== "high" ? "border-warn-line bg-warn-soft/60" : auto[k] ? "border-brand/40" : "";
  const hint = (k: string) => auto[k] ? <span className={auto[k] === "high" ? "text-brand" : "text-warn"}>{auto[k] === "high" ? "From the posting" : "From the posting, please check"}</span> : undefined;
  function undoTidy() {
    if (!tidied) return;
    skipTidy.current = tidied.original;
    setF((cur) => ({ ...cur, job_description: tidied.original }));
    setTidied(null);
  }
  const canSave = f.position.trim() && f.company.trim();

  async function save(another: boolean) {
    if (!canSave) return;
    setBusy(true);
    try {
      const body: Dict = { ...f, fit_rating: f.fit_rating || null, ...over };
      delete body.deadline;
      Object.keys(body).forEach((k) => body[k] === "" && delete body[k]);
      if (rem.on && rem.title && rem.date) { body.reminder_title = rem.title; body.reminder_date = rem.date; }
      const r = await api.post<{ id: number }>("/api/applications", body);
      refresh();
      toast(`Added ${f.position} at ${f.company}`);
      if (another) reset();
      else { close(); openApp(r.id); }
    } catch (e: any) {
      toast(e.message, "error");
    } finally { setBusy(false); }
  }

  const dims = useMemo(() => ["role_area", "seniority", "industry", "region", "company_size", "work_authorization", "language", "work_mode"], []);

  if (!meta) return null;
  return (
    <Modal open={quickAdd} onClose={close} width="max-w-[1080px]" title="Add a job"
      footer={<>
        <span className="mr-auto text-[12px] text-ink-muted self-center hidden sm:block">Tip: press <kbd className="font-mono">N</kbd> anywhere to open this.</span>
        <button className="btn-secondary" onClick={close}>Cancel</button>
        <button className="btn-secondary" disabled={!canSave || busy} onClick={saveForLater} title="Not decided yet: collect it in your Inbox to rank later">Add to Inbox</button>
        <button className="btn-secondary" disabled={!canSave || busy} onClick={() => save(true)}>Save & add another</button>
        <button className="btn-primary" disabled={!canSave || busy} onClick={() => save(false)}>Save application</button>
      </>}>
      <div className="grid lg:grid-cols-[1fr_340px] gap-6">
        <div className="space-y-4 min-w-0">
          <Field label="Job description" hint="Paste the whole page. Title, company, location, workload, contract and deadline are filled in for you; amber fields are worth a check.">
            <textarea className="textarea h-36 font-[450]" placeholder="Paste the job posting here (optional)…" value={f.job_description}
              onChange={(e) => { setTidied(null); set("job_description")(e.target.value); }} />
          </Field>
          {tidied && (
            <div className="flex flex-wrap items-center gap-2 -mt-2 text-[12px] text-ink-muted">
              <Eraser size={13} className="text-brand" />Removed {tidied.lines} lines of page clutter (buttons, summaries, company boilerplate).
              <button className="text-brand font-medium hover:underline" onClick={undoTidy}>Undo</button>
            </div>
          )}
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Position *" hint={hint("position")}><input className={cls("input", check("position"))} value={f.position} onChange={(e) => set("position")(e.target.value)} placeholder="e.g. Clinical Trial Assistant" /></Field>
            <Field label="Company *" hint={hint("company")}><input className={cls("input", check("company"))} value={f.company} onChange={(e) => set("company")(e.target.value)} placeholder="e.g. Roche" /></Field>
            <Field label="Location" hint={hint("location")}><input className={cls("input", check("location"))} value={f.location} onChange={(e) => set("location")(e.target.value)} placeholder="e.g. Basel" /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Workload" hint={hint("workload")}><input className={cls("input", check("workload"))} value={f.workload} onChange={(e) => set("workload")(e.target.value)} placeholder="e.g. 80–100%" /></Field>
              <Field label="Contract" hint={hint("contract")}>
                <Select className={check("contract")} value={f.contract} onChange={set("contract")} options={f.contract && !CONTRACTS.includes(f.contract) ? [f.contract, ...CONTRACTS] : CONTRACTS} placeholder="—" />
              </Field>
            </div>
            <Field label="Status">
              <Select value={f.status} onChange={set("status")} options={meta.stages} />
            </Field>
            <Field label="Date applied"><input type="date" className="input num" value={f.date_applied} onChange={(e) => set("date_applied")(e.target.value)} /></Field>
            <Field label="Date posted" hint="Used to see whether applying early helps."><input type="date" className="input num" value={f.date_posted} onChange={(e) => set("date_posted")(e.target.value)} /></Field>
            <Field label="Application deadline" hint={hint("deadline") ?? "Kept with the job, and shown in your reminders."}><input type="date" className={cls("input num", check("deadline"))} value={f.deadline} onChange={(e) => set("deadline")(e.target.value)} /></Field>
            <Field label="Channel"><Select value={f.source} onChange={set("source")} options={meta.sources} placeholder="Where did you find it?" /></Field>
            <Field label="Link"><input className="input" value={f.url} onChange={(e) => set("url")(e.target.value)} placeholder="https://…" /></Field>
            <Field label="CV version">
              <input className="input" list="cv-versions" value={f.cv_version} onChange={(e) => set("cv_version")(e.target.value)} placeholder="e.g. Clinical v2" />
              <datalist id="cv-versions">{meta.cv_versions.map((v) => <option key={v} value={v} />)}</datalist>
            </Field>
            <Field label="How well do you fit?">
              <div className="flex items-center gap-1 h-9">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button key={n} type="button" aria-label={`${n} of 5`} onClick={() => set("fit_rating")(f.fit_rating === n ? 0 : n)}
                    className={cls("p-1 rounded", n <= f.fit_rating ? "text-amber" : "text-line-strong hover:text-ink-faint")}>
                    <Star size={18} fill={n <= f.fit_rating ? "currentColor" : "none"} />
                  </button>
                ))}
                <span className="text-[12px] text-ink-muted ml-1">{f.fit_rating ? `${f.fit_rating}/5` : "Not rated"}</span>
              </div>
            </Field>
            <Field label="Salary"><input className="input" value={f.salary} onChange={(e) => set("salary")(e.target.value)} /></Field>
            <Field label="Notes"><input className="input" value={f.notes} onChange={(e) => set("notes")(e.target.value)} /></Field>
          </div>
          <div className="rounded-lg border border-line p-3">
            <label className="flex items-center gap-2 text-[13px] font-medium cursor-pointer">
              <input type="checkbox" checked={rem.on} onChange={(e) => setRem({ ...rem, on: e.target.checked })} className="accent-brand" />
              <BellPlus size={15} className="text-ink-muted" /> Add a reminder
              <span className="font-normal text-ink-muted">for example when applications open or a deadline</span>
            </label>
            {rem.on && (
              <div className="grid sm:grid-cols-[1fr_170px] gap-3 mt-3">
                <input className="input" placeholder="e.g. Applications open, submit then" value={rem.title} onChange={(e) => setRem({ ...rem, title: e.target.value })} />
                <input type="date" className="input num" value={rem.date} onChange={(e) => setRem({ ...rem, date: e.target.value })} />
              </div>
            )}
          </div>
        </div>

        <div className="lg:border-l lg:border-line lg:pl-6 min-w-0">
          {fit && <FitPreview fit={fit} />}
          <div className="flex items-center gap-1.5 eyebrow mb-3"><Sparkles size={13} /> Detected</div>
          {!parsed && <p className="text-ink-muted text-[13px]">Type a title or paste a posting to see what gets picked up. You can correct anything here or later.</p>}
          {parsed && (
            <div className="space-y-3">
              {parsed.duplicate?.length > 0 && (
                <div className="flex gap-2 p-2.5 rounded-lg bg-alert-soft text-alert text-[12.5px]">
                  <AlertTriangle size={15} className="shrink-0 mt-0.5" />
                  You already applied to this role on {fmtDate(parsed.duplicate[0].date_applied)}.
                </div>
              )}
              {parsed.seen?.length > 0 && !parsed.duplicate?.length && (
                <div className="flex gap-2 p-2.5 rounded-lg bg-warn-soft text-warn-strong text-[12.5px]">
                  <AlertTriangle size={15} className="shrink-0 mt-0.5" />
                  {parsed.seen[0].status === "archived" ? "You skipped this role before" : "This role is already in your Inbox"}
                  {parsed.seen[0].created_at ? ` (added ${fmtDate(String(parsed.seen[0].created_at).slice(0, 10))})` : ""}.
                </div>
              )}
              {parsed.duplicate?.length === 0 && parsed.same_company?.length > 0 && (
                <div className="p-2.5 rounded-lg bg-canvas text-[12.5px] text-ink-soft">
                  <div className="font-medium mb-1">Earlier at {f.company}</div>
                  {parsed.same_company.map((a: Dict) => (
                    <div key={a.id} className="flex items-center justify-between gap-2 py-0.5">
                      <span className="truncate">{a.position}</span><StatusPill stage={a.status} size="sm" />
                    </div>
                  ))}
                </div>
              )}
              <div className="space-y-2">
                {dims.map((d) => {
                  const auto = parsed[d];
                  if (auto === null || auto === undefined) return null;
                  const uncertain = parsed.uncertain?.includes(d);
                  return (
                    <div key={d} className="grid grid-cols-[104px_1fr] items-center gap-2">
                      <span className="text-[12px] text-ink-muted flex items-center gap-1">
                        {DIM_LABELS[d]}
                        {uncertain && !over[d] && <span title="Not sure, please check" className="w-1.5 h-1.5 rounded-full bg-amber" />}
                      </span>
                      <Select className={cls("h-8 text-[12.5px]", uncertain && !over[d] && "border-warn-line bg-warn-soft")}
                        value={over[d] ?? ""} onChange={(v) => setOver((o) => { const n = { ...o }; if (v) n[d] = v; else delete n[d]; return n; })}
                        options={meta.options[d] ?? []} placeholder={`Auto: ${auto}`} />
                    </div>
                  );
                })}
              </div>
              {parsed.min_years !== null && parsed.min_years !== undefined && (
                <div className="text-[12.5px] text-ink-soft">Asks for <b className="num">{parsed.min_years}+</b> years of experience.</div>
              )}
              {parsed.skills?.length > 0 && (
                <div>
                  <div className="flex items-baseline justify-between mb-1.5">
                    <span className="text-[12px] text-ink-muted">Skills mentioned</span>
                    {parsed.match !== null && <span className="text-[12px]">Match <b className="num">{pct(parsed.match)}</b></span>}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {parsed.skills.map((s: Dict) => (
                      <span key={s.skill} className={cls("chip", s.have && "bg-brand-soft text-brand-strong border-brand/20")}>{s.skill}</span>
                    ))}
                  </div>
                  {parsed.match === null && <p className="text-[11.5px] text-ink-muted mt-1.5">Add your skills under Me to get a match score.</p>}
                </div>
              )}
              <p className="text-[11.5px] text-ink-muted pt-1">Amber marks values the app isn't sure about. "Auto" keeps updating if you edit the description or rules later.</p>
              {parsed.posting_language === "de" && <p className="text-[11.5px] text-ink-muted">German posting: only eligibility is checked. Rank it with your chat assistant from the board.</p>}
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}

const REQ_ICON: Record<string, JSX.Element> = {
  met: <Check size={12} className="text-ok-bright shrink-0 mt-0.5" strokeWidth={3} />,
  partial: <CircleDashed size={12} className="text-warn shrink-0 mt-0.5" />,
  missing: <X size={12} className="text-ink-faint shrink-0 mt-0.5" strokeWidth={3} />,
};

/** The instant rule-based verdict, with its reasons, before you save. */
function FitPreview({ fit }: { fit: Dict }) {
  const ess: Dict[] = (fit.requirements ?? []).filter((r: Dict) => r.type === "essential");
  const shown = [...ess.filter((r) => r.status !== "met"), ...ess.filter((r) => r.status === "met")].slice(0, 4);
  return (
    <section className="mb-5 rounded-xl border border-line p-3.5 bg-canvas/50">
      <div className="flex items-center justify-between gap-2">
        <span className="eyebrow flex items-center gap-1.5"><Gauge size={13} />Fit check</span>
        <span className="flex items-center gap-2">{fit.score !== null && fit.score !== undefined && <b className="num text-[13px]">{pct(fit.score)}</b>}<ActionPill action={fit.recommendation.action} size="sm" /></span>
      </div>
      <p className="text-[12.5px] mt-1.5 leading-snug text-ink-soft">{fit.recommendation.why}</p>
      {fit.blockers?.length > 0 && <ul className="mt-2 space-y-0.5">{fit.blockers.slice(0, 2).map((b: Dict, i: number) => (
        <li key={i} className="text-[12px] text-danger flex gap-1.5"><AlertTriangle size={12} className="shrink-0 mt-0.5" /><span><b className="font-medium">{b.type}:</b> {b.detail}</span></li>))}</ul>}
      {shown.length > 0 && <ul className="mt-2 space-y-1">{shown.map((r, i) => (
        <li key={i} className="flex gap-1.5 text-[12px] leading-snug">{REQ_ICON[r.status]}<span className="line-clamp-2">{r.text}</span></li>))}</ul>}
      {ess.length > shown.length && <p className="text-[11px] text-ink-faint mt-1">+{ess.length - shown.length} more essential; full list after saving.</p>}
    </section>
  );
}
