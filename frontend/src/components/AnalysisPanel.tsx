import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { actions, activeTab, useApp } from "../store";
import { useT, type TKey } from "../i18n";
import { Icon } from "../icons";
import SignalPicker from "./SignalPicker";
import FormulaInput from "./FormulaInput";
import MultiSignalPicker from "./MultiSignalPicker";
import { resolveFormula } from "../formulaRefs";
import { clearAllEdits, deleteAllDerived, editInPlace, opToStep } from "../transforms";

type Kind = "one" | "two" | "many" | "fx";
const UNARY: [string, TKey][] = [
  ["derivative", "opDerivative"], ["integral", "opIntegral"], ["abs", "opAbs"], ["negate", "opNegate"],
  ["normalize", "opNormalize"], ["affine", "opAffine"], ["smooth", "opSmooth"], ["rms", "opRms"], ["lowpass", "opLowpass"], ["highpass", "opHighpass"],
];
const BINARY: [string, string][] = [["sub", "A − B"], ["add", "A + B"], ["mul", "A × B"], ["div", "A ÷ B"], ["absdiff", "|A − B|"]];
const MULTI: [string, TKey][] = [["mean", "opMean"], ["sum", "opSum"], ["min", "opMin"], ["max", "opMax"], ["norm", "opNorm"]];

