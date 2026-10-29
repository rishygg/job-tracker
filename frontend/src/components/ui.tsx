import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check, ChevronDown, X } from "lucide-react";
import { cls, stageStyle } from "../lib";

export function StatusPill({ stage, size = "md" }: { stage: string; size?: "sm" | "md" }) {
  const s = stageStyle(stage);
  return (
    <span className={cls("inline-flex items-center gap-1.5 rounded-full font-medium whitespace-nowrap",
      size === "sm" ? "h-5 px-2 text-[11px]" : "h-6 px-2.5 text-[12px]")}
      style={{ background: s.bg, color: s.text, boxShadow: `inset 0 0 0 1px ${s.ring}` }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.dot }} />
      {stage}
    </span>
  );
}

export function Modal({ open, onClose, title, children, width = "max-w-3xl", footer }:
  { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; width?: string; footer?: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center p-4 sm:p-8 overflow-y-auto bg-ink/30 backdrop-blur-[1px]"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" className={cls("anim-in card w-full shadow-pop", width)}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-line">
          <h2 className="text-[16px] font-semibold">{title}</h2>
          <button className="btn-ghost btn-sm" onClick={onClose} aria-label="Close"><X size={16} /></button>
        </div>
        <div className="p-5">{children}</div>
        {footer && <div className="px-5 py-3.5 border-t border-line flex justify-end gap-2 bg-canvas/60 rounded-b-xl">{footer}</div>}
      </div>
    </div>
  );
}

