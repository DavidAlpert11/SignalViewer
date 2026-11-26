/* CC22: what a time plot draws on its canvas besides the lines - the state lanes, the named conditions and What
   changed?'s marks, the events and notes along the top - as functions of what they draw (TimeChart.tsx passes its
   refs' current values), so the component keeps the plot's life cycle and its gestures. */
import type uPlot from "uplot";
import type { RunInfo } from "../api";
import type { PlotSignal } from "../store";
import { inkOn, labelsOf, labelText, stateColor } from "../values";
import { fmtNum } from "../i18n";
import { dpr, PLOT_THEME, uiScale, type ThemeName } from "./chartUtil";

export type StateMarks = Record<string, { points: [number, number | null][]; tooMany: boolean; end: number | null }>;

/** Height of one state lane (CSS px) when it shares the plot with ordinary lines. */
const LANE_H = 18;
/** Height of each of n bottom lanes in a plot this tall (CSS px): 18, smaller when they would take
 *  more than a quarter of the plot (the lines keep the rest), never under 8. */
export function laneCss(plotH: number, n: number): number {
  return Math.max(8, Math.min(LANE_H, (0.25 * plotH - 4) / Math.max(1, n) - 2));
}

/** A named condition shown on the plot: its stretches, its colour, whether it is the one in focus. */
export interface CondMark { color: string; focus: boolean; iv: [number, number][] }
/** "What changed?": where a signal of the plot first left its usual range. */
export interface ChangeMark { t: number; color: string }
/** An event of a log or a note (t2: a note over a time range). */
export interface LogMark { t: number; t2?: number; text: string; level: string }

/** Where each state lane is (device px): filling the plot when it has only states, else thin rows along its bottom. */
export function laneRows(u: uPlot, n: number, onlyStates: boolean): { y: number; h: number }[] {
  const { top, height } = u.bbox, d = dpr() * uiScale();
  if (onlyStates) {
    const gap = 6 * d, h = Math.min(56 * d, (height - gap * (n - 1)) / Math.max(1, n));
    return Array.from({ length: n }, (_, k) => ({ y: top + k * (h + gap), h }));
  }
  const h = laneCss(height / d, n) * d, gap = 2 * d;
  return Array.from({ length: n }, (_, k) => ({ y: top + height - (n - k) * (h + gap) + gap, h }));
}

/* named conditions: the one in focus shaded over the whole height; every other shown one a thin
   strip along the top, one under the other (they never hide the lines) */
export function drawCondsOn(u: uPlot, list: CondMark[], changes: ChangeMark[]): void {
  if (!list.length && !changes.length) return;
  const ctx = u.ctx, { left, top, width, height } = u.bbox, d = dpr() * uiScale();
  const x0 = u.scales.x.min!, x1 = u.scales.x.max!;
  ctx.save();
  ctx.beginPath(); ctx.rect(left, top, width, height); ctx.clip();
  let k = 0;
  for (const c of list) {
    const row = c.focus ? -1 : k++;
    for (const [a, b] of c.iv) {
      if (b < x0 || a > x1) continue;
      const xa = Math.max(left, u.valToPos(a, "x", true)), xb = Math.min(left + width, Math.max(u.valToPos(b, "x", true), u.valToPos(a, "x", true) + 2 * d));
      ctx.fillStyle = c.color;
      if (row < 0) {
        ctx.globalAlpha = 0.13; ctx.fillRect(xa, top, xb - xa, height);
        ctx.globalAlpha = 0.9; ctx.fillRect(xa, top, xb - xa, 3 * d);
      } else {
        ctx.globalAlpha = 0.85; ctx.fillRect(xa, top + row * 5 * d, xb - xa, 4 * d);
      }
    }
  }
  ctx.restore();
  // "What changed?": where each signal of this plot first left its usual range (dashed, its colour)
  if (changes.length) {
    ctx.save();
    ctx.beginPath(); ctx.rect(left, top, width, height); ctx.clip();
    ctx.setLineDash([5 * d, 4 * d]); ctx.lineWidth = 1.5 * d;
    for (const m of changes) {
      if (m.t < x0 || m.t > x1) continue;
      const x = u.valToPos(m.t, "x", true);
      ctx.strokeStyle = m.color; ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + height); ctx.stroke();
    }
    ctx.restore();
  }
}

