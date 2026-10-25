import { useCallback, useState } from "react";
import { api, type SignalInfo } from "../api";
import SignalField from "./SignalField";
import { actions, activeTab, rangeKey, useApp } from "../store";
import { fmtNum, useT } from "../i18n";

type Res = Awaited<ReturnType<typeof api.errorSegments>>;

/* T25: how far A is from B (a simulation from the flight, a model from the test) - RMS, mean and the
   largest |A − B| over the time both have, and for each stretch of a state signal (flight mode, test
   phase): the phase where they part ways stands out. Shown under Create signals > Two signals (A − B),
   where the error signal itself is made. */
export default function ErrorSegments({ a, b, alignment }: { a: string; b: string; alignment: string }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const [state, setState] = useState("");
  const [res, setRes] = useState<Res | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  // per state signal: the ones with texts (modes) or few distinct values, typed by name; A's file first
  const stateOnly = useCallback((s: SignalInfo) => !!(s.discrete || s.labels), []);
  const run = async () => {
    setBusy(true); setErr("");
    try { setRes(await api.errorSegments(a, b, state || null, alignment)); }
    catch (e) { setRes(null); setErr(String((e as Error).message)); }
    finally { setBusy(false); }
  };
  const zoom = (t0: number, t1: number) => {
    const tab = activeTab(useApp.getState().ws);
    const p = tab.plots[tab.active];
    if (p) actions.setRange(rangeKey(tab, p), [t0, t1]);
  };
  const f = (v: number | undefined) => (v === undefined ? "–" : fmtNum(v, lang, 4));
  const worst = res?.rows.length ? Math.max(...res.rows.map((r) => r.rms ?? 0)) : 0;
  return (
    <div className="err-seg">
      <h3 className="alist-head">{t("errTitle")}</h3>
      <p className="hint">{t("errHint")}</p>
      <div className="arow">
        <label className="afield grow"><span>{t("errPer")}</span>
          <SignalField value={state || null} ariaLabel={t("errPer")} placeholder={t("errWhole")} noneLabel={t("errWhole")}
            filter={stateOnly} prefer={a.split("/")[0]} onChange={(id) => { setState(id ?? ""); setRes(null); }} /></label>
        <button className="btn outline" disabled={!a || !b || busy} onClick={run}>{busy ? t("loading") : t("errShow")}</button>
      </div>
      {err && <p className="hint err">{err}</p>}
      {res && (res.total.n === 0 ? <p className="hint">{t("errNoOverlap")}</p> : (
        <table className="err-table">
          <thead><tr><th>{t("errSegment")}</th><th>{t("errFrom")}</th><th>RMS</th><th>{t("errMean")}</th><th>{t("errMax")}</th></tr></thead>
          <tbody>
            {res.rows.map((r, i) => (
              <tr key={i} className={r.rms === worst && res.rows.length > 1 ? "worst" : ""}>
                <td><button className="linklike" onClick={() => zoom(r.t0, r.t1)} title={t("errZoom")}>{(r.label ?? fmtNum(r.value, lang, 4)) + (r.occurrence > 1 ? ` #${r.occurrence}` : "")}</button></td>
                <td>{fmtNum(r.t0, lang, 5)} · {fmtNum(r.t1 - r.t0, lang, 3)} s</td>
                <td>{f(r.rms)}</td><td>{f(r.mean)}</td>
                <td><button className="linklike" onClick={() => actions.goToTime(r.tMaxAbs!)} title={t("logGoTo")}>{f(r.maxAbs)}</button></td>
              </tr>
            ))}
            <tr className="total"><td>{t("errAll")}</td><td>{fmtNum(res.total.n, lang, 6)} {t("errSamples")}</td>
              <td>{f(res.total.rms)}</td><td>{f(res.total.mean)}</td>
              <td><button className="linklike" onClick={() => actions.goToTime(res.total.tMaxAbs!)} title={t("logGoTo")}>{f(res.total.maxAbs)}</button></td></tr>
          </tbody>
        </table>
      ))}
    </div>
  );
}