export function Drawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink/20" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="anim-slide h-full w-full max-w-[760px] bg-surface shadow-pop flex flex-col">{children}</aside>
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }:
  { tabs: { id: T; label: ReactNode }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="flex gap-1 border-b border-line overflow-x-auto overflow-y-hidden" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={cls("px-3 py-2.5 text-[13px] font-medium -mb-px border-b-2 transition-colors whitespace-nowrap shrink-0",
            value === t.id ? "border-brand text-ink" : "border-transparent text-ink-muted hover:text-ink")}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Segmented<T extends string>({ options, value, onChange }:
  { options: { id: T; label: ReactNode }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex p-0.5 rounded-lg bg-canvas border border-line">
      {options.map((o) => (
        <button key={o.id} onClick={() => onChange(o.id)}
          className={cls("h-7 px-3 rounded-md text-[12.5px] font-medium inline-flex items-center gap-1.5 transition",
            value === o.id ? "bg-surface text-ink shadow-card" : "text-ink-muted hover:text-ink")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function useOutside(ref: React.RefObject<HTMLElement>, onOut: () => void, active: boolean) {
  useEffect(() => {
    if (!active) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onOut(); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [active, onOut, ref]);
}

export function MultiSelect({ label, options, value, onChange }:
  { label: string; options: string[]; value: string[]; onChange: (v: string[]) => void }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  useOutside(ref, () => setOpen(false), open);
  const shown = options.filter((o) => o.toLowerCase().includes(q.toLowerCase()));
  const toggle = (o: string) => onChange(value.includes(o) ? value.filter((x) => x !== o) : [...value, o]);
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)}
        className={cls("h-8 px-3 rounded-lg border text-[12.5px] font-medium inline-flex items-center gap-1.5 transition",
          value.length ? "border-brand/40 bg-brand-soft text-brand-strong" : "border-line bg-surface text-ink-soft hover:bg-canvas")}>
        {label}{value.length > 0 && <span className="num text-[11px] px-1.5 rounded bg-surface/70">{value.length}</span>}
        <ChevronDown size={14} className="opacity-60" />
      </button>
      {open && (
        <div className="anim-in absolute z-30 mt-1.5 w-72 card shadow-pop p-1.5">
          {options.length > 8 && (
            <input autoFocus className="input h-8 mb-1.5" placeholder={`Search ${label.toLowerCase()}…`} value={q}
              onChange={(e) => setQ(e.target.value)} />
          )}
          <div className="max-h-72 overflow-y-auto scroll-thin">
            {shown.map((o) => (
              <button key={o} onClick={() => toggle(o)}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-left text-[13px] hover:bg-canvas">
                <span className={cls("w-4 h-4 rounded border flex items-center justify-center shrink-0",
                  value.includes(o) ? "bg-brand border-brand text-white" : "border-line-strong")}>
                  {value.includes(o) && <Check size={12} strokeWidth={3} />}
                </span>
                <span className="truncate">{o}</span>
              </button>
            ))}
            {!shown.length && <div className="px-2 py-3 text-ink-muted text-[12.5px]">No matches</div>}
          </div>
          {value.length > 0 && (
            <button className="w-full mt-1 pt-1.5 border-t border-line text-[12px] text-ink-muted hover:text-ink py-1"
              onClick={() => onChange([])}>Clear</button>
          )}
        </div>
      )}
    </div>
  );
}

export function Field({ label, children, hint, className }: { label: string; children: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <label className={cls("block", className)}>
      <span className="label">{label}</span>
      {children}
      {hint && <span className="block text-[11.5px] text-ink-muted mt-1">{hint}</span>}
    </label>
  );
}

export function Select({ value, onChange, options, placeholder, className }:
  { value: string; onChange: (v: string) => void; options: (string | { value: string; label: string })[]; placeholder?: string; className?: string }) {
  return (
    <select className={cls("input pr-8 appearance-none bg-no-repeat bg-[right_0.6rem_center] bg-[length:14px]", className)}
      style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236a7385' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E\")" }}
      value={value} onChange={(e) => onChange(e.target.value)}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => typeof o === "string"
        ? <option key={o} value={o}>{o}</option>
        : <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export type Art = "inbox" | "chat" | "book" | "chart" | "compass" | "spark" | "target" | "notes";

export function EmptyState({ icon, title, children, action, art }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode; art?: Art }) {
  return (
    <div className="flex flex-col items-center text-center py-10 px-6">
      {art ? <Illustration art={art} className="mb-3" />
        : icon && <div className="w-11 h-11 rounded-xl bg-canvas border border-line flex items-center justify-center text-ink-muted mb-3">{icon}</div>}
      <div className="font-semibold text-[14.5px]">{title}</div>
      {children && <div className="text-ink-muted text-[13px] mt-1 max-w-md">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cls("animate-pulse rounded-md bg-line/70", className)} />;
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
      <div>
        <h1 className="text-[24px] font-semibold tracking-[-0.01em]">{title}</h1>
        {subtitle && <p className="text-ink-muted mt-0.5">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
      <h2 className="text-[15px] font-semibold min-w-0">{children}</h2>
      {aside}
    </div>
  );
}

/** Simple line illustrations for empty states. They use theme colours, so they work in dark mode too. */
export function Illustration({ art, className }: { art: Art; className?: string }) {
  const L = "rgb(var(--line-strong))", S = "rgb(var(--surface))", B = "rgb(var(--brand))", BS = "rgb(var(--brand-soft))", A = "#d97f06";
  const common = { fill: S, stroke: L, strokeWidth: 1.5 };
  const pieces: Record<Art, ReactNode> = {
    inbox: <>
      <rect x="22" y="22" width="76" height="46" rx="8" {...common} transform="rotate(-6 60 45)" />
      <rect x="22" y="18" width="76" height="46" rx="8" {...common} />
      <rect x="32" y="29" width="34" height="5" rx="2.5" fill={L} /><rect x="32" y="39" width="52" height="4" rx="2" fill={L} opacity=".6" />
      <circle cx="90" cy="60" r="11" fill={B} /><path d="M85 60l3.5 3.5L95 57" stroke="#fff" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </>,
    chat: <>
      <path d="M18 22h54a8 8 0 018 8v20a8 8 0 01-8 8H38l-12 9v-9h-8a8 8 0 01-8-8V30a8 8 0 018-8z" {...common} />
      <path d="M58 34h40a8 8 0 018 8v16a8 8 0 01-8 8h-6v8l-10-8H58a8 8 0 01-8-8V42a8 8 0 018-8z" fill={BS} stroke={B} strokeWidth="1.5" />
      <circle cx="68" cy="50" r="2.5" fill={B} /><circle cx="78" cy="50" r="2.5" fill={B} /><circle cx="88" cy="50" r="2.5" fill={B} />
    </>,
    book: <>
      <path d="M60 24c-10-6-26-6-38-2v46c12-4 28-4 38 2" {...common} /><path d="M60 24c10-6 26-6 38-2v46c-12-4-28-4-38 2z" {...common} />
      <path d="M60 24v46" stroke={L} strokeWidth="1.5" />
      <path d="M68 34h20M68 42h22M68 50h14" stroke={B} strokeWidth="2" strokeLinecap="round" /><path d="M30 34h20M30 42h18" stroke={L} strokeWidth="2" strokeLinecap="round" />
    </>,
    chart: <>
      <rect x="14" y="14" width="92" height="60" rx="8" {...common} />
      <rect x="26" y="48" width="10" height="16" rx="2" fill={L} /><rect x="42" y="40" width="10" height="24" rx="2" fill={L} />
      <rect x="58" y="44" width="10" height="20" rx="2" fill={L} /><rect x="74" y="30" width="10" height="34" rx="2" fill={B} />
      <path d="M26 40l20-10 16 6 24-14" stroke={A} strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </>,
    compass: <>
      <circle cx="60" cy="44" r="30" {...common} /><circle cx="60" cy="44" r="22" fill="none" stroke={L} strokeDasharray="2 4" />
      <path d="M60 24l7 20-7 20-7-20z" fill={BS} stroke={B} strokeWidth="1.5" strokeLinejoin="round" /><path d="M60 24l7 20h-14z" fill={B} />
    </>,
    spark: <>
      <path d="M60 14l6 18 18 6-18 6-6 18-6-18-18-6 18-6z" fill={BS} stroke={B} strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M92 50l3 8 8 3-8 3-3 8-3-8-8-3 8-3z" fill={A} opacity=".85" /><path d="M28 54l2.5 6 6 2.5-6 2.5-2.5 6-2.5-6-6-2.5 6-2.5z" fill={L} />
    </>,
    target: <>
      <circle cx="56" cy="46" r="28" {...common} /><circle cx="56" cy="46" r="18" fill={S} stroke={L} strokeWidth="1.5" />
      <circle cx="56" cy="46" r="8" fill={BS} stroke={B} strokeWidth="1.5" />
      <path d="M58 44l30-24" stroke={A} strokeWidth="2.2" strokeLinecap="round" /><path d="M82 16l8 2-2 8" stroke={A} strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </>,
    notes: <>
      <rect x="30" y="14" width="56" height="64" rx="6" {...common} transform="rotate(4 58 46)" />
      <rect x="26" y="12" width="56" height="64" rx="6" {...common} />
      <path d="M36 28h30M36 37h36M36 46h24" stroke={L} strokeWidth="2" strokeLinecap="round" />
      <path d="M78 52l14-14 6 6-14 14-8 2z" fill={BS} stroke={B} strokeWidth="1.5" strokeLinejoin="round" />
    </>,
  };
  return <svg viewBox="0 0 120 88" width="120" height="88" aria-hidden="true" className={className}>{pieces[art]}</svg>;
}

const SUFFIX = /\b(ag|sa|gmbh|ltd|limited|inc|llc|plc|bv|nv|se|co|corp|corporation|group|holding|the|and|&|of)\b\.?/gi;

export function initials(name: string): string {
  const words = (name || "?").replace(SUFFIX, " ").replace(/[^\p{L}\p{N} ]/gu, " ").split(/\s+/).filter(Boolean);
  if (!words.length) return (name || "?").slice(0, 2).toUpperCase();
  return (words.length === 1 ? words[0].slice(0, 2) : words[0][0] + words[1][0]).toUpperCase();
}

function hue(name: string): number {
  let h = 0;
  for (const c of (name || "").toLowerCase()) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return [205, 255, 165, 30, 340, 190, 120, 280, 10, 225, 60, 300][h % 12];
}

/** Coloured initials for a company. Generated locally: nothing is fetched. */
export function Monogram({ name, size = 32, className }: { name: string; size?: number; className?: string }) {
  return (
    <span aria-hidden="true" className={cls("monogram inline-flex items-center justify-center rounded-lg font-semibold shrink-0 select-none", className)}
      style={{ ["--h" as string]: hue(name), width: size, height: size, fontSize: Math.round(size * 0.38), letterSpacing: "-0.02em" }}>
      {initials(name)}
    </span>
  );
}
