import { useEffect, useMemo, useRef, useState } from "react";
import { call } from "../api";
import { useApp, type MapObject } from "../store";
import { fmtNum, useT } from "../i18n";
import { fmtDistance } from "../mapObjects";

/* F5: the height profile - the chosen object's height and the ground under it along the distance it travelled, for
   any recording with positions (backend app/heightprofile.py). A strip under the map: the ground filled, the height
   a line in the object's colour, the cursor's moment a mark (amber, as every cursor); the pointer reads distance,
   height, ground and the height above it; a click moves the cursor there. Where the ground is coarse or missing it
   says why and what to do. */

interface Profile { t: number[]; d: number[]; alt: (number | null)[] | null; ground: (number | null)[] | null; agl: (number | null)[] | null;
  length_m: number; step_m: number | null; why: string }

const W = 1000, H = 100;                                     // the drawing's own units (the SVG scales to the strip)

export default function HeightProfile({ obj }: { obj: MapObject }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const cursor = useApp((s) => s.cursor);
  const [p, setP] = useState<Profile | null>(null);
  const [err, setErr] = useState("");
  const [hover, setHover] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const key = [obj.lat, obj.lon, obj.alt ?? "", obj.altRef ?? "msl"].join("|");
  useEffect(() => {
    let live = true;
    setErr("");
    call<Profile>("/api/profile", { lat: obj.lat, lon: obj.lon, alt: obj.alt ?? null, altRef: obj.altRef ?? "msl" })
      .then((r) => { if (live) setP(r); }).catch((e: Error) => { if (live) { setP(null); setErr(e.message); } });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const geo = useMemo(() => {
    if (!p) return null;
    const vals = [...(p.alt ?? []), ...(p.ground ?? [])].filter((v): v is number => v !== null);
    if (!vals.length) return { lo: 0, hi: 1, X: (d: number) => (d / (p.length_m || 1)) * W, Y: () => H / 2, ground: "", alt: "" };
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = Math.max(5, (hi - lo) * 0.08); lo -= pad; hi += pad;
    const X = (d: number) => (d / (p.length_m || 1)) * W, Y = (v: number) => H - ((v - lo) / (hi - lo)) * H;
    const path = (ys: (number | null)[] | null) => {
      if (!ys) return "";
      let s = "", pen = false;
      ys.forEach((v, i) => { if (v === null) { pen = false; return; } s += `${pen ? "L" : "M"}${X(p.d[i]).toFixed(1)},${Y(v).toFixed(1)}`; pen = true; });
      return s;
    };
    const g = path(p.ground);
    return { lo, hi, X, Y, ground: g ? `${g}L${W},${H}L0,${H}Z` : "", alt: path(p.alt) };
  }, [p]);

  if (err) return <div className="hprof hprof-empty" role="status">{err}</div>;
  if (!p || !geo) return <div className="hprof hprof-empty" role="status">{t("hpLoading")}</div>;
  // the cursor's moment, as a place along the distance
  const at = (time: number | null) => {
    if (time === null || !p.t.length) return null;
    let i = p.t.findIndex((x) => x >= time);
    if (i < 0) i = p.t.length - 1;
    return i;
  };
  const ci = cursor.on ? at(cursor.t1) : null;
  const hi = hover;
  const read = (i: number) => {
    const v = (a: (number | null)[] | null) => (a && a[i] !== null ? fmtDistance(a[i] as number, lang) : "–");
    return { d: fmtDistance(p.d[i], lang), alt: v(p.alt), ground: v(p.ground), agl: v(p.agl), t: fmtNum(p.t[i], lang, 6) };
  };
  const shown = hi ?? ci;
  const r = shown !== null ? read(shown) : null;
  const pick = (clientX: number) => {
    const b = svgRef.current?.getBoundingClientRect();
    if (!b || !p.d.length) return null;
    const d = ((clientX - b.left) / b.width) * p.length_m;
    let i = p.d.findIndex((x) => x >= d);
    if (i < 0) i = p.d.length - 1;
    return i;
  };
  return (
    <div className="hprof" role="figure" aria-label={t("hpTitle")} data-points={p.d.length} onMouseDown={(e) => e.stopPropagation()}
      onDoubleClick={(e) => e.stopPropagation()}>
      <div className="hprof-head">
        <b>{t("hpTitle")}</b><span className="hprof-name" style={{ color: obj.color }}>{obj.name}</span>
        <span className="num">{fmtDistance(p.length_m, lang)}</span>
        {r && <span className="hprof-read num">
          <bdi dir="ltr">{r.d}</bdi> · {t("hpAlt")} <bdi dir="ltr">{r.alt}</bdi> · {t("hpGround")} <bdi dir="ltr">{r.ground}</bdi>
          {p.agl && <> · {t("hpAgl")} <bdi dir="ltr">{r.agl}</bdi></>}</span>}
      </div>
      {p.why && <div className="hprof-why" role="note">{p.why}</div>}
      {!p.alt && <div className="hprof-why" role="note">{t("hpNoAlt")}</div>}
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="hprof-svg"
        onMouseMove={(e) => setHover(pick(e.clientX))} onMouseLeave={() => setHover(null)}
        onClick={(e) => { const i = pick(e.clientX); if (i !== null) useApp.setState({ cursor: { ...useApp.getState().cursor, on: true, t1: p.t[i], active: 1 } }); }}>
        {geo.ground && <path className="hprof-ground" d={geo.ground} />}
        {geo.alt && <path className="hprof-alt" d={geo.alt} style={{ stroke: obj.color }} vectorEffect="non-scaling-stroke" />}
        {ci !== null && <line className="hprof-cursor" x1={geo.X(p.d[ci])} x2={geo.X(p.d[ci])} y1={0} y2={H} vectorEffect="non-scaling-stroke" />}
        {hi !== null && <line className="hprof-hover" x1={geo.X(p.d[hi])} x2={geo.X(p.d[hi])} y1={0} y2={H} vectorEffect="non-scaling-stroke" />}
      </svg>
      <div className="hprof-axis num" dir="ltr"><span>{fmtDistance(0, lang)}</span>
        <span>{fmtNum(geo.lo, lang, 4)} – {fmtNum(geo.hi, lang, 4)} m</span><span>{fmtDistance(p.length_m, lang)}</span></div>
    </div>
  );
}
