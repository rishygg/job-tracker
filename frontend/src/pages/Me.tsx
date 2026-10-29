import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BookOpen, Check, Layers, PenLine, Plus, ShieldCheck, X } from "lucide-react";
import { api, type Dict } from "../api";
import { useApp } from "../store";
import { cls } from "../lib";
import { Field, PageHeader, Select, Tabs } from "../components/ui";
import { EntriesEditor, WritingStyle } from "../components/Entries";
import { StoriesTab } from "../components/CareerExtras";

type Tab = "profile" | "eligibility" | "stories" | "writing";

/** Everything about you that the app reuses: your entries, eligibility, stories and writing style. */
export default function Me() {
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab");
  const tab = (raw === "evidence" ? "profile" : (raw as Tab)) || "profile";
  const setTab = (t: Tab) => setParams({ tab: t }, { replace: true });
  return (
    <div className="max-w-[1180px]">
      <PageHeader title="Me" subtitle="What you've done, what you're eligible for, the stories you tell and how you write. Fit checks and chat prompts draw on this." />
      <Tabs value={tab} onChange={setTab} tabs={[
        { id: "profile", label: <span className="inline-flex items-center gap-1.5"><Layers size={14} />Experience & education</span> },
        { id: "eligibility", label: <span className="inline-flex items-center gap-1.5"><ShieldCheck size={14} />Eligibility & skills</span> },
        { id: "stories", label: <span className="inline-flex items-center gap-1.5"><BookOpen size={14} />Story bank</span> },
        { id: "writing", label: <span className="inline-flex items-center gap-1.5"><PenLine size={14} />How you write</span> },
      ]} />
      <div className="pt-6">
        {tab === "profile" && <div className="max-w-5xl"><EntriesEditor /></div>}
        {tab === "eligibility" && <div className="max-w-5xl"><MeProfile /></div>}
        {tab === "stories" && <StoriesTab />}
        {tab === "writing" && <div className="max-w-5xl"><WritingStyle /></div>}
      </div>
    </div>
  );
}

const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2", "Native"];
const DEGREES = ["Bachelor", "Master (in progress)", "Master", "PhD (in progress)", "PhD"];
const PERMITS = ["Citizen / no permit needed", "Have a valid work permit", "Eligible for a permit (e.g. graduate route)", "Would need sponsorship"];

export function MeProfile() {
  const { meta, refresh, toast } = useApp();
  const [s, setS] = useState<Dict | null>(null);
  const [q, setQ] = useState("");
  useEffect(() => { if (meta && !s) setS({ ...meta.settings, profile: { languages: [], permits: {}, locations: [], ...(meta.settings.profile ?? {}) } }); }, [meta]);
  if (!meta || !s) return null;
  const p = s.profile;
  const setP = (k: string, v: any) => setS({ ...s, profile: { ...p, [k]: v } });
  const skills: string[] = s.my_skills ?? [];
  const lower = new Set(skills.map((x) => x.toLowerCase()));
  const suggestions = meta.skills.filter((k) => !lower.has(k.toLowerCase()) && k.toLowerCase().includes(q.toLowerCase())).slice(0, 14);
  const add = (k: string) => { if (k.trim() && !lower.has(k.trim().toLowerCase())) setS({ ...s, my_skills: [...skills, k.trim()] }); setQ(""); };
  const regions = meta.options.region.filter((r) => !["Remote", "Other / unspecified"].includes(r));

  async function save() {
    try {
      const body: Dict = { profile: s!.profile, name: s!.name, my_skills: s!.my_skills };
      await api.put("/api/settings", body); refresh(); toast("Saved");
    } catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <div className="space-y-6">
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
            <label className="flex items-center gap-2 text-[13px] mt-3"><input type="checkbox" className="accent-brand" checked={!!p.relocate} onChange={(e) => setP("relocate", e.target.checked)} /> Open to relocating elsewhere</label>
          </div>
        </div>
      </section>

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
              <button aria-label={`Remove ${k}`} className="p-0.5 rounded hover:bg-surface/60" onClick={() => setS({ ...s, my_skills: skills.filter((x) => x !== k) })}><X size={12} /></button>
            </span>
          ))}
        </div>
        <div className="flex gap-2 max-w-md">
          <input className="input" placeholder="Search skills or type a new one…" value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(q); } }} />
          <button className="btn-secondary" disabled={!q.trim()} onClick={() => add(q)}><Plus size={15} /> Add</button>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-3">
          {suggestions.map((k) => <button key={k} className="chip h-7 hover:bg-surface hover:border-line-strong" onClick={() => add(k)}><Plus size={11} />{k}</button>)}
        </div>
      </section>
      <div className="sticky bottom-4 flex justify-end"><button className="btn-primary shadow-pop" onClick={save}>Save changes</button></div>
    </div>
  );
}

