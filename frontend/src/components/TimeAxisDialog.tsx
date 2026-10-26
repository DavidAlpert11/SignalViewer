import { useEffect, useMemo, useState } from "react";
import { api, type TimeAxisCheck } from "../api";
import { useApp } from "../store";
import { fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { useEscape } from "./Overlays";
import { applyTimeAxis, CONVERSIONS, conversionOf, conversionScale, linkedPeers, plotUses, UNIT_SECONDS, xyInstead,
  type AxisChange } from "../timeAxis";

/** The time axis of one file: which column is its time (CSV / MAT / Parquet), its unit (a ready
 *  conversion or any scale) and its offset - with what the change does to the work, said before
 *  it is made (owner's request, 2026-10-26). */
export default function TimeAxisDialog() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runId = useApp((s) => s.timeAxisFor)!;
  const runs = useApp((s) => s.runs);
  const run = runs.find((r) => r.id === runId);
  const close = () => useApp.setState({ timeAxisFor: null });
  useEscape(close);
  const ax = run?.timeAxis;
  const [base, setBase] = useState<TimeAxisCheck | null>(null);     // the file as it is
  const [check, setCheck] = useState<TimeAxisCheck | null>(null);   // with the chosen column
  const [error, setError] = useState("");
  const [column, setColumn] = useState("");                          // "" = keep the current one
  const [scaleText, setScaleText] = useState(String(ax?.scale ?? 1));
  const [ownText, setOwnText] = useState(String(ax?.ownScale ?? 1));
  const [offsetText, setOffsetText] = useState(String(ax?.offset ?? 0));
  const [sortOk, setSortOk] = useState(false);
  const [peerOff, setPeerOff] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.checkTimeAxis(runId, null).then(setBase).catch((e) => setError(String((e as Error).message)));
  }, [runId]);
  const choose = async (c: string) => {
    setColumn(c); setCheck(null); setSortOk(false); setError("");
    if (!c) { setOffsetText(String(ax?.offset ?? 0)); return; }
    setOffsetText("0");                         // the old offset was on the old axis: it means nothing now
    try {
      const r = await api.checkTimeAxis(runId, c);
      setCheck(r);
      // the column's name says its unit: offered as the conversion to seconds (the user can change it)
      const u = r.column?.unit;
      setScaleText(String(u && UNIT_SECONDS[u] ? UNIT_SECONDS[u] : 1));
    } catch (e) { setError(String((e as Error).message)); }
  };

  const scale = Number(scaleText), own = Number(ownText), offset = Number(offsetText);
  const badNumber = !(scale > 0) || !Number.isFinite(scale) || !(own > 0) || !Number.isFinite(own) || !Number.isFinite(offset);
  const change: AxisChange = { column: column || null, scale, ownScale: own, offset };
  const changesSomething = !!ax && (!!column || scale !== ax.scale || own !== ax.ownScale || offset !== ax.offset);
  const col = check?.column;
  const mixed = !!col && (col.order === "mixed" || col.order === "decreasing");
  const peers = useMemo(() => (changesSomething && !badNumber ? linkedPeers(runId, change) : []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [runId, column, scale, own, runs, changesSomething, badNumber]);
  const others = runs.filter((r) => r.format !== "derived" && r.id !== runId).length;

  if (!run || !ax) return null;
  const info = base?.info ?? ax;
  const candidates = (base?.info.candidates ?? []);
  const fmt = (v: number | null | undefined, d = 6) => (v === null || v === undefined ? "–" : fmtNum(v, lang, d));
  const scaleChanges = scale !== ax.scale || own !== ax.ownScale;
  const conv = conversionOf(scale);

  // what the change means for the work, said before it is made
  const notes: { kind: "warn" | "info"; text: string }[] = [];
  if (col) {
    if (col.order === "empty") notes.push({ kind: "warn", text: t("taEmpty") });
    if (mixed) notes.push({ kind: "warn", text: t("taMixed", { n: col.backSteps ?? 0 }) });
    if ((col.repeats ?? 0) > 0) notes.push({ kind: "warn", text: t("taRepeats", { n: col.repeats ?? 0 }) });
    if (col.missing > 0) notes.push({ kind: "warn", text: t("taMissing", { n: col.missing }) });
    if ((col.gaps ?? 0) > 0) notes.push({ kind: "info", text: t("taGaps", { n: col.gaps ?? 0, gap: fmt(col.maxGap, 4), step: fmt(col.step, 4) }) });
    if (col.unit && col.unit !== "s") notes.push({ kind: "info", text: t("taUnitFromName", { unit: t(`unit_${col.unit}` as "unit_ms") }) });
    const uses = plotUses(`${runId}/${column}`);
    if (uses) notes.push({ kind: "info", text: t("taLeavesPlots", { name: column, n: uses }) });
    notes.push({ kind: "info", text: t("taOldTimeSignal", { name: info.column ?? "Time" }) });
    if ((check?.brokenDerived ?? []).length) notes.push({ kind: "warn", text: t("taBrokenDerived", { names: check!.brokenDerived!.join(", ") }) });
    if (info.ownTimes) notes.push({ kind: "info", text: t("taOwnTimesStay", { n: info.ownTimes }) });
    if (ax.offset) notes.push({ kind: "info", text: t("taOffsetReset", { s: fmt(ax.offset, 4) }) });
  }
  if ((column || scaleChanges) && base) {
    const timed = [...base.timedDerived, ...base.timedEdits.map((n) => `${n} (ƒ)`)];
    if (timed.length) notes.push({ kind: "warn", text: t("taTimedWork", { names: timed.slice(0, 8).join(", ") + (timed.length > 8 ? "…" : "") }) });
  }
  if (changesSomething && others) notes.push({ kind: "info", text: t(column || scaleChanges ? "taOthersKeepAxis" : "taOthersOffset", { n: others }) });
  if (changesSomething && !others) notes.push({ kind: "info", text: t("taPositionsFollow") });

  const apply = async () => {
    setBusy(true);
    try {
      await applyTimeAxis(runId, change, peers.filter((p) => !peerOff.has(p.id)).map((p) => p.id));
      close();
    } catch (e) {
      setError(String((e as Error).message));
    } finally { setBusy(false); }
  };

  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog rt-dialog ta-dialog" role="dialog" aria-label={t("timeAxisTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head">
          <h2>{t("timeAxisTitle")} <span className="muted">· {run.name}</span></h2>
          <button className="iconbtn" onClick={close} aria-label={t("close")}><Icon.X /></button>
        </div>
        <p className="hint rt-lead">{t("timeAxisLead")}</p>
        <div className="dialog-body rt-rows">
          {info.canColumn && (
            <fieldset className="sw-mode ta-column">
              <legend>{t("taColumn")}</legend>
              <label className="ta-field">
                <select className="ta-col" value={column} onChange={(e) => choose(e.target.value)} aria-label={t("taColumn")}>
                  <option value="">{t("taKeepColumn", { name: info.column ?? "–" })}</option>
                  {candidates.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
              {col && (
                <p className="hint ta-stats">
                  {t("taStats", { n: col.n, min: fmt(col.min), max: fmt(col.max), step: fmt(col.step, 4) })}
                  {" · "}{t(`taOrder_${col.order}` as "taOrder_increasing")}
                </p>
              )}
            </fieldset>
          )}
          {info.canScale ? (
            <fieldset className="sw-mode ta-scale">
              <legend>{t("taUnit")}</legend>
              <label className="ta-field">{t("taConversion")}
                <select className="ta-conv" value={conv || (scale === 1 ? "none" : "custom")}
                  onChange={(e) => { const v = e.target.value; if (v === "none") setScaleText("1"); else if (v !== "custom") setScaleText(String(conversionScale(v))); }}>
                  <option value="none">{t("taNoConversion")}</option>
                  {CONVERSIONS.map((c) => <option key={c.id} value={c.id}>{t(`unit_${c.from}` as "unit_ms")} → {t(`unit_${c.to}` as "unit_ms")} (×{fmtNum(conversionScale(c.id), lang, 6)})</option>)}
                  <option value="custom">{t("taCustom")}</option>
                </select>
              </label>
              <label className="ta-field">{t("taScale")}
                <input className="ta-scale-in" type="number" step="any" value={scaleText} onChange={(e) => setScaleText(e.target.value)} />
              </label>
              {info.ownTimes > 0 && (
                <label className="ta-field">{t("taOwnScale", { n: info.ownTimes })}
                  <input className="ta-own-in" type="number" step="any" value={ownText} onChange={(e) => setOwnText(e.target.value)} />
                </label>
              )}
            </fieldset>
          ) : <p className="hint">{t("taLogClock")}</p>}
          <fieldset className="sw-mode">
            <legend>{t("taOffset")}</legend>
            <label className="ta-field">{t("taOffsetLabel")}
              <input className="ta-offset-in" type="number" step="any" value={offsetText} onChange={(e) => setOffsetText(e.target.value)} />
            </label>
            <p className="hint">{t("taFormula")}</p>
          </fieldset>
          {notes.length > 0 && (
            <ul className="ta-notes">
              {notes.map((n, i) => <li key={i} className={n.kind}>{n.text}</li>)}
            </ul>
          )}
          {mixed && (
            <div className="ta-mixed">
              <label><input type="checkbox" className="ta-sort-ok" checked={sortOk} onChange={(e) => setSortOk(e.target.checked)} /> {t("taSortOk")}</label>
              <button className="btn outline sm ta-xy" onClick={() => { xyInstead(runId, column); close(); }}>{t("taXyInstead")}</button>
            </div>
          )}
          {peers.length > 0 && (
            <fieldset className="sw-mode ta-peers">
              <legend>{t("taPeers")}</legend>
              {peers.map((p) => (
                <label key={p.id}><input type="checkbox" checked={!peerOff.has(p.id)}
                  onChange={(e) => { const n = new Set(peerOff); if (e.target.checked) n.delete(p.id); else n.add(p.id); setPeerOff(n); }} /> {p.name}</label>
              ))}
            </fieldset>
          )}
          {badNumber && <p className="hint err">{t("taBadNumber")}</p>}
          {error && <p className="hint err">{error}</p>}
        </div>
        <div className="dialog-foot">
          <span className="spacer" />
          <button className="btn outline" onClick={close}>{t("cancel")}</button>
          <button className="btn primary ta-apply" disabled={busy || badNumber || !changesSomething || (mixed && !sortOk) || col?.order === "empty" || (!!column && !check)}
            onClick={apply}>{t("taApply")}</button>
        </div>
      </div>
    </div>
  );
}
