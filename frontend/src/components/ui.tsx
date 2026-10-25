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
      <aside className="anim-slide h-full w-full max-w-[760px] bg-white shadow-pop flex flex-col">{children}</aside>
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }:
  { tabs: { id: T; label: ReactNode }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="flex gap-1 border-b border-line" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={cls("px-3 py-2.5 text-[13px] font-medium -mb-px border-b-2 transition-colors",
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
            value === o.id ? "bg-white text-ink shadow-card" : "text-ink-muted hover:text-ink")}>
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
          value.length ? "border-brand/40 bg-brand-soft text-brand-strong" : "border-line bg-white text-ink-soft hover:bg-canvas")}>
        {label}{value.length > 0 && <span className="num text-[11px] px-1.5 rounded bg-white/70">{value.length}</span>}
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

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center text-center py-10 px-6">
      {icon && <div className="w-11 h-11 rounded-xl bg-canvas border border-line flex items-center justify-center text-ink-muted mb-3">{icon}</div>}
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
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-[15px] font-semibold">{children}</h2>
      {aside}
    </div>
  );
}
