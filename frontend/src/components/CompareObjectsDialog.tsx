import { useMemo, useState } from "react";
import { useEscape } from "./Overlays";
import { actions, pickPath, useApp, type MapObject } from "../store";
import { api } from "../api";
import { fmtNum, translate, useT, type TKey } from "../i18n";
import { copyText } from "../errorReport";
import { RingIcon } from "./RelationPanel";
import { comparable, compareObjects, errorSignals, makeComparison, overlayObjects, pairOf, plotRelation, statsCsv,
  type CmpQty, type CmpShow, type CmpStat, type CompareFrame } from "../relation";

/* L8: Compare objects… - the one place to compare the objects of a map / 3D plot against a reference:
   positions, velocities and angles; their values, their errors or both; one tab per quantity and the
   errors' statistics. The relation box's old four actions are the presets at the top (same results). */
const FRAMES = ["ned", "enu", "ecef", "lla", "track"] as const;
const QTYS: CmpQty[] = ["position", "velocity", "attitude"];

export default function CompareObjectsDialog() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const req = useApp((s) => s.compareDialog);
  const ws = useApp((s) => s.ws);
  const plot = ws.tabs.flatMap((tb) => tb.plots).find((p) => p.id === req?.plotId);
  const objects = useMemo<MapObject[]>(() => plot?.objects ?? [], [plot]);
  const close = () => useApp.setState({ compareDialog: null });
  useEscape(close, true);
  const pair = plot ? pairOf(plot) : { primary: null, secondary: null };
  const ref = objects.find((o) => o.id === pair.primary) ?? objects[0];
  const [picked, setPicked] = useState<Set<string> | null>(null);       // null: every other object
  const others = objects.filter((o) => o.id !== ref?.id && (!picked || picked.has(o.id)));
  const can = useMemo(() => (ref ? comparable(ref, objects.filter((o) => o.id !== ref.id), objects) : null), [ref, objects]);
  const [qty, setQty] = useState<Set<CmpQty>>(() => new Set(["position", "velocity", "attitude"]));
  const [show, setShow] = useState<CmpShow>("both");
  const [frame, setFrame] = useState<CompareFrame>("ned");
  const [busy, setBusy] = useState(false);
  const [stats, setStats] = useState<CmpStat[] | null>(null);
  if (!plot || !ref || objects.length < 2 || !can) return null;
  const on = (q: CmpQty) => qty.has(q) && !can[q].reason;
  const chosen = QTYS.filter(on);
  const run = async (f: () => Promise<unknown>, done = true) => { setBusy(true); try { await f(); if (done) close(); } finally { setBusy(false); } };
  const S = objects.find((o) => o.id === pair.secondary) ?? others[0];
  const make = () => run(async () => {
    const r = await makeComparison({ ref, others, qty: chosen, show, frame }, objects);
    if (r.stats.length) setStats(r.stats); else if (r.tabs) close();
  }, false);
  const saveCsv = async () => {
    const path = await pickPath({ mode: "save", title: t("cmpSaveCsv"), exts: [".csv"], defaultName: `compare_vs_${ref.name}.csv` });
    if (!path || !stats) return;
    const r = await api.saveText(path, statsCsv(stats));
    useApp.getState().toast({ kind: "info", text: translate(lang, "savedTo", { path: r.path }) });
  };
  const num = (v?: number) => (v === undefined || !Number.isFinite(v) ? "—" : fmtNum(v, lang, 4));
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog cmpobj" role="dialog" aria-modal="true" aria-label={t("cmpTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("cmpTitle")}</h2></div>
        <div className="dialog-body">
          {/* the four one-click actions the relation box had (Q7): same results as before */}
          <div className="cmpobj-presets" role="group" aria-label={t("cmpPresets")}>
            <span className="cmpobj-label">{t("cmpPresets")}</span>
            <button className="btn sm rel-plot" disabled={busy || !S} title={t("cmpPresetPairHint", { s: S?.name ?? "", p: ref.name })}
              onClick={() => S && void run(() => plotRelation(ref, S, objects))}>{t("relPlot")}</button>
            <button className="btn sm rel-errors" disabled={busy || !S} title={t("cmpPresetPairHint", { s: S?.name ?? "", p: ref.name })}
              onClick={() => S && void run(() => errorSignals(ref, S, objects))}>{t("relErrors")}</button>
            <button className="btn sm rel-compare-btn" disabled={busy} title={t("relDiffsHint")} onClick={() => void run(() => compareObjects(ref, objects, frame))}>{t("relDiffs")}</button>
            <button className="btn sm rel-overlay-btn" disabled={busy || frame === "track"} title={t("relOverlayHint")}
              onClick={() => { if (frame !== "track") void run(() => overlayObjects(ref, objects, frame)); }}>{t("relOverlay")}</button>
          </div>
          <div className="cmpobj-grid">
            <label className="cmpobj-label" htmlFor="cmpobj-ref"><RingIcon kind="primary" /> {t("relPrimary")}</label>
            <select id="cmpobj-ref" className="cmpobj-ref" value={ref.id}
              onChange={(e) => { const x = e.target.value; actions.setObjectPair(plot.id, x, x === pair.secondary ? pair.primary : pair.secondary); setStats(null); }}>
              {objects.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
            <span className="cmpobj-label">{t("cmpObjects")}</span>
            <div className="cmpobj-objs" role="group" aria-label={t("cmpObjects")}>
              {objects.filter((o) => o.id !== ref.id).map((o) => (
                <label key={o.id}><input type="checkbox" checked={!picked || picked.has(o.id)}
                  onChange={(e) => { const n = new Set(picked ?? objects.filter((x) => x.id !== ref.id).map((x) => x.id)); if (e.target.checked) n.add(o.id); else n.delete(o.id); setPicked(n); setStats(null); }} />
                  <i className="cmpobj-dot" style={{ background: o.color }} />{o.name}</label>
              ))}
            </div>
            <span className="cmpobj-label">{t("cmpQuantities")}</span>
            <div className="cmpobj-qty" role="group" aria-label={t("cmpQuantities")}>
              {QTYS.map((q) => {
                const c = can[q];
                const outs = c.out.filter((x) => others.some((o) => o.id === x.o.id));
                return (
                  <div key={q} className="cmpobj-q">
                    <label title={c.reason}><input type="checkbox" className={`cmpobj-q-${q}`} disabled={!!c.reason} checked={on(q)}
                      onChange={(e) => { const n = new Set(qty); if (e.target.checked) n.add(q); else n.delete(q); setQty(n); }} />{t(`cmpQ_${q}` as TKey)}</label>
                    {c.reason ? <span className="hint cmpobj-why">{c.reason}</span>
                      : outs.length > 0 && on(q) && <span className="hint cmpobj-why">{outs.map((x) => x.why).join(" · ")}</span>}
                  </div>
                );
              })}
            </div>
            <span className="cmpobj-label">{t("cmpShow")}</span>
            <div className="seg cmpobj-show" role="radiogroup" aria-label={t("cmpShow")}>
              {(["values", "errors", "both"] as const).map((v) => (
                <button key={v} role="radio" aria-checked={show === v} className={show === v ? "on" : ""} onClick={() => setShow(v)}>{t(`cmpShow_${v}` as TKey)}</button>
              ))}
            </div>
            <label className="cmpobj-label" htmlFor="cmpobj-frame">{t("relFrame")}</label>
            <span>
              <select id="cmpobj-frame" className="cmpobj-frame" value={frame} title={t(`relFrameHint_${frame}` as TKey)} onChange={(e) => setFrame(e.target.value as CompareFrame)}>
                {FRAMES.map((f) => <option key={f} value={f} title={t(`relFrameHint_${f}` as TKey)}>{f === "track" ? t("cmpTrackFrame") : f.toUpperCase()}</option>)}
              </select>
              <span className="hint cmpobj-frame-hint">{t(`relFrameHint_${frame}` as TKey)}{frame === "track" && show !== "errors" ? ` ${t("cmpTrackNoValues")}` : ""}</span>
            </span>
          </div>
          {stats && (
            <div className="cmpobj-stats">
              <h3>{t("cmpStats")}</h3>
              <div className="cmpobj-stats-scroll">
                <table>
                  <thead><tr><th>{t("cmpStObject")}</th><th>{t("cmpStComp")}</th><th>RMS</th><th>{t("cmpStMean")}</th><th>{t("cmpStMax")}</th><th>{t("cmpStP95")}</th><th>{t("cmpStTmax")}</th></tr></thead>
                  <tbody>
                    {stats.map((r) => (
                      <tr key={r.id}><td>{r.object}</td><td>{r.comp}</td>
                        {[r.s?.rms, r.s?.mean, r.s?.abs_max, r.s?.p95_abs, r.s?.t_abs_max].map((v, i) => <td key={i}><bdi dir="ltr">{num(v)}</bdi></td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="hint">{t("cmpStatsHint")}</p>
            </div>
          )}
        </div>
        <div className="dialog-foot">
          {stats && <>
            <button className="btn cmpobj-copy" onClick={() => void copyText(statsCsv(stats)).then((ok) => ok && useApp.getState().toast({ kind: "info", text: t("cmpCopied") }))}>{t("cmpCopy")}</button>
            <button className="btn cmpobj-csv" onClick={() => void saveCsv()}>{t("cmpSaveCsv")}</button>
          </>}
          <span className="spacer" />
          <button className="btn" onClick={close}>{t("close")}</button>
          <button className="btn primary cmpobj-make" disabled={busy || !chosen.length || !others.length} onClick={() => void make()}>
            {busy ? t("cmpMaking") : t("cmpMake")}</button>
        </div>
      </div>
    </div>
  );
}
