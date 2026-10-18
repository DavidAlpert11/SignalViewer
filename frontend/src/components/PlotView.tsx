import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { plotHasContent, actions, pickPath, signalName, useApp, type Plot, type PlotMode, type Tab } from "../store";
import { fmtNum, translate, useT } from "../i18n";
import { api } from "../api";
import { exportRange, plotSpec } from "../plotSpec";
import { unitOf, withUnit } from "../units";
import { labelsOf, labelText } from "../values";
import { Icon } from "../icons";
import TimeChart from "./TimeChart";
import SignalPicker from "./SignalPicker";
import { createSignalItem } from "../createSignalMenu";
import XYChart from "./XYChart";
import GeoChart from "./GeoChart";
import { iconSvg } from "./mapIcons";
// the 3D view (CesiumJS, a few MB) loads only when a plot is switched to 3D
const Globe3D = lazy(() => import("./Globe3D"));
const VideoView = lazy(() => import("./VideoView"));
import FFTChart from "./FFTChart";
import EnvelopeChart from "./EnvelopeChart";
import XYZChart from "./XYZChart";
import SpecChart from "./SpecChart";
import PlotBoundary from "./PlotBoundary";

export const SIGNAL_MIME = "application/x-sv-signal";
export const CHIP_MIME = "application/x-sv-chip";      // a chip dragged from a plot legend
import { openMenu } from "./Overlays";

interface Props { tab: Tab; plot: Plot; index: number; active: boolean }

