import { useMemo, useState } from "react";
import { useEscape } from "./Overlays";
import { actions, pickPath, useApp } from "../store";
import { api } from "../api";
import { fmtNum, translate, useT, type TKey } from "../i18n";
import { copyText } from "../errorReport";
import { findDerived } from "../peers";
import { cmpLayout, statsCsv, type CmpShow, type CmpStat } from "../relation";
import { angleWrap, familiesOf, findFamilies, referenceOf, wrapFor, type Family, type Member } from "../similar";

/* L9: Compare with similar… - the families of one file's signals that differ in one segment of their
   names (nav1 / nav2, XKF1[0] / XKF1[1], truth / nav): their values on one side, each member minus the
   reference on the other (angles wrapped), one row per leaf, in one new tab; the errors' statistics. */
export default function CompareSimilarDialog() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const req = useApp((s) => s.similarDialog);
  const runs = useApp((s) => s.runs);
  const close = () => useApp.setState({ similarDialog: null });
  useEscape(close, true);
  const run = runs.find((r) => r.id === req?.runId);
  const [loose, setLoose] = useState(false);
  const fams = useMemo(() => {
    if (!run) return [];
    const all = findFamilies(run.signals, loose);
    return req?.ids.length ? familiesOf(all, req.ids) : all;
  }, [run, loose, req]);
  const [off, setOff] = useState<Set<string>>(new Set());
  const chosen = fams.filter((f) => !off.has(f.key));
  // the reference: one segment for all the chosen families (a truth-class one, else the first family's)
  const segs = [...new Set(chosen.flatMap((f) => f.members.map((m) => m.seg)))];
  const [refSeg, setRefSeg] = useState<string | null>(null);
  const refDefault = chosen.length ? referenceOf(chosen[0]).seg : "";
  const ref = refSeg && segs.includes(refSeg) ? refSeg : refDefault;
  const refOf = (f: Family): Member => f.members.find((m) => m.seg === ref) ?? referenceOf(f);
  const [show, setShow] = useState<CmpShow>("both");
  const [busy, setBusy] = useState(false);
  const [stats, setStats] = useState<CmpStat[] | null>(null);
  if (!req || !run) return null;
  // the same names in other open files: that is Compare's job (ComparePanel), not this dialog's
  const names = new Set(run.signals.filter((s) => req.ids.includes(s.id)).map((s) => s.name));
  const elsewhere = names.size > 0 && runs.some((r) => r.id !== run.id && r.format !== "derived" && r.signals.some((s) => names.has(s.name)));

  const make = async () => {
    setBusy(true);
    try {
      const plots: { values: { title: string; ids: string[] }[]; errors: { title: string; ids: string[] }[] } = { values: [], errors: [] };
      const rows: CmpStat[] = [];
      for (const f of chosen) {
        const R = refOf(f);
        const others = f.members.filter((m) => m.id !== R.id);
        plots.values.push({ title: f.leaf, ids: [R.id, ...others.map((m) => m.id)] });
        const errs: string[] = [];
        if (show !== "values" && !f.unitsDiffer) {
          for (const m of others) {
            const wrap = await wrapFor(useApp.getState().runs, m.id);
            const params = wrap ? { wrap } : {};
            let id = findDerived(useApp.getState().runs, "sub", params, [m.id, R.id]);
            if (!id) {
              const r = await api.createDerived("sub", [m.id, R.id], params);
              useApp.setState({ runs: r.runs });
              id = r.id;
            }
            errs.push(id);
            rows.push({ object: m.seg, qty: f.leaf, comp: `${m.seg} − ${R.seg}`, id });
          }
        }
        plots.errors.push({ title: `${f.leaf}: − ${R.seg}`, ids: errs });
      }
      const lay = cmpLayout(show, plots.values, plots.errors, []);
      const n = actions.plotTabs([{ name: t("simTab", { leaf: chosen.length === 1 ? chosen[0].leaf : run.name, ref }), ...lay }]);
      if (n) useApp.getState().toast({ kind: "info", undoesWs: true, text: t("cmpMade", { n }), action: { label: t("undo"), run: () => useApp.getState().undo() } });
      if (rows.length) {
        try { const st = (await api.stats(rows.map((r) => r.id), null, null)).stats; rows.forEach((r) => (r.s = st[r.id])); } catch { /* the plots are made */ }
        setStats(rows);
      } else close();
    } catch (e) {
      useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
    } finally { setBusy(false); }
  };
  const saveCsv = async () => {
    const path = await pickPath({ mode: "save", title: t("cmpSaveCsv"), exts: [".csv"], defaultName: "similar_signals.csv" });
    if (!path || !stats) return;
    const r = await api.saveText(path, statsCsv(stats));
    useApp.getState().toast({ kind: "info", text: translate(lang, "savedTo", { path: r.path }) });
  };
  const num = (v?: number) => (v === undefined || !Number.isFinite(v) ? "—" : fmtNum(v, lang, 4));
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog cmpobj simdlg" role="dialog" aria-modal="true" aria-label={t("simTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("simTitle")}</h2></div>
        <div className="dialog-body">
          {elsewhere && (
            <p className="hint sim-elsewhere">{t("simElsewhere")}{" "}
              <button className="linklike" onClick={() => { close(); useApp.setState({ panel: "compare" }); }}>{t("simOpenCompare")}</button></p>
          )}
          {!fams.length ? <p className="hint sim-none">{t(loose ? "simNoneLoose" : "simNone")}</p> : (
            <ul className="sim-list">
              {fams.map((f) => (
                <li key={f.key} className="sim-fam">
                  <label>
                    <input type="checkbox" checked={!off.has(f.key)} onChange={(e) => { const n = new Set(off); if (e.target.checked) n.delete(f.key); else n.add(f.key); setOff(n); setStats(null); }} />
                    <bdi dir="ltr" className="sim-leaf">{f.leaf}</bdi>
                  </label>
                  <span className="sim-members">{f.members.map((m) => <bdi dir="ltr" key={m.id} className={`sim-member${m.id === refOf(f).id ? " ref" : ""}`}>{m.seg}</bdi>)}</span>
                  <span className="hint sim-how">{t(`simHow_${f.how}` as TKey)}{f.unitsDiffer ? ` · ${t("simUnits")}` : ""}</span>
                </li>
              ))}
            </ul>
          )}
          <label className="sim-loose"><input type="checkbox" checked={loose} onChange={(e) => { setLoose(e.target.checked); setStats(null); }} /> {t("simLoose")}</label>
          {chosen.length > 0 && (
            <div className="cmpobj-grid">
              <label className="cmpobj-label" htmlFor="sim-ref">{t("relPrimary")}</label>
              <select id="sim-ref" className="sim-ref" value={ref} onChange={(e) => { setRefSeg(e.target.value); setStats(null); }}>
                {segs.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
              <span className="cmpobj-label">{t("cmpShow")}</span>
              <div className="cmpobj-show" role="radiogroup" aria-label={t("cmpShow")}>
                {(["values", "errors", "both"] as const).map((v) => (
                  <button key={v} role="radio" aria-checked={show === v} className={show === v ? "on" : ""} onClick={() => setShow(v)}>{t(`cmpShow_${v}` as TKey)}</button>
                ))}
              </div>
            </div>
          )}
          {chosen.some((f) => angleWrap(f.members[0].name) !== null) && <p className="hint">{t("simWrapHint")}</p>}
          {stats && (
            <div className="cmpobj-stats">
              <h3>{t("cmpStats")}</h3>
              <div className="cmpobj-stats-scroll">
                <table>
                  <thead><tr><th>{t("simStSignal")}</th><th>{t("cmpStComp")}</th><th>RMS</th><th>{t("cmpStMean")}</th><th>{t("cmpStMax")}</th><th>{t("cmpStP95")}</th><th>{t("cmpStTmax")}</th></tr></thead>
                  <tbody>{stats.map((r) => (
                    <tr key={r.id}><td><bdi dir="ltr">{r.qty}</bdi></td><td><bdi dir="ltr">{r.comp}</bdi></td>
                      {[r.s?.rms, r.s?.mean, r.s?.abs_max, r.s?.p95_abs, r.s?.t_abs_max].map((v, i) => <td key={i}><bdi dir="ltr">{num(v)}</bdi></td>)}</tr>
                  ))}</tbody>
                </table>
              </div>
            </div>
          )}
        </div>
        <div className="dialog-foot">
          {stats && <>
            <button className="btn" onClick={() => void copyText(statsCsv(stats)).then((ok) => ok && useApp.getState().toast({ kind: "info", text: t("cmpCopied") }))}>{t("cmpCopy")}</button>
            <button className="btn" onClick={() => void saveCsv()}>{t("cmpSaveCsv")}</button>
          </>}
          <span className="spacer" />
          <button className="btn" onClick={close}>{t("close")}</button>
          <button className="btn primary sim-make" disabled={busy || !chosen.length} onClick={() => void make()}>{busy ? t("cmpMaking") : t("cmpMake")}</button>
        </div>
      </div>
    </div>
  );
}
