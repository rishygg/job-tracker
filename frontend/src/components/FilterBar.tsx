import { RotateCcw } from "lucide-react";
import { EMPTY_FILTERS, useApp } from "../store";
import { MultiSelect } from "./ui";
import { cls } from "../lib";

/** The same filters drive the application list, the overview insights and every chart. */
export function FilterBar({ extra }: { extra?: React.ReactNode }) {
  const { meta, filters, setFilters, activeFilterCount } = useApp();
  if (!meta) return null;
  const o = meta.options;
  const set = (k: keyof typeof filters) => (v: string[] | string) => setFilters({ ...filters, [k]: v });
  return (
    <div className="flex flex-wrap items-center gap-2">
      <MultiSelect label="Job family" options={o.role_area} value={filters.role_area} onChange={set("role_area")} />
      <MultiSelect label="Industry" options={o.industry} value={filters.industry} onChange={set("industry")} />
      <MultiSelect label="Seniority" options={o.seniority} value={filters.seniority} onChange={set("seniority")} />
      <MultiSelect label="Location" options={o.region} value={filters.region} onChange={set("region")} />
      <MultiSelect label="Channel" options={o.source} value={filters.source} onChange={set("source")} />
      <MultiSelect label="Status now" options={meta.stages} value={filters.status ?? []} onChange={set("status")} />
      <label className={cls("flex items-center gap-1.5 h-8 pl-2.5 pr-1 rounded-lg border text-[12.5px]", filters.reached ? "border-brand/40 bg-brand-soft text-brand-strong" : "border-line bg-surface text-ink-soft")}>
        <span className={filters.reached ? "" : "text-ink-muted"}>Reached</span>
        <select aria-label="Reached at least this stage" value={filters.reached ?? ""} onChange={(e) => set("reached")(e.target.value)}
          className="bg-transparent outline-none text-[12.5px] pr-1">
          <option value="">any stage</option>
          <option value="Screening">screening or later</option>
          <option value="Interview">an interview or later</option>
          <option value="Final interview">a final round or later</option>
          <option value="Offer">an offer</option>
        </select>
      </label>
      <div className="flex items-center gap-1 h-8 px-2 rounded-lg border border-line bg-surface text-[12.5px] text-ink-soft">
        <span className="text-ink-muted">Applied</span>
        <input type="date" aria-label="Applied from" value={filters.date_from}
          onChange={(e) => set("date_from")(e.target.value)} className="bg-transparent outline-none num text-[12px] w-[112px]" />
        <span className="text-ink-faint">–</span>
        <input type="date" aria-label="Applied until" value={filters.date_to}
          onChange={(e) => set("date_to")(e.target.value)} className="bg-transparent outline-none num text-[12px] w-[112px]" />
      </div>
      {activeFilterCount > 0 && (
        <button className="btn-ghost btn-sm" onClick={() => setFilters(EMPTY_FILTERS)}>
          <RotateCcw size={13} /> Reset filters
        </button>
      )}
      {extra && <div className="ml-auto flex items-center gap-2">{extra}</div>}
    </div>
  );
}
