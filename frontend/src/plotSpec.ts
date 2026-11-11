import { rangeKey, signalName, useApp, type Plot, type Tab } from "./store";
import { lineLook, setpointsIn } from "./desired";
import { effectiveBase } from "./mapBase";
import { geoViewBounds } from "./globeBridge";
import { trackRequest } from "./mapObjects";
import { pairOf } from "./relation";

/** 1.26: why a plot is not in a report / replay page (listed with this reason, never dropped without a word) */
export type PageWhy = "pageWhyEmpty" | "pageWhyOcc" | "pageWhyVideo";
/** One rule for what goes into a page - the report (every format), the replay and the report panel's list. */
export function pagePlot(p: Plot): { include: boolean; why?: PageWhy } {
  const m = p.mode ?? "time";
  if (m === "occ") return { include: false, why: "pageWhyOcc" };        // needs a condition's stretches
  if (m === "video") return { include: false, why: "pageWhyVideo" };    // the video file is not put into the page
  if (m === "geo" || m === "3d") return (p.objects?.length || (m === "geo" && p.signals.length)) ? { include: true } : { include: false, why: "pageWhyEmpty" };
  return p.signals.length ? { include: true } : { include: false, why: "pageWhyEmpty" };
}
export const pagePlots = (tab: Tab) => tab.plots.map((p, pi) => ({ p, pi, ...pagePlot(p) }));

/** L11: a map with objects is drawn by the server as a map (app/mapimage.py): the objects' positions, the
 *  layer shown (an online one only from the tiles already cached), the cursor, and the view (`view`: what is
 *  shown now; else every track fitted). Without objects a map stays the lon-lat X-Y it always was. */
function geoSpec(plot: Plot, view: boolean) {
  const st = useApp.getState();
  return {
    objects: (plot.objects ?? []).map((o) => ({ name: o.name, color: o.color, lat: o.lat, lon: o.lon, alt: o.alt ?? null, track: o.track ?? null })),
    ...pairNames(plot),
    base: effectiveBase(st.geoBase, st.offlineOnly || st.offlineForced),
    cursor: st.cursor.on && st.cursor.t1 !== null ? st.cursor.t1 : null,
    bounds: view ? geoViewBounds.get(plot.id)?.() ?? null : null,
  };
}

/** The reference and the compared object by name (the offline pages' relation box starts on them). */
function pairNames(plot: Plot) {
  const { primary, secondary } = pairOf(plot), nameOf = (id?: string | null) => plot.objects?.find((o) => o.id === id)?.name ?? null;
  return { primary: nameOf(primary), secondary: nameOf(secondary) };
}

/** What the server needs to draw / export one plot (reports, images, CSV). `view`: a map as shown now. */
export function plotSpec(tab: Tab, plot: Plot, index: number, plotLabel: string, view = false) {
  const st = useApp.getState();
  // 1.26: the map seen in 3D - the server draws it (app/scene3d.py): a picture in PDF / Word / PNG, a live
  // three.js page in HTML. The objects as the 3D view fetches them (a borrowed attitude resolved).
  if (plot.mode === "3d" && plot.objects?.length) {
    const objs = plot.objects, nameOf = (id?: string | null) => objs.find((o) => o.id === id)?.name ?? null;
    return { title: plot.title || plotLabel.replace("{n}", String(index + 1)), caption: plot.caption || "", mode: "3d", signals: [], geo: geoSpec(plot, false),
      scene: { objects: objs.map((o) => trackRequest(o, objs)), follow: nameOf(plot.followObject), ...pairNames(plot) } };
  }
  if (plot.mode === "geo" && plot.objects?.length) {
    return { title: plot.title || plotLabel.replace("{n}", String(index + 1)), caption: plot.caption || "", mode: "geo", signals: [], geo: geoSpec(plot, view) };
  }
  const runs = st.runs;
  const range = st.ranges[rangeKey(tab, plot)] ?? null;
  const setpoints = setpointsIn(plot.signals);
  return {
    title: plot.title || plotLabel.replace("{n}", String(index + 1)),
    caption: plot.caption || "",
    mode: plot.mode === "geo" ? "xy" : (plot.mode ?? "time"),   // reports / images draw a map as lon-lat X-Y
    xSignal: plot.xSignal ?? null,
    xLabel: plot.xSignal ? signalName(runs, plot.xSignal, false) : "",
    xyAlign: plot.xyAlign ?? "linear",
    fftWindow: plot.fftWindow ?? "hanning",
    fftMethod: plot.fftMethod ?? "fft",
    fftLog: plot.fftLog ?? true,
    xyzEqual: plot.xyzEqual ?? true,
    xyzFlipZ: !!plot.xyzFlipZ,
    range,
    signals: plot.signals.map((s) => ({
      // N3: the line's style as drawn (by hand, or a setpoint dashed by itself) - time plots only
      ...((plot.mode ?? "time") === "time" && lineLook(s, setpoints).dashed ? { style: lineLook(s, setpoints).style } : {}),
      id: s.sig, label: s.label || signalName(runs, s.sig), color: s.color, width: s.width,
      scale: s.scale, offset: s.offset, state: !!s.state, tOffset: s.tOffset ?? 0, limits: s.limits ?? null,
      ...(s.axis === "right" ? { axis: "right" } : {}),
    })),
  };
}

/** Time range for exporting data: between the cursors, else what is shown, else everything. */
export function exportRange(tab: Tab, plot: Plot): [number, number] | null {
  const st = useApp.getState();
  const c = st.cursor;
  if (c.on && c.dual && c.t1 !== null && c.t2 !== null) return [Math.min(c.t1, c.t2), Math.max(c.t1, c.t2)];
  return st.ranges[rangeKey(tab, plot)] ?? null;
}
