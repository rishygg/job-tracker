import { useEffect, useRef, useState } from "react";
import { Check, Download, FileUp, HardDriveDownload, Plus, Trash2, X } from "lucide-react";
import { api, type Dict } from "../api";
import { useApi, useApp } from "../store";
import { cls } from "../lib";
import { Field, PageHeader, Select, Tabs } from "../components/ui";
import { EvidenceBank, WritingStyle } from "../components/EvidenceBank";
import { useSearchParams } from "react-router-dom";
import { JobProgress, isActive, useJob } from "../components/AiJob";

type Tab = "profile" | "evidence" | "rules" | "data";

export default function Settings() {
  const [params] = useSearchParams();
  const [tab, setTab] = useState<Tab>(((params.get("tab") as Tab) || "profile"));
  return (
    <div className="max-w-5xl">
      <PageHeader title="Settings" subtitle="Your profile, goals, the rules that categorise roles, and your data." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "profile", label: "Profile, CV & AI" }, { id: "evidence", label: "Evidence bank & writing" }, { id: "rules", label: "Categorisation rules" }, { id: "data", label: "Import & export" }]} />
      <div className="pt-6">
        {tab === "profile" && <Profile />}
        {tab === "evidence" && <div className="space-y-6"><EvidenceBank /><WritingStyle /></div>}
        {tab === "rules" && <Rules />}
        {tab === "data" && <DataTab />}
      </div>
    </div>
  );
}

const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2", "Native"];
const DEGREES = ["Bachelor", "Master (in progress)", "Master", "PhD (in progress)", "PhD"];
const PERMITS = ["Citizen / no permit needed", "Have a valid work permit", "Eligible for a permit (e.g. graduate route)", "Would need sponsorship"];

