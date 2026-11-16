import { useMemo, useState } from "react";
import { api } from "../api";
import { activeTab, pickPath, rangeKey, signalName, useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { signalUnit } from "../units";
import { useEscape } from "./Overlays";

type TimeChoice = "all" | "view" | "cursors" | "where";

/** E1: Export recording… - a part of a recording as a new file (svcore/subset.py): the signals on screen or
 *  every signal, all the time / the plots' view / between the cursors / only where a condition holds, as
 *  recorded or at one rate. One file, or one per open file (the same signals by name in each). */
export default function ExportRecordingDialog() {
  const t = useT();
  const runs = useApp((s) => s.runs).filter((r) => r.format !== "derived");
  const ws = useApp((s) => s.ws);
  const cursor = useApp((s) => s.cursor);
  const close = () => useApp.setState({ exportRecOpen: false });
  useEscape(close);
  const tab = activeTab(ws);
  const plots = tab?.plots ?? [];
  const onScreen = useMemo(() => [...new Set(plots.flatMap((p) => p.signals.map((s) => s.sig)))], [plots]);
  const labelOf = (sig: string) => plots.flatMap((p) => p.signals).find((s) => s.sig === sig)?.label || "";
  const [runId, setRunId] = useState<string>(() => {
    const first = onScreen.find((s) => runs.some((r) => s.startsWith(r.id + "/")));
    return first ? first.slice(0, first.indexOf("/")) : runs[0]?.id ?? "";
  });
  const every = runId === "*";
  const shownIn = (rid: string) => {
    const run = runs.find((r) => r.id === rid);
    if (!run) return [];
    const names = new Set(run.signals.map((s) => s.name));
    // the same signals by name in each file; in the one file of a plot, its derived signals too
    return onScreen.flatMap((sig) => {
      if (sig.startsWith(rid + "/")) return [sig];
      const nm = sig.slice(sig.indexOf("/") + 1);
      if (sig.startsWith("derived/")) return every ? [] : [sig];
      return every && names.has(nm) ? [`${rid}/${nm}`] : [];
    }).filter((v, i, a) => a.indexOf(v) === i);
  };
  const countRun = every ? runs[0]?.id ?? "" : runId;
  const nShown = shownIn(countRun).length;
  const nAll = runs.find((r) => r.id === countRun)?.signals.length ?? 0;
  const [which, setWhich] = useState<"screen" | "all">(() => (nShown ? "screen" : "all"));
  const cursorsOn = cursor.on && cursor.dual && cursor.t1 !== null && cursor.t2 !== null;
  const view = tab && plots[0] ? useApp.getState().ranges[rangeKey(tab, plots[0])] ?? null : null;
  const [time, setTime] = useState<TimeChoice>(cursorsOn ? "cursors" : "all");
  const [where, setWhere] = useState("");
  const [margin, setMargin] = useState("0");
  const [atRate, setAtRate] = useState(false);
  const [rate, setRate] = useState("50");
  const [antialias, setAntialias] = useState(true);
  const [fromZero, setFromZero] = useState(false);
  const [busy, setBusy] = useState(false);
  const rateN = Number(rate);
  const bad = (atRate && !(rateN > 0)) || (time === "where" && !where.trim()) || (which === "screen" ? !nShown : !nAll);

  const signalsOf = (rid: string) => {
    const run = runs.find((r) => r.id === rid);
    const ids = which === "screen" ? shownIn(rid) : (run?.signals.map((s) => s.id) ?? []);
    return ids.map((id) => {
      const label = labelOf(id) || signalName(runs, id, false);
      return { id, label, unit: signalUnit(runs, id, label) ?? "" };
    });
  };
  const range = (): [number, number] | null => {
    if (time === "cursors" && cursorsOn) return [Math.min(cursor.t1!, cursor.t2!), Math.max(cursor.t1!, cursor.t2!)];
    if (time === "view" && view) return [view[0], view[1]];
    return null;
  };

  const run = async () => {
    const targets = every ? runs.map((r) => r.id) : [runId];
    const firstName = runs.find((r) => r.id === targets[0])?.name.replace(/\.[^.]+$/, "") ?? "recording";
    const path = await pickPath({ mode: "save", title: t("xrTitle"), exts: [".csv", ".parquet", ".mat", ".h5"],
      defaultName: `${every ? "recordings" : firstName}_part.csv` });
    if (!path) return;
    const dot = path.lastIndexOf(".");
    const [stem, ext] = dot > path.lastIndexOf("/") && dot > path.lastIndexOf("\\") ? [path.slice(0, dot), path.slice(dot)] : [path, ".csv"];
    const r = range();
    setBusy(true);
    const toast = useApp.getState().toast;
    try {
      let rows = 0, last = path;
      for (const rid of targets) {
        const sigs = signalsOf(rid);
        if (!sigs.length) continue;
        const info = runs.find((x) => x.id === rid);
        const one = every ? `${stem}_${(info?.name ?? rid).replace(/\.[^.]+$/, "").replace(/[\\/:*?"<>|]+/g, "_")}${ext}` : path;
        const res = await api.exportRecording({
          path: one, signals: sigs, t0: r?.[0] ?? null, t1: r?.[1] ?? null, source: info?.path ?? "",
          where: time === "where" ? where : "", margin: Number(margin) || 0,
          rate: atRate ? rateN : null, antialias, fromZero,
        });
        rows += res.rows; last = res.path;
      }
      toast({ kind: "info", text: every ? t("xrDoneMany", { n: targets.length, path: last }) : t("xrDone", { n: rows, path: last }) });
      close();
    } catch (e) {
      toast({ kind: "error", text: String((e as Error).message) });
    } finally { setBusy(false); }
  };

  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog rt-dialog xr-dialog" role="dialog" aria-label={t("xrTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head">
          <h2>{t("xrTitle")}</h2>
          <button className="iconbtn" onClick={close} aria-label={t("close")}><Icon.X /></button>
        </div>
        <p className="hint rt-lead">{t("xrLead")}</p>
        <div className="dialog-body rt-rows">
          {runs.length > 1 && (
            <fieldset className="sw-mode">
              <legend>{t("xrRun")}</legend>
              <select className="xr-run" value={runId} onChange={(e) => setRunId(e.target.value)} aria-label={t("xrRun")}>
                {runs.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                <option value="*">{t("xrEveryRun")}</option>
              </select>
            </fieldset>
          )}
          <fieldset className="sw-mode">
            <legend>{t("xrSignals")}</legend>
            <label><input type="radio" name="xr-sig" checked={which === "screen"} disabled={!nShown} onChange={() => setWhich("screen")} />
              {" "}{t("xrOnScreen", { n: nShown })}</label>
            <label><input type="radio" name="xr-sig" checked={which === "all"} onChange={() => setWhich("all")} />
              {" "}{t("xrAll", { n: nAll })}</label>
          </fieldset>
          <fieldset className="sw-mode">
            <legend>{t("xrTime")}</legend>
            <label><input type="radio" name="xr-time" checked={time === "all"} onChange={() => setTime("all")} /> {t("xrTimeAll")}</label>
            {view && <label><input type="radio" name="xr-time" checked={time === "view"} onChange={() => setTime("view")} /> {t("xrTimeView")}</label>}
            {cursorsOn && <label><input type="radio" name="xr-time" checked={time === "cursors"} onChange={() => setTime("cursors")} /> {t("xrTimeCursors")}</label>}
            <label><input type="radio" name="xr-time" checked={time === "where"} onChange={() => setTime("where")} /> {t("xrTimeWhere")}</label>
            {time === "where" && (
              <div className="xr-where">
                <input className="xr-cond" dir="ltr" value={where} placeholder={t("xrWherePh")} onChange={(e) => setWhere(e.target.value)}
                  aria-label={t("xrTimeWhere")} autoFocus />
                <label className="ta-field">{t("xrMargin")}
                  <input className="xr-margin" type="number" min={0} step={0.5} value={margin} onChange={(e) => setMargin(e.target.value)} /></label>
              </div>
            )}
          </fieldset>
          <fieldset className="sw-mode">
            <legend>{t("xrRate")}</legend>
            <label><input type="radio" name="xr-rate" checked={!atRate} onChange={() => setAtRate(false)} /> {t("xrAsRecorded")}</label>
            <label><input type="radio" name="xr-rate" checked={atRate} onChange={() => setAtRate(true)} /> {t("xrAtRate")}{" "}
              <input className="xr-hz" type="number" min={0.001} step="any" value={rate} disabled={!atRate}
                onChange={(e) => setRate(e.target.value)} aria-label={t("xrRate")} /> Hz</label>
            {atRate && <>
              <label><input type="checkbox" checked={antialias} onChange={(e) => setAntialias(e.target.checked)} /> {t("xrAntialias")}</label>
              <p className="hint">{t("xrHow")}</p>
            </>}
          </fieldset>
          <label><input type="checkbox" checked={fromZero} onChange={(e) => setFromZero(e.target.checked)} /> {t("xrFromZero")}</label>
          <p className="hint">{t("xrFormatHint")}</p>
          {which === "screen" && !nShown && <p className="hint err">{t("xrNothing")}</p>}
        </div>
        <div className="dialog-foot">
          <span className="spacer" />
          <button className="btn outline" onClick={close}>{t("cancel")}</button>
          <button className="btn primary xr-go" disabled={bad || busy || !runs.length} onClick={run}><Icon.Download /> {t("xrExport")}</button>
        </div>
      </div>
    </div>
  );
}
