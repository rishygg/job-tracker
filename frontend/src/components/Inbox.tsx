import { useEffect, useMemo, useState } from "react";
import { ArchiveRestore, CalendarClock, Check, MessagesSquare, Trash2, X } from "lucide-react";
import { api, type Dict } from "../api";
import { useApp } from "../store";
import { cls, pct, relDays, today } from "../lib";
import { EmptyState, Monogram, Segmented } from "./ui";
import { RankChip, RankExtras } from "./Chat";

type Tab = "new" | "ranked" | "skipped";

/** Jobs you've collected but not decided on: rank them with your chat assistant, then mark each Applied or Skip. */
export function Inbox({ jobs, onRank }: { jobs: Dict[]; onRank: (items?: Dict[]) => void }) {
  const { toast, refresh, openSaved } = useApp();
  const [tab, setTab] = useState<Tab>("new");
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Rows move at once when you act on them; the server's list catches up a moment later.
  const [moved, setMoved] = useState<Map<number, string>>(new Map());
  useEffect(() => {  // forget a move once the server's list shows it
    setMoved((m) => {
      const keep = new Map<number, string>();
      m.forEach((to, id) => {
        const now = jobs.find((o) => o.id === id)?.status ?? "gone";
        const reached = to === "deleted" || to === "applied" ? now === "gone" : now === to;
        if (!reached) keep.set(id, to);
      });
      return keep.size === m.size ? m : keep;
    });
  }, [jobs]);
  const shown = useMemo(() => jobs.map((o) => (moved.has(o.id) ? { ...o, status: moved.get(o.id) } : o)), [jobs, moved]);

  const groups = useMemo(() => {
    const inbox = shown.filter((o) => o.status === "saved");
    const byScore = (a: Dict, b: Dict) => (b.rank?.score ?? -1) - (a.rank?.score ?? -1);
    return {
      new: inbox.filter((o) => !o.rank),
      ranked: inbox.filter((o) => o.rank).sort(byScore),
      skipped: shown.filter((o) => o.status === "archived"),
    } as Record<Tab, Dict[]>;
  }, [shown]);

  // After ranking, show the ranked list; with nothing new waiting, don't leave the user on an empty tab.
  useEffect(() => { if (tab === "new" && !groups.new.length && groups.ranked.length) setTab("ranked"); }, [groups.new.length, groups.ranked.length]);
  useEffect(() => { setSel(new Set()); setConfirmDelete(false); }, [tab]);
  useEffect(() => { setSel((s) => new Set([...s].filter((id) => jobs.some((o) => o.id === id)))); }, [jobs]);

  const rows = groups[tab];
  const allSel = rows.length > 0 && rows.every((o) => sel.has(o.id));
  const toggle = (id: number) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  async function act(ids: number[], action: "archive" | "restore" | "delete" | "apply") {
    const to = { archive: "archived", restore: "saved", delete: "deleted", apply: "applied" }[action];
    setMoved((m) => { const n = new Map(m); ids.forEach((id) => n.set(id, to)); return n; });
    try {
      await api.post("/api/opportunities/batch", { ids, action });
      const n = ids.length, s = n === 1 ? "" : "s";
      if (action === "apply") toast(`${n} job${s} moved to Applied. Good luck!`);
      else if (action === "archive") toast(`Skipped ${n} job${s}`, "ok", { label: "Undo", run: () => act(ids, "restore") });
      else if (action === "restore") toast(`${n} job${s} back in your Inbox`);
      else toast(`Deleted ${n} job${s}`);
      setSel(new Set()); setConfirmDelete(false); refresh();
    } catch (e: any) {
      setMoved((m) => { const n = new Map(m); ids.forEach((id) => n.delete(id)); return n; });
      toast(e.message, "error");
    }
  }

  const fresh = groups.new.length, ranked = groups.ranked.length, skipped = groups.skipped.length;
  if (!fresh && !ranked && !skipped) {
    return (
      <div className="card">
        <EmptyState art="inbox" title="Your Inbox is empty">
          Press <b>N</b> or use the browser bookmark to add jobs as you find them, as many as you like. Rank them all with your chat assistant, then mark the ones you apply to.
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <Segmented value={tab} onChange={setTab} options={[
          { id: "new", label: <>To rank <span className="num text-ink-muted">{fresh}</span></> },
          { id: "ranked", label: <>Ranked <span className="num text-ink-muted">{ranked}</span></> },
          { id: "skipped", label: <>Skipped <span className="num text-ink-muted">{skipped}</span></> },
        ]} />
        <div className="flex-1" />
        {tab !== "skipped" && (
          <button className="btn-primary btn-sm" onClick={() => onRank()} disabled={!fresh && !ranked}>
            <MessagesSquare size={13} /> {fresh ? `Rank ${fresh} new with chat assistant` : "Rank again with chat assistant"}
          </button>
        )}
      </div>

      {sel.size > 0 && (
        <div className="anim-in flex flex-wrap items-center gap-2 px-3 py-2 rounded-lg border border-line bg-brand-soft/60 text-[12.5px]">
          <b className="num">{sel.size}</b> selected
          <span className="w-px h-5 bg-line mx-1" />
          {tab !== "skipped" ? <>
            <button className="btn-secondary btn-sm" onClick={() => act([...sel], "apply")}><Check size={13} /> Applied</button>
            <button className="btn-secondary btn-sm" onClick={() => act([...sel], "archive")}><X size={13} /> Skip</button>
            <button className="btn-secondary btn-sm" onClick={() => onRank([...sel].map((id) => ({ kind: "opportunity", ref_id: id })))}><MessagesSquare size={13} /> Rank selected</button>
          </> : <>
            <button className="btn-secondary btn-sm" onClick={() => act([...sel], "restore")}><ArchiveRestore size={13} /> Restore</button>
            {confirmDelete
              ? <span className="inline-flex items-center gap-1"><span className="text-danger font-medium">Delete {sel.size} for good?</span>
                  <button className="btn btn-sm bg-danger text-white" onClick={() => act([...sel], "delete")}>Yes, delete</button>
                  <button className="btn-ghost btn-sm" onClick={() => setConfirmDelete(false)}>No</button></span>
              : <button className="btn-ghost btn-sm text-danger" onClick={() => setConfirmDelete(true)}><Trash2 size={13} /> Delete</button>}
          </>}
          <button className="btn-ghost btn-sm ml-auto" onClick={() => setSel(new Set())}><X size={13} /> Clear</button>
        </div>
      )}

      {!rows.length ? (
        <div className="card"><EmptyState art="inbox" title={tab === "new" ? "Everything is ranked" : tab === "ranked" ? "Nothing ranked yet" : "No skipped jobs"}>
          {tab === "new" ? "New jobs you add will wait here until you rank them." : tab === "ranked" ? "Rank the jobs under “To rank” and they appear here, best first." : "Jobs you skip are kept here, out of the way. Pasting the same posting again will warn you."}
        </EmptyState></div>
      ) : (
        <div className="card overflow-hidden">
          <div className="flex items-center gap-3 px-3 py-2 border-b border-line text-[12px] text-ink-muted">
            <input type="checkbox" aria-label="Select all" className="accent-brand w-4 h-4" checked={allSel}
              onChange={() => setSel(allSel ? new Set() : new Set(rows.map((o) => o.id)))} />
            {tab === "ranked" ? "Best score first" : "Newest first"} · {rows.length} job{rows.length === 1 ? "" : "s"}
          </div>
          <ul className="divide-y divide-line">
            {rows.map((o) => <Row key={o.id} o={o} tab={tab} checked={sel.has(o.id)} onToggle={() => toggle(o.id)} onOpen={() => openSaved(o.id)} act={(a) => act([o.id], a)} />)}
          </ul>
        </div>
      )}
    </div>
  );
}

function Row({ o, tab, checked, onToggle, onOpen, act }:
  { o: Dict; tab: Tab; checked: boolean; onToggle: () => void; onOpen: () => void; act: (a: "archive" | "restore" | "delete" | "apply") => void }) {
  const soon = o.deadline && o.deadline >= today() && (new Date(o.deadline).getTime() - Date.now()) / 86400000 <= 7;
  const action = o.fit?.action;
  const missing = o.rank?.missing && String(o.rank.missing).toLowerCase() !== "none" ? o.rank.missing : null;
  return (
    <li className={cls("flex flex-wrap sm:flex-nowrap items-start gap-3 px-3 py-3 hover:bg-canvas/60 cursor-pointer", checked && "bg-brand-soft/40")} onClick={onOpen}>
      <input type="checkbox" aria-label={`Select ${o.company}`} className="accent-brand w-4 h-4 mt-1.5" checked={checked}
        onClick={(e) => e.stopPropagation()} onChange={onToggle} />
      <Monogram name={o.company} size={30} />
      <div className="min-w-0 flex-1">
        <div className="flex items-start gap-2 flex-wrap">
          <span className="font-semibold text-[13.5px] leading-snug">{o.position}</span>
          <RankChip rank={o.rank} />
        </div>
        <div className="text-[12.5px] text-ink-soft mt-0.5">{o.company}{o.location ? <span className="text-ink-muted"> · {o.location}</span> : null}</div>
        {o.rank?.reason && <p className="text-[12.5px] text-ink-soft mt-1 leading-snug">{o.rank.reason}{missing ? <span className="text-ink-muted"> Missing: {missing}</span> : null}</p>}
        <div className="flex flex-wrap gap-1 mt-1.5">
          <RankExtras rank={o.rank} mode="card" />
          {!o.rank && o.fit && <span title="Rule-based fit" className={cls("chip h-5 text-[10.5px]", action === "Apply" ? "bg-ok-soft text-ok border-ok-line" : action === "Deprioritise" || action === "Not scored" ? "" : "bg-warn-soft text-warn border-warn-line")}>
            {o.fit.score !== null && o.fit.score !== undefined ? `${pct(o.fit.score)} · ` : ""}{action}</span>}
          {o.workload && <span className="chip h-5 text-[10.5px]">{o.workload}</span>}
          {o.deadline && <span className={cls("chip h-5 text-[10.5px]", soon && "bg-alert-soft text-alert border-alert/30")}><CalendarClock size={10} />{relDays(o.deadline)}</span>}
          {!o.has_jd && <span className="chip h-5 text-[10.5px]">No description</span>}
        </div>
      </div>
      <div className="flex items-center gap-1.5 shrink-0 w-full sm:w-auto pl-[74px] sm:pl-0" onClick={(e) => e.stopPropagation()}>
        {tab === "skipped" ? <>
          <button className="btn-secondary btn-sm" onClick={() => act("restore")}><ArchiveRestore size={13} /> Restore</button>
        </> : <>
          <button className="btn-secondary btn-sm" title="I applied: moves it to the Applied column" onClick={() => act("apply")}><Check size={13} /> Applied</button>
          <button className="btn-ghost btn-sm" title="Not for me: moves it to Skipped" onClick={() => act("archive")}><X size={13} /> Skip</button>
        </>}
      </div>
    </li>
  );
}
