import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Layer, Rectangle, ResponsiveContainer, Sankey, Tooltip, XAxis, YAxis } from "recharts";
import { Info } from "lucide-react";
import { type Dict } from "../api";
import { useApi, useApp } from "../store";
import { CHART, cls, OUTCOME_COLORS, pct } from "../lib";
import { FilterBar } from "../components/FilterBar";
import { EmptyState, PageHeader, SectionTitle, Select, Skeleton } from "../components/ui";

const VERDICT: Record<string, { color: string; bg: string }> = {
  Strength: { color: "#0a7a53", bg: "#e8f6f0" }, Promising: { color: "#0a7a53", bg: "#f1f9f5" },
  "About average": { color: "#5d6676", bg: "#f2f3f5" }, "Below average": { color: "#a35f00", bg: "#fdf4e6" },
  "Weak spot": { color: "#b42318", bg: "#fdecea" }, "Too few to tell": { color: "#9aa2b1", bg: "#f6f7f9" },
};
const STAGE_NODE: Record<string, string> = {
  Applied: "#3d6fd6", Screening: "#7f5bd1", Interview: "#d97f06", "Final interview": "#c06a00", Offer: "#0e9a69",
  Accepted: "#0a7a53", Rejected: "#b9bfca", Ghosted: "#7c8494", Withdrawn: "#dfe2e8", "Awaiting reply": "#9db6e0",
};