export default function AnalysisPanel() {
  const t = useT();
  const runs = useApp((s) => s.runs);
  const ws = useApp((s) => s.ws);
  const selected = useApp((s) => s.selected);
  const tab = activeTab(ws);
  const plot = tab.plots[tab.active];
  const plotSigs = plot?.signals.map((s) => s.sig) ?? [];

  const options = useMemo(() => runs.flatMap((r) => r.signals.map((s) => ({
    id: s.id, label: r.format === "derived" ? `ƒ ${s.name}` : s.name, group: r.format === "derived" ? undefined : r.name,
  }))), [runs]);

  const [kind, setKind] = useState<Kind>("one");
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
  const [busy, setBusy] = useState(false);

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

  const switchKind = (k: Kind) => { setKind(k); setOp(k === "one" ? "derivative" : k === "two" ? "sub" : k === "many" ? "mean" : "expr"); };
  const tr = (k: string, v?: Record<string, string | number>) => t(k as never, v);
  const fxRes = kind === "fx" && fx.trim() ? resolveFormula(fx, runs, tr) : null;
  const params = { window: windowN, cutoff, alignment, gain, bias };
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
    const jobs: string[][] = kind === "one" ? (batch ? batchSigs.map((s) => [s]) : [[a]]) : kind === "two" ? [[a, b]] : [many];
    if (!jobs.length || jobs.some((j) => j.some((s) => !s))) return;
    setBusy(true);
    try {
      for (const sources of jobs) {
        const r = await api.createDerived(op, sources, params, jobs.length === 1 ? name : undefined);
        useApp.setState({ runs: r.runs });
        if (addToPlot) actions.addSignal(r.id);
      }
      setName("");
    } catch (e) {
      useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
    } finally { setBusy(false); }
  };

  const previewOn = useApp((s) => !!s.preview);
  const showPreview = async () => {
    if (kind === "fx" && (!fxRes || fxRes.error)) return;
    const sources = kind === "fx" ? fxRes!.sources : kind === "one" ? [a] : kind === "two" ? [a, b] : many;
    const pOp = kind === "fx" ? "expr" : op;
    const pParams = kind === "fx" ? { expr: fxRes!.expr, text: fx, alignment } : params;
    if (!plot || sources.some((x) => !x)) return;
    const st = useApp.getState();
    const r = st.ranges[(plot && (tab.linkX ? tab.id : plot.id)) as string] ?? null;
    try {
      const d = await api.previewDerived(pOp, sources, pParams, r?.[0] ?? null, r?.[1] ?? null);
      useApp.setState({ preview: { plotId: plot.id, label: pOp, x: d.x, y: d.y } });
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
  };
  const derivedRun = runs.find((r) => r.format === "derived");
  const editedCount = runs.reduce((n, r) => n + r.signals.filter((x) => x.transform).length, 0);
  const remove = async (id: string, nm: string) => {
    const r = await api.deleteDerived(nm);
    actions.removeSignalRefs((s) => s === id);
    useApp.setState({ runs: r.runs });
  };

  const sigSelect = (value: string, set: (v: string) => void, label: string) => (
    <div className="afield"><span>{label}</span>
      <SignalPicker value={value} options={options} onChange={set} ariaLabel={label} placeholder={t("signal")} />
    </div>
  );

  const canCreate = kind === "fx" ? !!fxRes && !fxRes.error : kind === "one" ? (batch ? batchSigs.length > 0 : !!a) : kind === "two" ? !!a && !!b : many.length >= 2;

  return (
    <aside className="side" aria-label={t("analysis")}>
      <div className="side-head"><h2>{t("analysis")}</h2></div>
      {!options.length ? <p className="empty-note">{t("noFilesHint")}</p> : (
        <div className="tree analysis">
          <div className="seg wide" role="tablist">
            <button className={kind === "one" ? "on" : ""} onClick={() => switchKind("one")}>{t("kindOne")}</button>
            <button className={kind === "two" ? "on" : ""} onClick={() => switchKind("two")}>{t("kindTwo")}</button>
            <button className={kind === "many" ? "on" : ""} onClick={() => switchKind("many")}>{t("kindMany")}</button>
            <button className={kind === "fx" ? "on" : ""} onClick={() => switchKind("fx")}>{t("formula")}</button>
          </div>

          {kind === "fx" && <FormulaInput value={fx} onChange={setFx} runs={runs} error={fxRes?.error} />}
          {kind !== "fx" && <label className="afield"><span>{t("operation")}</span>
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
              <button className={!batch ? "on" : ""} onClick={() => setBatch(false)}>{t("oneSignalOpt")}</button>
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

          {(kind === "two" || kind === "many" || (kind === "fx" && (fxRes?.sources.length ?? 0) > 1)) && (
            <label className="afield"><span>{t("alignment")}</span>
              <select value={alignment} onChange={(e) => setAlignment(e.target.value)}>
                <option value="linear">{t("alignLinear")}</option>
                <option value="nearest">{t("alignNearest")}</option>
              </select></label>
          )}

          {!(kind === "one" && (batch || output === "edit")) && (
            <label className="afield"><span>{t("resultName")}</span>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("auto")} /></label>
          )}
          {!(kind === "one" && output === "edit") && <label className="acheck"><input type="checkbox" checked={addToPlot} onChange={(e) => setAddToPlot(e.target.checked)} />{t("addToActivePlot")}</label>}
          <div className="arow" style={{ marginTop: 4 }}>
            <button className="btn outline" disabled={!canCreate || busy || (kind === "one" && batch)} onClick={showPreview}>{t("previewOp")}</button>
            <button className="btn primary" disabled={!canCreate || busy} onClick={async () => { await create(); useApp.setState({ preview: null }); }}>
              {busy ? t("loading") : kind === "one" && output === "edit" ? t("applyEdit") : t("createSignal")}</button>
          </div>
          {previewOn && <p className="hint" style={{ fontSize: "0.923rem", margin: "6px 0 0" }}>{t("previewShown")} ·{" "}
            <button className="linklike" onClick={() => useApp.setState({ preview: null })}>{t("clearPreview")}</button></p>}

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
          {derivedRun?.signals.map((s) => (
            <div key={s.id} className={`dsig${s.valid === false ? " broken" : ""}`}>
              <div className="dsig-main">
                <button className="dsig-name" onClick={() => actions.toggleSignal(s.id)} title={t("addToActivePlot")}>{s.name}</button>
                {s.formula && s.formula !== s.name && <span className="dsig-formula">{s.formula}</span>}
                {s.valid === false && <span className="dsig-formula">{t("derivedBroken")}</span>}
              </div>
              <button className="iconbtn" onClick={() => remove(s.id, s.name)} aria-label={t("remove")} title={t("remove")}><Icon.Trash /></button>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
