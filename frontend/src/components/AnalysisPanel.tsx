import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { showFileTags, actions, activeTab, useApp } from "../store";
import { useT, type TKey } from "../i18n";
import { Icon } from "../icons";
import SignalPicker from "./SignalPicker";
import FormulaInput from "./FormulaInput";
import MultiSignalPicker from "./MultiSignalPicker";
import { resolveFormula } from "../formulaRefs";
import { clearAllEdits, deleteAllDerived, editInPlace, opToStep } from "../transforms";
import { AXES, createFrameGroup, frameGroupName, suggestFrames, type Frame, type FrameSuggestion, type Qty } from "../frames";
import { groupDerived, memberLabel } from "../signalGroups";
import { rangeKey, type PreviewLine } from "../store";
import { PREVIEW_DASH } from "./chartUtil";
import PyOpsSection, { type PyChoice } from "./PyOpsSection";
import ErrorSegments from "./ErrorSegments";

type Kind = "one" | "two" | "many" | "fx" | "frame" | "py";   // py: the user's own Python operations (T31)
const UNARY: [string, TKey][] = [
  ["derivative", "opDerivative"], ["integral", "opIntegral"], ["abs", "opAbs"], ["negate", "opNegate"],
  ["normalize", "opNormalize"], ["affine", "opAffine"], ["smooth", "opSmooth"], ["rms", "opRms"], ["lowpass", "opLowpass"], ["highpass", "opHighpass"],
];
const BINARY: [string, string][] = [["sub", "A − B"], ["add", "A + B"], ["mul", "A × B"], ["div", "A ÷ B"], ["absdiff", "|A − B|"]];
const MULTI: [string, TKey][] = [["mean", "opMean"], ["sum", "opSum"], ["min", "opMin"], ["max", "opMax"], ["norm", "opNorm"]];
// Frame conversion (svcore/analysis.py "frame"): one derived signal per output axis, the three
// made as one nested group (frames.ts). A vector (velocity...) only rotates; a position also moves
// its origin, so the frames differ.
const FRAME_KEYS: Record<Frame, TKey> = { ned: "frameNed", enu: "frameEnu", body: "frameBody", ecef: "frameEcef", lla: "frameLla" };
const FRAMES_OF: Record<Qty, Frame[]> = { vector: ["ned", "enu", "body", "ecef"], position: ["lla", "ecef", "ned", "enu"] };
const LLA_KEYS: TKey[] = ["objRole_lat", "objRole_lon", "objRole_alt"];
const FRAME_SHORT: Record<Frame, string> = { ned: "NED", enu: "ENU", body: "Body", ecef: "ECEF", lla: "LLA" };
const EULER: TKey[] = ["objRole_roll", "objRole_pitch", "objRole_yaw"];
const QUAT: TKey[] = ["objRole_qw", "objRole_qx", "objRole_qy", "objRole_qz"];

