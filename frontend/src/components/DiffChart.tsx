import { useEffect, useRef, useState } from "react";
import type { DiffTrace } from "../api";
import { actions, useApp } from "../store";
import { fmtNum, useT } from "../i18n";
import { ink, useSize } from "./chartUtil";

const H = 132, PADL = 40, PADR = 8, PADT = 6, PADB = 18;

/** U5 (owner, 2026-11-07, as the Simulink Data Inspector): under the overlay, each run's difference
 *  from the baseline over time, the tolerance band shaded around zero and the stretches outside it
 *  in red - where and by how much a signal fails. A click puts the cursor there (the overlay plot
 *  follows); off in a segment comparison, whose times are since each segment's start. */
export default function DiffChart({ traces, segment }: { traces: { id: string; color: string; name: string; trace: DiffTrace }[]; segment: boolean }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const theme = useApp((s) => s.theme);
  const ref = useRef<SVGSVGElement>(null);
  const [hx, setHx] = useState<number | null>(null);
  const box = useRef<HTMLDivElement>(null);         // always there: its width is the chart's
  // 26.U2: drawn at its real width - a stretched viewBox stretched the axis numbers with it
  const W = Math.max(240, useSize(box).w || 320);
  const key = traces.map((x) => x.id).join("|");
  // a new signal picked in the list: its difference comes into view (it sits under the list)
  useEffect(() => { box.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [key]);
  const all = traces.filter((x) => x.trace.t.length > 1).map((x) => ({ ...x, color: ink(x.color, theme) }));
  if (!all.length) return <div className="diff-wrap" ref={box} />;
  const t0 = Math.min(...all.map((x) => x.trace.t[0])), t1 = Math.max(...all.map((x) => x.trace.t[x.trace.t.length - 1]));
  const vals = all.flatMap((x) => [...x.trace.d, ...(x.trace.lo ?? []), ...(x.trace.hi ?? [])]).filter((v): v is number => v !== null && Number.isFinite(v));
  let y0 = Math.min(0, ...vals), y1 = Math.max(0, ...vals);
  if (y1 - y0 < 1e-12) { y0 -= 1; y1 += 1; }
  const pad = (y1 - y0) * 0.08; y0 -= pad; y1 += pad;
  const X = (v: number) => PADL + ((v - t0) / Math.max(t1 - t0, 1e-12)) * (W - PADL - PADR);
  const Y = (v: number) => PADT + (1 - (v - y0) / (y1 - y0)) * (H - PADT - PADB);
  const line = (ts: number[], ys: (number | null | undefined)[]) => {
    let dpath = "", pen = false;
    ts.forEach((tv, i) => { const v = ys[i]; if (v === null || v === undefined || !Number.isFinite(v)) { pen = false; return; }
      dpath += `${pen ? "L" : "M"}${X(tv).toFixed(1)},${Y(v).toFixed(1)}`; pen = true; });
    return dpath;
  };
  const first = all[0].trace;
  const band = first.lo && first.hi ? (() => {
    const up = first.t.map((tv, i) => `${X(tv).toFixed(1)},${Y(first.hi![i] ?? 0).toFixed(1)}`);
    const dn = first.t.map((tv, i) => `${X(tv).toFixed(1)},${Y(first.lo![i] ?? 0).toFixed(1)}`).reverse();
    return `M${up.join("L")}L${dn.join("L")}Z`;
  })() : null;
  const timeAt = (clientX: number) => {
    const r = ref.current!.getBoundingClientRect();
    const x = ((clientX - r.left) / r.width) * W;
    return t0 + ((x - PADL) / (W - PADL - PADR)) * (t1 - t0);
  };
  const outs = all.flatMap((x) => x.trace.out.map((o) => ({ ...x, o })));
  return (
    <div className="diff-wrap" ref={box}><figure className="diff-chart">
      <figcaption>{t("diffTitle")}{band ? <span className="muted"> · {t("diffBand")}</span> : null}
        {outs.length > 0 && <span className="diff-out-n">{t("diffOutN", { n: outs.length })}</span>}</figcaption>
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label={t("diffTitle")}
        onMouseMove={(e) => setHx(timeAt(e.clientX))} onMouseLeave={() => setHx(null)}
        onClick={(e) => { if (!segment) useApp.setState({ cursor: { ...useApp.getState().cursor, on: true, t1: timeAt(e.clientX), active: 1 } }); }}
        style={{ cursor: segment ? "default" : "crosshair" }}>
        {band && <path className="diff-band" d={band} />}
        {band && first.hi && <path className="diff-band-edge" d={line(first.t, first.hi)} />}
        {band && first.lo && <path className="diff-band-edge" d={line(first.t, first.lo)} />}
        {/* 26.U2: outside the tolerance - a faint shade over the height (the lines stay readable) and a
            solid mark along the bottom, so where it fails reads at a glance */}
        {outs.map(({ o }, i) => <rect key={i} className="diff-out" x={X(o[0])} y={PADT} width={Math.max(1.5, X(o[1]) - X(o[0]))} height={H - PADT - PADB} />)}
        {outs.map(({ o }, i) => <rect key={`m${i}`} className="diff-out-mark" x={X(o[0])} y={H - PADB - 4} width={Math.max(2, X(o[1]) - X(o[0]))} height={4} />)}
        <line className="diff-zero" x1={PADL} x2={W - PADR} y1={Y(0)} y2={Y(0)} />
        {all.map((x) => <path key={x.id} className="diff-line" d={line(x.trace.t, x.trace.d)} style={{ stroke: x.color }} />)}
        {hx !== null && hx >= t0 && hx <= t1 && <line className="diff-hover" x1={X(hx)} x2={X(hx)} y1={PADT} y2={H - PADB} />}
        {hx !== null && hx >= t0 && hx <= t1 && all.map((x) => {                // 26.U2: each run's difference there
          const i = nearest(x.trace.t, hx), v = x.trace.d[i];
          return v === null || v === undefined || !Number.isFinite(v) ? null
            : <circle key={`h${x.id}`} className="diff-hover-pt" cx={X(x.trace.t[i])} cy={Y(v)} r={3} style={{ fill: x.color }} />;
        })}
        <text className="diff-tick" x={PADL - 4} y={Y(y1 - pad) + 3} textAnchor="end">{fmtNum(y1 - pad, lang, 3)}</text>
        <text className="diff-tick" x={PADL - 4} y={Y(0) + 3} textAnchor="end">0</text>
        <text className="diff-tick" x={PADL - 4} y={Y(y0 + pad) + 3} textAnchor="end">{fmtNum(y0 + pad, lang, 3)}</text>
        <text className="diff-tick" x={PADL} y={H - 4} textAnchor="start">{fmtNum(t0, lang, 5)}</text>
        <text className="diff-tick" x={W - PADR} y={H - 4} textAnchor="end">{fmtNum(t1, lang, 5)} s</text>
      </svg>
      {hx !== null && hx >= t0 && hx <= t1 && (
        <div className="diff-readout" aria-live="off"><bdi dir="ltr">t = {fmtNum(hx, lang, 5)} s</bdi>
          {all.map((x) => { const v = x.trace.d[nearest(x.trace.t, hx)];
            return <span key={x.id}><span className="run-dot" style={{ background: x.color }} /> <bdi dir="ltr">{v === null || v === undefined || !Number.isFinite(v) ? "–" : (v >= 0 ? "+" : "") + fmtNum(v, lang, 4)}</bdi></span>; })}
        </div>
      )}
      {outs.length > 0 && (
        <ul className="diff-outs">
          {outs.slice(0, 6).map(({ o, name, color }, i) => (
            <li key={i}><button className="linklike" disabled={segment} onClick={() => {
              const st = useApp.getState();
              const span = Math.max(o[1] - o[0], 0.5);
              st.set({ cursor: { ...st.cursor, on: true, dual: o[1] > o[0], t1: o[0], t2: o[1] > o[0] ? o[1] : null, active: 1 } });
              actions.showSpan(o[0] - span, o[1] + span);
            }}><span className="run-dot" style={{ background: color }} /> {name}: {fmtNum(o[0], lang, 5)} – {fmtNum(o[1], lang, 5)} s</button></li>
          ))}
          {outs.length > 6 && <li className="muted">+{outs.length - 6}</li>}
        </ul>
      )}
    </figure></div>
  );
}

/** The index of the sample of `ts` (sorted) nearest to `t`. */
function nearest(ts: number[], t: number): number {
  let lo = 0, hi = ts.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (ts[m] < t) lo = m; else hi = m; }
  return Math.abs(ts[lo] - t) <= Math.abs(ts[hi] - t) ? lo : hi;
}
