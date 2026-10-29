import { useEffect, useRef, useState } from "react";
import { BookmarkPlus, Download, FileUp, HardDriveDownload, Monitor, Moon, Sun, Trash2 } from "lucide-react";
import { api, type Dict } from "../api";
import { useApi, useApp, type Theme } from "../store";
import { cls } from "../lib";
import { Field, PageHeader, Select, Tabs } from "../components/ui";
import { Link, useSearchParams } from "react-router-dom";
import { JobProgress, isActive, useJob } from "../components/AiJob";
import { DigestPanel } from "../components/Digest";
import { resetRankConfig } from "../components/Chat";

type Tab = "general" | "rules" | "data";

export default function Settings() {
  const [params] = useSearchParams();
  const [tab, setTab] = useState<Tab>(((params.get("tab") as Tab) || "general"));
  return (
    <div className="max-w-5xl">
      <PageHeader title="Settings" subtitle={<>How the app works: AI, goals, appearance, rules and your data. Your CV and material are under <Link to="/me" className="text-brand hover:underline">Me</Link>.</>} />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "general", label: "General & AI" }, { id: "rules", label: "Categorisation rules" }, { id: "data", label: "Import & export" }]} />
      <div className="pt-6">
        {tab === "general" && <General />}
        {tab === "rules" && <Rules />}
        {tab === "data" && <DataTab />}
      </div>
    </div>
  );
}

function General() {
  const { meta, refresh, toast } = useApp();
  const [s, setS] = useState<Dict | null>(null);
  useEffect(() => { if (meta && !s) setS({ ...meta.settings }); }, [meta]);
  if (!meta || !s) return null;
  async function save() {
    const keys = ["digest_auto", "ollama_url", "ollama_model", "weekly_goal", "follow_up_after", "ghost_after", "too_new_days"];
    try { await api.put("/api/settings", Object.fromEntries(keys.map((k) => [k, s![k]]))); refresh(); toast("Settings saved"); }
    catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <div className="space-y-6">
      <Appearance />
      <AiSettings s={s} setS={setS} />
      <section className="card p-5">
        <h2 className="text-[15px] font-semibold mb-4">Goals and reminders</h2>
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Weekly application goal" hint="Shown as a ring on the Overview, with your streak."><input type="number" min={1} className="input num" value={s.weekly_goal} onChange={(e) => setS({ ...s, weekly_goal: Number(e.target.value) })} /></Field>
          <Field label="Suggest a follow-up after (days without news)"><input type="number" min={3} className="input num" value={s.follow_up_after} onChange={(e) => setS({ ...s, follow_up_after: Number(e.target.value) })} /></Field>
          <Field label="Suggest 'ghosted' after (days without a reply)"><input type="number" min={7} className="input num" value={s.ghost_after} onChange={(e) => setS({ ...s, ghost_after: Number(e.target.value) })} /></Field>
          <Field label="Leave out of stats until (days old)" hint="Recent applications haven't had time to get a reply, so counting them would drag every rate down.">
            <input type="number" min={0} className="input num" value={s.too_new_days} onChange={(e) => setS({ ...s, too_new_days: Number(e.target.value) })} />
          </Field>
        </div>
      </section>
      <BookmarkCard />
      <div className="sticky bottom-4 flex justify-end"><button className="btn-primary shadow-pop" onClick={save}>Save settings</button></div>
    </div>
  );
}

