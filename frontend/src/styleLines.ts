import { TRACE_COLORS, type LineStyle, type PlotSignal, type Workspace } from "./store/model";
import { activeTab } from "./store/selectors";

/** N4: style a whole group of signals at once - which lines a scope hits, and the one change. */
export type StyleScope = "plot" | "tab" | "all";
export interface LineRef { plotId: string; sig: string }
/** What to change; a field left out stays as each line has it. `color: "palette"` gives each line its
 *  own colour from the palette (in order), `lineStyle: "auto"` hands the line back to automatic. */
export interface LineLook { color?: string | "palette"; width?: number; lineStyle?: LineStyle | "auto" }

/** The lines of these signals the scope reaches: the active plot of the active tab ("plot"), every
 *  plot of the active tab ("tab"), or every plot of every tab ("all") - in the order they are drawn. */
export function linesInScope(ws: Workspace, sigs: string[], scope: StyleScope): LineRef[] {
  const want = new Set(sigs);
  const tab = activeTab(ws);
  const plots = scope === "all" ? ws.tabs.flatMap((t) => t.plots)
    : scope === "tab" ? tab.plots
    : tab.plots[tab.active] ? [tab.plots[tab.active]] : [];
  const out: LineRef[] = [];
  for (const p of plots) for (const s of p.signals) if (want.has(s.sig)) out.push({ plotId: p.id, sig: s.sig });
  return out;
}

/** The scope a group's dialog opens with: the narrowest one that reaches any of its lines. */
export function defaultScope(ws: Workspace, sigs: string[]): StyleScope {
  if (linesInScope(ws, sigs, "plot").length) return "plot";
  if (linesInScope(ws, sigs, "tab").length) return "tab";
  return "all";
}

/** One line with the look applied (the i-th of the batch, for the palette). */
export function restyle(s: PlotSignal, look: LineLook, i: number): PlotSignal {
  const n: PlotSignal = { ...s };
  if (look.color === "palette") n.color = TRACE_COLORS[i % TRACE_COLORS.length];
  else if (look.color) n.color = look.color;
  if (look.width !== undefined && Number.isFinite(look.width)) n.width = Math.max(0.5, Math.min(6, look.width));
  if (look.lineStyle !== undefined) {
    // the same writing as the Inspector: Solid / Dashed keep the old `dash`, Dotted / Dash-dot `lineStyle`
    delete n.lineStyle; delete n.dash;
    if (look.lineStyle === "solid" || look.lineStyle === "dash") n.dash = look.lineStyle === "dash";
    else if (look.lineStyle !== "auto") n.lineStyle = look.lineStyle;
  }
  return n;
}

const same = (a: PlotSignal, b: PlotSignal) =>
  a.color === b.color && a.width === b.width && a.lineStyle === b.lineStyle && a.dash === b.dash;

/** The workspace with the look applied to these lines; `changed` counts the lines that differ (0 = leave
 *  the history alone). Palette colours follow the order of `targets`. */
export function applyLook(ws: Workspace, targets: LineRef[], look: LineLook): { ws: Workspace; changed: number } {
  const key = (r: LineRef) => `${r.plotId}\u0000${r.sig}`;
  const order = new Map(targets.map((r, i) => [key(r), i]));
  let changed = 0;
  for (const t of ws.tabs) for (const p of t.plots) {
    p.signals = p.signals.map((s) => {
      const i = order.get(key({ plotId: p.id, sig: s.sig }));
      if (i === undefined) return s;
      const n = restyle(s, look, i);
      if (!same(n, s)) changed++;
      return n;
    });
  }
  return { ws, changed };
}
