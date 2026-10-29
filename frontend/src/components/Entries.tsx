import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, ClipboardPaste, FileUp, Loader2, Pencil, Plus, Trash2, Wand2 } from "lucide-react";
import { api, type Dict } from "../api";
import { useApp } from "../store";
import { cls } from "../lib";
import { EmptyState, Field, Modal, Select } from "./ui";

const SECTION_HINT: Record<string, string> = {
  experience: "Jobs, internships, research positions, volunteering. One line per achievement or responsibility.",
  education: "Degrees and schools. Add your thesis, grade or relevant modules as lines.",
  projects: "Personal, university or side projects. Say what you built and the result.",
  publications: "Papers, posters, talks.",
  skills: "Tools, methods and languages, separated by commas.",
  other: "Awards, certificates, anything else worth matching on.",
};
const BLANK = { title: "", org: "", location: "", start: "", end: "", details: "" };

/** Your profile as entries: the tracker matches on every line, and builds a clean profile text for your chat assistant. */
export function EntriesEditor() {
  const { toast, refresh } = useApp();
  const [d, setD] = useState<Dict | null>(null);
  const [edit, setEdit] = useState<Dict | null>(null);
  const [paste, setPaste] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<{ items: Dict[]; from: "cv" | "paste" } | null>(null);
  const [busy, setBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const load = () => api.get("/api/entries").then(setD).catch(() => setD({ entries: [], sections: {} }));
  useEffect(() => { load(); }, []);
  if (!d) return <div className="py-10 flex justify-center"><Loader2 className="animate-spin text-ink-muted" /></div>;
  const sections: Record<string, string> = d.sections ?? {};
  const entries: Dict[] = d.entries ?? [];
  const done = () => { load(); refresh(); };

  async function upload(f: File) {
    const fd = new FormData(); fd.append("file", f);
    setBusy(true);
    try {
      const r = await api.form("/api/profile/cv", fd);
      if (r.entries_created) { toast(`Made ${r.entries_created} entries from ${r.filename}. Tidy anything that looks off.`); done(); }
      else { await load(); await fromCv(); }
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  }
  async function fromCv() {
    try { const r = await api.post("/api/entries/from-cv", {}); setDrafts({ items: r.drafts, from: "cv" }); }
    catch (e: any) { toast(e.message, "error"); }
  }
  async function remove(e: Dict) {
    await api.del(`/api/entries/${e.id}`); done();
    toast(`Deleted "${e.title || sections[e.section]}"`, "ok", {
      label: "Undo", run: () => api.post("/api/entries", { ...e, id: undefined }).then(done),
    });
  }
  async function move(e: Dict, dir: -1 | 1) {
    const same = entries.filter((x) => x.section === e.section);
    const i = same.findIndex((x) => x.id === e.id), j = i + dir;
    if (j < 0 || j >= same.length) return;
    [same[i], same[j]] = [same[j], same[i]];
    const order = Object.keys(sections).flatMap((s) => s === e.section ? same : entries.filter((x) => x.section === s));
    setD({ ...d!, entries: order });
    await api.post("/api/entries/reorder", { ids: order.map((x) => x.id) }); refresh();
  }

  return (
    <div className="space-y-5">
      <div className="card p-4 flex flex-wrap items-center gap-3">
        <div className="flex-1 min-w-[220px]">
          <div className="text-[14px] font-semibold">Your experience, as entries</div>
          <p className="text-[12.5px] text-ink-muted">Every line is matched against job requirements, and the same entries become the profile in prompts for your chat assistant. No CV file needed.</p>
        </div>
        <input ref={file} type="file" accept=".pdf,.docx,.txt,.md" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
        <button className="btn-secondary btn-sm" onClick={() => setPaste("")}><ClipboardPaste size={13} /> Paste a section</button>
        {d.has_cv && <button className="btn-secondary btn-sm" onClick={fromCv} title={d.cv_filename ?? ""}><Wand2 size={13} /> From my uploaded CV</button>}
        <button className="btn-secondary btn-sm" disabled={busy} onClick={() => file.current?.click()}>{busy ? <Loader2 size={13} className="animate-spin" /> : <FileUp size={13} />} Import a CV file</button>
      </div>

      {!entries.length && (
        <EmptyState art="notes" title="Start with what you've done"
          action={<div className="flex flex-wrap justify-center gap-2">
            <button className="btn-primary" onClick={() => setEdit({ section: "experience", ...BLANK })}><Plus size={15} /> Add an entry</button>
            <button className="btn-secondary" onClick={() => file.current?.click()}><FileUp size={15} /> Import my CV once</button>
          </div>}>
          Add entries one by one, paste a section of your CV to split it, or import your CV once and tidy the result.
        </EmptyState>
      )}

      {entries.length > 0 && Object.entries(sections).map(([sec, label]) => {
        const items = entries.filter((e) => e.section === sec);
        return (
          <section key={sec} className="card">
            <div className="px-5 py-3 border-b border-line flex items-center justify-between gap-2">
              <div className="min-w-0">
                <h3 className="text-[14px] font-semibold">{label} <span className="text-ink-faint font-normal num">{items.length || ""}</span></h3>
                {!items.length && <p className="text-[11.5px] text-ink-muted">{SECTION_HINT[sec]}</p>}
              </div>
              <button className="btn-ghost btn-sm shrink-0" onClick={() => setEdit({ section: sec, ...BLANK })}><Plus size={13} /> Add</button>
            </div>
            {items.length > 0 && (
              <ul className="divide-y divide-line">
                {items.map((e, i) => <EntryRow key={e.id} e={e} first={i === 0} last={i === items.length - 1}
                  onEdit={() => setEdit(e)} onDelete={() => remove(e)} onMove={(dir) => move(e, dir)} />)}
              </ul>
            )}
          </section>
        );
      })}

      {edit && <EntryModal entry={edit} sections={sections} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); done(); }} />}
      {paste !== null && <PasteModal sections={sections} onClose={() => setPaste(null)} onDrafts={(items) => { setPaste(null); setDrafts({ items, from: "paste" }); }} />}
      {drafts && <DraftsModal drafts={drafts.items} from={drafts.from} hasEntries={entries.length > 0} sections={sections}
        onClose={() => setDrafts(null)} onSaved={(n) => { setDrafts(null); done(); toast(`Saved ${n} ${n === 1 ? "entry" : "entries"}`); }} />}
    </div>
  );
}