export function drawLogMarksOn(u: uPlot, marks: LogMark[], theme: ThemeName): void {
  const pt = PLOT_THEME[theme];
  if (!marks.length) return;
  const ctx = u.ctx, { left, top, width, height } = u.bbox, d = dpr() * uiScale();
  const x0 = u.scales.x.min!, x1 = u.scales.x.max!;
  // T23: a note over a time range is a shaded span (its marker and text at the start)
  const noteCol = theme === "dark" ? "#6cb6ff" : "#0969da";
  for (const m of marks) {
    if (m.t2 === undefined || m.t2 < x0 || m.t > x1) continue;
    const a = Math.max(left, u.valToPos(m.t, "x", true)), b = Math.min(left + width, u.valToPos(m.t2, "x", true));
    if (b <= a) continue;
    ctx.save();
    ctx.globalAlpha = 0.1; ctx.fillStyle = noteCol; ctx.fillRect(a, top, b - a, height);
    ctx.globalAlpha = 0.5; ctx.strokeStyle = noteCol; ctx.lineWidth = Math.max(1, dpr());
    if (m.t2 <= x1) { const xe = Math.round(b) + 0.5; ctx.beginPath(); ctx.moveTo(xe, top); ctx.lineTo(xe, top + height); ctx.stroke(); }
    ctx.restore();
  }
  // events on the same pixels become one marker: texts joined, the most severe colour
  const rank = (l: string) => (l === "note" ? 3 : l === "error" ? 2 : l === "warning" ? 1 : 0);
  const vis: { t: number; text: string; level: string }[] = [];
  let lastX = -Infinity;
  for (const m of marks) {
    if (m.t < x0 || m.t > x1) continue;
    const px = u.valToPos(m.t, "x", true);
    const prev = vis[vis.length - 1];
    if (prev && px - lastX < 3 * d) {
      prev.text += " · " + m.text;
      if (rank(m.level) > rank(prev.level)) prev.level = m.level;
    } else { vis.push({ ...m }); lastX = px; }
  }
  if (!vis.length) return;
  ctx.save();
  ctx.beginPath(); ctx.rect(left, top, width, height); ctx.clip();
  ctx.font = `${Math.round(10.5 * d)}px "IBM Plex Sans", "IBM Plex Sans Hebrew", sans-serif`;
  ctx.textBaseline = "middle"; ctx.textAlign = "left";
  const xs = vis.map((m) => Math.round(u.valToPos(m.t, "x", true)) + 0.5);
  const font = ctx.font;
  vis.forEach((m, i) => {
    const x = xs[i];
    ctx.font = font;
    const col = m.level === "note" ? (theme === "dark" ? "#6cb6ff" : "#0969da")
      : m.level === "error" ? (theme === "dark" ? "#f47067" : "#cf222e") : m.level === "warning" ? pt.amber : pt.axis;
    ctx.strokeStyle = col; ctx.lineWidth = Math.max(1, dpr());
    ctx.globalAlpha = m.level === "info" ? 0.3 : m.level === "note" ? 0.8 : 0.55;
    ctx.setLineDash(m.level === "note" ? [] : [3 * d, 3 * d]);
    ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + height); ctx.stroke();
    ctx.setLineDash([]); ctx.globalAlpha = 1;
    ctx.fillStyle = col;
    ctx.beginPath(); ctx.moveTo(x - 5 * d, top); ctx.lineTo(x + 5 * d, top); ctx.lineTo(x, top + 7 * d); ctx.closePath(); ctx.fill();
    // the text, when there is room before the next marker
    const room = (i + 1 < xs.length ? xs[i + 1] : left + width) - x - 10 * d;
    if (room < 34 * d) return;
    let txt = m.text;
    const maxW = Math.min(room, 220 * d);
    if (ctx.measureText(txt).width > maxW) {
      while (txt.length > 2 && ctx.measureText(txt + "…").width > maxW) txt = txt.slice(0, -1);
      txt += "…";
    }
    const tw = ctx.measureText(txt).width;
    ctx.globalAlpha = 0.85; ctx.fillStyle = pt.bg; ctx.fillRect(x + 4 * d, top + 3 * d, tw + 8 * d, 14 * d);
    ctx.globalAlpha = 1; ctx.fillStyle = m.level === "info" ? pt.text : col;
    if (m.level === "note") ctx.font = `600 ${Math.round(10.5 * d)}px "IBM Plex Sans", "IBM Plex Sans Hebrew", sans-serif`;
    ctx.fillText(txt, x + 8 * d, top + 10 * d);
  });
  ctx.restore();
}

