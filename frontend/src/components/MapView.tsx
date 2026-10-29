import { useEffect, useMemo, useRef, useState } from "react";
import { geoArea, geoAzimuthalEqualArea, geoCentroid, geoNaturalEarth1, geoPath, type GeoProjection } from "d3-geo";
import { feature } from "topojson-client";
import { Globe2, Layers3, MapPin, Minus, Plus, RotateCcw, Wifi } from "lucide-react";
import { type Dict } from "../api";
import { useApi, useApp } from "../store";
import { cls, COLUMN_OF, STAGE_STYLE } from "../lib";
import { EmptyState, Segmented, Skeleton, StatusPill } from "./ui";

const W = 900, H = 560;
const MAX_ZOOM = 12;
type View = { k: number; x: number; y: number };
const ID: View = { k: 1, x: 0, y: 0 };

/** Centre of a country's main landmass, so France's marker sits in France, not between it and French Guiana. */
function mainCentroid(f: any): [number, number] {
  if (f.geometry?.type !== "MultiPolygon") return geoCentroid(f);
  const parts = f.geometry.coordinates.map((c: any) => ({ type: "Feature", geometry: { type: "Polygon", coordinates: c } }));
  return geoCentroid(parts.reduce((a: any, b: any) => (geoArea(b) > geoArea(a) ? b : a)));
}
const VIEWS = {
  switzerland: { label: "Switzerland", bounds: [[5.9, 45.75], [10.5, 47.85]] as [number, number][] },
  europe: { label: "Europe", bounds: [[-11, 36], [30, 61]] as [number, number][] },
  world: { label: "World", bounds: [[-170, -55], [180, 75]] as [number, number][] },
};

