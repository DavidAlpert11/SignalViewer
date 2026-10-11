import { useEffect, useMemo, useRef, useState } from "react";
import { api, type SpecData } from "../api";
import { actions, rangeKey, shownSpan, useApp, type Plot, type Tab } from "../store";
import { fmtNum, useT } from "../i18n";
import { PLOT_THEME, uiScale, useSize } from "./chartUtil";

interface Props { tab: Tab; plot: Plot; index: number; onLoading: (b: boolean) => void }

/* Spectrogram (frequency over time) of the plot's first signal, over the same time window as the
   tab's other plots: drag = zoom time, wheel = zoom time, double-click = whole signal, click = cursor.
   Colour = power in dB (viridis, from the 5th to the 99.7th percentile of what is in view). */

const C = [[0.2777273272234177, 0.005407344544966578, 0.3340998053353061], [0.1050930431085774, 1.404613529898575, 1.384590162594685],
  [-0.3308618287255563, 0.214847559468213, 0.09509516302823659], [-4.634230498983486, -5.799100973351585, -19.33244095627987],
  [6.228269936347081, 14.17993336680509, 56.69055419421445], [4.776384997670288, -13.74514537774601, -65.35303263337234],
  [-5.435455855934631, 4.645852612178535, 26.3124352495832]];
const LUT = (() => {
  const out = new Uint8ClampedArray(256 * 3);
  for (let i = 0; i < 256; i++) {
    const t = i / 255;
    for (let ch = 0; ch < 3; ch++) {
      let v = C[6][ch];
      for (let k = 5; k >= 0; k--) v = C[k][ch] + t * v;
      out[i * 3 + ch] = Math.round(Math.max(0, Math.min(1, v)) * 255);
    }
  }
  return out;
})();

function niceTicks(lo: number, hi: number, n: number): number[] {
  const span = hi - lo;
  if (!(span > 0)) return [lo];
  const raw = span / Math.max(1, n);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9 * span; v += step) out.push(+v.toPrecision(12));
  return out;
}