function headline(e: Dict) {
  return [e.title, e.org, e.location].filter(Boolean).join(" · ");
}

function EntryRow({ e, first, last, onEdit, onDelete, onMove }:
  { e: Dict; first: boolean; last: boolean; onEdit: () => void; onDelete: () => void; onMove: (d: -1 | 1) => void }) {
  const lines = (e.details ?? "").split("\n").filter((x: string) => x.trim());
  const dates = [e.start, e.end].filter(Boolean).join(" – ");
  return (
    <li className="group px-5 py-3 flex gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <button className="text-left text-[13.5px] font-medium hover:text-brand" onClick={onEdit}>{headline(e) || <span className="text-ink-muted italic">Untitled</span>}</button>
          {dates && <span className="text-[11.5px] text-ink-muted num">{dates}</span>}
        </div>
        {e.section === "skills" ? (
          <div className="flex flex-wrap gap-1 mt-1.5">{lines.join(", ").split(/\s*,\s*/).filter(Boolean).map((k: string, i: number) => <span key={i} className="chip h-6">{k}</span>)}</div>
        ) : lines.length > 0 && (
          <ul className="mt-1 space-y-0.5">{lines.map((l: string, i: number) => <li key={i} className="text-[12.5px] text-ink-soft leading-snug flex gap-1.5"><span className="text-ink-faint">•</span>{l}</li>)}</ul>
        )}
      </div>
      <div className="flex items-start gap-0.5 sm:opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition">
        <button className="btn-ghost btn-sm px-1.5" disabled={first} aria-label="Move up" onClick={() => onMove(-1)}><ArrowUp size={13} /></button>
        <button className="btn-ghost btn-sm px-1.5" disabled={last} aria-label="Move down" onClick={() => onMove(1)}><ArrowDown size={13} /></button>
        <button className="btn-ghost btn-sm px-1.5" aria-label="Edit" onClick={onEdit}><Pencil size={13} /></button>
        <button className="btn-ghost btn-sm px-1.5 text-danger" aria-label="Delete" onClick={onDelete}><Trash2 size={13} /></button>
      </div>
    </li>
  );
}

