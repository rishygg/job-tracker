// Formatting helpers and stage styling.

export const today = () => new Date().toISOString().slice(0, 10);

export function fmtDate(iso?: string | null, withYear = true): string {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", ...(withYear ? { year: "numeric" } : {}) });
}

export function relDays(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00").getTime();
  const t = new Date(today() + "T00:00:00").getTime();
  const n = Math.round((d - t) / 86400000);
  if (n === 0) return "today";
  if (n === 1) return "tomorrow";
  if (n === -1) return "yesterday";
  return n > 0 ? `in ${n} days` : `${-n} days ago`;
}

export const pct = (v?: number | null, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : `${(v * 100).toFixed(digits)}%`;

export function cls(...xs: (string | false | null | undefined)[]) {
  return xs.filter(Boolean).join(" ");
}

// Stage -> board column + colours. Palette chosen to stay distinguishable with colour-blindness
// (blue / purple / orange / green / grey), and paired with labels everywhere.
export const COLUMN_OF: Record<string, string> = {
  Saved: "saved", Applied: "applied", Screening: "screening", Interview: "interviewing", "Final interview": "interviewing",
  Offer: "offer", Accepted: "offer", Rejected: "closed", Ghosted: "closed", Withdrawn: "closed",
};

const stage = (key: string, dot: string) => ({
  dot, text: `var(--stage-${key}-text)`, bg: `var(--stage-${key}-bg)`, ring: `var(--stage-${key}-ring)`,
});
export const STAGE_STYLE: Record<string, { dot: string; text: string; bg: string; ring: string }> = {
  saved: stage("saved", "#3a9ea5"),
  applied: stage("applied", "#3d6fd6"),
  screening: stage("screening", "#7f5bd1"),
  interviewing: stage("interview", "#d97f06"),
  offer: stage("offer", "#0e9a69"),
  closed: stage("closed", "#8f97a6"),
};

/** A theme token for inline styles, e.g. tok("danger") -> "rgb(var(--danger))". */
export const tok = (name: string, alpha?: number) => alpha === undefined ? `rgb(var(--${name}))` : `rgb(var(--${name}) / ${alpha})`;

/** The resolved colour of a token, for SVG attributes (charts) that can't read CSS variables. */
export function cssVar(name: string): string {
  if (typeof window === "undefined") return "#888";
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
  return v ? `rgb(${v.split(/\s+/).join(",")})` : "#888";
}

export function stageStyle(stage: string) {
  return STAGE_STYLE[COLUMN_OF[stage] ?? "closed"];
}

export const OUTCOME_COLORS: Record<string, string> = {
  Offer: "#0e9a69", Interviewed: "#d97f06", Rejected: "#a9b0bd", Ghosted: "#6f7888", Withdrawn: "#c9ced8",
  Waiting: "#3d6fd6",
};

export const CHART = {
  get primary() { return cssVar("brand"); },
  secondary: "#3d6fd6", tertiary: "#d97f06",
  get muted() { return cssVar("line-strong"); },
  get grid() { return cssVar("line"); },
  get axis() { return cssVar("ink-faint"); },
  get surface() { return cssVar("surface"); },
  get ink() { return cssVar("ink"); },
};