function Appearance() {
  const { theme, setTheme } = useApp();
  const opts: { id: Theme; label: string; icon: typeof Sun }[] = [{ id: "light", label: "Light", icon: Sun }, { id: "dark", label: "Dark", icon: Moon }, { id: "system", label: "Match my computer", icon: Monitor }];
  return (
    <section className="card p-5">
      <h2 className="text-[15px] font-semibold">Appearance</h2>
      <p className="text-[12.5px] text-ink-muted mb-3">Saved in this browser. You can also switch from the sidebar.</p>
      <div className="inline-flex p-0.5 rounded-lg bg-canvas border border-line" role="radiogroup" aria-label="Theme">
        {opts.map((o) => (
          <button key={o.id} role="radio" aria-checked={theme === o.id} onClick={() => setTheme(o.id)}
            className={cls("h-8 px-3 rounded-md text-[12.5px] font-medium inline-flex items-center gap-1.5 transition", theme === o.id ? "bg-surface text-ink shadow-card" : "text-ink-muted hover:text-ink")}>
            <o.icon size={14} />{o.label}
          </button>
        ))}
      </div>
    </section>
  );
}

function BookmarkCard() {
  const { data } = useApi<Dict>("/api/bookmarklet");
  const ref = useRef<HTMLAnchorElement>(null);
  // React refuses javascript: URLs in href, so set it directly.
  useEffect(() => { if (ref.current && data?.href) ref.current.setAttribute("href", data.href); }, [data]);
  return (
    <section className="card p-5">
      <h2 className="text-[15px] font-semibold">Send jobs from your browser</h2>
      <p className="text-[12.5px] text-ink-muted mt-0.5 mb-4">Drag this button to your bookmarks bar. On any job posting (LinkedIn, jobs.ch, a company site), click it: the posting opens here in Quick add with the description filled in. Select the job text first for the cleanest result; otherwise the whole page is sent. Everything stays on your computer.</p>
      <div className="flex flex-wrap items-center gap-3">
        <a ref={ref} onClick={(e) => e.preventDefault()} draggable
          className="inline-flex items-center gap-2 h-10 px-4 rounded-lg bg-brand text-white text-[13px] font-semibold shadow-card cursor-grab active:cursor-grabbing select-none">
          <BookmarkPlus size={16} /> Send to Job Tracker
        </a>
        <span className="text-[12px] text-ink-muted">← drag me to the bookmarks bar (Ctrl+Shift+B shows it)</span>
      </div>
      <p className="text-[11.5px] text-ink-faint mt-3">Works while the app is running at {data?.base ?? "this address"}. If a site blocks it, select the text, copy it and press N here instead.</p>
    </section>
  );
}