export default function AnalysisPanel() {
  const t = useT();
  const runs = useApp((s) => s.runs);
  const ws = useApp((s) => s.ws);
  const selected = useApp((s) => s.selected);
  const tab = activeTab(ws);
  const plot = tab.plots[tab.active];
  const plotSigs = plot?.signals.map((s) => s.sig) ?? [];

  const tagged = showFileTags(runs);         // T46: which file a signal is from, at a glance
  const options = useMemo(() => runs.flatMap((r) => r.signals.map((s) => ({
    id: s.id, label: r.format === "derived" ? `ƒ ${s.name}` : s.name, group: r.format === "derived" ? undefined : r.name,
    ...(tagged && r.format !== "derived" ? { tag: r.tag, color: r.color } : {}),
  }))), [runs, tagged]);

  const [kind, setKind] = useState<Kind>("one");
  const [py, setPy] = useState<PyChoice | null>(null);
  const [op, setOp] = useState("derivative");
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [many, setMany] = useState<string[]>([]);
  const [batch, setBatch] = useState(false);
  const [windowN, setWindowN] = useState(10);
  const [cutoff, setCutoff] = useState(10);
  const [gain, setGain] = useState(1);
  const [bias, setBias] = useState(0);
  const multi = useApp((s) => s.multi);
  const multiSigs = Array.from(new Set(multi.map((m) => m.sig)));
  const [alignment, setAlignment] = useState("linear");
  const [name, setName] = useState("");
  const [fx, setFx] = useState("");
  const [output, setOutput] = useState<"new" | "edit">("new");
  const [addToPlot, setAddToPlot] = useState(true);
  const [frameAdd, setFrameAdd] = useState<"active" | "each" | "none">("active");   // where the three new signals go
  const [busy, setBusy] = useState(false);
  const [frSrc, setFrSrc] = useState<Frame>("body");
  const [frDst, setFrDst] = useState<Frame>("ned");
  const [att, setAtt] = useState<"euler" | "quat">("euler");
  const [unit, setUnit] = useState<"deg" | "rad">("deg");
  const [vec, setVec] = useState<string[]>(["", "", ""]);
  const [attSigs, setAttSigs] = useState<string[]>(["", "", "", ""]);
  const [qty, setQty] = useState<Qty>("vector");
  const [geoSigs, setGeoSigs] = useState<string[]>(["", ""]);
  const [refMode, setRefMode] = useState<"first" | "manual" | "signals">("first");
  const [refSigs, setRefSigs] = useState<string[]>(["", "", ""]);
  const [refLla, setRefLla] = useState<string[]>(["", "", ""]);
  const [pvWhere, setPvWhere] = useState<"plot" | "separate">("plot");      // several outputs: in one plot or a plot each
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const ends = [frSrc, frDst];
  const needsAtt = qty === "vector" && ends.includes("body");
  const needsGeo = qty === "vector" && ends.includes("ecef");
  const needsRef = qty === "position" && ends.some((f) => f === "ned" || f === "enu") && ends.some((f) => f === "lla" || f === "ecef");
  const refFromData = frSrc === "lla" || frSrc === "ecef";       // "first sample" only has a place to start from then
  const refEff = refMode === "first" && !refFromData ? "manual" : refMode;
  const refManual = needsRef && refEff === "manual";
  const refFromSigs = needsRef && refEff === "signals";       // the origin: another position's first valid sample (T17c)
  const refOk = !refManual || refLla.every((x) => x.trim() !== "" && Number.isFinite(Number(x)));
  const frameSources = [...vec, ...(needsAtt ? attSigs.slice(0, att === "quat" ? 4 : 3) : []), ...(needsGeo ? geoSigs : []),
    ...(refFromSigs ? refSigs : [])];
  const pickQty = (q: Qty) => { setQty(q); setFrSrc(q === "vector" ? "body" : "lla"); setFrDst("ned"); };
  const setAt = (arr: string[], set: (v: string[]) => void, i: number) => (v: string) => set(arr.map((x, k) => (k === i ? v : x)));
  const pickSrc = (f: Frame) => { setFrSrc(f); if (f === frDst) setFrDst(f === "ned" ? "enu" : "ned"); };
  // T30: conversions the names suggest (the active plot's file, else the first one), filled in on a click
  const frameRun = useApp((s) => {
    const rid = plotSigs[0]?.split("/")[0];
    return s.runs.find((r) => r.id === rid && r.format !== "derived") ?? s.runs.find((r) => r.format !== "derived");
  });
  const frameSugs = useMemo(() => suggestFrames(frameRun), [frameRun]);
  const applySug = (g: FrameSuggestion) => {
    setQty(g.qty); setFrSrc(g.src); setFrDst(g.dst); setVec(g.vec); setRefMode("first");
    if (g.att) { setAtt(g.att.kind); setAttSigs([...g.att.sigs, "", "", "", ""].slice(0, 4)); setUnit(g.att.unit); }
  };
  const sugOn = (g: FrameSuggestion) => g.qty === qty && g.src === frSrc && g.dst === frDst && g.vec.every((x, i) => vec[i] === x);

  // sensible defaults: the selected signal, else the active plot's signals
  useEffect(() => {
    const first = selected?.sig ?? plotSigs[0] ?? options[0]?.id ?? "";
    if (!a || !options.some((o) => o.id === a)) setA(first);
    if (!b || !options.some((o) => o.id === b)) setB(plotSigs[1] ?? options.find((o) => o.id !== first)?.id ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.sig, plotSigs.join("|"), options.length]);
  // start from the legend selection, else the active plot; the user can then pick any signal by typing
  // Nothing is chosen behind the user's back (that once added the plotted signal to a
  // "select all" of search results). Signals arrive only when the user hands them over.
  const seed = useApp((s) => s.analysisSeed);
  useEffect(() => {
    if (!seed?.length) return;
    setKind("one"); setBatch(true); setMany(seed);
    useApp.setState({ analysisSeed: null });
  }, [seed]);
  const listSel = useApp((s) => s.listSel);
  const quick = [
    { label: t("fromActivePlot"), ids: plotSigs },
    { label: t("fromLegendSelection"), ids: multiSigs },
    { label: t("fromListSelection"), ids: listSel },
  ];

  const switchKind = (k: Kind) => {
    setKind(k); setOp(k === "one" ? "derivative" : k === "two" ? "sub" : k === "many" ? "mean" : k === "frame" ? "frame" : k === "py" ? "py" : "expr");
    if (k === "frame" && vec.every((x) => !x)) {
      if (frameSugs.length) applySug(frameSugs[0]);       // what the names suggest (T30); the user confirms
      else {                                               // else the active plot's signals, in order, as a start
        setVec([0, 1, 2].map((i) => plotSigs[i] ?? ""));
        setAttSigs([3, 4, 5, 6].map((i) => plotSigs[i] ?? ""));
      }
    }
  };
  const tr = (k: string, v?: Record<string, string | number>) => t(k as never, v);
  /** The conversion's parameters without the output axis (one derived signal per axis). */
  const frameParams = (): Record<string, unknown> => {
    const p: Record<string, unknown> = { qty, src: frSrc, dst: frDst, att, unit, alignment };
    if (needsRef) Object.assign(p, refManual
      ? { ref: "manual", ref_lat: Number(refLla[0]), ref_lon: Number(refLla[1]), ref_alt: Number(refLla[2]) }
      : { ref: refFromSigs ? "signals" : "first" });
    return p;
  };
  const fxRes = kind === "fx" && fx.trim() ? resolveFormula(fx, runs, tr) : null;
  const params = { window: windowN, cutoff, alignment, gain, bias };
  // T31: a Python operation's sources follow how many inputs it takes
  const pySources = !py ? [] : py.op.inputs === 1 ? [a] : py.op.inputs === 2 ? [a, b] : many;
  const pyParams = py ? { op: py.op.id, args: py.args } : {};
  const batchSigs = many;

  const create = async () => {
    if (kind === "one" && output === "edit") {
      const step = opToStep(op, params);
      const ids = batch ? many : [a];
      if (!step || !ids.length) return;
      setBusy(true);
      try { await editInPlace(ids, step); }
      catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
      finally { setBusy(false); }
      return;
    }
    if (kind === "frame") {
      if (frameSources.some((x) => !x)) return;
      setBusy(true);
      try {
        const ids = await createFrameGroup(frameSources, frameParams(), name.trim() || frameGroupName(frSrc, frDst, qty));
        if (frameAdd === "active") actions.addSignals(ids);              // one undo step for the three
        else if (frameAdd === "each") actions.addSignalsToNewPlots(ids);
        setName("");
      } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
      finally { setBusy(false); }
      return;
    }
    if (kind === "fx") {
      if (!fxRes || fxRes.error) return;
      setBusy(true);
      try {
        const r = await api.createDerived("expr", fxRes.sources, { expr: fxRes.expr, text: fx.trim(), alignment }, name);
        useApp.setState({ runs: r.runs });
        if (addToPlot) actions.addSignal(r.id);
        setName("");
      } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
      finally { setBusy(false); }
      return;
    }
    const jobs: string[][] = kind === "py" ? [pySources] : kind === "one" ? (batch ? batchSigs.map((s) => [s]) : [[a]]) : kind === "two" ? [[a, b]] : [many];
    if (!jobs.length || jobs.some((j) => j.some((s) => !s))) return;
    setBusy(true);
    try {
      for (const sources of jobs) {
        const r = await api.createDerived(kind === "py" ? "py" : op, sources, kind === "py" ? pyParams : params, jobs.length === 1 ? name : undefined);
        useApp.setState({ runs: r.runs });
        if (addToPlot) actions.addSignal(r.id);
      }
      setName("");
    } catch (e) {
      useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
    } finally { setBusy(false); }
  };

  const previewNow = useApp((s) => s.preview);
  const previewOn = !!previewNow;
  const clearPreviews = () => useApp.setState({ preview: null });
  // a preview is drawn in a time plot: the active one, else the tab's first; with none (a map, XY
  // or XYZ plot active), in plots of its own under the grid
  const timePlot = plot && (plot.mode ?? "time") === "time" ? plot : tab.plots.find((p) => (p.mode ?? "time") === "time");
  const showLines = (lines: PreviewLine[], separate: boolean) => useApp.setState({ preview:
    !separate && timePlot ? { plotId: timePlot.id, lines } : { plotId: "", lines, separate: true } });
  const showPreview = async () => {
    const st = useApp.getState();
    const r = timePlot ? st.ranges[rangeKey(tab, timePlot)] ?? timePlot.xlim ?? null : null;
    if (kind === "frame") {
      // the three axes, computed but not kept: dashed in one plot, or a plot each
      if (frameSources.some((x) => !x)) return;
      const base = name.trim() || frameGroupName(frSrc, frDst, qty);
      try {
        const p = frameParams();
        const lines = await Promise.all(AXES[frDst].map(async (lbl, axis) => {
          const d = await api.previewDerived("frame", frameSources, { ...p, axis }, r?.[0] ?? null, r?.[1] ?? null);
          return { label: `${base}.${lbl}`, x: d.x, y: d.y };
        }));
        showLines(lines, pvWhere === "separate");
      } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
      return;
    }
    if (kind === "fx" && (!fxRes || fxRes.error)) return;
    const sources = kind === "fx" ? fxRes!.sources : kind === "py" ? pySources : kind === "one" ? [a] : kind === "two" ? [a, b] : many;
    const pOp = kind === "fx" ? "expr" : kind === "py" ? "py" : op;
    const pParams = kind === "fx" ? { expr: fxRes!.expr, text: fx, alignment } : kind === "py" ? pyParams : params;
    if (kind === "py" && !py) return;
    if (sources.some((x) => !x)) return;
    try {
      const d = await api.previewDerived(pOp, sources, pParams, r?.[0] ?? null, r?.[1] ?? null);
      showLines([{ label: pOp, x: d.x, y: d.y }], false);
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
  };
  const derivedRun = runs.find((r) => r.format === "derived");
  const editedCount = runs.reduce((n, r) => n + r.signals.filter((x) => x.transform).length, 0);
  const remove = async (items: { id: string; name: string }[]) => {
    let r: { runs: typeof runs } | null = null;
    for (const s of items) r = await api.deleteDerived(s.name);
    const gone = new Set(items.map((s) => s.id));
    actions.removeSignalRefs((s) => gone.has(s));
    if (r) useApp.setState({ runs: r.runs });
  };

  const sigSelect = (value: string, set: (v: string) => void, label: string) => (
    <div className="afield"><span>{label}</span>
      <SignalPicker value={value} options={options} onChange={set} ariaLabel={label} placeholder={t("signal")} />
    </div>
  );

  const canCreate = kind === "frame" ? frSrc !== frDst && frameSources.every((x) => !!x) && refOk
    : kind === "py" ? !!py && pySources.length >= py.op.inputs && pySources.every((x) => !!x)
    : kind === "fx" ? !!fxRes && !fxRes.error : kind === "one" ? (batch ? batchSigs.length > 0 : !!a) : kind === "two" ? !!a && !!b : many.length >= 2;

  return (
    <aside className="side" aria-label={t("analysis")}>
      <div className="side-head"><h2>{t("analysis")}</h2></div>
      {!options.length ? <p className="empty-note">{t("noFilesHint")}</p> : (
        <div className="tree analysis">
          <div className="seg wide kinds" role="tablist">
            <button className={kind === "one" ? "on" : ""} onClick={() => switchKind("one")}>{t("kindOne")}</button>
            <button className={kind === "two" ? "on" : ""} onClick={() => switchKind("two")}>{t("kindTwo")}</button>
            <button className={kind === "many" ? "on" : ""} onClick={() => switchKind("many")}>{t("kindMany")}</button>
            <button className={kind === "fx" ? "on" : ""} onClick={() => switchKind("fx")}>{t("formula")}</button>
            <button className={kind === "frame" ? "on" : ""} onClick={() => switchKind("frame")}>{t("kindFrame")}</button>
            <button className={kind === "py" ? "on" : ""} onClick={() => switchKind("py")} title={t("pyIntro")}>Python</button>
          </div>

          {kind === "fx" && <FormulaInput value={fx} onChange={setFx} runs={runs} error={fxRes?.error} />}
          {kind === "py" && <>
            <PyOpsSection choice={py} onChange={setPy} />
            {py && py.op.inputs === 1 && sigSelect(a, setA, t("signal"))}
            {py && py.op.inputs === 2 && <>{sigSelect(a, setA, "A")}{sigSelect(b, setB, "B")}</>}
            {py && py.op.inputs > 2 && <MultiSignalPicker options={options} value={many} onChange={setMany} quick={quick} />}
          </>}
          {kind !== "fx" && kind !== "frame" && kind !== "py" && <label className="afield"><span>{t("operation")}</span>
            <select value={op} onChange={(e) => setOp(e.target.value)}>
              {kind === "one" && UNARY.map(([v, k]) => <option key={v} value={v}>{t(k)}</option>)}
              {kind === "two" && BINARY.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              {kind === "many" && MULTI.map(([v, k]) => <option key={v} value={v}>{t(k)}</option>)}
            </select>
          </label>}

          {kind === "one" && <>
            <div className="afield"><span>{t("resultLabel")}</span>
              <div className="seg wide small" role="group">
                <button className={output === "new" ? "on" : ""} onClick={() => setOutput("new")} title={t("resultNewHint")}>{t("resultNew")}</button>
                <button className={output === "edit" ? "on" : ""} onClick={() => setOutput("edit")} title={t("resultEditHint")}>{t("resultEdit")}</button>
              </div>
              <p className="hint" style={{ fontSize: "0.846rem", margin: "4px 0 0" }}>{output === "edit" ? t("resultEditHint") : t("resultNewHint")}</p>
            </div>
            <div className="seg wide small" role="group">
              <button className={!batch ? "on" : ""} onClick={() => setBatch(false)}>{t("applyToThis")}</button>
              <button className={batch ? "on" : ""} onClick={() => setBatch(true)}>{t("eachOfSeveral")}</button>
            </div>
            {!batch && sigSelect(a, setA, t("signal"))}
            {batch && <MultiSignalPicker options={options} value={many} onChange={setMany} quick={quick} />}
            {(op === "smooth" || op === "rms") && (
              <label className="afield"><span>{t("windowSamples")}</span>
                <input type="number" min={2} value={windowN} onChange={(e) => setWindowN(Math.max(2, +e.target.value))} /></label>
            )}
            {op === "affine" && (
              <div className="arow">
                <label className="afield"><span>k</span><input type="number" step="any" value={gain} onChange={(e) => setGain(+e.target.value)} /></label>
                <label className="afield"><span>c</span><input type="number" step="any" value={bias} onChange={(e) => setBias(+e.target.value)} /></label>
              </div>
            )}
            {(op === "lowpass" || op === "highpass") && (
              <label className="afield"><span>{t("cutoffHz")}</span>
                <input type="number" min={0} step="any" value={cutoff} onChange={(e) => setCutoff(+e.target.value)} /></label>
            )}
          </>}

          {kind === "two" && <>
            {sigSelect(a, setA, "A")}
            {sigSelect(b, setB, "B")}
          </>}

          {kind === "many" && <MultiSignalPicker options={options} value={many} onChange={setMany} quick={quick} />}

          {kind === "frame" && <>
            {frameSugs.length > 0 && <div className="frame-sugs" role="group" aria-label={t("frameSuggested")}>
              <span>{t("frameSuggested")}</span>
              {frameSugs.map((g) => (
                <button key={g.key} className={`chip-btn${sugOn(g) ? " on" : ""}`} onClick={() => applySug(g)}
                  title={g.vec.map((x) => x.split("/").slice(1).join("/")).join(", ")}>
                  {g.group ? `${g.group}: ` : ""}{FRAME_SHORT[g.src]} → {FRAME_SHORT[g.dst]}</button>
              ))}
            </div>}
            <div className="seg wide small" role="group" aria-label={t("frameQty")}>
              <button className={qty === "vector" ? "on" : ""} onClick={() => pickQty("vector")}>{t("qtyVector")}</button>
              <button className={qty === "position" ? "on" : ""} onClick={() => pickQty("position")}>{t("qtyPosition")}</button>
            </div>
            <p className="hint" style={{ fontSize: "0.846rem", margin: "0 0 8px" }}>{t(qty === "vector" ? "qtyVectorHint" : "qtyPositionHint")}</p>
            <label className="afield"><span>{t("frameFrom")}</span>
              <select value={frSrc} onChange={(e) => pickSrc(e.target.value as Frame)}>
                {FRAMES_OF[qty].map((f) => <option key={f} value={f}>{t(FRAME_KEYS[f])}</option>)}
              </select></label>
            <label className="afield"><span>{t("frameTo")}</span>
              <select value={frDst} onChange={(e) => setFrDst(e.target.value as Frame)}>
                {FRAMES_OF[qty].filter((f) => f !== frSrc).map((f) => <option key={f} value={f}>{t(FRAME_KEYS[f])}</option>)}
              </select></label>
            <h3 className="alist-head">{t(qty === "vector" ? "frameVector" : "framePosition")}</h3>
            {AXES[frSrc].map((lbl, i) => <div key={`v${i}`}>{sigSelect(vec[i], setAt(vec, setVec, i), frSrc === "lla" ? t(LLA_KEYS[i]) : lbl)}</div>)}
            {needsAtt && <>
              <h3 className="alist-head">{t("frameAttitude")}</h3>
              <div className="seg wide small" role="group">
                <button className={att === "euler" ? "on" : ""} onClick={() => setAtt("euler")}>{t("attEuler")}</button>
                <button className={att === "quat" ? "on" : ""} onClick={() => setAtt("quat")}>{t("attQuat")}</button>
              </div>
              {(att === "quat" ? QUAT : EULER).map((k, i) => <div key={k}>{sigSelect(attSigs[i], setAt(attSigs, setAttSigs, i), t(k))}</div>)}
              {att === "euler" && <label className="afield"><span>{t("angleUnit")}</span>
                <select value={unit} onChange={(e) => setUnit(e.target.value as "deg" | "rad")}>
                  <option value="deg">{t("unitDeg")}</option>
                  <option value="rad">{t("unitRad")}</option>
                </select></label>}
            </>}
            {needsGeo && <>
              <h3 className="alist-head">{t("frameWhere")}</h3>
              {[0, 1].map((i) => <div key={`g${i}`}>{sigSelect(geoSigs[i], setAt(geoSigs, setGeoSigs, i), t(LLA_KEYS[i]))}</div>)}
            </>}
            {needsRef && <>
              <h3 className="alist-head">{t("frameRef")}</h3>
              <div className="seg wide small" role="group">
                {refFromData && <button className={refEff === "first" ? "on" : ""} onClick={() => setRefMode("first")}>{t("refFirst")}</button>}
                <button className={refEff === "signals" ? "on" : ""} onClick={() => setRefMode("signals")}>{t("refSignalsShort")}</button>
                <button className={refEff === "manual" ? "on" : ""} onClick={() => setRefMode("manual")}>{t("refManual")}</button>
              </div>
              {refFromSigs && LLA_KEYS.map((k, i) => <div key={`r${i}`}>{sigSelect(refSigs[i], setAt(refSigs, setRefSigs, i), t(k))}</div>)}
              {refManual && LLA_KEYS.map((k, i) => (
                <label key={k} className="afield"><span>{t(k)}{i < 2 ? " (°)" : " (m)"}</span>
                  <input type="number" step="any" value={refLla[i]} onChange={(e) => setAt(refLla, setRefLla, i)(e.target.value)} /></label>))}
              <p className="hint" style={{ fontSize: "0.846rem", margin: "0 0 8px" }}>{t(refManual ? "refManualHint" : refFromSigs ? "refSignalsHint" : "refFirstHint")}</p>
            </>}
            <p className="hint" style={{ fontSize: "0.846rem", margin: "0 0 8px" }}>{t("frameHint")}</p>
          </>}

          {(kind === "two" || kind === "many" || kind === "frame" || (kind === "fx" && (fxRes?.sources.length ?? 0) > 1)) && (
            <label className="afield"><span>{t("alignment")}</span>
              <select value={alignment} onChange={(e) => setAlignment(e.target.value)}>
                <option value="linear">{t("alignLinear")}</option>
                <option value="nearest">{t("alignNearest")}</option>
              </select></label>
          )}

          {!(kind === "one" && (batch || output === "edit")) && (
            <label className="afield"><span>{t("resultName")}</span>
              <input value={name} onChange={(e) => setName(e.target.value)}
                placeholder={kind === "frame" ? frameGroupName(frSrc, frDst, qty) : t("auto")} /></label>
          )}
          {kind === "frame" && (
            <label className="afield"><span>{t("frameAddTo")}</span>
              <select value={frameAdd} onChange={(e) => setFrameAdd(e.target.value as typeof frameAdd)}>
                <option value="active">{t("frameAddActive")}</option>
                <option value="each">{t("frameAddEach")}</option>
                <option value="none">{t("frameAddNone")}</option>
              </select></label>
          )}
          {kind === "two" && (op === "sub" || op === "absdiff") && a && b && <ErrorSegments a={a} b={b} alignment={alignment} />}
          {!(kind === "one" && output === "edit") && kind !== "frame" && <label className="acheck"><input type="checkbox" checked={addToPlot} onChange={(e) => setAddToPlot(e.target.checked)} />{t("addToActivePlot")}</label>}
          {kind === "frame" && (
            <div className="afield"><span>{t("previewWhere")}</span>
              <div className="seg wide small" role="group" aria-label={t("previewWhere")}>
                <button className={pvWhere === "plot" ? "on" : ""} onClick={() => setPvWhere("plot")}>{t("previewInPlot")}</button>
                <button className={pvWhere === "separate" ? "on" : ""} onClick={() => setPvWhere("separate")}>{t("previewSeparate")}</button>
              </div></div>
          )}
          <div className="arow" style={{ marginTop: 4 }}>
            <button className="btn outline" disabled={!canCreate || busy || (kind === "one" && batch)}
              onClick={showPreview}>{t("previewOp")}</button>
            <button className="btn primary" disabled={!canCreate || busy} onClick={async () => { await create(); clearPreviews(); }}>
              {busy ? t("loading") : kind === "one" && output === "edit" ? t("applyEdit") : kind === "frame" ? t("createThree") : t("createSignal")}</button>
          </div>
          {previewOn && <p className="hint" style={{ fontSize: "0.923rem", margin: "6px 0 0" }}>{t(previewNow?.separate ? "previewShownSeparate" : "previewShown")} ·{" "}
            <button className="linklike" onClick={clearPreviews}>{t("clearPreview")}</button></p>}
          {previewNow && !previewNow.separate && previewNow.lines.length > 1 && <PreviewKey lines={previewNow.lines} />}

          {(editedCount > 0 || (derivedRun?.signals.length ?? 0) > 0) && (
            <div className="bulk-undo">
              <h3 className="alist-head">{t("undoAllTitle")}</h3>
              <div className="arow wrap">
                <button className="btn outline" disabled={!editedCount} onClick={() => clearAllEdits()}>{t("removeAllEdits", { n: editedCount })}</button>
                <button className="btn outline" disabled={!derivedRun?.signals.length} onClick={() => deleteAllDerived()}>{t("deleteAllDerived", { n: derivedRun?.signals.length ?? 0 })}</button>
              </div>
            </div>
          )}
          <h3 className="alist-head">{t("derivedSignals")}</h3>
          {!derivedRun?.signals.length && <p className="hint">{t("noDerived")}</p>}
          {groupDerived(derivedRun?.signals ?? []).map((g) => {
            const row = (s: NonNullable<typeof derivedRun>["signals"][number], deep: boolean) => (
              <div key={s.id} className={`dsig${deep ? " deep" : ""}${s.valid === false ? " broken" : ""}`}>
                <div className="dsig-main">
                  <button className="dsig-name" onClick={() => actions.toggleSignal(s.id)} title={`${s.name}\n${t("addToActivePlot")}`}>{deep ? memberLabel(s.name, g.key) : s.name}</button>
                  {!deep && s.formula && s.formula !== s.name && <span className="dsig-formula">{s.formula}</span>}
                  {s.valid === false && <span className="dsig-formula">{t("derivedBroken")}</span>}
                </div>
                <button className="iconbtn" onClick={() => remove([s])} aria-label={t("remove")} title={t("remove")}><Icon.Trash /></button>
              </div>
            );
            if (!g.key) return row(g.items[0], false);
            const open = openGroups[g.key] ?? false;
            const ids = g.items.map((s) => s.id);
            // "N pos LLA→NED(lat, lon, alt)" -> "pos LLA→NED(lat, lon, alt)": the conversion, not one axis
            const f0 = g.items[0].formula ?? "", a0 = memberLabel(g.items[0].name, g.key);
            const groupFormula = f0.startsWith(a0 + " ") ? f0.slice(a0.length + 1) : f0;
            return (
              <div key={`g:${g.key}`} className="dsig-group">
                <div className={`dsig grp${open ? "" : " closed"}${g.items.some((s) => s.valid === false) ? " broken" : ""}`}>
                  <button className="iconbtn chev-btn" aria-expanded={open} aria-label={g.key} onClick={() => setOpenGroups({ ...openGroups, [g.key]: !open })}>
                    <Icon.Chevron className="chev" /></button>
                  <div className="dsig-main">
                    <button className="dsig-name" onClick={() => actions.addSignals(ids)} title={t("addGroupToPlot")}>
                      {g.key} <span className="dsig-axes">{g.items.map((s) => memberLabel(s.name, g.key)).join(", ")}</span></button>
                    {groupFormula && <span className="dsig-formula">{groupFormula}</span>}
                  </div>
                  <button className="iconbtn" onClick={() => remove(g.items)} aria-label={t("removeGroup")} title={t("removeGroup")}><Icon.Trash /></button>
                </div>
                {open && g.items.map((s) => row(s, true))}
              </div>
            );
          })}
        </div>
      )}
    </aside>
  );
}

/** Which dashed line is which, when a preview puts several in the active plot. */
function PreviewKey({ lines }: { lines: PreviewLine[] }) {
  return (
    <div className="pv-key">
      {lines.map((l, k) => (
        <span key={k} className="pv-key-item">
          <svg width="28" height="8" aria-hidden="true"><line x1="0" y1="4" x2="28" y2="4" stroke="currentColor" strokeWidth="1.5"
            strokeDasharray={PREVIEW_DASH[k % PREVIEW_DASH.length].join(" ")} /></svg>
          {l.label}
        </span>
      ))}
    </div>
  );
}