export default function Analytics() {
  const { filterQuery, meta } = useApp();
  const [metric, setMetric] = useState("positive");
  const [dim, setDim] = useState("role_area");
  const [rows, setRows] = useState("role_area");
  const [cols, setCols] = useState("seniority");
  const { data, loading } = useApi<Dict>(`/api/analytics${filterQuery({ metric, dim, rows, cols })}`);
  const dims = meta?.dimensions ?? {};
  const metrics = meta?.metrics ?? {};

  return (
    <div>
      <PageHeader title="Analytics" subtitle="How your applications convert, and which kinds of roles work best for you." />
      <div className="mb-6"><FilterBar /></div>
      {loading && !data ? <div className="grid grid-cols-3 gap-4">{[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-32" />)}</div>
        : !data || data.empty ? <div className="card"><EmptyState title="No applications match these filters">Clear some filters to see your analytics.</EmptyState></div>
        : (
          <div className="space-y-8">
            <Conversion c={data.conversion} />
            <div className="grid xl:grid-cols-2 gap-5">
              <Funnel funnel={data.funnel} />
              <Flow links={data.flow} />
            </div>
            <RolesTable data={data} dim={dim} setDim={setDim} dims={dims} />
            <Scorecard data={data} metric={metric} setMetric={setMetric} metrics={metrics} dim={dim} setDim={setDim} dims={dims}
              rows={rows} cols={cols} setRows={setRows} setCols={setCols} />
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

function Flow({ links }: { links: Dict[] }) {
  const graph = useMemo(() => {
    const names = Array.from(new Set(links.flatMap((l) => [l.source, l.target])));
    return { nodes: names.map((n) => ({ name: n })), links: links.map((l) => ({ source: names.indexOf(l.source), target: names.indexOf(l.target), value: l.count })) };
  }, [links]);
  return (
    <section className="card p-5">
      <SectionTitle>Where applications go</SectionTitle>
      {links.length === 0 ? <p className="text-ink-muted">No data yet.</p> : (
        <div className="h-[290px]">
          <ResponsiveContainer width="100%" height="100%">
            <Sankey data={graph} nodePadding={22} nodeWidth={10} margin={{ left: 4, right: 110, top: 8, bottom: 8 }}
              link={{ stroke: "#9aa2b1", strokeOpacity: 0.22 }} node={<SankeyNode />}>
              <Tooltip formatter={(v: number) => [`${v} applications`, ""]} />
            </Sankey>
          </ResponsiveContainer>
        </div>
      )}
      <p className="text-[12px] text-ink-muted mt-2">Record each stage as it happens to see exactly where applications stop.</p>
    </section>
  );
}

function SankeyNode(props: any) {
  const { x, y, width, height, payload } = props;
  const color = STAGE_NODE[payload.name] ?? "#9aa2b1";
  return (
    <Layer>
      <Rectangle x={x} y={y} width={width} height={height} fill={color} radius={2} />
      <text x={x + width + 6} y={y + height / 2} dy="0.35em" fontSize={12} fill="#3b4556">{payload.name} <tspan fill="#9aa2b1" fontFamily="JetBrains Mono Variable, monospace">{payload.value}</tspan></text>
    </Layer>
  );
}

// ------------------------------------------------------- rates by dimension
function RolesTable({ data, dim, setDim, dims }: { data: Dict; dim: string; setDim: (d: string) => void; dims: Record<string, string> }) {
  const [all, setAll] = useState(false);
  const allRows: Dict[] = data.by_dim;
  const rows = all ? allRows : allRows.slice(0, 12);
  const max = Math.max(...rows.map((r) => r.response_rate ?? 0), 0.01);
  return (
    <section className="card p-5">
      <SectionTitle aside={<Select className="h-8 w-56 text-[12.5px]" value={dim} onChange={setDim}
        options={Object.entries(dims).map(([value, label]) => ({ value, label }))} />}>
        Response, interview and offer rate by {dims[dim]?.toLowerCase() ?? dim}
      </SectionTitle>
      <div className="overflow-x-auto scroll-thin">
        <table className="w-full text-[13px] min-w-[720px]">
          <thead>
            <tr className="text-ink-muted text-[12px]">
              <th className="text-left font-medium py-2">{dims[dim]}</th>
              <th className="text-right font-medium py-2 px-2">Applied</th>
              <th className="text-left font-medium py-2 px-3 w-[28%]">Response rate</th>
              <th className="text-right font-medium py-2 px-2">Interviews</th>
              <th className="text-right font-medium py-2 px-2">Interview rate</th>
              <th className="text-right font-medium py-2 px-2">Offers</th>
              <th className="text-right font-medium py-2 px-2">Offer rate</th>
              <th className="text-right font-medium py-2 pl-2">Interview → offer</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.value} className={cls("border-t border-line", r.applied < 5 && "text-ink-muted")}>
                <td className="py-2 pr-2 font-medium">{r.value}{r.applied < 5 && <span className="text-[11px] text-ink-faint font-normal"> · few</span>}</td>
                <td className="py-2 px-2 text-right num">{r.applied}</td>
                <td className="py-2 px-3">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 rounded-full bg-canvas overflow-hidden"><div className="h-full rounded-full bg-[#3d6fd6]" style={{ width: `${(r.response_rate / max) * 100}%` }} /></div>
                    <span className="num text-[12px] w-10 text-right">{pct(r.response_rate)}</span>
                  </div>
                </td>
                <td className="py-2 px-2 text-right num">{r.interviews}</td>
                <td className="py-2 px-2 text-right num">{pct(r.interview_rate)}</td>
                <td className="py-2 px-2 text-right num">{r.offers}</td>
                <td className="py-2 px-2 text-right num font-medium">{pct(r.offer_rate)}</td>
                <td className="py-2 pl-2 text-right num">{r.interview_to_offer === null ? "—" : pct(r.interview_to_offer)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {allRows.length > 12 && <button className="btn-ghost btn-sm mt-2" onClick={() => setAll(!all)}>{all ? "Show top 12" : `Show all ${allRows.length}`}</button>}
    </section>
  );
}

// ---------------------------------------------------------------- scorecard
function Scorecard({ data, metric, setMetric, metrics, dim, setDim, dims, rows, cols, setRows, setCols }: Dict) {
  const [allBars, setAllBars] = useState(false);
  const scAll: Dict[] = data.scorecard ?? [];
  const sc: Dict[] = allBars ? scAll : [...scAll].sort((a, b) => b.applied - a.applied).slice(0, 15).sort((a, b) => b.smoothed - a.smoothed);
  const avg = data.average ?? 0;
  const maxHigh = Math.max(...sc.map((s) => s.ci_high), avg, 0.05);
  const segLine = (r: Dict) => (
    <li key={`${r.dimension}-${r.value}`} className="flex items-center gap-2 py-1.5">
      <span className="text-[11px] font-medium px-1.5 py-0.5 rounded" style={{ color: VERDICT[r.verdict]?.color, background: VERDICT[r.verdict]?.bg }}>{r.verdict}</span>
      <span className="text-[13px] min-w-0 truncate"><span className="text-ink-muted">{r.dimension_label}:</span> <b className="font-medium">{r.value}</b></span>
      <span className="ml-auto num text-[12px] text-ink-muted whitespace-nowrap">{r.successes}/{r.applied} · {r.lift >= 0 ? "+" : ""}{Math.round(r.lift * 100)}%</span>
    </li>
  );
  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-[15px] font-semibold">Role Success Scorecard</h2>
          <p className="text-[12.5px] text-ink-muted max-w-2xl">Your personal success rate for each kind of role. Small groups are pulled towards your average so a lucky 1-of-2 doesn't outrank 5-of-30.</p>
        </div>
        <label className="flex items-center gap-2 text-[12.5px] text-ink-muted">Count as success
          <Select className="h-8 w-[290px] text-[12.5px]" value={metric} onChange={setMetric}
            options={Object.entries(metrics).map(([label, value]) => ({ value: value as string, label }))} />
        </label>
      </div>
      <div className="grid sm:grid-cols-3 gap-3 mb-5">
        <div className="rounded-lg bg-canvas p-3"><div className="text-[12px] text-ink-muted">Applications judged</div><div className="num text-[20px] font-semibold">{data.judged}</div></div>
        <div className="rounded-lg bg-canvas p-3"><div className="text-[12px] text-ink-muted">Successes</div><div className="num text-[20px] font-semibold">{data.successes}</div></div>
        <div className="rounded-lg bg-canvas p-3"><div className="text-[12px] text-ink-muted">Your average</div><div className="num text-[20px] font-semibold">{pct(avg, 1)}</div></div>
      </div>
      {data.successes < 10 && (
        <div className="flex gap-2 p-3 rounded-lg bg-[#fdf4e6] text-[#7a4a00] text-[12.5px] mb-5">
          <Info size={15} className="shrink-0 mt-0.5" />
          Only {data.successes} successes so far, so differences are hints rather than proof. Try "Any reply" for a bigger sample.
        </div>
      )}
      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <div><div className="eyebrow mb-1">Where you do best</div><ul className="divide-y divide-line">{data.strengths.length ? data.strengths.map(segLine) : <li className="text-ink-muted text-[13px] py-2">Nothing stands out yet.</li>}</ul></div>
        <div><div className="eyebrow mb-1">Where you struggle</div><ul className="divide-y divide-line">{data.gaps.length ? data.gaps.map(segLine) : <li className="text-ink-muted text-[13px] py-2">Nothing stands out yet.</li>}</ul></div>
      </div>

      <div className="flex flex-wrap gap-1.5 mb-4">
        {Object.entries(dims).map(([k, label]) => (
          <button key={k} onClick={() => setDim(k)}
            className={cls("h-7 px-2.5 rounded-full text-[12px] font-medium border transition", dim === k ? "bg-ink text-white border-ink" : "bg-white border-line text-ink-soft hover:bg-canvas")}>{label as string}</button>
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
                <span className="num text-ink-soft">{s.successes}/{s.applied} · {pct(s.rate)}</span>
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

      <div className="mt-8 pt-6 border-t border-line">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h3 className="text-[14px] font-semibold">Combine two dimensions</h3>
          <div className="flex items-center gap-2">
            <Select className="h-8 w-48 text-[12.5px]" value={rows} onChange={setRows} options={Object.entries(dims).map(([value, label]) => ({ value, label: label as string }))} />
            <span className="text-ink-faint">×</span>
            <Select className="h-8 w-48 text-[12.5px]" value={cols} onChange={setCols} options={Object.entries(dims).map(([value, label]) => ({ value, label: label as string }))} />
          </div>
        </div>
        {rows === cols ? <p className="text-ink-muted text-[13px]">Pick two different dimensions.</p> : <Heatmap hm={data.heatmap} />}
      </div>
    </section>
  );
}

function Heatmap({ hm: full }: { hm: Dict }) {
  if (!full.rows.length) return <p className="text-ink-muted text-[13px]">No data.</p>;
  // Keep the 12 largest rows and 8 largest columns so the grid stays readable.
  const rowTot = full.rows.map((_: string, i: number) => full.n[i].reduce((a: number, b: number | null) => a + (b ?? 0), 0));
  const colTot = full.cols.map((_: string, j: number) => full.n.reduce((a: number, r: (number | null)[]) => a + (r[j] ?? 0), 0));
  const ri = rowTot.map((t: number, i: number) => [t, i]).sort((a: number[], b: number[]) => b[0] - a[0]).slice(0, 12).map((x: number[]) => x[1]).sort((a: number, b: number) => a - b);
  const ci = colTot.map((t: number, j: number) => [t, j]).sort((a: number[], b: number[]) => b[0] - a[0]).slice(0, 8).map((x: number[]) => x[1]).sort((a: number, b: number) => a - b);
  const hm = { rows: ri.map((i: number) => full.rows[i]), cols: ci.map((j: number) => full.cols[j]),
    rate: ri.map((i: number) => ci.map((j: number) => full.rate[i][j])), n: ri.map((i: number) => ci.map((j: number) => full.n[i][j])) };
  const trimmed = hm.rows.length < full.rows.length || hm.cols.length < full.cols.length;
  const max = Math.max(0.01, ...hm.rate.flat().filter((x: number | null) => x !== null));
  return (
    <div className="overflow-x-auto scroll-thin">
      <table className="text-[12px] border-separate border-spacing-1">
        <thead><tr><th />{hm.cols.map((c: string) => <th key={c} className="font-medium text-ink-muted px-1 pb-1 max-w-[110px] align-bottom text-center leading-tight">{c}</th>)}</tr></thead>
        <tbody>
          {hm.rows.map((r: string, i: number) => (
            <tr key={r}>
              <th className="text-left font-medium text-ink-soft pr-2 whitespace-nowrap max-w-[220px] truncate">{r}</th>
              {hm.cols.map((c: string, j: number) => {
                const v = hm.rate[i][j], n = hm.n[i][j];
                if (v === null || !n) return <td key={c} className="w-[92px] h-11 rounded-md bg-canvas/60" />;
                const a = 0.08 + 0.85 * (v / max);
                return (
                  <td key={c} className="w-[92px] h-11 rounded-md text-center align-middle" style={{ background: `rgba(14,122,92,${a})`, color: a > 0.5 ? "white" : "#18212f" }}
                    title={`${r} × ${c}: ${pct(v)} of ${n}`}>
                    <div className="num font-semibold">{pct(v)}</div>
                    <div className="text-[10px] opacity-80 num">n={n}</div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[11.5px] text-ink-muted mt-2">Cells with few applications are noisy; check n before drawing conclusions.{trimmed && " Showing the largest groups only; filter to see others."}</p>
    </div>
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
              <Tooltip cursor={{ fill: "#f6f7f9" }} contentStyle={{ borderRadius: 8, border: "1px solid #e4e7ec", fontSize: 12 }} />
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