export default function PlotView({ tab, plot, index, active }: Props) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const cursor = useApp((s) => s.cursor);
  const cvals = useApp((s) => s.cvals);
  const selected = useApp((s) => s.selected);
  const multi = useApp((s) => s.multi);
  const hover = useApp((s) => (s.hover && s.hover.plotId === plot.id ? s.hover : null));
  const [dragOver, setDragOver] = useState<null | "y" | "x" | "right" | "bottom">(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [loading, setLoading] = useState(false);
  const [peaks, setPeaks] = useState<Record<string, number>>({});
  const [menu, setMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const moreRef = useRef<HTMLButtonElement>(null);
  // F17: the plot menu closes like every other menu - Esc, a click anywhere else, the window losing
  // focus (it closed only when the mouse entered it and left again, so by keyboard never)
  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(false);
    const outside = (e: MouseEvent) => {
      const n = e.target as Node;
      if (!menuRef.current?.contains(n) && !moreRef.current?.contains(n)) close();
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); close(); moreRef.current?.focus(); } };
    window.addEventListener("mousedown", outside, true);
    window.addEventListener("keydown", onKey, true);
    window.addEventListener("blur", close);
    menuRef.current?.querySelector<HTMLButtonElement>("button:not(:disabled)")?.focus();
    return () => { window.removeEventListener("mousedown", outside, true); window.removeEventListener("keydown", onKey, true); window.removeEventListener("blur", close); };
  }, [menu]);
  const theme = useApp((s) => s.theme);
  const sectionRef = useRef<HTMLElement>(null);

  const done = (path: string) => useApp.getState().toast({ kind: "info", text: translate(lang, "savedTo", { path }) });
  const failed = (e: unknown) => useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
  const baseName = (plot.title || t("plotTitle", { n: index + 1 })).replace(/[\\/:*?"<>|]+/g, "_");
  const chipMenu = (e: React.MouseEvent, sig: string) => {
    const i = plot.signals.findIndex((x) => x.sig === sig);
    const ps = plot.signals[i];
    openMenu(e, [
      { label: t("properties"), run: () => useApp.setState({ selected: { plotId: plot.id, sig }, inspectorOpen: true }) },
      { label: ps.state ? t("asLine") : t("asStates"), run: () => actions.updateSignal(plot.id, sig, { state: !ps.state }) },
      ...(ps.state || labelsOf(runs, sig) ? [{
        label: (tab.sharedStates ?? []).includes(sig) ? t("lanesSharedOff") : t("lanesSharedOn"),
        run: () => actions.toggleSharedState(sig) }] : []),
      { label: "", run: () => {}, sep: true },
      { label: t("moveUp"), run: () => actions.moveSignal(plot.id, sig, -1), disabled: i === 0 },
      { label: t("moveDown"), run: () => actions.moveSignal(plot.id, sig, 1), disabled: i === plot.signals.length - 1 },
      { label: t("duplicateNewPlot"), run: () => actions.duplicateToNewPlot(plot.id, sig) },
      { label: t("useAsX"), run: () => actions.setAsX(plot.id, sig) },
      { label: "", run: () => {}, sep: true },
      createSignalItem(sig, plot.id),
      { label: "", run: () => {}, sep: true },
      { label: t("remove"), run: () => actions.removeSignal(plot.id, sig), danger: true },
    ]);
  };
  const exportCsv = async () => {
    setMenu(false);
    const path = await pickPath({ mode: "save", title: t("exportData"), exts: [".csv"], defaultName: `${baseName}.csv` });
    if (!path) return;
    const r = exportRange(tab, plot);
    try {
      const res = await api.exportCsv(path, plot.signals.map((s) => ({ id: s.sig, label: s.label || signalName(runs, s.sig), scale: s.scale, offset: s.offset, tOffset: s.tOffset ?? 0 })),
        r?.[0] ?? null, r?.[1] ?? null);
      done(res.path);
    } catch (e) { failed(e); }
  };
  const saveImage = async (format: "png" | "svg") => {
    setMenu(false);
    const path = await pickPath({ mode: "save", title: t("saveImage"), exts: [`.${format}`], defaultName: `${baseName}.${format}` });
    if (!path) return;
    try { done((await api.image(path, format, theme, plotSpec(tab, plot, index, t("plotTitle", { n: "{n}" })))).path); } catch (e) { failed(e); }
  };
  const copyImage = async () => {
    setMenu(false);
    const canvas = sectionRef.current?.querySelector("canvas");
    if (!canvas) return;
    try {
      const blob: Blob = await new Promise((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej(new Error("No image"))), "image/png"));
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      useApp.getState().toast({ kind: "info", text: t("copied") });
    } catch { useApp.getState().toast({ kind: "error", text: t("copyFailed") }); }
  };
  const mode: PlotMode = plot.mode ?? "time";
  const allSignals = runs.flatMap((r) => r.signals.map((s) => ({ id: s.id, label: s.name, group: r.format === "derived" ? undefined : r.name })));

  // T20: dropping on a plot's right or bottom edge splits it (a new plot there with the signal)
  const edgeOf = (e: React.DragEvent): "right" | "bottom" | null => {
    const r = sectionRef.current?.getBoundingClientRect();
    if (!r) return null;
    const rtl = document.documentElement.dir === "rtl";
    const fromEnd = rtl ? e.clientX - r.left : r.right - e.clientX;
    if (fromEnd < Math.min(48, r.width * 0.15)) return "right";
    if (r.bottom - e.clientY < Math.min(40, r.height * 0.15)) return "bottom";
    return null;
  };
  const onDrop = (e: React.DragEvent, target: "x" | "y" | "right" | "bottom", beforeSig: string | null = null) => {
    setDragOver(null);
    const chip = e.dataTransfer.getData(CHIP_MIME);
    if (chip) {
      e.preventDefault(); e.stopPropagation();
      const { plotId, sig } = JSON.parse(chip);
      if (target === "right" || target === "bottom") actions.splitPlot(plot.id, sig, target, e.ctrlKey || e.altKey ? undefined : plotId);
      else if (target === "x") actions.setAsX(plot.id, sig);
      else actions.dropSignal(plotId, sig, plot.id, beforeSig, e.ctrlKey || e.altKey);
      return;
    }
    const sig = e.dataTransfer.getData(SIGNAL_MIME);
    if (!sig) return;
    e.preventDefault();
    e.stopPropagation();
    if (target === "x") actions.updatePlot(plot.id, { xSignal: sig });
    else if (target === "right" || target === "bottom") actions.splitPlot(plot.id, sig, target);
    else actions.addSignalLinked(sig, plot.id);
  };

  const title = plot.title || t("plotTitle", { n: index + 1 });
  const geoBase = useApp((s) => s.geoBase);
  const modes: [PlotMode, string][] = [["time", t("modeTime")], ["xy", "X-Y"], ["xyz", t("modeXyz")], ["geo", t("modeGeo")], ["3d", t("mode3d")], ["fft", "FFT"], ["spec", t("modeSpec")], ["env", t("modeEnv")], ["video", t("modeVideo")]];

  return (
    <section
      ref={sectionRef}
      className={`plot${active ? " active" : ""}${dragOver ? " dragover" : ""}${dragOver === "right" || dragOver === "bottom" ? ` split-${dragOver}` : ""}`}
      onDragOver={(e) => { if (e.dataTransfer.types.includes(SIGNAL_MIME) || e.dataTransfer.types.includes(CHIP_MIME)) { e.preventDefault(); setDragOver(edgeOf(e) ?? "y"); } }}
      onDragLeave={() => setDragOver(null)}
      onDrop={(e) => onDrop(e, edgeOf(e) ?? "y")}
      onMouseDown={() => actions.setActivePlot(index)}
      aria-label={title}
    >
      <header className="plot-head">
        {editingTitle ? (
          <input className="plot-title" autoFocus defaultValue={plot.title} placeholder={title}
            onBlur={(e) => { actions.renamePlot(plot.id, e.target.value.trim()); setEditingTitle(false); }}
            onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); if (e.key === "Escape") setEditingTitle(false); }} />
        ) : (
          <button className="plot-title" onDoubleClick={() => setEditingTitle(true)} title={title}>{title}</button>
        )}
        <span className="seg mode-seg" role="group" aria-label={t("plotMode")}>
          {modes.map(([m, label]) => (
            <button key={m} className={mode === m ? "on" : ""} aria-pressed={mode === m} onClick={() => actions.setPlotMode(plot.id, m)}>{label}</button>
          ))}
        </span>
        {(mode === "xy" || mode === "geo") && (
          <span className={`xpick${dragOver === "x" ? " over" : ""}`}
            onDragOver={(e) => { if (e.dataTransfer.types.includes(SIGNAL_MIME) || e.dataTransfer.types.includes(CHIP_MIME)) { e.preventDefault(); e.stopPropagation(); setDragOver("x"); } }}
            onDrop={(e) => onDrop(e, "x")}>
            <label>{mode === "geo" ? t("geoLon") : "X"}</label>
            <SignalPicker compact value={plot.xSignal ?? null} options={allSignals} ariaLabel={mode === "geo" ? t("geoLon") : t("xSignal")}
              onChange={(id) => actions.updatePlot(plot.id, { xSignal: id })} />
            {mode === "geo" && <>
              <label>{t("geoLat")}</label>
              <SignalPicker compact value={plot.signals[0]?.sig ?? null} options={allSignals} ariaLabel={t("geoLat")}
                onChange={(id) => actions.setGeoLat(plot.id, id)} />
            </>}
            <select value={plot.xyAlign ?? "linear"} onChange={(e) => actions.updatePlot(plot.id, { xyAlign: e.target.value as "linear" | "nearest" })} aria-label={t("alignment")} title={t("alignment")}>
              <option value="linear">{t("alignLinear")}</option>
              <option value="nearest">{t("alignNearest")}</option>
            </select>
          </span>
        )}
        {mode === "fft" && (
          <span className="xpick">
            <select value={plot.fftMethod ?? "fft"} onChange={(e) => actions.updatePlot(plot.id, { fftMethod: e.target.value as Plot["fftMethod"] })} aria-label={t("fftMethod")} title={t("fftMethodHint")}>
              <option value="fft">FFT</option><option value="welch">{t("fftWelch")}</option>
            </select>
            <select value={plot.fftWindow ?? "hanning"} onChange={(e) => actions.updatePlot(plot.id, { fftWindow: e.target.value as Plot["fftWindow"] })} aria-label={t("fftWindow")} title={t("fftWindow")}>
              <option value="hanning">Hann</option><option value="hamming">Hamming</option>
              <option value="blackman">Blackman</option><option value="none">{t("noWindow")}</option>
            </select>
            <button className="btn" aria-pressed={plot.fftLog ?? true} onClick={() => actions.updatePlot(plot.id, { fftLog: !(plot.fftLog ?? true) })}>{t("logScale")}</button>
            <OrderPicker plot={plot} />
          </span>
        )}
        {mode === "xyz" && (
          <span className="xpick">
            <button className="btn sm" aria-pressed={plot.xyzEqual !== false} title={t("xyzEqualHint")}
              onClick={() => actions.updatePlot(plot.id, { xyzEqual: plot.xyzEqual === false })}>{t("xyzEqual")}</button>
            <button className="btn sm" aria-pressed={!!plot.xyzFlipZ} title={t("xyzFlipZHint")}
              onClick={() => actions.updatePlot(plot.id, { xyzFlipZ: !plot.xyzFlipZ })}>{t("xyzFlipZ")}</button>
            <button className="btn sm obj-add" disabled={plot.signals.length < 3} title={t("placeHint")}
              onClick={() => useApp.setState({ placeDialog: plot.id })}>{t("placeBtn")}</button>
          </span>
        )}
        {(mode === "geo" || mode === "3d") && (
          <span className="xpick">
            <select value={geoBase} onChange={(e) => useApp.setState({ geoBase: e.target.value as typeof geoBase })}
              aria-label={t("geoLayer")} title={t("geoLayerHint")}>
              {(["auto", "osm", "esri", "light", "dark", "satellite", "topo", "offline"] as const).map((b) =>
                <option key={b} value={b}>{t(`geo_${b}` as "geo_auto")}</option>)}
            </select>
            {/* objects: things that move, drawn at the timeline's time */}
            <button className="btn sm obj-add" onClick={() => useApp.setState({ objectDialog: { plotId: plot.id } })} title={t("objAddHint")}>
              + {t("objAdd")}</button>
          </span>
        )}
        {(mode === "geo" || mode === "3d") && (plot.objects?.length ?? 0) > 0 && (
          <span className="obj-chips" role="list" aria-label={t("objects")}>
            {plot.objects!.map((o) => (
              <span key={o.id} className="obj-chip" role="listitem">
                <button className="obj-chip-main" onClick={() => useApp.setState({ objectDialog: { plotId: plot.id, objectId: o.id } })} title={t("objEdit")}>
                  <img src={iconSvg(o.kind, o.color)} alt="" width={16} height={16} />{o.name}
                </button>
                <button className={`iconbtn sm${plot.followObject === o.id ? " on" : ""}`} aria-pressed={plot.followObject === o.id}
                  title={t("objFollow")} aria-label={`${t("objFollow")}: ${o.name}`}
                  onClick={() => actions.updatePlot(plot.id, { followObject: plot.followObject === o.id ? null : o.id })}>
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="7" /><circle cx="12" cy="12" r="2" fill="currentColor" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></svg>
                </button>
                <button className="iconbtn sm" aria-label={`${t("remove")}: ${o.name}`} title={t("remove")} onClick={() => actions.removeObject(plot.id, o.id)}>×</button>
              </span>
            ))}
          </span>
        )}
        {mode === "spec" && (
          <span className="xpick">
            <select value={plot.specN ?? 1024} onChange={(e) => actions.updatePlot(plot.id, { specN: Number(e.target.value) })}
              aria-label={t("specWindow")} title={t("specWindowHint")}>
              {[128, 256, 512, 1024, 2048, 4096, 8192].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
            <select value={plot.specFmax ?? ""} onChange={(e) => actions.updatePlot(plot.id, { specFmax: e.target.value ? Number(e.target.value) : null })}
              aria-label={t("specFmax")} title={t("specFmax")}>
              <option value="">{t("specAllFreq")}</option>
              {[10, 25, 50, 100, 200, 500, 1000].map((f) => <option key={f} value={f}>≤ {f} Hz</option>)}
            </select>
          </span>
        )}
        {hover && mode === "time" && <span className="hover-t" title={t("hoverValue")}>t = {fmtNum(hover.t, lang, 7)}</span>}
        <div className="legend">
          {plot.signals.map((s) => {
            const inMulti = multi.some((m) => m.plotId === plot.id && m.sig === s.sig);
            const sel = (selected?.plotId === plot.id && selected.sig === s.sig) || inMulti;
            const raw = cvals[s.sig]?.[0];
            let val: string | null = null;
            const unit = unitOf(s.label || s.sig.slice(s.sig.indexOf("/") + 1));
            let hv = false;
            if (mode === "fft") val = Number.isFinite(peaks[s.sig]) ? `${fmtNum(peaks[s.sig], lang, 4)} Hz` : null;
            const labels = labelsOf(runs, s.sig);
            const plain = s.scale === 1 && s.offset === 0;
            if (mode === "fft") { /* peak above */ }
            else if (cursor.on && raw !== undefined && raw !== null) val = (plain && labelText(labels, raw)) || withUnit(fmtNum(raw * s.scale + s.offset, lang), unit);
            else if (hover && mode === "time" && hover.vals[s.sig] !== null && hover.vals[s.sig] !== undefined) {
              const hvv = hover.vals[s.sig] as number;     // already scaled
              val = (plain && labelText(labels, hvv)) || withUnit(fmtNum(hvv, lang), unit); hv = true;
            }
            return (
              <span key={s.sig} className={`chip${sel ? " sel" : ""}`} role="button" tabIndex={0} draggable
                title={t("chipHint")}
                onDragStart={(e) => { e.dataTransfer.setData(CHIP_MIME, JSON.stringify({ plotId: plot.id, sig: s.sig })); e.dataTransfer.effectAllowed = "copyMove"; }}
                onDragOver={(e) => { if (e.dataTransfer.types.includes(CHIP_MIME)) { e.preventDefault(); e.stopPropagation(); } }}
                onDrop={(e) => onDrop(e, "y", s.sig)}
                onContextMenu={(e) => chipMenu(e, s.sig)}
                onClick={(e) => {
                  const me = { plotId: plot.id, sig: s.sig };
                  if (e.ctrlKey || e.metaKey) {      // multi-select for batch editing
                    const st = useApp.getState();
                    const base = st.multi.length ? st.multi : st.selected ? [st.selected] : [];
                    const next = inMulti || (st.selected?.plotId === me.plotId && st.selected.sig === me.sig && !st.multi.length)
                      ? base.filter((m) => !(m.plotId === me.plotId && m.sig === me.sig)) : [...base, me];
                    useApp.setState({ multi: next, selected: next.length === 1 ? next[0] : st.selected, inspectorOpen: true });
                  } else useApp.setState({ selected: me, multi: [], inspectorOpen: true });
                }}
                onKeyDown={(e) => { if (e.key === "Delete") actions.removeSignal(plot.id, s.sig); }}>
                <span className="sw" style={{ background: s.color }} />
                <span className="nm">{s.label || signalName(runs, s.sig)}</span>
                {s.state && mode === "time" && <span className="tag">{t("stateTag")}</span>}
                {val && <span className={`val${hv ? " hov" : ""}`} title={mode === "fft" ? t("peak") : hv ? t("hoverValue") : undefined}>{val}</span>}
                <span className="rm" role="button" aria-label={t("remove")}
                  onClick={(e) => { e.stopPropagation(); actions.removeSignal(plot.id, s.sig); }}><Icon.X width={11} height={11} /></span>
              </span>
            );
          })}
        </div>
        <button ref={moreRef} className="iconbtn plot-more" aria-haspopup="menu" aria-label={t("plotMenu")} title={t("plotMenu")} aria-expanded={menu}
          onClick={(e) => { e.stopPropagation(); setMenu(!menu); }}><Icon.More /></button>
        {menu && (
          <div className="menu" role="menu" ref={menuRef}>
            <button role="menuitem" disabled={!plot.signals.length} onClick={exportCsv}><Icon.Table />{t("exportData")}</button>
            <button role="menuitem" disabled={!plot.signals.length} onClick={() => saveImage("png")}><Icon.Image />{t("saveImage")} (PNG)</button>
            <button role="menuitem" disabled={!plot.signals.length} onClick={() => saveImage("svg")}><Icon.Image />{t("saveImage")} (SVG)</button>
            <button role="menuitem" disabled={!plot.signals.length} onClick={copyImage}><Icon.Copy />{t("copyImage")}</button>
            <div className="menu-sep" />
            <button role="menuitem" onClick={() => { setMenu(false); useApp.setState({ axisDialog: plot.id }); }}><Icon.Layout />{t("axisLimits")}{(plot.xlim || plot.ylim) ? " •" : ""}</button>
            <button role="menuitem" disabled={!plotHasContent(plot) && !plot.xSignal} onClick={() => { setMenu(false); actions.clearPlot(plot.id); }}><Icon.Trash />{t("clearPlot")}</button>
            {mode === "3d" && <button role="menuitem" onClick={() => { setMenu(false); actions.remove3d(plot.id); }}><Icon.Trash />{t("g3Remove")}</button>}
          </div>
        )}
      </header>
      <div className="plot-body">
        <PlotBoundary label={t("plotFailed")} retry={t("tryAgain")} resetKey={`${mode}|${plot.signals.map((x) => x.sig).join(",")}|${plot.xSignal ?? ""}`}>
          {mode === "time" && <TimeChart tab={tab} plot={plot} index={index} onLoading={setLoading} />}
          {mode === "xy" && <XYChart plot={plot} index={index} onLoading={setLoading} emptyText={!plot.xSignal ? t("xyNeedsX") : t("emptyPlot")} />}
          {mode === "3d" && <Suspense fallback={<div className="plot-empty">{t("globeLoading")}</div>}>
            <Globe3D plot={plot} index={index} onLoading={setLoading} emptyText={t("globeNeedsObject")} /></Suspense>}
          {mode === "geo" && <GeoChart plot={plot} index={index} onLoading={setLoading} emptyText={!plot.xSignal ? t("geoNeedsLon") : t("emptyPlot")} notDegrees={t("geoNotDegrees")} />}
          {mode === "env" && <EnvelopeChart plot={plot} index={index} onLoading={setLoading} />}
          {mode === "xyz" && <XYZChart plot={plot} index={index} onLoading={setLoading} emptyText={t("xyzNeedsThree")} />}
          {mode === "fft" && <FFTChart plot={plot} index={index} onLoading={setLoading} onPeaks={setPeaks} />}
          {mode === "spec" && <SpecChart tab={tab} plot={plot} index={index} onLoading={setLoading} />}
          {mode === "video" && <Suspense fallback={null}><VideoView plot={plot} /></Suspense>}
        </PlotBoundary>
        {!plot.signals.length && mode !== "xy" && mode !== "geo" && mode !== "3d" && mode !== "xyz" && mode !== "video" && <div className="plot-empty">{t("emptyPlot")}</div>}
        {loading && <div className="plot-loading">{t("loading")}</div>}
      </div>
    </section>
  );
}

