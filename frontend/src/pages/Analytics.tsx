import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Info } from "lucide-react";
import { type Dict } from "../api";
import { useApi, useApp } from "../store";
import { CHART, cls, OUTCOME_COLORS, pct } from "../lib";

const TOOLTIP = { borderRadius: 8, border: "1px solid rgb(var(--line))", background: "rgb(var(--surface))", color: "rgb(var(--ink))", fontSize: 12 };
import { FilterBar } from "../components/FilterBar";
import { EmptyState, PageHeader, SectionTitle, Select, Skeleton, Tabs } from "../components/ui";
import { Companies } from "../components/Companies";
import { MapView } from "../components/MapView";
import { useSearchParams } from "react-router-dom";
import { BarChart3, Building2, Map as MapIcon } from "lucide-react";

const VERDICT: Record<string, { color: string; bg: string }> = {
  Strength: { color: "rgb(var(--ok))", bg: "rgb(var(--ok-soft))" }, Promising: { color: "rgb(var(--ok))", bg: "rgb(var(--ok-soft) / .55)" },
  "About average": { color: "rgb(var(--ink-muted))", bg: "rgb(var(--neutral-soft))" }, "Below average": { color: "rgb(var(--warn))", bg: "rgb(var(--warn-soft))" },
  "Weak spot": { color: "rgb(var(--danger))", bg: "rgb(var(--danger-soft))" }, "Too few to tell": { color: "rgb(var(--ink-faint))", bg: "rgb(var(--canvas))" },
};
export default function Analytics() {
  const { filterQuery, meta } = useApp();
  const [metric, setMetric] = useState("positive");
  const [dim, setDim] = useState("role_area");
  const { data, loading } = useApi<Dict>(`/api/analytics${filterQuery({ metric, dim })}`);
  const dims = meta?.dimensions ?? {};
  const metrics = meta?.metrics ?? {};
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as "overview" | "companies" | "map") || "overview";

  return (
    <div>
      <PageHeader title="Analytics" subtitle="How your applications convert, and which kinds of roles work best for you." />
      <div className="mb-4"><FilterBar /></div>
      <div className="mb-6"><Tabs value={tab} onChange={(t) => setParams(t === "overview" ? {} : { tab: t }, { replace: true })} tabs={[
        { id: "overview", label: <span className="inline-flex items-center gap-1.5"><BarChart3 size={14} />Conversion & roles</span> },
        { id: "companies", label: <span className="inline-flex items-center gap-1.5"><Building2 size={14} />Companies</span> },
        { id: "map", label: <span className="inline-flex items-center gap-1.5"><MapIcon size={14} />Map</span> }]} /></div>
      {tab === "companies" ? <Companies /> : tab === "map" ? <MapView /> : loading && !data ? <div className="grid grid-cols-3 gap-4">{[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-32" />)}</div>
        : !data || data.empty ? <div className="card"><EmptyState art="chart" title="No applications match these filters">Clear some filters to see your analytics.</EmptyState></div>
        : (
          <div className="space-y-8">
            <Conversion c={data.conversion} />
            <Funnel funnel={data.funnel} />
            <Scorecard data={data} metric={metric} setMetric={setMetric} metrics={metrics} dim={dim} setDim={setDim} dims={dims} />
            <Trends data={data} />
            <Coverage coverage={data.coverage} />
          </div>
        )}
    </div>
  );
}

// ------------------------------------------------------------ conversion
function Conversion({ c }: { c: Dict }) {
  const tiles: { key: string; label: string; help: string }[] = [
    { key: "application_to_response", label: "Application → response", help: "Are employers replying at all (including rejections)?" },
    { key: "application_to_interview", label: "Application → first interview", help: "Which share of applications earns an interview." },
    { key: "interview_to_later_round", label: "First interview → later round", help: "Do you get past the first conversation?" },
    { key: "interview_to_offer", label: "Interview → offer", help: "How often interviews turn into offers." },
    { key: "application_to_offer", label: "Application → offer", help: "End-to-end success rate." },
  ];
  return (
    <section>
      <SectionTitle aside={<span className="text-[12px] text-ink-muted">{c.excluded_recent > 0 && `${c.excluded_recent} recent applications without a reply left out`}</span>}>Conversion</SectionTitle>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
        {tiles.map((t) => {
          const r = c[t.key];
          return (
            <div key={t.key} className="card p-4 flex flex-col">
              <div className="text-[12px] font-medium text-ink-muted leading-snug min-h-[32px]">{t.label}</div>
              <div className="num text-[28px] font-semibold tracking-tight mt-1">{r.denominator ? pct(r.rate, r.rate < 0.1 ? 1 : 0) : "—"}</div>
              <div className="text-[12px] text-ink-soft num">{r.numerator} of {r.denominator}</div>
              {r.denominator > 0 && <RangeBar low={r.ci_low} high={r.ci_high} value={r.rate} />}
              <div className="text-[11.5px] text-ink-muted mt-auto pt-2 leading-snug">{r.denominator ? t.help : "Not enough data yet."}</div>
            </div>
          );
        })}
        <div className="card p-4 flex flex-col">
          <div className="text-[12px] font-medium text-ink-muted leading-snug min-h-[32px]">Median time to response</div>
          <div className="num text-[28px] font-semibold tracking-tight mt-1">{c.median_days_to_response !== null ? `${Math.round(c.median_days_to_response)}d` : "—"}</div>
          <div className="text-[12px] text-ink-soft num">{c.response_time_samples} dated replies</div>
          <div className="text-[11.5px] text-ink-muted mt-auto pt-2 leading-snug">
            {c.response_time_samples < 5 ? "Record replies with their date to measure this; imported history has no reply dates." : "How quickly employers tend to respond."}
          </div>
        </div>
      </div>
    </section>
  );
}

function RangeBar({ low, high, value }: { low: number; high: number; value: number }) {
  return (
    <div className="mt-2" title={`95% range ${pct(low)}–${pct(high)}`}>
      <div className="relative h-1.5 rounded-full bg-canvas">
        <div className="absolute h-full rounded-full bg-brand/25" style={{ left: `${low * 100}%`, width: `${Math.max(1, (high - low) * 100)}%` }} />
        <div className="absolute w-1.5 h-1.5 rounded-full bg-brand" style={{ left: `calc(${value * 100}% - 3px)` }} />
      </div>
      <div className="text-[10.5px] text-ink-faint num mt-0.5">95% range {pct(low)}–{pct(high)}</div>
    </div>
  );
}

// ------------------------------------------------------------------ funnel
function Funnel({ funnel }: { funnel: Dict[] }) {
  const max = funnel[0]?.count || 1;
  const steps = funnel.slice(1).filter((f) => f.from_previous !== null);
  const worst = steps.length ? steps.reduce((a, b) => (b.from_previous < a.from_previous ? b : a)) : null;
  return (
    <section className="card p-5">
      <SectionTitle>Funnel</SectionTitle>
      <div className="space-y-2.5">
        {funnel.map((f, i) => (
          <div key={f.step} className="grid grid-cols-[130px_1fr_92px] items-center gap-3">
            <div className="text-[12.5px] text-ink-soft truncate">{f.step}</div>
            <div className="h-7 rounded-md bg-canvas relative overflow-hidden">
              <div className="h-full rounded-md" style={{ width: `${Math.max(0.5, (f.count / max) * 100)}%`, background: worst?.step === f.step ? "#d97f06" : i === 0 ? "#3d6fd6" : "#0e7a5c", opacity: 1 - i * 0.08 }} />
              <span className="absolute inset-y-0 left-2 flex items-center num text-[12px] font-semibold text-white mix-blend-normal" style={{ textShadow: "0 0 3px rgba(0,0,0,.25)" }}>{f.count}</span>
            </div>
            <div className="text-right text-[12px] num text-ink-muted">{i === 0 ? "100%" : pct(f.of_applied, f.of_applied < 0.1 ? 1 : 0)}
              {i > 0 && f.from_previous !== null && <div className="text-[10.5px]">{pct(f.from_previous)} of prev.</div>}
            </div>
          </div>
        ))}
      </div>
      {worst && <p className="text-[12.5px] text-ink-soft mt-4"><b>Biggest drop-off:</b> only {pct(worst.from_previous)} make it to "{worst.step}". That's the step to work on.</p>}
    </section>
  );
}

// ---------------------------------------------------------------- scorecard
function Scorecard({ data, metric, setMetric, metrics, dim, setDim, dims }: Dict) {
  const [allBars, setAllBars] = useState(false);
  const scAll: Dict[] = data.scorecard ?? [];
  const sc: Dict[] = allBars ? scAll : [...scAll].sort((a, b) => b.applied - a.applied).slice(0, 15).sort((a, b) => b.smoothed - a.smoothed);
  const avg = data.average ?? 0;
  const maxHigh = Math.max(...sc.map((s) => s.ci_high), avg, 0.05);
  const segLine = (r: Dict) => (
    <li key={`${r.dimension}-${r.value}`} className="flex items-center gap-2 py-1.5">
      <span className="text-[11px] font-medium px-1.5 py-0.5 rounded shrink-0 whitespace-nowrap" style={{ color: VERDICT[r.verdict]?.color, background: VERDICT[r.verdict]?.bg }}>{r.verdict}</span>
      <span className="text-[13px] min-w-0 truncate"><span className="text-ink-muted">{r.dimension_label}:</span> <b className="font-medium">{r.value}</b></span>
      <span className="ml-auto num text-[12px] text-ink-muted whitespace-nowrap">{r.successes}/{r.applied} · {r.lift >= 0 ? "+" : ""}{Math.round(r.lift * 100)}%</span>
    </li>
  );
  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-[15px] font-semibold">What works for you</h2>
          <p className="text-[12.5px] text-ink-muted max-w-2xl">Your success rate by job family, seniority, industry, location and more. Pick what counts as success; small groups are pulled towards your average so a lucky 1-of-2 doesn't outrank 5-of-30.</p>
        </div>
        <label className="flex flex-wrap items-center gap-2 text-[12.5px] text-ink-muted w-full sm:w-auto">Count as success
          <Select className="h-8 w-full sm:w-[290px] text-[12.5px]" value={metric} onChange={setMetric}
            options={Object.entries(metrics).map(([label, value]) => ({ value: value as string, label }))} />
        </label>
      </div>
      <div className="grid sm:grid-cols-3 gap-3 mb-5">
        <div className="rounded-lg bg-canvas p-3"><div className="text-[12px] text-ink-muted">Applications judged</div><div className="num text-[20px] font-semibold">{data.judged}</div></div>
        <div className="rounded-lg bg-canvas p-3"><div className="text-[12px] text-ink-muted">Successes</div><div className="num text-[20px] font-semibold">{data.successes}</div></div>
        <div className="rounded-lg bg-canvas p-3"><div className="text-[12px] text-ink-muted">Your average</div><div className="num text-[20px] font-semibold">{pct(avg, 1)}</div></div>
      </div>
      {data.successes < 10 && (
        <div className="flex gap-2 p-3 rounded-lg bg-warn-soft text-warn-strong text-[12.5px] mb-5">
          <Info size={15} className="shrink-0 mt-0.5" />
          Only {data.successes} successes so far, so differences are hints rather than proof. Try "Any reply" for a bigger sample.
        </div>
      )}
      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <div className="min-w-0"><div className="eyebrow mb-1">Where you do best</div><ul className="divide-y divide-line">{data.strengths.length ? data.strengths.map(segLine) : <li className="text-ink-muted text-[13px] py-2">Nothing stands out yet.</li>}</ul></div>
        <div className="min-w-0"><div className="eyebrow mb-1">Where you struggle</div><ul className="divide-y divide-line">{data.gaps.length ? data.gaps.map(segLine) : <li className="text-ink-muted text-[13px] py-2">Nothing stands out yet.</li>}</ul></div>
      </div>

      <div className="flex flex-wrap gap-1.5 mb-4">
        {Object.entries(dims).map(([k, label]) => (
          <button key={k} onClick={() => setDim(k)}
            className={cls("h-7 px-2.5 rounded-full text-[12px] font-medium border transition", dim === k ? "bg-ink text-white border-ink" : "bg-surface border-line text-ink-soft hover:bg-canvas")}>{label as string}</button>
        ))}
      </div>
      <div className="space-y-1.5">
        {sc.map((s) => {
          const v = VERDICT[s.verdict] ?? VERDICT["About average"];
          return (
            <div key={s.value} className="grid grid-cols-[minmax(120px,240px)_1fr_190px] items-center gap-3">
              <div className="text-[12.5px] truncate" title={s.value}>{s.value}</div>
              <div className="relative h-6">
                <div className="absolute inset-y-[7px] left-0 right-0 rounded-full bg-canvas" />
                <div className="absolute inset-y-[7px] left-0 rounded-full" style={{ width: `${(s.rate / maxHigh) * 100}%`, background: v.color, opacity: s.applied < 5 ? 0.35 : 0.85 }} />
                <div className="absolute top-[11px] h-[2px] bg-ink/30" style={{ left: `${(s.ci_low / maxHigh) * 100}%`, width: `${((s.ci_high - s.ci_low) / maxHigh) * 100}%` }} />
                <div className="absolute top-0 bottom-0 w-px bg-brand" style={{ left: `${(avg / maxHigh) * 100}%` }} />
              </div>
              <div className="flex items-center justify-end gap-2 text-[12px]">
                <span className="num text-ink-soft" title={`${s.successes} of ${s.applied}`}>{s.successes}/{s.applied} · {pct(s.rate)}</span>
                <span className="text-[10.5px] font-medium px-1.5 py-0.5 rounded whitespace-nowrap" style={{ color: v.color, background: v.bg }}>{s.verdict}</span>
              </div>
            </div>
          );
        })}
      </div>
      {scAll.length > 15 && <button className="btn-ghost btn-sm mt-2" onClick={() => setAllBars(!allBars)}>{allBars ? "Show the 15 largest groups" : `Show all ${scAll.length} groups`}</button>}
      <div className="flex items-center gap-4 text-[11.5px] text-ink-muted mt-3">
        <span className="inline-flex items-center gap-1.5"><span className="w-3 h-px bg-brand" /> your average</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-4 h-[2px] bg-ink/30" /> 95% range</span>
        <span>Faded bars: fewer than 5 applications</span>
      </div>

    </section>
  );
}

// -------------------------------------------------------------------- trends
function Trends({ data }: { data: Dict }) {
  const outcomes = ["Offer", "Interviewed", "Rejected", "Ghosted", "Withdrawn", "Waiting"].filter((o) => data.monthly.some((m: Dict) => m[o]));
  return (
    <div className="grid xl:grid-cols-[2fr_1fr] gap-5">
      <section className="card p-5">
        <SectionTitle>Applications per month by outcome</SectionTitle>
        <div className="h-[260px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.monthly} margin={{ left: -18, right: 8, top: 4 }}>
              <CartesianGrid stroke={CHART.grid} vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: CHART.axis }} tickLine={false} axisLine={{ stroke: CHART.grid }}
                tickFormatter={(m: string) => new Date(m + "-01").toLocaleDateString("en-GB", { month: "short" })} />
              <YAxis tick={{ fontSize: 11, fill: CHART.axis }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip cursor={{ fill: CHART.grid }} contentStyle={TOOLTIP} />
              {outcomes.map((o, i) => <Bar key={o} dataKey={o} stackId="a" fill={OUTCOME_COLORS[o]} radius={i === outcomes.length - 1 ? [4, 4, 0, 0] : 0} maxBarSize={36} />)}
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="flex flex-wrap gap-4 mt-2">
          {outcomes.map((o) => <span key={o} className="text-[12px] text-ink-soft inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: OUTCOME_COLORS[o] }} />{o}</span>)}
        </div>
      </section>
      <section className="card p-5">
        <SectionTitle>Median time to response</SectionTitle>
        {data.response_time.length === 0 ? (
          <p className="text-[13px] text-ink-muted">No dated replies yet. When a company replies, record the stage with the date it happened and this fills in by job family.</p>
        ) : (
          <div className="space-y-2">
            {data.response_time.map((r: Dict) => (
              <div key={r.value} className="flex items-center justify-between text-[13px]"><span className="truncate">{r.value}</span><span className="num text-ink-soft">{Math.round(r.median)}d <span className="text-ink-faint">(n={r.count})</span></span></div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Coverage({ coverage }: { coverage: Dict }) {
  const items = [
    ["date_posted", "Date posted", "whether applying early helps"], ["job_description", "Job description", "skills match, language and permit requirements"],
    ["source", "Channel", "which channels work"], ["cv_version", "CV version", "which CV gets replies"], ["fit_rating", "Fit rating", "whether your gut feeling is right"],
  ];
  return (
    <section className="card p-5">
      <SectionTitle>What your data can tell you</SectionTitle>
      <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {items.map(([k, label, what]) => (
          <div key={k}>
            <div className="flex items-baseline justify-between"><span className="text-[13px] font-medium">{label}</span><span className="num text-[12px] text-ink-muted">{pct(coverage[k])}</span></div>
            <div className="h-1.5 rounded-full bg-canvas mt-1.5 overflow-hidden"><div className="h-full bg-brand rounded-full" style={{ width: `${(coverage[k] ?? 0) * 100}%` }} /></div>
            <div className="text-[11.5px] text-ink-muted mt-1.5">Record it to learn {what}.</div>
          </div>
        ))}
      </div>
    </section>
  );
}