export default function SpecChart({ tab, plot, index, onLoading }: Props) {
  const t = useT();
  const theme = useApp((s) => s.theme);
  const lang = useApp((s) => s.lang);
  const dataVersion = useApp((s) => s.dataVersion);
  const cursor = useApp((s) => s.cursor);
  const key = rangeKey(tab, plot);
  const range = useApp((s) => s.ranges[key] ?? null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const size = useSize(wrapRef);
  const [data, setData] = useState<SpecData | null>(null);
  const [err, setErr] = useState("");
  const [readout, setReadout] = useState("");
  const ps = plot.signals[0];
  const tOff = ps?.tOffset ?? 0;
  const nfft = plot.specN ?? 1024;
  const M = useMemo(() => ({ l: 54, r: 46, t: 8, b: 26 }), []);
  const plotW = Math.max(10, size.w - M.l - M.r), plotH = Math.max(10, size.h - M.t - M.b);

  useEffect(() => {
    if (!ps || size.w < 80 || size.h < 60) { setData(null); return; }
    let cancelled = false;
    const h = window.setTimeout(async () => {
      onLoading(true);
      try {
        const r = await api.spectrogram(ps.sig, range ? range[0] - tOff : null, range ? range[1] - tOff : null, nfft,
          Math.round(plotW), Math.round(plotH), plot.specFmax ?? null);
        if (!cancelled) { setData(r); setErr(""); }
      } catch (e) {
        if (!cancelled) { setData(null); setErr(String((e as Error).message)); }
      } finally { if (!cancelled) onLoading(false); }
    }, 120);
    return () => { cancelled = true; window.clearTimeout(h); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ps?.sig, range?.[0], range?.[1], tOff, nfft, plot.specFmax, dataVersion, Math.round(plotW / 40), Math.round(plotH / 40)]);

  // x extent of the image: column centres +- half a column
  const ext = useMemo(() => {
    if (!data) return null;
    const cw = data.nt > 1 ? (data.t1 - data.t0) / (data.nt - 1) : data.dt;
    return { x0: (range ? range[0] : data.t0 - cw / 2 + tOff), x1: (range ? range[1] : data.t1 + cw / 2 + tOff),
      i0: data.t0 - cw / 2 + tOff, i1: data.t1 + cw / 2 + tOff, f0: data.f0, f1: data.f1 };
  }, [data, range, tOff]);

  /* the image, decoded once per data (it was decoded again on every cursor move - every frame in playback) */
  const off = useMemo(() => {
    if (!data) return null;
    const img = Uint8Array.from(atob(data.img), (c) => c.charCodeAt(0));
    const cvs = document.createElement("canvas");
    cvs.width = data.nt; cvs.height = data.nf;
    const oc = cvs.getContext("2d")!;
    const id = oc.createImageData(data.nt, data.nf);
    for (let fi = 0; fi < data.nf; fi++) {
      const row = data.nf - 1 - fi;                       // high frequencies at the top
      for (let ti = 0; ti < data.nt; ti++) {
        const q = img[fi * data.nt + ti], o = (row * data.nt + ti) * 4;
        id.data[o] = LUT[q * 3]; id.data[o + 1] = LUT[q * 3 + 1]; id.data[o + 2] = LUT[q * 3 + 2]; id.data[o + 3] = 255;
      }
    }
    oc.putImageData(id, 0, 0);
    return cvs;
  }, [data]);
  const playMode = useApp((s) => s.playMode);
  const windowSec = useApp((s) => s.windowSec);

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv || size.w < 10) return;
    const d = window.devicePixelRatio || 1, s = uiScale();
    cv.width = Math.round(size.w * d); cv.height = Math.round(size.h * d);
    const ctx = cv.getContext("2d")!;
    ctx.setTransform(d, 0, 0, d, 0, 0);
    const pt = PLOT_THEME[theme];
    ctx.clearRect(0, 0, size.w, size.h);
    if (!data || !ext || !off) return;
    const X = (v: number) => M.l + ((v - ext.x0) / (ext.x1 - ext.x0)) * plotW;
    const Y = (f: number) => M.t + plotH - ((f - ext.f0) / (ext.f1 - ext.f0)) * plotH;
    ctx.save();
    ctx.beginPath(); ctx.rect(M.l, M.t, plotW, plotH); ctx.clip();
    ctx.fillStyle = pt.bg; ctx.fillRect(M.l, M.t, plotW, plotH);
    ctx.imageSmoothingEnabled = data.nt < plotW / 2;
    ctx.drawImage(off, X(ext.i0), M.t, X(ext.i1) - X(ext.i0), plotH);
    // the timeline's mode: what is outside the time shown is covered
    const span = shownSpan({ playMode, windowSec, cursor });
    if (span) {
      const a = Number.isFinite(span[0]) ? Math.max(M.l, X(span[0])) : M.l, b = Math.min(M.l + plotW, X(span[1]));
      ctx.globalAlpha = 0.88; ctx.fillStyle = pt.bg;
      if (a > M.l) ctx.fillRect(M.l, M.t, a - M.l, plotH);
      if (b < M.l + plotW) ctx.fillRect(b, M.t, M.l + plotW - b, plotH);
      ctx.globalAlpha = 1;
    }
    // cursors
    const curs = [cursor.on ? cursor.t1 : null, cursor.on && cursor.dual ? cursor.t2 : null];
    curs.forEach((ct) => {
      if (ct === null) return;
      ctx.strokeStyle = pt.amber; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(Math.round(X(ct)) + 0.5, M.t); ctx.lineTo(Math.round(X(ct)) + 0.5, M.t + plotH); ctx.stroke();
    });
    ctx.restore();
    // axes
    ctx.font = `${Math.round(11 * s)}px "IBM Plex Sans", "IBM Plex Sans Hebrew", sans-serif`;
    ctx.fillStyle = pt.axis; ctx.strokeStyle = pt.grid; ctx.lineWidth = 1;
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    for (const v of niceTicks(ext.x0, ext.x1, Math.max(2, Math.floor(plotW / 90)))) {
      const x = X(v);
      if (x < M.l - 1 || x > M.l + plotW + 1) continue;
      ctx.beginPath(); ctx.moveTo(x, M.t + plotH); ctx.lineTo(x, M.t + plotH + 4); ctx.stroke();
      ctx.fillText(fmtNum(v, "en", 6), x, M.t + plotH + 6);
    }
    ctx.textAlign = "right"; ctx.textBaseline = "middle";
    for (const f of niceTicks(ext.f0, ext.f1, Math.max(2, Math.floor(plotH / 40)))) {
      const y = Y(f);
      if (y < M.t - 1 || y > M.t + plotH + 1) continue;
      ctx.beginPath(); ctx.moveTo(M.l - 4, y); ctx.lineTo(M.l, y); ctx.stroke();
      ctx.fillText(fmtNum(f, "en", 4), M.l - 6, y);
    }
    ctx.save(); ctx.translate(12, M.t + plotH / 2); ctx.rotate(-Math.PI / 2); ctx.textAlign = "center";
    ctx.fillText("Hz", 0, 0); ctx.restore();
    // colour bar with its dB range
    const bx = M.l + plotW + 10, bw = 10;
    for (let i = 0; i < plotH; i++) {
      const q = Math.round((1 - i / plotH) * 255);
      ctx.fillStyle = `rgb(${LUT[q * 3]},${LUT[q * 3 + 1]},${LUT[q * 3 + 2]})`;
      ctx.fillRect(bx, M.t + i, bw, 1.5);
    }
    ctx.fillStyle = pt.axis; ctx.textAlign = "left"; ctx.textBaseline = "top";
    ctx.font = `${Math.round(9.5 * s)}px "IBM Plex Sans", sans-serif`;
    ctx.fillText(`${Math.round(data.dbHi)}`, bx + bw + 2, M.t);
    ctx.textBaseline = "bottom";
    ctx.fillText(`${Math.round(data.dbLo)}`, bx + bw + 2, M.t + plotH);
    ctx.textBaseline = "middle";
    ctx.fillText("dB", bx + bw + 2, M.t + plotH / 2);
  }, [data, off, ext, size.w, size.h, theme, cursor, M, plotW, plotH, playMode, windowSec]);

  // interactions: drag = zoom time, wheel = zoom time, double-click = all, click = cursor, hover = read-out
  const toT = (clientX: number) => {
    const r = canvasRef.current!.getBoundingClientRect();
    return ext ? ext.x0 + ((clientX - r.left - M.l) / plotW) * (ext.x1 - ext.x0) : 0;
  };
  const [drag, setDrag] = useState<{ a: number; b: number } | null>(null);
  const onDown = (e: React.MouseEvent) => {
    actions.setActivePlot(index);
    if (!ext || e.button !== 0) return;
    const a = e.clientX;
    let moved = false;
    const move = (ev: MouseEvent) => { if (Math.abs(ev.clientX - a) > 4) { moved = true; setDrag({ a, b: ev.clientX }); } };
    const up = (ev: MouseEvent) => {
      window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up);
      setDrag(null);
      if (moved) {
        const x0 = toT(Math.min(a, ev.clientX)), x1 = toT(Math.max(a, ev.clientX));
        if (x1 > x0) actions.setRange(key, [x0, x1]);
      } else {
        const c = useApp.getState().cursor;
        useApp.setState({ cursor: { ...c, on: true, t1: toT(ev.clientX), active: 1 } });
      }
    };
    window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
  };
  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const wheel = (e: WheelEvent) => {
      if (!ext) return;
      e.preventDefault();
      const tv = toT(e.clientX), f = e.deltaY < 0 ? 0.8 : 1.25;
      actions.setRange(key, [tv - (tv - ext.x0) * f, tv + (ext.x1 - tv) * f]);
    };
    cv.addEventListener("wheel", wheel, { passive: false });
    return () => cv.removeEventListener("wheel", wheel);
  });
  const onMove = (e: React.MouseEvent) => {
    if (!data || !ext) return;
    const r = canvasRef.current!.getBoundingClientRect();
    const px = e.clientX - r.left - M.l, py = e.clientY - r.top - M.t;
    if (px < 0 || px > plotW || py < 0 || py > plotH) { setReadout(""); return; }
    const tv = ext.x0 + (px / plotW) * (ext.x1 - ext.x0);
    const f = ext.f1 - (py / plotH) * (ext.f1 - ext.f0);
    const ti = Math.round(((tv - tOff - data.t0) / ((data.t1 - data.t0) || 1)) * (data.nt - 1));
    const fi = Math.round(((f - data.f0) / ((data.f1 - data.f0) || 1)) * data.nf - 0.5);
    let db = "";
    if (ti >= 0 && ti < data.nt && fi >= 0 && fi < data.nf) {
      const raw = atob(data.img).charCodeAt(fi * data.nt + ti);
      db = ` · ${Math.round(data.dbLo + (raw / 255) * (data.dbHi - data.dbLo))} dB`;
    }
    setReadout(`t = ${fmtNum(tv, lang, 6)} · ${fmtNum(f, lang, 4)} Hz${db}`);
  };

  return (
    <div className="spec-wrap" ref={wrapRef}>
      <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block", cursor: "crosshair" }}
        onMouseDown={onDown} onMouseMove={onMove} onMouseLeave={() => setReadout("")}
        onDoubleClick={() => actions.setRange(key, null)} role="img"
        aria-label={t("spectrogramOf", { name: ps ? ps.sig.slice(ps.sig.indexOf("/") + 1) : "" })} />
      {drag && <div className="spec-sel" style={{ left: Math.min(drag.a, drag.b) - (canvasRef.current?.getBoundingClientRect().left ?? 0), width: Math.abs(drag.b - drag.a), top: M.t, height: plotH }} />}
      {readout && <div className="spec-read" dir="ltr">{readout}</div>}
      {err && <div className="plot-empty">{err}</div>}
      {plot.signals.length > 1 && <div className="spec-note">{t("specFirstOnly")}</div>}
    </div>
  );
}