/** T16b: which rotation signal (RPM / ESC / motor speed of the plotted files) marks the spectrum
 *  with its 1x / 2x / 3x orders, and how many blades (the blade-pass frequency). */
function OrderPicker({ plot }: { plot: Plot }) {
  const t = useT();
  const runs = useApp((s) => s.runs);
  const ord = plot.fftOrders;
  const rids = new Set(plot.signals.map((s) => s.sig.split("/")[0]));
  const cands = runs.filter((r) => rids.has(r.id) || r.id === ord?.sig.split("/")[0]).flatMap((r) => r.signals
    .filter((s) => !s.labels && (ORDER_NAME.test(s.name) || s.id === ord?.sig)).map((s) => ({ id: s.id, name: s.name })));
  if (!cands.length && !ord) return null;
  const unitOf = (name: string): "rpm" | "hz" => (/rpm|rev.?min|\[1\/min\]/i.test(name) ? "rpm" : "hz");
  return <>
    <select value={ord?.sig ?? ""} aria-label={t("fftOrders")} title={t("fftOrdersHint")}
      onChange={(e) => {
        const c = cands.find((x) => x.id === e.target.value);
        actions.updatePlot(plot.id, { fftOrders: c ? { sig: c.id, unit: unitOf(c.name), blades: ord?.blades } : undefined });
      }}>
      <option value="">{t("fftOrdersOff")}</option>
      {cands.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
    </select>
    {ord && <select value={ord.blades ?? 0} aria-label={t("fftBlades")} title={t("fftBlades")}
      onChange={(e) => actions.updatePlot(plot.id, { fftOrders: { ...ord, blades: Number(e.target.value) || undefined } })}>
      <option value={0}>{t("fftNoBlades")}</option>
      {[2, 3, 4, 5].map((b) => <option key={b} value={b}>{t("fftBladesN", { n: b })}</option>)}
    </select>}
  </>;
}
/** Names that are a rotation rate: RPM, ESC telemetry, motor / rotor / propeller speed. */
const ORDER_NAME = /rpm|^esc[^.]*\.(rpm|erpm)|motor.*(speed|rate)|rotor.*(speed|rate)|prop.*(speed|rate)/i;
