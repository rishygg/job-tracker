// Thin client for the Python API.

export type Dict = Record<string, any>;

export interface AppItem {
  id: number;
  company: string;
  position: string;
  location: string | null;
  date_applied: string;
  date_posted: string | null;
  status: string;
  furthest_stage: string;
  role_area: string;
  region: string;
  source: string | null;
  seniority: string;
  industry: string;
  company_size: string;
  work_authorization: string;
  language: string;
  work_mode: string;
  cv_version: string | null;
  fit_rating: number | null;
  salary: string | null;
  url: string | null;
  contact: string | null;
  notes: string | null;
  days_since_applied: number;
  days_since_activity: number;
  last_activity: string;
  responded: boolean;
  positive: boolean;
  reached_interview: boolean;
  active: boolean;
  outcome: string;
  jd_match: number | null;
  has_jd: boolean;
  days_to_apply: number | null;
}

export interface Meta {
  stages: string[];
  pipeline: string[];
  closed: string[];
  sources: string[];
  board_columns: { id: string; label: string; stages: string[]; drop_stage: string | null }[];
  options: Record<string, string[]>;
  skills: string[];
  dimensions: Record<string, string>;
  metrics: Record<string, string>;
  count: number;
  cv_versions: string[];
  settings: Dict;
}

export class ApiError extends Error {}

async function request<T>(method: string, url: string, body?: unknown, isForm = false): Promise<T> {
  const init: RequestInit = { method, headers: {} };
  if (body !== undefined) {
    if (isForm) init.body = body as FormData;
    else {
      init.body = JSON.stringify(body);
      (init.headers as Dict)["Content-Type"] = "application/json";
    }
  }
  const res = await fetch(url, init);
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail)) msg = j.detail.map((d: Dict) => d.msg).join("; ");
    } catch { /* not JSON */ }
    throw new ApiError(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T = any>(url: string) => request<T>("GET", url),
  post: <T = any>(url: string, body?: unknown) => request<T>("POST", url, body ?? {}),
  patch: <T = any>(url: string, body: unknown) => request<T>("PATCH", url, body),
  put: <T = any>(url: string, body: unknown) => request<T>("PUT", url, body),
  del: <T = any>(url: string) => request<T>("DELETE", url),
  form: <T = any>(url: string, form: FormData) => request<T>("POST", url, form, true),
};

export function qs(params: Dict): string {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "" || (Array.isArray(v) && v.length === 0)) return;
    p.set(k, Array.isArray(v) ? v.join("|") : String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : "";
}