export function drawStatesOn(u: uPlot, o: { stateSigs: PlotSignal[]; onlyStates: boolean; marks: StateMarks; runs: RunInfo[];
  theme: ThemeName; hatch: { p: CanvasPattern | null } }): void {
  const { stateSigs, onlyStates, marks, runs, theme, hatch } = o;
  if (!stateSigs.length) return;
  const pt = PLOT_THEME[theme];
  const ctx = u.ctx, { left, width } = u.bbox, d = dpr() * uiScale();
  if (!hatch.p) {
    const c = document.createElement("canvas"); c.width = c.height = Math.round(8 * dpr());
    const g = c.getContext("2d")!;
    g.strokeStyle = pt.axis; g.globalAlpha = 0.55; g.lineWidth = dpr();
    g.beginPath(); g.moveTo(0, c.height); g.lineTo(c.width, 0); g.stroke();
    hatch.p = ctx.createPattern(c, "repeat");
  }
  const lanes = laneRows(u, stateSigs.length, onlyStates);
  ctx.save();
  ctx.beginPath(); ctx.rect(left, u.bbox.top, width, u.bbox.height); ctx.clip();
  ctx.textBaseline = "middle";
  ctx.textAlign = "left";                  // uPlot leaves its axis alignment on the context
  stateSigs.forEach((s, k) => {
    const m = marks[s.sig];
    const { y, h } = lanes[k];
    if (!onlyStates) { ctx.fillStyle = pt.bg; ctx.globalAlpha = 0.85; ctx.fillRect(left, y, width, h); ctx.globalAlpha = 1; }
    if (!m || !m.points.length) return;
    const labels = labelsOf(runs, s.sig);
    ctx.font = `${Math.round((onlyStates ? 12 : 11) * d)}px "IBM Plex Sans", "IBM Plex Sans Hebrew", sans-serif`;
    const pts = m.points;
    for (let i = 0; i < pts.length; i++) {
      const [t0, v] = pts[i];
      const t1 = i + 1 < pts.length ? pts[i + 1][0] : (m.end ?? t0);
      let x0 = u.valToPos(t0, "x", true), x1 = u.valToPos(t1, "x", true);
      if (x1 < left || x0 > left + width) continue;
      x0 = Math.max(left - 1, x0); x1 = Math.min(left + width + 1, x1);
      const w = Math.max(1, x1 - x0);
      if (v === null) {                       // too many changes here to draw one by one
        ctx.fillStyle = hatch.p ?? pt.grid; ctx.fillRect(x0, y, w, h);
        continue;
      }
      const col = stateColor(v, theme);
      ctx.fillStyle = col; ctx.fillRect(x0, y, w, h);
      ctx.fillStyle = pt.bg; ctx.fillRect(Math.round(x0), y, Math.max(1, Math.round(dpr())), h);   // separator
      const txt = labelText(labels, v) ?? (Number.isInteger(v * s.scale + s.offset) ? String(v * s.scale + s.offset) : fmtNum(v * s.scale + s.offset, "en", 4));
      const room = w - 8 * d;
      if (room < 10 * d || h < 11 * d) continue;       // too small for a word: the colour alone
      let shown = txt;
      if (ctx.measureText(shown).width > room) {
        while (shown.length > 1 && ctx.measureText(shown + "…").width > room) shown = shown.slice(0, -1);
        shown += "…";
        if (shown.length < 3) continue;
      }
      ctx.fillStyle = inkOn(col);
      const tw = ctx.measureText(shown).width;
      const cx = Math.min(Math.max(x0 + w / 2, left + tw / 2 + 4 * d), left + width - tw / 2 - 4 * d);
      ctx.fillText(shown, cx - tw / 2, y + h / 2 + 0.5);
    }
    // which signal this lane is: its colour along the left edge (and its name when lanes fill the plot)
    ctx.fillStyle = s.color; ctx.fillRect(left, y, 3 * d, h);
    if (onlyStates) {
      const nm = s.label || s.sig.slice(s.sig.indexOf("/") + 1);
      ctx.font = `600 ${Math.round(10.5 * d)}px "IBM Plex Sans", "IBM Plex Sans Hebrew", sans-serif`;
      const tw = ctx.measureText(nm).width;
      ctx.fillStyle = pt.bg; ctx.globalAlpha = 0.82;
      ctx.fillRect(left + 3 * d, y, tw + 10 * d, 15 * d); ctx.globalAlpha = 1;
      ctx.fillStyle = pt.text; ctx.textBaseline = "middle";
      ctx.fillText(nm, left + 8 * d, y + 7.5 * d);
    }
  });
  ctx.restore();
  /* thin lanes under lines: the name in the margin left of the lane, never over the data - drawn
     over the plot it hid the last stretch of the state, which then looked like one more state
     with an unclear text. The value axis has no meaning beside the lanes (the lines are above). */
  if (!onlyStates) {
    ctx.save();
    ctx.textBaseline = "middle"; ctx.textAlign = "right";
    stateSigs.forEach((s, k) => {
      const { y, h } = lanes[k];
      const room = left - 6 * d;
      if (room < 16 * d) return;
      ctx.fillStyle = pt.bg; ctx.fillRect(0, y - d, left - 1, h + 2 * d);
      ctx.font = `${Math.round(Math.min(10, Math.max(8, h / d - 4)) * d)}px "IBM Plex Sans", "IBM Plex Sans Hebrew", sans-serif`;
      let nm = s.label || s.sig.slice(s.sig.indexOf("/") + 1);
      if (ctx.measureText(nm).width > room) {
        while (nm.length > 1 && ctx.measureText(nm + "…").width > room) nm = nm.slice(0, -1);
        nm += "…";
      }
      ctx.fillStyle = pt.axis;
      ctx.fillText(nm, left - 4 * d, y + h / 2 + 0.5);
    });
    ctx.restore();
  }
}
