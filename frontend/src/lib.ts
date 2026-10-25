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
  Applied: "applied", Screening: "screening", Interview: "interviewing", "Final interview": "interviewing",
  Offer: "offer", Accepted: "offer", Rejected: "closed", Ghosted: "closed", Withdrawn: "closed",
};

export const STAGE_STYLE: Record<string, { dot: string; text: string; bg: string; ring: string }> = {
  applied: { dot: "#3d6fd6", text: "#2a55b0", bg: "#edf2fc", ring: "#c9d7f4" },
  screening: { dot: "#7f5bd1", text: "#6442b4", bg: "#f2eefb", ring: "#dcd0f3" },
  interviewing: { dot: "#d97f06", text: "#a35f00", bg: "#fdf4e6", ring: "#f5dcb1" },
  offer: { dot: "#0e9a69", text: "#0a7a53", bg: "#e8f6f0", ring: "#bfe6d6" },
  closed: { dot: "#8f97a6", text: "#5d6676", bg: "#f2f3f5", ring: "#dde0e6" },
};

export function stageStyle(stage: string) {
  return STAGE_STYLE[COLUMN_OF[stage] ?? "closed"];
}

export const OUTCOME_COLORS: Record<string, string> = {
  Offer: "#0e9a69", Interviewed: "#d97f06", Rejected: "#b9bfca", Ghosted: "#7c8494", Withdrawn: "#dfe2e8",
  Waiting: "#3d6fd6",
};

export const CHART = {
  primary: "#0e7a5c", secondary: "#3d6fd6", tertiary: "#d97f06", muted: "#c9ced8", grid: "#eef0f3", axis: "#9aa2b1",
};
