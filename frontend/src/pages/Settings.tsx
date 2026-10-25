import { useEffect, useRef, useState } from "react";
import { Download, FileUp, HardDriveDownload, Plus, Trash2, X } from "lucide-react";
import { api, type Dict } from "../api";
import { useApi, useApp } from "../store";
import { cls } from "../lib";
import { Field, PageHeader, Select, Tabs } from "../components/ui";

type Tab = "profile" | "rules" | "data";

export default function Settings() {
  const [tab, setTab] = useState<Tab>("profile");
  return (
    <div className="max-w-5xl">
      <PageHeader title="Settings" subtitle="Your profile, goals, the rules that categorise roles, and your data." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "profile", label: "Profile & goals" }, { id: "rules", label: "Categorisation rules" }, { id: "data", label: "Import & export" }]} />
      <div className="pt-6">
        {tab === "profile" && <Profile />}
        {tab === "rules" && <Rules />}
        {tab === "data" && <DataTab />}
      </div>
    </div>
  );
}

function Profile() {
  const { meta, refresh, toast } = useApp();
  const [s, setS] = useState<Dict | null>(null);
  const [q, setQ] = useState("");
  useEffect(() => { if (meta && !s) setS({ ...meta.settings }); }, [meta]);
  if (!meta || !s) return null;
  const skills: string[] = s.my_skills ?? [];
  const lower = new Set(skills.map((x) => x.toLowerCase()));
  const suggestions = meta.skills.filter((k) => !lower.has(k.toLowerCase()) && k.toLowerCase().includes(q.toLowerCase())).slice(0, 14);
  const add = (k: string) => { if (k.trim() && !lower.has(k.trim().toLowerCase())) setS({ ...s, my_skills: [...skills, k.trim()] }); setQ(""); };
  async function save() {
    try { await api.put("/api/settings", s); refresh(); toast("Settings saved"); } catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <div className="space-y-6">
      <section className="card p-5">
        <h2 className="text-[15px] font-semibold mb-4">You</h2>
        <Field label="First name" className="max-w-xs" hint="Used for the greeting on the Overview.">
          <input className="input" value={s.name ?? ""} onChange={(e) => setS({ ...s, name: e.target.value })} />
        </Field>
      </section>
      <section className="card p-5">
        <h2 className="text-[15px] font-semibold">Your skills</h2>
        <p className="text-[12.5px] text-ink-muted mb-4">Used to score how well each job description matches you and to find your skill gaps. Stored only in your local database.</p>
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
      <div className="flex justify-end"><button className="btn-primary" onClick={save}>Save settings</button></div>
    </div>
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
