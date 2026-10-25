import { useEffect, useMemo, useState } from "react";
import { DndContext, PointerSensor, useDraggable, useDroppable, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { ArrowDown, ArrowUp, Columns3, MapPin, Rows3, Search, Star } from "lucide-react";
import { api, type AppItem, type Dict } from "../api";
import { useApi, useApp } from "../store";
import { cls, COLUMN_OF, fmtDate, pct, STAGE_STYLE, today } from "../lib";
import { FilterBar } from "../components/FilterBar";
import { EmptyState, Modal, PageHeader, Segmented, Select, Skeleton, StatusPill } from "../components/ui";

type View = "board" | "table";

export default function Applications() {
  const { filterQuery, meta, refresh, toast, openApp } = useApp();
  const [view, setView] = useState<View>(() => (localStorage.getItem("jt.view") as View) || "board");
  const [q, setQ] = useState("");
  const [qDebounced, setQDebounced] = useState("");
  useEffect(() => { const t = setTimeout(() => setQDebounced(q), 200); return () => clearTimeout(t); }, [q]);
  useEffect(() => { try { localStorage.setItem("jt.view", view); } catch { /* ignore */ } }, [view]);

  const { data, loading, setData } = useApi<{ items: AppItem[]; total: number }>(`/api/applications${filterQuery({ q: qDebounced })}`);
  const items = data?.items ?? [];

  async function moveTo(app: AppItem, stage: string) {
    if (stage === app.status) return;
    // Optimistic update so the card moves immediately.
    setData((d) => d && { ...d, items: d.items.map((x) => (x.id === app.id ? { ...x, status: stage } : x)) });
    try {
      await api.post(`/api/applications/${app.id}/stages`, { stage, date: today() });
      toast(`${app.company}: moved to ${stage}`);
      refresh();
    } catch (e: any) { toast(e.message, "error"); refresh(); }
  }

  return (
    <div>
      <PageHeader title="Applications" subtitle={data ? `${items.length} of ${data.total} applications` : " "}
        actions={<Segmented value={view} onChange={setView} options={[
          { id: "board", label: <><Columns3 size={14} /> Board</> }, { id: "table", label: <><Rows3 size={14} /> Table</> }]} />} />
      <div className="flex flex-col gap-3 mb-5">
        <div className="relative max-w-md">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
          <input className="input pl-9" placeholder="Search company, role, location, notes…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <FilterBar />
      </div>
      {loading && !data ? (
        <div className="grid grid-cols-5 gap-4">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-80" />)}</div>
      ) : data && data.total === 0 ? (
        <div className="card"><EmptyState title="No applications yet" action={<SampleOrImport />}>
          Add your first one with the button on the left, import your spreadsheet in Settings, or load sample data to look around.
        </EmptyState></div>
      ) : view === "board" ? (
        <Board items={items} columns={meta?.board_columns ?? []} onMove={moveTo} onOpen={openApp} followUpAfter={meta?.settings?.follow_up_after ?? 10} />
      ) : (
        <Table items={items} stages={meta?.stages ?? []} onMove={moveTo} onOpen={openApp} />
      )}
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

function Board({ items, columns, onMove, onOpen, followUpAfter }:
  { items: AppItem[]; columns: { id: string; label: string; stages: string[]; drop_stage: string | null }[];
    onMove: (a: AppItem, stage: string) => void; onOpen: (id: number) => void; followUpAfter: number }) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const [closing, setClosing] = useState<AppItem | null>(null);
  const byId = useMemo(() => new Map(items.map((i) => [i.id, i])), [items]);

  function onDragEnd(e: DragEndEvent) {
    const app = byId.get(Number(e.active.id));
    const col = columns.find((c) => c.id === e.over?.id);
    if (!app || !col) return;
    if (COLUMN_OF[app.status] === col.id) return;
    if (col.drop_stage) onMove(app, col.drop_stage);
    else setClosing(app);
  }

  return (
    <DndContext sensors={sensors} onDragEnd={onDragEnd}>
      <div className="grid gap-3 overflow-x-auto pb-2 scroll-thin" style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(224px, 1fr))` }}>
        {columns.map((c) => (
          <Column key={c.id} col={c} items={items.filter((i) => c.stages.includes(i.status))} onOpen={onOpen} followUpAfter={followUpAfter} />
        ))}
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

function Column({ col, items, onOpen, followUpAfter }:
  { col: { id: string; label: string }; items: AppItem[]; onOpen: (id: number) => void; followUpAfter: number }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.id });
  const [sort, setSort] = useState("Newest first");
  const [limit, setLimit] = useState(25);
  const st = STAGE_STYLE[col.id];
  const sorted = [...items].sort(SORTS[sort]);
  return (
    <section ref={setNodeRef} aria-label={col.label}
      className={cls("rounded-xl border bg-[#f0f2f5]/70 flex flex-col min-h-[420px] transition-colors",
        isOver ? "border-brand bg-brand-soft/60" : "border-line")}>
      <header className="px-3 pt-3 pb-2">
        <div className="h-[3px] rounded-full mb-2.5" style={{ background: st.dot }} />
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold text-[13.5px]">
            <span className="w-2 h-2 rounded-full" style={{ background: st.dot }} />{col.label}
          </div>
          <span className="num text-[11.5px] min-w-[22px] h-[22px] px-1.5 rounded-full bg-white border border-line inline-flex items-center justify-center text-ink-soft">{items.length}</span>
        </div>
        <select aria-label={`Sort ${col.label}`} value={sort} onChange={(e) => setSort(e.target.value)}
          className="mt-2 w-full h-7 px-2 rounded-md border border-line bg-white text-[12px] text-ink-muted">
          {Object.keys(SORTS).map((s) => <option key={s}>{s}</option>)}
        </select>
      </header>
      <div className="flex-1 px-2 pb-2 space-y-2 overflow-y-auto scroll-thin max-h-[calc(100vh-290px)]">
        {sorted.slice(0, limit).map((a) => <Card key={a.id} app={a} onOpen={onOpen} followUpAfter={followUpAfter} />)}
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

function Card({ app, onOpen, followUpAfter }: { app: AppItem; onOpen: (id: number) => void; followUpAfter: number }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: app.id });
  const stale = app.active && app.days_since_activity >= followUpAfter;
  const upcoming = app.days_since_activity < 0;
  const style = transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined;
  const closedLabel = ["Rejected", "Ghosted", "Withdrawn"].includes(app.status) ? app.status : app.status === "Final interview" ? "Final round" : null;
  return (
    <article ref={setNodeRef} style={style} {...listeners} {...attributes}
      onClick={() => onOpen(app.id)}
      className={cls("bg-white rounded-lg border border-line p-3 cursor-pointer select-none transition-shadow hover:shadow-pop hover:border-line-strong",
        isDragging && "shadow-pop ring-2 ring-brand/30 z-10 relative")}>
      <div className="font-semibold text-[13.5px] leading-snug">{app.position}</div>
      <div className="text-[12.5px] text-ink-soft mt-0.5">{app.company}</div>
      <div className="text-[11.5px] text-ink-muted num mt-1.5">{fmtDate(app.date_applied)}</div>
      <div className="flex flex-wrap gap-1 mt-2">
        {closedLabel && <span className="chip h-5 text-[10.5px]">{closedLabel}</span>}
        {upcoming && <span className="chip h-5 text-[10.5px] bg-[#fdf4e6] text-[#a35f00] border-[#f5dcb1]">Next step in {-app.days_since_activity}d</span>}
        {stale && <span className="chip h-5 text-[10.5px] bg-alert-soft text-alert border-[#f6d3bd]">{app.days_since_activity}d no news</span>}
        <span className="chip h-5 text-[10.5px] max-w-full truncate">{app.role_area}</span>
        {app.location && <span className="chip h-5 text-[10.5px]"><MapPin size={10} />{app.location.length > 18 ? app.location.slice(0, 17) + "…" : app.location}</span>}
        {app.jd_match !== null && <span className="chip h-5 text-[10.5px] bg-brand-soft text-brand-strong border-brand/20">{pct(app.jd_match)} match</span>}
        {app.fit_rating ? <span className="chip h-5 text-[10.5px]"><Star size={10} fill="currentColor" className="text-[#d97f06]" />{app.fit_rating}</span> : null}
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

function Table({ items, stages, onMove, onOpen }: { items: AppItem[]; stages: string[]; onMove: (a: AppItem, s: string) => void; onOpen: (id: number) => void }) {
  const [sort, setSort] = useState<{ key: keyof AppItem; dir: 1 | -1 }>({ key: "date_applied", dir: -1 });
  const [limit, setLimit] = useState(100);
  const rows = useMemo(() => [...items].sort((a, b) => {
    const x = a[sort.key] as any, y = b[sort.key] as any;
    if (x === y) return 0;
    if (x === null || x === undefined) return 1;
    if (y === null || y === undefined) return -1;
    return (x > y ? 1 : -1) * sort.dir;
  }), [items, sort]);
  if (!items.length) return <div className="card"><EmptyState title="No applications match">Try clearing the search or filters.</EmptyState></div>;
  return (
    <div className="card overflow-hidden">
      <div className="overflow-auto max-h-[calc(100vh-260px)] scroll-thin">
        <table className="w-full text-[13px]">
          <thead className="sticky top-0 z-10 bg-white shadow-[0_1px_0_#e4e7ec]">
            <tr>
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
            {rows.slice(0, limit).map((a) => (
              <tr key={a.id} onClick={() => onOpen(a.id)} className="border-t border-line hover:bg-canvas/70 cursor-pointer">
                <td className="px-3 py-2 font-medium">{a.company}</td>
                <td className="px-3 py-2">{a.position}</td>
                <td className="px-3 py-1.5" onClick={(e) => e.stopPropagation()}>
                  <div className="relative inline-flex">
                    <StatusPill stage={a.status} />
                    <select aria-label="Change status" value={a.status} onChange={(e) => onMove(a, e.target.value)}
                      className="absolute inset-0 opacity-0 cursor-pointer">
                      {stages.map((s) => <option key={s}>{s}</option>)}
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