function EntryFields({ e, set, sections }: { e: Dict; set: (e: Dict) => void; sections: Record<string, string> }) {
  const skills = e.section === "skills";
  const labels: Record<string, [string, string]> = {
    experience: ["Role", "Organisation"], education: ["Degree / course", "School"], projects: ["Project", "Context (e.g. course, team)"],
    publications: ["Title", "Venue / journal"], other: ["Title", "Issuer / organisation"], skills: ["Group (e.g. Programming)", ""],
  };
  const [t, o] = labels[e.section] ?? labels.other;
  return (
    <div className="space-y-3">
      <div className="grid sm:grid-cols-[160px_1fr] gap-3">
        <Field label="Section"><Select value={e.section} onChange={(v) => set({ ...e, section: v })} options={Object.entries(sections).map(([value, label]) => ({ value, label }))} /></Field>
        <Field label={t}><input className="input" autoFocus value={e.title ?? ""} onChange={(x) => set({ ...e, title: x.target.value })} /></Field>
      </div>
      {!skills && (
        <div className="grid sm:grid-cols-[1fr_1fr_110px_110px] gap-3">
          <Field label={o}><input className="input" value={e.org ?? ""} onChange={(x) => set({ ...e, org: x.target.value })} /></Field>
          <Field label="Location"><input className="input" value={e.location ?? ""} onChange={(x) => set({ ...e, location: x.target.value })} /></Field>
          <Field label="From"><input className="input" placeholder="Sep 2023" value={e.start ?? ""} onChange={(x) => set({ ...e, start: x.target.value })} /></Field>
          <Field label="To"><input className="input" placeholder="Present" value={e.end ?? ""} onChange={(x) => set({ ...e, end: x.target.value })} /></Field>
        </div>
      )}
      <Field label={skills ? "Skills, comma-separated" : "What you did, one per line"} hint={SECTION_HINT[e.section]}>
        <textarea className="textarea h-36 text-[13px]" value={e.details ?? ""} onChange={(x) => set({ ...e, details: x.target.value })}
          placeholder={skills ? "Python, R, SQL, Power BI, GCP" : "Built a … that cut … by 30%\nLed …"} />
      </Field>
    </div>
  );
}

function EntryModal({ entry, sections, onClose, onSaved }: { entry: Dict; sections: Record<string, string>; onClose: () => void; onSaved: () => void }) {
  const { toast } = useApp();
  const [e, setE] = useState<Dict>({ ...entry });
  async function save() {
    const body = { section: e.section, title: e.title, org: e.org || null, location: e.location || null, start: e.start || null, end: e.end || null,
      details: (e.details ?? "").split("\n").map((l: string) => l.replace(/^\s*[•\-–*]\s*/, "").trim()).filter(Boolean).join("\n") };
    try {
      if (e.id) await api.patch(`/api/entries/${e.id}`, body); else await api.post("/api/entries", body);
      onSaved();
    } catch (x: any) { toast(x.message, "error"); }
  }
  return (
    <Modal open onClose={onClose} title={e.id ? "Edit entry" : `Add to ${sections[e.section] ?? "profile"}`}
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!e.title?.trim() && !e.details?.trim()} onClick={save}>Save</button></>}>
      <EntryFields e={e} set={setE} sections={sections} />
    </Modal>
  );
}