/** Where you've applied, coloured by the furthest stage reached. The outlines ship with the app; nothing is fetched. */
export function MapView() {
  const { filterQuery, openApp } = useApp();
  const { data, loading } = useApi<Dict>(`/api/map${filterQuery()}`);
  const [countries, setCountries] = useState<any[] | null>(null);
  const [view, setView] = useState<keyof typeof VIEWS>("europe");
  const [sel, setSel] = useState<Dict | null>(null);
  const [z, setZ] = useState<View>(ID);
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<{ x: number; y: number; vx: number; vy: number; moved: boolean } | null>(null);
  useEffect(() => setZ(ID), [view]);

  // SVG units per screen pixel, so pointer movement maps onto the map.
  const unit = () => { const r = svgRef.current?.getBoundingClientRect(); return r ? W / r.width : 1; };
  const toSvg = (cx: number, cy: number) => { const r = svgRef.current!.getBoundingClientRect(); return [(cx - r.left) * W / r.width, (cy - r.top) * H / r.height]; };
  const zoomAt = (factor: number, px = W / 2, py = H / 2) => setZ((v) => {
    const k = Math.min(MAX_ZOOM, Math.max(1, v.k * factor));
    if (k === 1) return ID;
    const f = k / v.k;
    return { k, x: px - (px - v.x) * f, y: py - (py - v.y) * f };
  });
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const [px, py] = toSvg(e.clientX, e.clientY);
      zoomAt(Math.exp(-e.deltaY * 0.0022), px, py);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  });

  useEffect(() => {
    // Loaded on demand so the map's outline data isn't part of every page.
    import("world-atlas/countries-50m.json").then((m: any) => {
      const topo = m.default ?? m;
      setCountries((feature(topo, topo.objects.countries) as any).features);
    });
  }, []);

  const projection: GeoProjection = useMemo(() => {
    const b = VIEWS[view].bounds;
    const box = { type: "MultiPoint", coordinates: [b[0], [b[1][0], b[0][1]], b[1], [b[0][0], b[1][1]]] } as any;
    const p = view === "world" ? geoNaturalEarth1() : geoAzimuthalEqualArea().rotate(view === "switzerland" ? [-8.2, -46.8] : [-10, -50]);
    return p.fitExtent([[10, 10], [W - 10, H - 10]], box);
  }, [view]);
  const path = useMemo(() => geoPath(projection), [projection]);

  const byId = useMemo(() => new Map((countries ?? []).map((c) => [String(c.id).padStart(3, "0"), c])), [countries]);
  const pts = useMemo(() => (data?.points ?? []).map((p: Dict) => {
    let ll: [number, number] | null = p.lat !== null && p.lat !== undefined ? [p.lon, p.lat] : null;
    if (!ll && p.iso_num && byId.get(p.iso_num)) ll = mainCentroid(byId.get(p.iso_num));
    const xy = ll ? projection(ll) : null;
    return { ...p, x: xy?.[0] ?? -999, y: xy?.[1] ?? -999 };
  }), [data, projection, byId]);
  const sx = (p: Dict) => p.x * z.k + z.x, sy = (p: Dict) => p.y * z.k + z.y;
  const inView = pts.filter((p: Dict) => sx(p) >= 0 && sx(p) <= W && sy(p) >= 0 && sy(p) <= H);
  const highlighted = new Set(pts.filter((p: Dict) => p.level === "country").map((p: Dict) => p.iso_num));
  const outside = pts.length - inView.length;
  const maxN = Math.max(1, ...pts.map((p: Dict) => p.applications));
  // Bubbles grow a little when zooming in, but much less than the map, so they spread apart.
  const radius = (n: number) => (5 + Math.sqrt(n / maxN) * (view === "switzerland" ? 30 : view === "europe" ? 19 : 15)) * Math.pow(z.k, 0.15) / z.k;

  if (loading && !data) return <Skeleton className="h-[480px]" />;
  if (!data?.points?.length && !data?.remote) return <div className="card"><EmptyState art="compass" title="Nothing to map yet">Add a location to your applications (a city like "Zurich" or "London") and they'll appear here.</EmptyState></div>;

  return (
    <div className="grid xl:grid-cols-[1fr_300px] gap-5 items-start">
      <section className="card p-4 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <Segmented value={view} onChange={(v) => { setView(v); setSel(null); }} options={[
            { id: "switzerland", label: <><MapPin size={13} /> Switzerland</> }, { id: "europe", label: "Europe" }, { id: "world", label: <><Globe2 size={13} /> World</> }]} />
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11.5px] text-ink-muted">
            {(["applied", "screening", "interviewing", "offer"] as const).map((k) => (
              <span key={k} className="inline-flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full" style={{ background: STAGE_STYLE[k].dot }} />
                {{ applied: "Applied", screening: "Screening", interviewing: "Interview", offer: "Offer" }[k]}</span>
            ))}
            <span>· size = number of applications</span>
          </div>
        </div>
        <div className="relative">
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className={cls("w-full h-auto rounded-lg touch-none select-none", z.k > 1 ? "cursor-grab active:cursor-grabbing" : "")}
          role="img" aria-label="Map of your applications" style={{ background: "rgb(var(--info-soft) / .45)" }}
          onPointerDown={(e) => { drag.current = { x: e.clientX, y: e.clientY, vx: z.x, vy: z.y, moved: false }; }}
          onPointerMove={(e) => {
            const d = drag.current;
            if (!d || z.k === 1) return;
            const dx = (e.clientX - d.x) * unit(), dy = (e.clientY - d.y) * unit();
            if (Math.abs(dx) + Math.abs(dy) > 4) { d.moved = true; (e.currentTarget as Element).setPointerCapture?.(e.pointerId); }
            if (d.moved) setZ((v) => ({ ...v, x: d.vx + dx, y: d.vy + dy }));
          }}
          onPointerUp={() => { setTimeout(() => { drag.current = null; }, 0); }}
          onDoubleClick={(e) => { const [px, py] = toSvg(e.clientX, e.clientY); zoomAt(2, px, py); }}>
          <g transform={`translate(${z.x},${z.y}) scale(${z.k})`}>
          {countries ? countries.map((c, i) => (
            <path key={i} d={path(c) ?? ""} vectorEffect="non-scaling-stroke"
              style={{ fill: highlighted.has(String(c.id).padStart(3, "0")) ? "rgb(var(--brand-soft))" : "rgb(var(--surface))", stroke: "rgb(var(--line-strong))", strokeWidth: 0.6 }} />
          )) : <text x={W / 2} y={H / 2} textAnchor="middle" style={{ fill: "rgb(var(--ink-faint))", fontSize: 14 }}>Loading map…</text>}
          {[...inView].sort((a, b) => b.applications - a.applications).map((p: Dict) => {
            const st = STAGE_STYLE[COLUMN_OF[p.best] ?? "applied"];
            const r = radius(p.applications);
            const on = sel?.city === p.city;
            const country = p.level === "country";
            const sr = r * z.k; // on-screen radius
            return (
              <g key={p.city} transform={`translate(${p.x},${p.y})`} className="cursor-pointer" role="button"
                onClick={() => { if (!drag.current?.moved) setSel(p); }} aria-label={`${p.city}: ${p.applications} applications`}>
                <circle r={r} vectorEffect="non-scaling-stroke" style={country
                  ? { fill: st.dot, fillOpacity: 0.12, stroke: st.dot, strokeWidth: on ? 3 : 2, strokeDasharray: "4 3" }
                  : { fill: st.dot, fillOpacity: 0.78, stroke: on ? "rgb(var(--ink))" : "rgb(var(--surface))", strokeWidth: on ? 2.5 : 1.5 }}>
                  <title>{`${p.city}${country ? " (country only, no city given)" : ""}: ${p.applications} applications, ${p.interviews} reached interview`}</title>
                </circle>
                {sr > 11 && <text textAnchor="middle" dy="0.35em" style={{ fill: country ? st.dot : "#fff", fontSize: Math.min(13, sr * 0.7) / z.k, fontWeight: 700, pointerEvents: "none" }}>{p.applications}</text>}
              </g>
            );
          })}
          {/* City names drawn last so a neighbouring bubble never hides them. */}
          {inView.map((p: Dict) => {
            const r = radius(p.applications);
            return (r * z.k > 13 || z.k >= 3 || sel?.city === p.city) && (
              <text key={`l-${p.city}`} x={p.x} y={p.y + r + 13 / z.k} textAnchor="middle" style={{ fill: "rgb(var(--ink-soft))", fontSize: 12 / z.k, fontWeight: 600, paintOrder: "stroke", stroke: "rgb(var(--surface))", strokeWidth: 3 / z.k, pointerEvents: "none" }}>{p.city}</text>
            );
          })}
          </g>
        </svg>
        <div className="absolute top-2 right-2 flex flex-col rounded-lg border border-line bg-surface/95 shadow-card overflow-hidden">
          <button className="w-8 h-8 flex items-center justify-center hover:bg-canvas disabled:opacity-40" aria-label="Zoom in" disabled={z.k >= MAX_ZOOM} onClick={() => zoomAt(1.6)}><Plus size={15} /></button>
          <button className="w-8 h-8 flex items-center justify-center hover:bg-canvas border-t border-line disabled:opacity-40" aria-label="Zoom out" disabled={z.k <= 1} onClick={() => zoomAt(1 / 1.6)}><Minus size={15} /></button>
          {z.k > 1 && <button className="w-8 h-8 flex items-center justify-center hover:bg-canvas border-t border-line" aria-label="Reset zoom" onClick={() => setZ(ID)}><RotateCcw size={13} /></button>}
        </div>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[12px] text-ink-muted">
          <span>Scroll or use + / − to zoom, drag to move.</span>
          {pts.some((p: Dict) => p.level === "country") && <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded-full border-2 border-dashed border-ink-faint" />country only, no city</span>}
          {data.remote > 0 && <span className="inline-flex items-center gap-1"><Wifi size={12} />{data.remote} remote</span>}
          {data.various > 0 && <span className="inline-flex items-center gap-1"><Layers3 size={12} />{data.various} with several locations</span>}
          {outside > 0 && <button className="text-brand hover:underline" onClick={() => { if (z.k > 1) setZ(ID); else setView(view === "switzerland" ? "europe" : "world"); }}>{outside} place{outside > 1 ? "s" : ""} outside this view: zoom out</button>}
        </div>
      </section>
      <aside className="space-y-4">
        <section className="card p-4">
          {sel ? (
            <>
              <div className="flex items-baseline justify-between"><h3 className="text-[15px] font-semibold">{sel.city}</h3><button className="text-[12px] text-ink-muted hover:text-ink" onClick={() => setSel(null)}>Clear</button></div>
              <div className="text-[12.5px] text-ink-muted mt-0.5 num">{sel.applications} applications · {sel.interviews} interviews{sel.offers ? ` · ${sel.offers} offer${sel.offers > 1 ? "s" : ""}` : ""} · {sel.active} active</div>
              <ul className="mt-3 space-y-1.5">
                {sel.items.map((a: Dict) => (
                  <li key={a.id}><button className="w-full text-left flex items-center gap-2 rounded-md px-1.5 py-1 hover:bg-canvas" onClick={() => openApp(a.id)}>
                    <span className="flex-1 min-w-0 text-[12.5px] truncate">{a.position} <span className="text-ink-muted">· {a.company}</span></span><StatusPill stage={a.status} size="sm" /></button></li>
                ))}
                {sel.applications > sel.items.length && <li className="text-[11.5px] text-ink-faint px-1.5">and {sel.applications - sel.items.length} more</li>}
              </ul>
            </>
          ) : (
            <>
              <h3 className="text-[14px] font-semibold mb-2">Cities</h3>
              <ul className="space-y-1">
                {pts.slice(0, 10).map((p: Dict) => (
                  <li key={p.city}><button onClick={() => { setSel(p); if (!inView.includes(p)) { if (z.k > 1) setZ(ID); else setView(view === "switzerland" ? "europe" : "world"); } }} className="w-full flex items-center justify-between text-[12.5px] rounded-md px-1.5 py-1 hover:bg-canvas">
                    <span>{p.city}{p.level === "country" && <span className="text-ink-faint"> · country</span>}</span><span className="num text-ink-muted">{p.applications} · {p.applications ? Math.round((p.interviews / p.applications) * 100) : 0}% interview</span></button></li>
                ))}
              </ul>
            </>
          )}
        </section>
        {data.unmatched?.length > 0 && (
          <section className={cls("card p-4")}>
            <h3 className="text-[13px] font-semibold">Not on the map</h3>
            <p className="text-[11.5px] text-ink-muted mt-0.5 mb-2">Not recognised as a town (over 15,000 people) or a country. Edit the location on the application, or add the place to <code className="font-mono">config/places.yaml</code>.</p>
            <ul className="text-[12px] space-y-0.5">{data.unmatched.map((u: Dict) => <li key={u.location} className="flex justify-between"><span className="truncate">{u.location}</span><span className="num text-ink-faint">{u.count}</span></li>)}</ul>
          </section>
        )}
      </aside>
    </div>
  );
}
