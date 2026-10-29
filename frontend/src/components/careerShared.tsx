import { type Dict } from "../api";
import { useApi } from "../store";
import { cls, tok } from "../lib";

export const CAT_COLOR: Record<string, string> = {
  Motivation: tok("info-bright"), "Experience & CV": tok("brand"), Behavioural: tok("violet-bright"), Situational: tok("warn"),
  Technical: tok("info"), "Case & problem-solving": tok("danger"), "Career goals": tok("ok"), "Company & industry": tok("violet"),
  Logistics: tok("ink-muted"), Other: tok("ink-faint"),
};

export function CategoryChip({ category }: { category?: string | null }) {
  if (!category) return null;
  const c = CAT_COLOR[category] ?? tok("ink-faint");
  return <span className="chip h-5 text-[10.5px] bg-surface" style={{ color: c, borderColor: `color-mix(in srgb, ${c} 30%, transparent)` }}>{category}</span>;
}

/** 1-5 rating as numbered buttons (readable without colour). */
export function Rating({ value, onChange, label }: { value?: number | null; onChange: (v: number | null) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" role="radio" aria-checked={value === n} title={["Poor", "Weak", "OK", "Good", "Strong"][n - 1]}
          onClick={() => onChange(value === n ? null : n)}
          className={cls("w-7 h-7 rounded-md border text-[12px] font-semibold num transition",
            value && n <= value ? "bg-brand text-white border-brand" : "bg-surface text-ink-muted border-line hover:border-line-strong")}>{n}</button>
      ))}
    </div>
  );
}

export function useCareerMeta() {
  return useApi<Dict>("/api/career/meta").data;
}