function AiSettings({ s, setS }: { s: Dict; setS: (s: Dict) => void }) {
  const [status, setStatus] = useState<Dict | null>(null);
  const [checking, setChecking] = useState(false);
  const check = async () => {
    setChecking(true);
    try {
      await api.put("/api/settings", { ollama_url: s.ollama_url, ollama_model: s.ollama_model });
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
  const secs = (tokens: number) => Math.max(1, Math.round(tokens / sp.gen_tps + (sp.prompt_tps ? 1200 / sp.prompt_tps : 15)));
  return (
    <section className="card p-5">
      <h2 className="text-[15px] font-semibold">Reading descriptions with Ollama (optional)</h2>
      <p className="text-[12.5px] text-ink-muted mb-4">Everything in the tracker works without AI: fit checks are instant rules, and deeper questions go to your chat assistant through copy-and-paste prompts. A local Ollama model only reads your saved job descriptions in the background, once each, to improve the skills and industry statistics under Career. Nothing leaves your computer.</p>
      <div className="grid sm:grid-cols-2 gap-3 items-end">
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
            <span className={cls("w-2 h-2 rounded-full", status.available ? "bg-ok-bright" : "bg-alert")} />
            {status.available ? `Connected · ${status.models.length} model${status.models.length === 1 ? "" : "s"} installed` : status.error}
          </span>
        )}
        {status?.available && !isActive(job) && <button className="btn-secondary btn-sm" onClick={speedTest}>Measure speed</button>}
      </div>
      {isActive(job) && <div className="mt-3"><JobProgress job={job!} speed={sp} /></div>}
      {status?.available && (
        <div className="mt-4 space-y-3">
          <DigestPanel />
          <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" className="accent-brand" checked={!!s.digest_auto} onChange={(e) => setS({ ...s, digest_auto: e.target.checked })} />
            Read new job descriptions automatically when I add them (save settings to apply)</label>
        </div>
      )}
      {sp?.gen_tps && (
        <div className="mt-3 rounded-lg bg-canvas p-3.5 text-[12.5px]">
          <div><b className="num">{sp.gen_tps.toFixed(1)}</b> tokens per second with <b>{sp.model}</b>{sp.prompt_tps ? <> · reads about <b className="num">{Math.round(sp.prompt_tps)}</b> tokens/s</> : null} <span className="text-ink-muted">(measured {sp.at})</span></div>
          <div className="text-ink-soft mt-1">On this computer, reading one description takes about <b>{secs(170)} s</b>.</div>
          {sp.gen_tps < 4 && <div className="text-warn mt-1">That's slow. Close other heavy programs, or try a smaller model (<code className="font-mono">ollama pull qwen2.5:3b</code>): about twice as fast, a bit less sharp.</div>}
        </div>
      )}
      {!status?.available && (
        <div className="mt-4 rounded-lg bg-canvas p-3.5 text-[12.5px] space-y-1.5">
          <div className="font-medium">Set up in three steps</div>
          <div>1. Install Ollama from <a className="text-brand underline" href="https://ollama.com/download" target="_blank" rel="noreferrer">ollama.com/download</a> and start it.</div>
          <div>2. Download a model in a terminal: <code className="font-mono bg-surface px-1.5 py-0.5 rounded border border-line">ollama pull qwen2.5:7b</code> (about 4.7 GB; good on 16 GB RAM). On 8 GB RAM use <code className="font-mono bg-surface px-1.5 py-0.5 rounded border border-line">qwen2.5:3b</code>.</div>
          <div>3. Click "Test connection", pick the model and save.</div>
        </div>
      )}
    </section>
  );
}

function Rules() {
  const [which, setWhich] = useState<"categories" | "dimensions" | "ranking">("categories");
  const { refresh, toast } = useApp();
  const { data } = useApi<Dict>(`/api/rules/${which}`, [which]);
  const [text, setText] = useState("");
  useEffect(() => { if (data) setText(data.text); }, [data]);
  async function save() {
    try {
      await api.put(`/api/rules/${which}`, { text });
      if (which === "ranking") { resetRankConfig(); toast("Ranking fields saved. The next prompt asks for them."); }
      else toast("Rules saved; categories updated everywhere");
      refresh();
    }
    catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <div className={cls("grid gap-5", which !== "ranking" && "lg:grid-cols-[1fr_300px]")}>
      <section className="card p-5 min-w-0">
        <div className="flex items-center justify-between mb-3 gap-3">
          <Select className="w-72" value={which} onChange={(v) => setWhich(v as any)} options={[
            { value: "categories", label: "Job families & location groups" }, { value: "dimensions", label: "Seniority, industry, permit, language, skills" },
            { value: "ranking", label: "Chat ranking fields" }]} />
          <button className="btn-primary" disabled={!data || text === data.text} onClick={save}>Save rules</button>
        </div>
        <p className="text-[12.5px] text-ink-muted mb-3">{which === "ranking"
          ? "What your chat assistant fills in for each job (salary, ATS match…). Add, remove or reword fields; the prompt, the board and the job panel follow. Instructions are at the top of the file."
          : "Rules are checked top to bottom and the first match wins. Keywords match whole words, ignoring case."}</p>
        <textarea spellCheck={false} className="textarea font-mono text-[12px] h-[560px] leading-[1.55]" value={text} onChange={(e) => setText(e.target.value)} />
      </section>
      {which !== "ranking" && <aside className="space-y-4">
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
      </aside>}
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
            <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" className="accent-brand" checked={replace} onChange={(e) => setReplace(e.target.checked)} /> Replace everything currently in the tracker</label>
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
      <section className="card p-5 border-danger/30">
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
