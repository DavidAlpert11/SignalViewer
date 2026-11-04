/* Any two columns as points (a point per set, or per run), coloured like the lines and with the
   same filters: a chart kind of the Charts tab (S05, MF02). */
import { useEffect, useMemo, useRef, useState } from "react";
import { useApp } from "../../store";
import type { Filter } from "../../sweeps/model";
import { useT } from "../../i18n";
import { category, FAILS, FLAG_COLS, HOLDS, rampOf } from "../../sweeps/colors";
import { keptMask } from "../../sweeps/filters";
import { makeScale } from "../../sweeps/scales";
import { useSweeps, type Study } from "../../sweeps/state";
import { axisChoices, colLabel, groupRows, scaleOf, scopedColumns, styleOf } from "../../sweeps/view";

// room for the ticks and the axes' titles (S11)
const W = 560, H = 380, L = 72, B = 52, T = 12, R = 16;
/** two columns; `size`: a third as the points' size (a bubble chart, MF02) */
type Pair = { x: string; y: string; size?: string };

export function ScatterPanel({ study, pair, onChange, onRemove, group, objectivesOnly }: { study: Study; pair: Pair; onChange: (p: Partial<Pair>) => void; onRemove?: () => void;
  /** the Pareto chart: only the objectives (their worst case per set) on the axes */
  objectivesOnly?: boolean;
  /** MF02: only this group's sets (a desk pane's group) */
  group?: string }) {
  const t = useT();
  const cv = useRef<HTMLCanvasElement>(null);
  const { cols, n, index } = useMemo(() => scopedColumns(study), [study]);
  const choices = axisChoices(study).filter((c) => !objectivesOnly || c === "#goal" || /^#obj\d+$/.test(c));
  const v = study.view;
  const xName = pair.x, yName = pair.y;          // checked by scatterList
  const kept = useMemo(() => {
    const k = keptMask(cols, v.filters, n), g = groupRows(study, group, cols, n, index);
    if (g) for (let r = 0; r < n; r++) k[r] &= g[r];
    return k;
  }, [cols, v.filters, n, study, group, index]);
  // a rectangle dragged on the plot keeps what is in it (S19): the lines' filters on its two columns
  const [drag, setDrag] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null);
  const at = (e: React.PointerEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect(), k = W / r.width;
    return { x: (e.clientX - r.left) * k, y: (e.clientY - r.top) * k };
  };
  const finish = () => {
    if (!drag) return;
    setDrag(null);
    const xc = cols.get(xName), yc = cols.get(yName);
    if (!xc || !yc) return;
    const w = Math.abs(drag.x1 - drag.x0), h = Math.abs(drag.y1 - drag.y0);
    const st = useSweeps.getState();
    if (w < 4 && h < 4) {                                  // a click: the rectangle's filters go
      if (v.filters[xName] || v.filters[yName]) { st.setFilter(xName, null); st.setFilter(yName, null); }
      return;
    }
    const tx = (X: number) => (X - L) / (W - L - R), ty = (Y: number) => (H - B - Y) / (H - B - T);
    const range = (c: typeof xc, a: number, b: number): Filter | null => {
      const s = makeScale(c, scaleOf(study, c.name, c));
      const lo = Math.max(0, Math.min(a, b)), hi = Math.min(1, Math.max(a, b));
      if (c.kind === "cat") {
        const codes = (c.labels ?? []).map((_, i) => i).filter((i) => { const f = s.norm(i); return f >= lo && f <= hi; });
        return codes.length ? { kind: "values", values: codes } : null;
      }
      const u = s.inv(lo), w2 = s.inv(hi);
      return { kind: "ranges", ranges: [[Math.min(u, w2), Math.max(u, w2)]] };
    };
    const fx = range(xc, tx(drag.x0), tx(drag.x1)), fy = range(yc, ty(drag.y0), ty(drag.y1));
    if (fx) st.setFilter(xName, fx);
    if (fy) st.setFilter(yName, fy);
    useApp.getState().toast({ kind: "info", text: t("swPointsKept"), ms: 7000,
      action: { label: t("swShowLines"), run: () => useSweeps.getState().setView({ center: "lines" }) } });
  };
  useEffect(() => {
    const c = cv.current, xc = cols.get(xName ?? ""), yc = cols.get(yName ?? "");
    if (!c || !xc || !yc) return;
    const style = styleOf(study), ramp = rampOf(style.cmap);
    const dpr = window.devicePixelRatio || 1;
    c.width = W * dpr; c.height = H * dpr;
    const ctx = c.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const css = getComputedStyle(c), muted = css.getPropertyValue("--muted").trim() || "#888";
    const line = css.getPropertyValue("--line").trim() || "#ccc";
    const sx = makeScale(xc, scaleOf(study, xc.name, xc)), sy = makeScale(yc, scaleOf(study, yc.name, yc));
    const px = (val: number) => L + sx.norm(val) * (W - L - R), py = (val: number) => H - B - sy.norm(val) * (H - B - T);
    const gx = (f: number) => L + f * (W - L - R), gy = (f: number) => H - B - f * (H - B - T);
    // the grid: at the ticks, and (minor) half way between them
    if (style.grid) {
      const at = (ts: { t: number }[], minor: boolean) => {
        const out = ts.map((x) => x.t);
        if (!minor) return out;
        const mid: number[] = [];
        for (let k = 0; k + 1 < out.length; k++) mid.push((out[k] + out[k + 1]) / 2);
        return mid;
      };
      for (const [minor, alpha] of [[false, 0.9], ...(style.minor ? [[true, 0.4]] : [])] as [boolean, number][]) {
        ctx.strokeStyle = line; ctx.globalAlpha = alpha; ctx.lineWidth = minor ? 0.5 : 1; ctx.beginPath();
        for (const f of at(sx.ticks, minor)) { ctx.moveTo(gx(f), T); ctx.lineTo(gx(f), H - B); }
        for (const f of at(sy.ticks, minor)) { ctx.moveTo(L, gy(f)); ctx.lineTo(W - R, gy(f)); }
        ctx.stroke();
      }
      ctx.globalAlpha = 1; ctx.lineWidth = 1;
    }
    ctx.strokeStyle = muted; ctx.beginPath(); ctx.moveTo(L, T); ctx.lineTo(L, H - B); ctx.lineTo(W - R, H - B); ctx.stroke();
    ctx.fillStyle = muted; ctx.font = "11px 'IBM Plex Sans', sans-serif"; ctx.textAlign = "center";
    for (const tk of sx.ticks) ctx.fillText(tk.label, gx(tk.t), H - B + 14);
    ctx.textAlign = "right";
    for (const tk of sy.ticks) ctx.fillText(tk.label, L - 5, gy(tk.t) + 4);
    // the axes' titles (S11)
    ctx.font = "12px 'IBM Plex Sans', sans-serif"; ctx.textAlign = "center";
    ctx.fillText(colLabel(t, study, xc.name), (L + W - R) / 2, H - 8);
    ctx.save(); ctx.translate(14, (T + H - B) / 2); ctx.rotate(-Math.PI / 2); ctx.fillText(colLabel(t, study, yc.name), 0, 0); ctx.restore();
    const cc = v.colorBy ? cols.get(v.colorBy) : undefined;
    const cs = cc && cc.kind === "num" ? makeScale(cc, "linear") : null;
    const colour = (r: number) => !cc ? HOLDS : FLAG_COLS.has(v.colorBy ?? "") ? (cc.values[r] === 1 ? HOLDS : FAILS)
      : cc.kind === "cat" ? category(cc.values[r]) : ramp(cs!.norm(cc.values[r]));
    const sz = style.size;
    // bubble (MF02): the size column, its range to 1..4 x the point size (by area)
    const zc = pair.size ? cols.get(pair.size) : undefined;
    const zs = zc && zc.kind === "num" ? makeScale(zc, "linear") : null;
    const radius = (r: number) => (zs ? (sz / 2) * Math.sqrt(1 + 15 * Math.max(0, Math.min(1, zs.norm(zc!.values[r]) || 0))) : sz / 2);
    const jitter = (s: typeof sx) => (s.places ? (Math.random() - 0.5) * 6 : 0);
    ctx.globalAlpha = style.opacity ?? (n > 20000 ? 0.25 : n > 2000 ? 0.5 : 0.85);
    for (let r = 0; r < n; r++) {
      if (!kept[r]) continue;
      const X = px(xc.values[r]) + jitter(sx), Y = py(yc.values[r]) + jitter(sy);
      if (!Number.isFinite(X) || !Number.isFinite(Y)) continue;
      ctx.fillStyle = colour(r); ctx.beginPath(); ctx.arc(X, Y, radius(r), 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
    // two objectives against each other: the Pareto front's sets ringed and joined (S19)
    const front = cols.get("#pareto");
    const isObj = (name: string) => name === "#goal" || /^#obj\d+$/.test(name);
    if (front && isObj(xc.name) && isObj(yc.name)) {
      const pts: [number, number][] = [];
      for (let r = 0; r < n; r++) if (front.values[r] === 1 && kept[r]) pts.push([px(xc.values[r]), py(yc.values[r])]);
      pts.sort((a, b) => a[0] - b[0]);
      ctx.strokeStyle = HOLDS; ctx.lineWidth = 1.5;
      // the front joined only with two objectives: with more, a set on the front can look dominated
      // in any one pair (it is better on a third) - ringed, not joined
      if (!cols.has("#obj2")) {
        ctx.beginPath();
        pts.forEach(([X, Y], k) => (k ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y)));
        ctx.stroke();
      }
      for (const [X, Y] of pts) { ctx.beginPath(); ctx.arc(X, Y, sz / 2 + 3, 0, Math.PI * 2); ctx.stroke(); }
      ctx.lineWidth = 1;
      // the balanced choice: the front's set closest to the ideal (best on every objective)
      const knee = cols.get("#knee");
      for (let r = 0; knee && r < n; r++) {
        if (knee.values[r] !== 1) continue;
        const X = px(xc.values[r]), Y = py(yc.values[r]);
        if (!Number.isFinite(X) || !Number.isFinite(Y)) continue;
        ctx.fillStyle = "#f2a93b"; ctx.beginPath();
        for (let k = 0; k < 10; k++) {
          const a = -Math.PI / 2 + (k * Math.PI) / 5, rr = k % 2 ? 4 : 10;
          (k ? ctx.lineTo : ctx.moveTo).call(ctx, X + rr * Math.cos(a), Y + rr * Math.sin(a));
        }
        ctx.closePath(); ctx.fill();
        ctx.font = "12px 'IBM Plex Sans', sans-serif"; ctx.textAlign = "left"; ctx.fillStyle = "#f2a93b";
        ctx.fillText(t("swKnee"), X + 12, Y - 8);
      }
    }
  }, [cols, n, kept, xName, yName, pair.size, v.colorBy, study, t]);
  const sel = (key: "x" | "y" | "size", val: string | undefined) => (
    <select value={val ?? ""} onChange={(e) => onChange({ [key]: e.target.value })}>
      {choices.map((c) => <option key={c} value={c}>{colLabel(t, study, c)}</option>)}
    </select>
  );
  return (
    <div className="sw-scatter sw-map">
      <div className="sw-row sw-map-head"><label>{t("swMapX")} {sel("x", xName)}</label><label>{t("swMapY")} {sel("y", yName)}</label>
        {pair.size !== undefined && <label>{t("swBubbleSize")} {sel("size", pair.size)}</label>}
        {onRemove && <button className="iconbtn" aria-label={t("swRemoveScatter")} title={t("swRemoveScatter")} onClick={onRemove}>×</button>}</div>
      <div className="sw-scatter-box" style={{ maxWidth: W }}
        onPointerDown={(e) => { const p = at(e); (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); setDrag({ x0: p.x, y0: p.y, x1: p.x, y1: p.y }); }}
        onPointerMove={(e) => { if (drag) { const p = at(e); setDrag({ ...drag, x1: p.x, y1: p.y }); } }}
        onPointerUp={finish} title={t("swPointsDrag")}>
        <canvas ref={cv} style={{ width: "100%", aspectRatio: `${W} / ${H}`, display: "block" }} role="img" aria-label={`${xName} / ${yName}`} />
        {drag && <div className="sw-brush" style={{ left: `${(Math.min(drag.x0, drag.x1) / W) * 100}%`, top: `${(Math.min(drag.y0, drag.y1) / H) * 100}%`,
          width: `${(Math.abs(drag.x1 - drag.x0) / W) * 100}%`, height: `${(Math.abs(drag.y1 - drag.y0) / H) * 100}%` }} />}
      </div>
    </div>
  );
}
