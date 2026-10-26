import { type Dict } from "../api";
import { useApi } from "../store";
import { cls } from "../lib";

export const CAT_COLOR: Record<string, string> = {
  Motivation: "#3d6fd6", "Experience & CV": "#0e7a5c", Behavioural: "#7f5bd1", Situational: "#a35f00", Technical: "#2a55b0",
  "Case & problem-solving": "#b42318", "Career goals": "#0a7a53", "Company & industry": "#6442b4", Logistics: "#5d6676", Other: "#8f97a6",
};

export function CategoryChip({ category }: { category?: string | null }) {
  if (!category) return null;
  const c = CAT_COLOR[category] ?? "#8f97a6";
  return <span className="chip h-5 text-[10.5px] bg-white" style={{ color: c, borderColor: `${c}40` }}>{category}</span>;
}

/** 1-5 rating as numbered buttons (readable without colour). */
export function Rating({ value, onChange, label }: { value?: number | null; onChange: (v: number | null) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" role="radio" aria-checked={value === n} title={["Poor", "Weak", "OK", "Good", "Strong"][n - 1]}
          onClick={() => onChange(value === n ? null : n)}
          className={cls("w-7 h-7 rounded-md border text-[12px] font-semibold num transition",
            value && n <= value ? "bg-brand text-white border-brand" : "bg-white text-ink-muted border-line hover:border-line-strong")}>{n}</button>
      ))}
    </div>
  );
}

export function useCareerMeta() {
  return useApi<Dict>("/api/career/meta").data;
}