function Profile() {
  const { meta, refresh, toast } = useApp();
  const [s, setS] = useState<Dict | null>(null);
  const [q, setQ] = useState("");
  const [cv, setCv] = useState<string | null>(null);
  const [showCv, setShowCv] = useState(false);
  const cvRef = useRef<HTMLInputElement>(null);
  useEffect(() => { if (meta && !s) setS({ ...meta.settings, profile: { languages: [], permits: {}, locations: [], ...(meta.settings.profile ?? {}) } }); }, [meta]);
  useEffect(() => { api.get("/api/settings").then((x) => setCv(x.cv_text ?? "")); }, []);
  if (!meta || !s) return null;
  const p = s.profile;
  const setP = (k: string, v: any) => setS({ ...s, profile: { ...p, [k]: v } });
  const skills: string[] = s.my_skills ?? [];
  const lower = new Set(skills.map((x) => x.toLowerCase()));
  const suggestions = meta.skills.filter((k) => !lower.has(k.toLowerCase()) && k.toLowerCase().includes(q.toLowerCase())).slice(0, 14);
  const add = (k: string) => { if (k.trim() && !lower.has(k.trim().toLowerCase())) setS({ ...s, my_skills: [...skills, k.trim()] }); setQ(""); };
  const regions = meta.options.region.filter((r) => !["Remote", "Other / unspecified"].includes(r));

  async function uploadCv(f: File) {
    const fd = new FormData(); fd.append("file", f);
    try { const r = await api.form("/api/profile/cv", fd); setCv(r.text); setS((c) => c && { ...c, cv_filename: r.filename }); refresh(); toast(`Read ${r.chars.toLocaleString()} characters from ${r.filename}`); }
    catch (e: any) { toast(e.message, "error"); }
  }
  async function save() {
    try {
      const body: Dict = { ...s };
      delete body.cv_chars;
      if (cv !== null) body.cv_text = cv;
      await api.put("/api/settings", body); refresh(); toast("Settings saved");
    } catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <div className="space-y-6">
      <section className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-[15px] font-semibold">Your CV</h2>
            <p className="text-[12.5px] text-ink-muted">Used for fit analysis, target CVs and cover letters. Stored only in your local database and only sent to Ollama on your own computer.</p>
          </div>
          <input ref={cvRef} type="file" accept=".pdf,.docx,.txt,.md" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadCv(f); e.target.value = ""; }} />
          <button className="btn-secondary" onClick={() => cvRef.current?.click()}><FileUp size={15} /> {cv ? "Replace CV" : "Upload CV"}</button>
        </div>
        {cv ? (
          <div className="mt-3">
            <div className="flex items-center gap-2 text-[13px]">
              <span className="w-2 h-2 rounded-full bg-[#0e9a69]" />
              <b className="font-medium">{s.cv_filename || "Pasted text"}</b>
              <span className="text-ink-muted num">{cv.length.toLocaleString()} characters</span>
              <button className="btn-ghost btn-sm ml-auto" onClick={() => setShowCv(!showCv)}>{showCv ? "Hide text" : "Check or edit text"}</button>
            </div>
            {showCv && <textarea className="textarea h-72 mt-3 text-[12.5px] font-mono" value={cv} onChange={(e) => setCv(e.target.value)} />}
            {showCv && <p className="text-[11.5px] text-ink-muted mt-1">PDF text can come out jumbled. Fix anything odd here, keeping one bullet per line, then save.</p>}
          </div>
        ) : (
          <div className="mt-3">
            <p className="text-[12.5px] text-ink-muted mb-2">Upload a PDF or Word file, or paste the text:</p>
            <textarea className="textarea h-32 text-[12.5px]" placeholder="Paste your CV text…" value={cv ?? ""} onChange={(e) => setCv(e.target.value)} />
          </div>
        )}
      </section>

      <section className="card p-5">
        <h2 className="text-[15px] font-semibold">Eligibility</h2>
        <p className="text-[12.5px] text-ink-muted mb-4">Checked against every job description to spot blockers: language requirements, degree, experience and work permits.</p>
        <div className="grid lg:grid-cols-2 gap-6">
          <div>
            <div className="label">Languages</div>
            <div className="space-y-2">
              {p.languages.map((l: Dict, i: number) => (
                <div key={i} className="flex gap-2">
                  <input className="input" value={l.language} placeholder="e.g. German" onChange={(e) => setP("languages", p.languages.map((x: Dict, j: number) => j === i ? { ...x, language: e.target.value } : x))} />
                  <Select className="w-32" value={l.level} onChange={(v) => setP("languages", p.languages.map((x: Dict, j: number) => j === i ? { ...x, level: v } : x))} options={LEVELS} />
                  <button className="btn-ghost" aria-label="Remove language" onClick={() => setP("languages", p.languages.filter((_: Dict, j: number) => j !== i))}><X size={15} /></button>
                </div>
              ))}
              <button className="btn-secondary btn-sm" onClick={() => setP("languages", [...p.languages, { language: "", level: "B1" }])}><Plus size={13} /> Add language</button>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-5">
              <Field label="Highest degree"><Select value={p.degree ?? ""} onChange={(v) => setP("degree", v)} options={DEGREES} placeholder="Not set" /></Field>
              <Field label="Years of relevant experience"><input type="number" min={0} step={0.5} className="input num" value={p.years_experience ?? ""} onChange={(e) => setP("years_experience", e.target.value === "" ? null : Number(e.target.value))} /></Field>
            </div>
          </div>
          <div>
            <div className="label">Work permit status by location</div>
            <div className="space-y-2">
              {regions.map((r) => (
                <div key={r} className="grid grid-cols-[130px_1fr] items-center gap-2">
                  <span className="text-[13px]">{r}</span>
                  <Select className="h-8 text-[12.5px]" value={p.permits?.[r] ?? ""} onChange={(v) => setP("permits", { ...p.permits, [r]: v })} options={PERMITS} placeholder="Not set" />
                </div>
              ))}
            </div>
            <div className="label mt-5">Preferred locations</div>
            <div className="flex flex-wrap gap-1.5">
              {meta.options.region.filter((r) => r !== "Other / unspecified").map((r) => {
                const on = (p.locations ?? []).includes(r);
                return <button key={r} onClick={() => setP("locations", on ? p.locations.filter((x: string) => x !== r) : [...(p.locations ?? []), r])}
                  className={cls("chip h-7", on && "bg-brand-soft text-brand-strong border-brand/30")}>{on && <Check size={12} />}{r}</button>;
              })}
            </div>
            <label className="flex items-center gap-2 text-[13px] mt-3"><input type="checkbox" className="accent-[#0e7a5c]" checked={!!p.relocate} onChange={(e) => setP("relocate", e.target.checked)} /> Open to relocating elsewhere</label>
          </div>
        </div>
      </section>

      <AiSettings s={s} setS={setS} />

      <section className="card p-5">
        <h2 className="text-[15px] font-semibold mb-4">You</h2>
        <Field label="First name" className="max-w-xs" hint="Used for the greeting on the Overview.">
          <input className="input" value={s.name ?? ""} onChange={(e) => setS({ ...s, name: e.target.value })} />
        </Field>
      </section>
      <section className="card p-5">
        <h2 className="text-[15px] font-semibold">Your skills</h2>
        <p className="text-[12.5px] text-ink-muted mb-4">Used for the quick skills-match score on every job and for your skill gaps.</p>
        <div className="flex flex-wrap gap-1.5 mb-3 min-h-[28px]">
          {skills.length === 0 && <span className="text-[13px] text-ink-muted">No skills yet. Search below or type your own.</span>}
          {skills.map((k) => (
            <span key={k} className="chip h-7 bg-brand-soft text-brand-strong border-brand/20 pr-1">{k}
              <button aria-label={`Remove ${k}`} className="p-0.5 rounded hover:bg-white/60" onClick={() => setS({ ...s, my_skills: skills.filter((x) => x !== k) })}><X size={12} /></button>
            </span>
          ))}
        </div>
        <div className="flex gap-2 max-w-md">
          <input className="input" placeholder="Search skills or type a new one…" value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(q); } }} />
          <button className="btn-secondary" disabled={!q.trim()} onClick={() => add(q)}><Plus size={15} /> Add</button>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-3">
          {suggestions.map((k) => <button key={k} className="chip h-7 hover:bg-white hover:border-line-strong" onClick={() => add(k)}><Plus size={11} />{k}</button>)}
        </div>
      </section>
      <section className="card p-5">
        <h2 className="text-[15px] font-semibold mb-4">Goals and reminders</h2>
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Weekly application goal"><input type="number" min={1} className="input num" value={s.weekly_goal} onChange={(e) => setS({ ...s, weekly_goal: Number(e.target.value) })} /></Field>
          <Field label="Suggest a follow-up after (days without news)"><input type="number" min={3} className="input num" value={s.follow_up_after} onChange={(e) => setS({ ...s, follow_up_after: Number(e.target.value) })} /></Field>
          <Field label="Suggest 'ghosted' after (days without a reply)"><input type="number" min={7} className="input num" value={s.ghost_after} onChange={(e) => setS({ ...s, ghost_after: Number(e.target.value) })} /></Field>
          <Field label="Leave out of stats until (days old)" hint="Recent applications haven't had time to get a reply, so counting them would drag every rate down.">
            <input type="number" min={0} className="input num" value={s.too_new_days} onChange={(e) => setS({ ...s, too_new_days: Number(e.target.value) })} />
          </Field>
        </div>
      </section>
      <div className="sticky bottom-4 flex justify-end"><button className="btn-primary shadow-pop" onClick={save}>Save settings</button></div>
    </div>
  );
}

