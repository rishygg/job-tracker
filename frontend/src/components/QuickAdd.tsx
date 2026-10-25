import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, BellPlus, Sparkles, Star } from "lucide-react";
import { api, type Dict } from "../api";
import { useApp } from "../store";
import { cls, fmtDate, pct, today } from "../lib";
import { Field, Modal, Select, StatusPill } from "./ui";

const DIM_LABELS: Record<string, string> = {
  role_area: "Job family", seniority: "Seniority", industry: "Industry", region: "Location group",
  company_size: "Company size", work_authorization: "Work permit", language: "Language", work_mode: "Work mode",
};

const blank = () => ({
  position: "", company: "", location: "", status: "Applied", date_applied: today(), date_posted: "",
  source: "", url: "", cv_version: "", fit_rating: 0, salary: "", notes: "", job_description: "",
});

export function QuickAdd() {
  const { quickAdd, setQuickAdd, meta, refresh, toast, openApp } = useApp();
  const [f, setF] = useState(blank());
  const [over, setOver] = useState<Dict>({});
  const [parsed, setParsed] = useState<Dict | null>(null);
  const [rem, setRem] = useState({ on: false, title: "", date: "" });
  const [busy, setBusy] = useState(false);
  const autoFilled = useRef({ position: false, company: false });

  const close = () => { setQuickAdd(false); };
  const reset = () => { setF(blank()); setOver({}); setParsed(null); setRem({ on: false, title: "", date: "" }); autoFilled.current = { position: false, company: false }; };
  useEffect(() => { if (!quickAdd) reset(); }, [quickAdd]);

  // Live detection, debounced.
  useEffect(() => {
    if (!quickAdd) return;
    if (!f.position && !f.company && !f.job_description) { setParsed(null); return; }
    const t = setTimeout(() => {
      api.post("/api/parse", { company: f.company, position: f.position, location: f.location, job_description: f.job_description })
        .then((p) => {
          setParsed(p);
          // Prefill title/company from the first lines of a pasted posting, only into empty fields.
          setF((cur) => {
            const next = { ...cur };
            if (!cur.position && p.guess?.position && !autoFilled.current.position) { next.position = p.guess.position; autoFilled.current.position = true; }
            if (!cur.company && p.guess?.company && !autoFilled.current.company) { next.company = p.guess.company; autoFilled.current.company = true; }
            return next;
          });
        })
        .catch(() => {});
    }, 350);
    return () => clearTimeout(t);
  }, [quickAdd, f.company, f.position, f.location, f.job_description]);

  const set = (k: keyof ReturnType<typeof blank>) => (v: string | number) => setF((cur) => ({ ...cur, [k]: v }));
  const canSave = f.position.trim() && f.company.trim();

  async function save(another: boolean) {
    if (!canSave) return;
    setBusy(true);
    try {
      const body: Dict = { ...f, fit_rating: f.fit_rating || null, ...over };
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
    <Modal open={quickAdd} onClose={close} width="max-w-[1080px]" title="Add application"
      footer={<>
        <span className="mr-auto text-[12px] text-ink-muted self-center hidden sm:block">Tip: press <kbd className="font-mono">N</kbd> anywhere to open this.</span>
        <button className="btn-secondary" onClick={close}>Cancel</button>
        <button className="btn-secondary" disabled={!canSave || busy} onClick={() => save(true)}>Save & add another</button>
        <button className="btn-primary" disabled={!canSave || busy} onClick={() => save(false)}>Save application</button>
      </>}>
      <div className="grid lg:grid-cols-[1fr_340px] gap-6">
        <div className="space-y-4 min-w-0">
          <Field label="Job description" hint="Paste the full posting. Title, company, seniority, language and permit requirements and skills are picked out for you.">
            <textarea className="textarea h-36 font-[450]" placeholder="Paste the job posting here (optional)…" value={f.job_description}
              onChange={(e) => set("job_description")(e.target.value)} />
          </Field>
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Position *"><input className="input" value={f.position} onChange={(e) => set("position")(e.target.value)} placeholder="e.g. Clinical Trial Assistant" /></Field>
            <Field label="Company *"><input className="input" value={f.company} onChange={(e) => set("company")(e.target.value)} placeholder="e.g. Roche" /></Field>
            <Field label="Location"><input className="input" value={f.location} onChange={(e) => set("location")(e.target.value)} placeholder="e.g. Basel" /></Field>
            <Field label="Status">
              <Select value={f.status} onChange={set("status")} options={meta.stages} />
            </Field>
            <Field label="Date applied"><input type="date" className="input num" value={f.date_applied} onChange={(e) => set("date_applied")(e.target.value)} /></Field>
            <Field label="Date posted" hint="Used to see whether applying early helps."><input type="date" className="input num" value={f.date_posted} onChange={(e) => set("date_posted")(e.target.value)} /></Field>
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
                    className={cls("p-1 rounded", n <= f.fit_rating ? "text-[#d97f06]" : "text-line-strong hover:text-ink-faint")}>
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
              <input type="checkbox" checked={rem.on} onChange={(e) => setRem({ ...rem, on: e.target.checked })} className="accent-[#0e7a5c]" />
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
                        {uncertain && !over[d] && <span title="Not sure, please check" className="w-1.5 h-1.5 rounded-full bg-[#d97f06]" />}
                      </span>
                      <Select className={cls("h-8 text-[12.5px]", uncertain && !over[d] && "border-[#f0cf9a] bg-[#fffaf1]")}
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
                  {parsed.match === null && <p className="text-[11.5px] text-ink-muted mt-1.5">Add your skills in Settings to get a match score.</p>}
                </div>
              )}
              <p className="text-[11.5px] text-ink-muted pt-1">Amber marks values the app isn't sure about. "Auto" keeps updating if you edit the description or rules later.</p>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
