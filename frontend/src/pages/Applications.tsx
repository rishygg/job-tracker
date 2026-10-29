import { useEffect, useMemo, useState } from "react";
import { DndContext, PointerSensor, useDraggable, useDroppable, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { ArrowDown, ArrowUp, Columns3, Ghost, Inbox as InboxIcon, MapPin, MessagesSquare, Rows3, Search, Star, Trash2, X, XCircle } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { api, type AppItem, type Dict } from "../api";
import { useApi, useApp } from "../store";
import { cls, COLUMN_OF, fmtDate, pct, STAGE_STYLE, today } from "../lib";
import { FilterBar } from "../components/FilterBar";
import { EmptyState, Modal, Monogram, PageHeader, Segmented, Skeleton, StatusPill } from "../components/ui";
import { celebrate } from "../components/Confetti";
import { RankChip, RankExtras, RankModal } from "../components/Chat";
import { Inbox } from "../components/Inbox";

type View = "board" | "inbox" | "table";

export default function Applications() {
  const { filterQuery, meta, refresh, toast, openApp, undoable } = useApp();
  const [view, setView] = useState<View>(() => (localStorage.getItem("jt.view") as View) || "board");
  const [q, setQ] = useState("");
  const [qDebounced, setQDebounced] = useState("");
  useEffect(() => { const t = setTimeout(() => setQDebounced(q), 200); return () => clearTimeout(t); }, [q]);
  useEffect(() => { try { localStorage.setItem("jt.view", view); } catch { /* ignore */ } }, [view]);
  const [params, setParams] = useSearchParams();
  const [rankOpen, setRankOpen] = useState<{ items?: Dict[]; title?: string } | null>(null);
  useEffect(() => {
    const p = new URLSearchParams(params);
    if (params.get("rank") === "1") { setView("inbox"); setRankOpen({}); p.delete("rank"); setParams(p, { replace: true }); }
    else if (params.get("view") === "inbox") { setView("inbox"); p.delete("view"); setParams(p, { replace: true }); }
  }, [params]);

  const { data, loading, setData } = useApi<{ items: AppItem[]; total: number }>(`/api/applications${filterQuery({ q: qDebounced })}`);
  const items = data?.items ?? [];
  const { data: oppAll } = useApi<Dict[]>("/api/opportunities?status=all");
  const inboxAll = useMemo(() => (oppAll ?? []).filter((o) => o.status === "saved" || o.status === "archived"), [oppAll]);
  const inbox = useMemo(() => inboxAll.filter((o) => !qDebounced || `${o.company} ${o.position} ${o.location ?? ""}`.toLowerCase().includes(qDebounced.toLowerCase())), [inboxAll, qDebounced]);
  const waiting = inboxAll.filter((o) => o.status === "saved" && !o.rank).length;
  const counts = useMemo(() => {
    const live = inboxAll.filter((o) => o.status === "saved");
    return { fresh: live.filter((o) => !o.rank && o.has_jd).length, ranked: live.filter((o) => o.rank).length };
  }, [inboxAll]);

  async function moveTo(app: AppItem, stage: string) {
    if (stage === app.status) return;
    // Optimistic update so the card moves immediately.
    setData((d) => d && { ...d, items: d.items.map((x) => (x.id === app.id ? { ...x, status: stage } : x)) });
    try {
      const r = await api.post(`/api/applications/${app.id}/stages`, { stage, date: today() });
      undoable(`${app.company}: moved to ${stage}`, r.event_id ? [r.event_id] : []);
      if (stage === "Offer" || stage === "Accepted") celebrate();
      refresh();
    } catch (e: any) { toast(e.message, "error"); refresh(); }
  }

  return (
    <div>
      <PageHeader title="Applications" subtitle={view === "inbox" ? "Jobs you've collected: rank them, then mark each Applied or Skip" : data ? `${items.length} of ${data.total} applications` : " "}
        actions={<Segmented value={view} onChange={setView} options={[
          { id: "board", label: <><Columns3 size={14} /> Board</> },
          { id: "inbox", label: <><InboxIcon size={14} /> Inbox{waiting > 0 && <span className="num text-[11px] px-1.5 rounded-full bg-brand text-white">{waiting}</span>}</> },
          { id: "table", label: <><Rows3 size={14} /> Table</> }]} />} />
      <div className="flex flex-col gap-3 mb-5">
        <div className="relative max-w-md">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
          <input className="input pl-9" placeholder="Search company, role, location, notes…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {view !== "inbox" && <FilterBar />}
      </div>
      {view === "inbox" ? (
        <Inbox jobs={inbox} onRank={(items) => setRankOpen(items ? { items, title: `Rank ${items.length} selected job${items.length === 1 ? "" : "s"} with your chat assistant` } : {})} />
      ) : loading && !data ? (
        <div className="grid grid-cols-5 gap-4">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-80" />)}</div>
      ) : data && data.total === 0 ? (
        <div className="card"><EmptyState art="inbox" title="No applications yet" action={<SampleOrImport />}>
          Add your first one with the button on the left, import your spreadsheet in Settings, or load sample data to look around.
        </EmptyState></div>
      ) : view === "board" ? (
        <Board items={items} columns={meta?.board_columns ?? []} onMove={moveTo} onOpen={openApp} followUpAfter={meta?.settings?.follow_up_after ?? 10} />
      ) : (
        <Table items={items} stages={meta?.stages ?? []} onMove={moveTo} onOpen={openApp}
          onRank={(ids) => setRankOpen({ items: ids.map((id) => ({ kind: "application", ref_id: id })), title: `Rank ${ids.length} applications with your chat assistant` })} />
      )}
      {rankOpen && <RankModal items={rankOpen.items} title={rankOpen.title} counts={rankOpen.items ? undefined : counts} onClose={() => setRankOpen(null)} />}
    </div>
  );
}

function SampleOrImport() {
  const { refresh, toast } = useApp();
  return (
    <button className="btn-secondary" onClick={async () => { await api.post("/api/sample"); refresh(); toast("Sample data loaded"); }}>
      Load sample data
    </button>
  );
}

// ------------------------------------------------------------------ board
const SORTS: Record<string, (a: AppItem, b: AppItem) => number> = {
  "Newest first": (a, b) => (a.date_applied < b.date_applied ? 1 : -1),
  "Oldest first": (a, b) => (a.date_applied > b.date_applied ? 1 : -1),
  "Longest without news": (a, b) => b.days_since_activity - a.days_since_activity,
  Company: (a, b) => a.company.localeCompare(b.company),
};

type Col = { id: string; label: string; stages: string[]; drop_stage: string | null };

function Board({ items, columns, onMove, onOpen, followUpAfter }:
  { items: AppItem[]; columns: Col[]; onMove: (a: AppItem, stage: string) => void; onOpen: (id: number) => void; followUpAfter: number }) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const [closing, setClosing] = useState<AppItem | null>(null);
  const [landed, setLanded] = useState<string | null>(null);
  const byId = useMemo(() => new Map(items.map((i) => [i.id, i])), [items]);

  function onDragEnd(e: DragEndEvent) {
    const key = String(e.active.id);
    const col = columns.find((c) => c.id === e.over?.id);
    if (!col) return;
    const app = byId.get(Number(key));
    if (!app) return;
    if (COLUMN_OF[app.status] === col.id) return;
    setLanded(key);
    if (col.drop_stage) onMove(app, col.drop_stage);
    else setClosing(app);
  }

  return (
    <DndContext sensors={sensors} onDragEnd={onDragEnd}>
      <div className="grid gap-3 overflow-x-auto pb-2 scroll-thin" style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(220px, 1fr))` }}>
        {columns.map((c) => <Column key={c.id} col={c} items={items.filter((i) => c.stages.includes(i.status))} onOpen={onOpen} followUpAfter={followUpAfter} landed={landed} />)}
      </div>
      <Modal open={!!closing} onClose={() => setClosing(null)} title="Close this application" width="max-w-md">
        <p className="text-ink-soft mb-4">How did <b>{closing?.position}</b> at {closing?.company} end?</p>
        <div className="grid grid-cols-3 gap-2">
          {["Rejected", "Ghosted", "Withdrawn"].map((s) => (
            <button key={s} className="btn-secondary h-11" onClick={() => { if (closing) onMove(closing, s); setClosing(null); }}>{s}</button>
          ))}
        </div>
      </Modal>
    </DndContext>
  );
}

function Column({ col, items, onOpen, followUpAfter, landed }:
  { col: { id: string; label: string }; items: AppItem[]; onOpen: (id: number) => void; followUpAfter: number; landed: string | null }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.id });
  const [sort, setSort] = useState("Newest first");
  const [limit, setLimit] = useState(25);
  const st = STAGE_STYLE[col.id];
  const sorted = [...items].sort(SORTS[sort]);
  return (
    <section ref={setNodeRef} aria-label={col.label}
      className={cls("rounded-xl border bg-column flex flex-col min-h-[420px] transition-colors",
        isOver ? "border-brand bg-brand-soft/60" : "border-line")}>
      <header className="px-3 pt-3 pb-2">
        <div className="h-[3px] rounded-full mb-2.5" style={{ background: st.dot }} />
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold text-[13.5px]">
            <span className="w-2 h-2 rounded-full" style={{ background: st.dot }} />{col.label}
          </div>
          <span className="num text-[11.5px] min-w-[22px] h-[22px] px-1.5 rounded-full bg-surface border border-line inline-flex items-center justify-center text-ink-soft">{items.length}</span>
        </div>
        <select aria-label={`Sort ${col.label}`} value={sort} onChange={(e) => setSort(e.target.value)}
          className="mt-2 w-full h-7 px-2 rounded-md border border-line bg-surface text-[12px] text-ink-muted">
          {Object.keys(SORTS).map((s) => <option key={s}>{s}</option>)}
        </select>
      </header>
      <div className="flex-1 px-2 pb-2 space-y-2 overflow-y-auto scroll-thin max-h-[calc(100vh-290px)]">
        {sorted.slice(0, limit).map((a) => <Card key={a.id} app={a} onOpen={onOpen} followUpAfter={followUpAfter} landed={landed === String(a.id)} />)}
        {sorted.length > limit && (
          <button className="w-full btn-ghost btn-sm" onClick={() => setLimit(limit + 50)}>Show {Math.min(50, sorted.length - limit)} more</button>
        )}
        {items.length === 0 && (
          <div className="h-24 rounded-lg border border-dashed border-line-strong flex items-center justify-center text-[12px] text-ink-faint">Drop cards here</div>
        )}
      </div>
    </section>
  );
}

function Card({ app, onOpen, followUpAfter, landed }: { app: AppItem; onOpen: (id: number) => void; followUpAfter: number; landed?: boolean }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: app.id });
  const stale = app.active && app.days_since_activity >= followUpAfter;
  const upcoming = app.days_since_activity < 0;
  const style = transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined;
  const closedLabel = ["Rejected", "Ghosted", "Withdrawn"].includes(app.status) ? app.status : app.status === "Final interview" ? "Final round" : null;
  return (
    <article ref={setNodeRef} style={style} {...listeners} {...attributes}
      onClick={() => onOpen(app.id)}
      className={cls("bg-surface rounded-lg border border-line p-3 cursor-pointer select-none transition-shadow hover:shadow-pop hover:border-line-strong",
        isDragging && "shadow-pop ring-2 ring-brand/30 z-10 relative", landed && !isDragging && "anim-pop anim-pulse-ring")}>
      <div className="flex items-start gap-2.5">
        <Monogram name={app.company} size={28} />
        <div className="min-w-0 flex-1">
          <div className="font-semibold text-[13.5px] leading-snug">{app.position}</div>
          <div className="text-[12.5px] text-ink-soft mt-0.5 truncate">{app.company}</div>
        </div>
      </div>
      <div className="text-[11.5px] text-ink-muted num mt-1.5">{fmtDate(app.date_applied)}</div>
      <div className="flex flex-wrap gap-1 mt-2">
        {closedLabel && <span className="chip h-5 text-[10.5px]">{closedLabel}</span>}
        {upcoming && <span className="chip h-5 text-[10.5px] bg-warn-soft text-warn border-warn-line">Next step in {-app.days_since_activity}d</span>}
        {stale && <span className="chip h-5 text-[10.5px] bg-alert-soft text-alert border-alert/30">{app.days_since_activity}d no news</span>}
        <span className="chip h-5 text-[10.5px] max-w-full truncate">{app.role_area}</span>
        {app.location && <span className="chip h-5 text-[10.5px]"><MapPin size={10} />{app.location.length > 18 ? app.location.slice(0, 17) + "…" : app.location}</span>}
        <RankChip rank={app.rank} />
        <RankExtras rank={app.rank} mode="card" />
        {app.jd_match !== null && <span className="chip h-5 text-[10.5px] bg-brand-soft text-brand-strong border-brand/20">{pct(app.jd_match)} match</span>}
        {app.fit_rating ? <span className="chip h-5 text-[10.5px]"><Star size={10} fill="currentColor" className="text-amber" />{app.fit_rating}</span> : null}
      </div>
    </article>
  );
}

// ------------------------------------------------------------------ table
const COLS: { key: keyof AppItem; label: string; w?: string; num?: boolean }[] = [
  { key: "company", label: "Company", w: "min-w-[150px]" },
  { key: "position", label: "Position", w: "min-w-[220px]" },
  { key: "status", label: "Status", w: "min-w-[150px]" },
  { key: "date_applied", label: "Applied", num: true },
  { key: "role_area", label: "Job family", w: "min-w-[170px]" },
  { key: "seniority", label: "Seniority" },
  { key: "industry", label: "Industry", w: "min-w-[150px]" },
  { key: "location", label: "Location" },
  { key: "source", label: "Channel" },
  { key: "days_since_activity", label: "Days idle", num: true },
];

function Table({ items, stages, onMove, onOpen, onRank }:
  { items: AppItem[]; stages: string[]; onMove: (a: AppItem, s: string) => void; onOpen: (id: number) => void; onRank: (ids: number[]) => void }) {
  const { refresh, toast, undoable } = useApp();
  const [sort, setSort] = useState<{ key: keyof AppItem; dir: 1 | -1 }>({ key: "date_applied", dir: -1 });
  const [limit, setLimit] = useState(100);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState(false);
  const rows = useMemo(() => [...items].sort((a, b) => {
    const x = a[sort.key] as any, y = b[sort.key] as any;
    if (x === y) return 0;
    if (x === null || x === undefined) return 1;
    if (y === null || y === undefined) return -1;
    return (x > y ? 1 : -1) * sort.dir;
  }), [items, sort]);
  useEffect(() => { setSel((s) => new Set([...s].filter((id) => items.some((i) => i.id === id)))); }, [items]);
  if (!items.length) return <div className="card"><EmptyState art="inbox" title="No applications match">Try clearing the search or filters.</EmptyState></div>;
  const shown = rows.slice(0, limit);
  const allShown = shown.length > 0 && shown.every((r) => sel.has(r.id));
  const toggle = (id: number) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  async function batch(action: string) {
    const ids = [...sel];
    try {
      const r = await api.post("/api/applications/batch", { ids, action });
      if (action === "delete") toast(`Deleted ${r.count} application${r.count === 1 ? "" : "s"}`);
      else undoable(`${r.count} moved to ${action}`, r.event_ids);
      setSel(new Set()); setConfirmDelete(false); refresh();
    } catch (e: any) { toast(e.message, "error"); }
  }
  return (
    <div className="card overflow-hidden relative">
      {sel.size > 0 && (
        <div className="anim-in flex flex-wrap items-center gap-2 px-3 py-2 border-b border-line bg-brand-soft/60 text-[12.5px]">
          <b className="num">{sel.size}</b> selected
          <span className="w-px h-5 bg-line mx-1" />
          <select aria-label="Move selected to" className="h-7 px-2 rounded-md border border-line bg-surface text-[12px]" value="" onChange={(e) => e.target.value && batch(e.target.value)}>
            <option value="">Move to…</option>{stages.map((st) => <option key={st}>{st}</option>)}
          </select>
          <button className="btn-secondary btn-sm" onClick={() => batch("Ghosted")}><Ghost size={13} /> Ghosted</button>
          <button className="btn-secondary btn-sm" onClick={() => batch("Rejected")}><XCircle size={13} /> Rejected</button>
          <button className="btn-secondary btn-sm" disabled={sel.size > 40} title={sel.size > 40 ? "Up to 40 at a time" : "Copy a ranking prompt for these"} onClick={() => onRank([...sel])}><MessagesSquare size={13} /> Rank with chat</button>
          {confirmDelete
            ? <span className="inline-flex items-center gap-1"><span className="text-danger font-medium">Delete {sel.size}?</span>
                <button className="btn btn-sm bg-danger text-white" onClick={() => batch("delete")}>Yes, delete</button>
                <button className="btn-ghost btn-sm" onClick={() => setConfirmDelete(false)}>No</button></span>
            : <button className="btn-ghost btn-sm text-danger" onClick={() => setConfirmDelete(true)}><Trash2 size={13} /> Delete</button>}
          <button className="btn-ghost btn-sm ml-auto" onClick={() => setSel(new Set())}><X size={13} /> Clear</button>
        </div>
      )}
      <div className="overflow-auto max-h-[calc(100vh-260px)] scroll-thin">
        <table className="w-full text-[13px]">
          <thead className="sticky top-0 z-10 bg-surface shadow-[0_1px_0_rgb(var(--line))]">
            <tr>
              <th className="pl-3 pr-1 w-8"><input type="checkbox" aria-label="Select all shown" className="accent-brand w-4 h-4 align-middle" checked={allShown}
                onChange={() => setSel(allShown ? new Set() : new Set(shown.map((r) => r.id)))} /></th>
              {COLS.map((c) => (
                <th key={c.key} className={cls("text-left font-medium text-ink-muted px-3 py-2.5 whitespace-nowrap", c.w)}>
                  <button className="inline-flex items-center gap-1 hover:text-ink" onClick={() => setSort({ key: c.key, dir: sort.key === c.key ? (sort.dir === 1 ? -1 : 1) : 1 })}>
                    {c.label}{sort.key === c.key && (sort.dir === 1 ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((a) => (
              <tr key={a.id} onClick={() => onOpen(a.id)} className={cls("border-t border-line hover:bg-canvas/70 cursor-pointer", sel.has(a.id) && "bg-brand-soft/40")}>
                <td className="pl-3 pr-1" onClick={(e) => e.stopPropagation()}>
                  <input type="checkbox" aria-label={`Select ${a.company}`} className="accent-brand w-4 h-4 align-middle" checked={sel.has(a.id)} onChange={() => toggle(a.id)} />
                </td>
                <td className="px-3 py-2 font-medium"><span className="inline-flex items-center gap-2"><Monogram name={a.company} size={22} />{a.company}</span></td>
                <td className="px-3 py-2">{a.position}</td>
                <td className="px-3 py-1.5" onClick={(e) => e.stopPropagation()}>
                  <div className="relative inline-flex">
                    <StatusPill stage={a.status} />
                    <select aria-label="Change status" value={a.status} onChange={(e) => onMove(a, e.target.value)}
                      className="absolute inset-0 opacity-0 cursor-pointer">
                      {stages.map((st) => <option key={st}>{st}</option>)}
                    </select>
                  </div>
                </td>
                <td className="px-3 py-2 num text-ink-soft whitespace-nowrap">{fmtDate(a.date_applied)}</td>
                <td className="px-3 py-2 text-ink-soft">{a.role_area}</td>
                <td className="px-3 py-2 text-ink-soft whitespace-nowrap">{a.seniority}</td>
                <td className="px-3 py-2 text-ink-soft">{a.industry}</td>
                <td className="px-3 py-2 text-ink-soft">{a.location ?? "—"}</td>
                <td className="px-3 py-2 text-ink-soft whitespace-nowrap">{a.source ?? "—"}</td>
                <td className="px-3 py-2 num text-right pr-5">{a.days_since_activity}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > limit && (
        <div className="border-t border-line p-2 text-center"><button className="btn-ghost btn-sm" onClick={() => setLimit(limit + 200)}>Show more ({rows.length - limit} left)</button></div>
      )}
    </div>
  );
}

export type { Dict };