function PasteModal({ sections, onClose, onDrafts }: { sections: Record<string, string>; onClose: () => void; onDrafts: (d: Dict[]) => void }) {
  const { toast } = useApp();
  const [section, setSection] = useState("experience");
  const [text, setText] = useState("");
  async function split() {
    try {
      const r = await api.post("/api/entries/split", { section, text });
      if (!r.drafts.length) return toast("Couldn't find any entries in that text", "error");
      onDrafts(r.drafts);
    } catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <Modal open onClose={onClose} title="Paste a section"
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={text.trim().length < 3} onClick={split}>Split into entries</button></>}>
      <div className="space-y-3">
        <Field label="Which section is this?" className="max-w-xs"><Select value={section} onChange={setSection} options={Object.entries(sections).map(([value, label]) => ({ value, label }))} /></Field>
        <Field label="Text" hint="Copy a whole section from your CV or LinkedIn. A line with dates or followed by bullets starts a new entry; you'll check the result before saving.">
          <textarea className="textarea h-64 text-[12.5px] font-mono" autoFocus value={text} onChange={(e) => setText(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

function DraftsModal({ drafts, from, hasEntries, sections, onClose, onSaved }:
  { drafts: Dict[]; from: "cv" | "paste"; hasEntries: boolean; sections: Record<string, string>; onClose: () => void; onSaved: (n: number) => void }) {
  const { toast } = useApp();
  const [items, setItems] = useState<Dict[]>(drafts.map((d) => ({ ...BLANK, ...d, keep: true })));
  const [open, setOpen] = useState<number | null>(null);
  const [replace, setReplace] = useState(from === "cv" && hasEntries);
  const kept = items.filter((x) => x.keep);
  async function save() {
    try {
      const r = await api.post("/api/entries/bulk", { entries: kept.map(({ keep, ...x }) => x), replace });
      onSaved(r.created);
    } catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <Modal open onClose={onClose} title={`Check ${items.length} draft ${items.length === 1 ? "entry" : "entries"}`} width="max-w-4xl"
      footer={<>
        {hasEntries && <label className="mr-auto flex items-center gap-2 text-[12.5px]"><input type="checkbox" className="accent-brand" checked={replace} onChange={(e) => setReplace(e.target.checked)} />Replace my current entries</label>}
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={!kept.length} onClick={save}>Save {kept.length}</button>
      </>}>
      <p className="text-[12.5px] text-ink-muted mb-3">Untick anything you don't want, and click an entry to fix it. You can still edit everything after saving.</p>
      <ul className="space-y-2">
        {items.map((e, i) => (
          <li key={i} className={cls("rounded-lg border border-line", !e.keep && "opacity-50")}>
            <div className="flex items-start gap-3 px-3 py-2">
              <input type="checkbox" className="accent-brand mt-1" checked={e.keep} aria-label="Keep"
                onChange={(x) => setItems(items.map((y, j) => j === i ? { ...y, keep: x.target.checked } : y))} />
              <button className="flex-1 min-w-0 text-left" onClick={() => setOpen(open === i ? null : i)}>
                <div className="text-[13px] font-medium"><span className="chip h-5 text-[10.5px] mr-1.5">{sections[e.section] ?? e.section}</span>
                  {headline(e) || <span className="italic text-ink-muted">Untitled</span>}
                  {(e.start || e.end) && <span className="text-[11.5px] text-ink-muted font-normal num"> · {[e.start, e.end].filter(Boolean).join(" – ")}</span>}</div>
                {open !== i && e.details && <div className="text-[12px] text-ink-muted line-clamp-2 mt-0.5 whitespace-pre-line">{e.details}</div>}
              </button>
            </div>
            {open === i && <div className="px-3 pb-3 pt-1 border-t border-line"><EntryFields e={e} sections={sections} set={(n) => setItems(items.map((y, j) => j === i ? n : y))} /></div>}
          </li>
        ))}
      </ul>
    </Modal>
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
      <p className="text-[12.5px] text-ink-muted mb-4">Added to the CV and cover-letter prompts you copy to a chat assistant, so drafts sound like you.</p>
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