function AiSettings({ s, setS }: { s: Dict; setS: (s: Dict) => void }) {
  const [status, setStatus] = useState<Dict | null>(null);
  const [checking, setChecking] = useState(false);
  const check = async () => {
    setChecking(true);
    try {
      await api.put("/api/settings", { ollama_url: s.ollama_url, ollama_model: s.ollama_model, ai_engine: s.ai_engine });
      const st = await api.get("/api/ai/status");
      setStatus(st);
      if (st.available && !s.ollama_model && st.model) setS({ ...s, ollama_model: st.model });
    } finally { setChecking(false); }
  };
  useEffect(() => { api.get("/api/ai/status").then(setStatus).catch(() => {}); }, []);
  const { toast } = useApp();
  const [job, setJob] = useJob(null, undefined, (j) => {
    api.get("/api/ai/status").then(setStatus).catch(() => {});
    if (j.status === "error") toast(j.error ?? "Speed test failed", "error");
  });
  async function speedTest() {
    try { setJob(await api.post("/api/ai/benchmark")); } catch (e: any) { toast(e.message, "error"); }
  }
  const sp = status?.speed;
  const mins = (tokens: number) => Math.max(1, Math.round(tokens / sp.gen_tps / 60 + (sp.prompt_tps ? 1800 / sp.prompt_tps / 60 : 0)));
  return (
    <section className="card p-5">
      <h2 className="text-[15px] font-semibold">AI analysis (Ollama)</h2>
      <p className="text-[12.5px] text-ink-muted mb-4">A local model reads job descriptions like a person would and reviews your CV and cover letter as a recruiter, without sending your data anywhere. Without it, the app uses keyword matching. AI tasks run in the background, one at a time; the sidebar shows what's running.</p>
      <div className="grid sm:grid-cols-3 gap-3 items-end">
        <Field label="Engine"><Select value={s.ai_engine ?? "auto"} onChange={(v) => setS({ ...s, ai_engine: v })} options={[
          { value: "auto", label: "Ollama when available, else keywords" }, { value: "ollama", label: "Always Ollama" }, { value: "keywords", label: "Keywords only" }]} /></Field>
        <Field label="Ollama address"><input className="input num" value={s.ollama_url ?? ""} onChange={(e) => setS({ ...s, ollama_url: e.target.value })} /></Field>
        <Field label="Model">
          {status?.models?.length ? (
            <Select value={s.ollama_model || status.model || ""} onChange={(v) => setS({ ...s, ollama_model: v })} options={status.models} />
          ) : <input className="input" value={s.ollama_model ?? ""} placeholder="e.g. qwen2.5:7b" onChange={(e) => setS({ ...s, ollama_model: e.target.value })} />}
        </Field>
      </div>
      <div className="flex flex-wrap items-center gap-3 mt-3">
        <button className="btn-secondary btn-sm" disabled={checking} onClick={check}>{checking ? "Checking…" : "Test connection"}</button>
        {status && (
          <span className="text-[12.5px] inline-flex items-center gap-1.5">
            <span className={cls("w-2 h-2 rounded-full", status.available ? "bg-[#0e9a69]" : "bg-[#c2410c]")} />
            {status.available ? `Connected · ${status.models.length} model${status.models.length === 1 ? "" : "s"} installed` : status.error}
          </span>
        )}
        {status?.available && !isActive(job) && <button className="btn-secondary btn-sm" onClick={speedTest}>Measure speed</button>}
      </div>
      {isActive(job) && <div className="mt-3"><JobProgress job={job!} speed={sp} /></div>}
      {sp?.gen_tps && (
        <div className="mt-3 rounded-lg bg-canvas p-3.5 text-[12.5px]">
          <div><b className="num">{sp.gen_tps.toFixed(1)}</b> tokens per second with <b>{sp.model}</b>{sp.prompt_tps ? <> · reads about <b className="num">{Math.round(sp.prompt_tps)}</b> tokens/s</> : null} <span className="text-ink-muted">(measured {sp.at})</span></div>
          <div className="text-ink-soft mt-1">On this computer, expect roughly: fit analysis <b>{mins(350)} min</b> · CV review <b>{mins(810)} min</b> · cover letter review <b>{mins(710)} min</b>.</div>
          {sp.gen_tps < 4 && <div className="text-[#a35f00] mt-1">That's slow. Close other heavy programs, or try a smaller model (<code className="font-mono">ollama pull qwen2.5:3b</code>): about twice as fast, a bit less sharp.</div>}
        </div>
      )}
      {!status?.available && (
        <div className="mt-4 rounded-lg bg-canvas p-3.5 text-[12.5px] space-y-1.5">
          <div className="font-medium">Set up in three steps</div>
          <div>1. Install Ollama from <a className="text-brand underline" href="https://ollama.com/download" target="_blank" rel="noreferrer">ollama.com/download</a> and start it.</div>
          <div>2. Download a model in a terminal: <code className="font-mono bg-white px-1.5 py-0.5 rounded border border-line">ollama pull qwen2.5:7b</code> (about 4.7 GB; good on 16 GB RAM). On 8 GB RAM use <code className="font-mono bg-white px-1.5 py-0.5 rounded border border-line">qwen2.5:3b</code>.</div>
          <div>3. Click "Test connection", pick the model and save.</div>
        </div>
      )}
    </section>
  );
}

function Rules() {
  const [which, setWhich] = useState<"categories" | "dimensions">("categories");
  const { refresh, toast } = useApp();
  const { data } = useApi<Dict>(`/api/rules/${which}`, [which]);
  const [text, setText] = useState("");
  useEffect(() => { if (data) setText(data.text); }, [data]);
  async function save() {
    try { await api.put(`/api/rules/${which}`, { text }); refresh(); toast("Rules saved; categories updated everywhere"); }
    catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <div className="grid lg:grid-cols-[1fr_300px] gap-5">
      <section className="card p-5 min-w-0">
        <div className="flex items-center justify-between mb-3 gap-3">
          <Select className="w-72" value={which} onChange={(v) => setWhich(v as any)} options={[
            { value: "categories", label: "Job families & location groups" }, { value: "dimensions", label: "Seniority, industry, permit, language, skills" }]} />
          <button className="btn-primary" disabled={!data || text === data.text} onClick={save}>Save rules</button>
        </div>
        <p className="text-[12.5px] text-ink-muted mb-3">Rules are checked top to bottom and the first match wins. Keywords match whole words, ignoring case.</p>
        <textarea spellCheck={false} className="textarea font-mono text-[12px] h-[560px] leading-[1.55]" value={text} onChange={(e) => setText(e.target.value)} />
      </section>
      <aside className="space-y-4">
        <section className="card p-4">
          <div className="eyebrow mb-2">Titles with no job family ({data?.unknown_titles?.length ?? 0})</div>
          <div className="max-h-56 overflow-y-auto scroll-thin text-[12.5px] space-y-1">
            {(data?.unknown_titles ?? []).map((t: string) => <div key={t} className="text-ink-soft">{t}</div>)}
            {data && !data.unknown_titles.length && <div className="text-ink-muted">Every title has a job family.</div>}
          </div>
        </section>
        <section className="card p-4">
          <div className="eyebrow mb-2">Companies with unknown industry ({data?.unknown_companies?.length ?? 0})</div>
          <div className="max-h-56 overflow-y-auto scroll-thin text-[12.5px] space-y-1">
            {(data?.unknown_companies ?? []).map((t: string) => <div key={t} className="text-ink-soft">{t}</div>)}
          </div>
          <p className="text-[11.5px] text-ink-muted mt-2">Add these under <code>industries → companies</code> in the second rules file.</p>
        </section>
      </aside>
    </div>
  );
}

function DataTab() {
  const { refresh, toast, meta } = useApp();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Dict | null>(null);
  const [sheet, setSheet] = useState("");
  const [replace, setReplace] = useState(false);
  const [confirmText, setConfirmText] = useState("");

  async function loadPreview(f: File, sh = "") {
    const fd = new FormData(); fd.append("file", f); if (sh) fd.append("sheet", sh);
    try { const p = await api.form("/api/import/preview", fd); setPreview(p); setSheet(p.sheet ?? ""); }
    catch (e: any) { toast(e.message, "error"); setPreview(null); }
  }
  async function doImport() {
    if (!file) return;
    const fd = new FormData(); fd.append("file", file); if (sheet) fd.append("sheet", sheet); fd.append("replace", String(replace));
    try { const r = await api.form("/api/import", fd); toast(`Imported ${r.imported} applications`); setFile(null); setPreview(null); refresh(); }
    catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <div className="space-y-6">
      <section className="card p-5">
        <h2 className="text-[15px] font-semibold">Import a spreadsheet</h2>
        <p className="text-[12.5px] text-ink-muted mb-4">Excel or CSV. The header row and common column names (Company, Position, Date Applied, Date Posted, Status, Location, Job Description…) are found automatically.</p>
        <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv,.tsv" className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) { setFile(f); setReplace((meta?.count ?? 0) === 0); loadPreview(f); } e.target.value = ""; }} />
        <button className="btn-secondary" onClick={() => fileRef.current?.click()}><FileUp size={15} /> Choose file</button>
        {file && preview && (
          <div className="mt-4 space-y-3">
            <div className="flex flex-wrap items-center gap-3 text-[13px]">
              <b>{file.name}</b>
              {preview.sheets && <Select className="w-56 h-8" value={sheet} onChange={(v) => { setSheet(v); loadPreview(file, v); }} options={preview.sheets} />}
              <span className="text-ink-muted">{preview.rows} applications · columns: {preview.columns.join(", ")}</span>
            </div>
            <div className="overflow-x-auto border border-line rounded-lg scroll-thin">
              <table className="text-[12px] w-full">
                <thead className="bg-canvas"><tr>{preview.columns.slice(0, 8).map((c: string) => <th key={c} className="text-left font-medium px-2 py-1.5 whitespace-nowrap">{c}</th>)}</tr></thead>
                <tbody>{preview.preview.map((r: Dict, i: number) => <tr key={i} className="border-t border-line">{preview.columns.slice(0, 8).map((c: string) => <td key={c} className="px-2 py-1.5 whitespace-nowrap max-w-[220px] truncate">{String(r[c] ?? "")}</td>)}</tr>)}</tbody>
              </table>
            </div>
            {preview.missing_dates > 0 && <p className="text-[12.5px] text-alert">{preview.missing_dates} rows have no date applied; today's date will be used.</p>}
            <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" className="accent-[#0e7a5c]" checked={replace} onChange={(e) => setReplace(e.target.checked)} /> Replace everything currently in the tracker</label>
            <button className="btn-primary" onClick={doImport}>Import {preview.rows} applications</button>
          </div>
        )}
      </section>
      <section className="card p-5">
        <h2 className="text-[15px] font-semibold mb-1">Export and back up</h2>
        <p className="text-[12.5px] text-ink-muted mb-4">The Excel export has every application (with inferred job family, seniority, industry…) and a sheet of stage history. It can be imported again.</p>
        <div className="flex flex-wrap gap-2">
          <a className="btn-secondary" href="/api/export.xlsx"><Download size={15} /> Download Excel</a>
          <a className="btn-secondary" href="/api/backup"><HardDriveDownload size={15} /> Download database backup</a>
        </div>
      </section>
      <section className="card p-5">
        <h2 className="text-[15px] font-semibold mb-1">Sample data</h2>
        <p className="text-[12.5px] text-ink-muted mb-3">180 fictional applications to explore the app.</p>
        <button className="btn-secondary" onClick={async () => { const r = await api.post("/api/sample"); refresh(); toast(`Loaded ${r.imported} sample applications`); }}>Load sample data</button>
      </section>
      <section className="card p-5 border-[#f3c7c2]">
        <h2 className="text-[15px] font-semibold mb-1 text-danger">Delete all applications</h2>
        <p className="text-[12.5px] text-ink-muted mb-3">Removes every application, stage and reminder. Download a backup first. Type DELETE to confirm.</p>
        <div className="flex gap-2 max-w-sm">
          <input className="input" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} placeholder="DELETE" />
          <button className={cls("btn bg-danger text-white hover:opacity-90")} disabled={confirmText !== "DELETE"}
            onClick={async () => { await api.del("/api/applications?confirm=DELETE"); setConfirmText(""); refresh(); toast("All applications deleted"); }}>
            <Trash2 size={15} /> Delete all
          </button>
        </div>
      </section>
    </div>
  );
}
