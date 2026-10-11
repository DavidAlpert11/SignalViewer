import { useEffect, useState } from "react";
import { api, type SyncCandidate } from "../api";
import { fileLabel, useApp } from "../store";
import { fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { useEscape } from "./Overlays";
import SignalPicker from "./SignalPicker";
import { applySyncOffset, openSyncCheck } from "../sync";

/** Align this file's time with another recording of the same flight. */
export default function SyncDialog() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const other = useApp((s) => s.syncFor);
  const close = () => useApp.setState({ syncFor: null });
  useEscape(close);
  const me = runs.find((r) => r.id === other);
  const refs = runs.filter((r) => r.id !== other && r.format !== "derived");
  const [ref, setRef] = useState<string>(() => {
    // the likely partner: an autopilot log for a .tlog and the other way round
    const want = me?.format === "tlog" ? ["bin", "ulg"] : ["tlog"];
    return (refs.find((r) => want.includes(r.format)) ?? refs[0])?.id ?? "";
  });
  const [cands, setCands] = useState<SyncCandidate[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [manual, setManual] = useState<"" | "signal" | "feature" | "cursor">("");
  const [sa, setSa] = useState<string | null>(null);
  const [sb, setSb] = useState<string | null>(null);
  const [useLag, setUseLag] = useState(false);
  const [lag, setLag] = useState("2");
  const [kind, setKind] = useState("rise");
  const [level, setLevel] = useState("50");
  const [occ, setOcc] = useState("1");
  const cursor = useApp((s) => s.cursor);

  const find = async (pair?: [string, string], opts: Parameters<typeof api.syncSuggest>[4] = {}) => {
    if (!other || !ref) return;
    setBusy(true); setErr("");
    try {
      const r = await api.syncSuggest(ref, other, pair?.[0], pair?.[1], opts);
      setCands(r.candidates);
    } catch (e) { setErr(String((e as Error).message)); setCands([]); }
    finally { setBusy(false); }
  };
  useEffect(() => { find(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [ref, other]);
  if (!me) return null;

  const describe = (c: SyncCandidate) => {
    if (c.method === "boot") return t("syncBootDetail", { n: c.pairs ?? 0, ms: Math.round((c.spread ?? 0) * 1000) })
      + (c.reboots ? " " + t("syncReboot") : "");
    if (c.method === "events") return t("syncEventsDetail", { n: c.matched ?? 0, ms: Math.round((c.spread ?? 0) * 1000), ex: (c.examples ?? []).join(", ") });
    if (c.method === "feature") {
      if (c.error) return t("syncFeatureMissing", { where: [!c.found?.[0] ? t("syncReferenceShort") : "", !c.found?.[1] ? t("syncThisShort") : ""].filter(Boolean).join(", ") });
      return t("syncFeatureDetail", { k: t(`syncK_${c.kind}` as "syncK_rise"), a: c.pair?.[0] ?? "", b: c.pair?.[1] ?? "",
        ta: fmtNum(c.at?.[0] ?? 0, lang, 6), tb: fmtNum(c.at?.[1] ?? 0, lang, 6) });
    }
    return (c.sameNames ? t("syncSameNames") + " " : "") + t("syncSignalDetail", { a: c.pair?.[0] ?? "", b: c.pair?.[1] ?? "", r: fmtNum(c.corr ?? 0, lang, 3) });
  };
  const nameOf = (id: string) => id.slice(id.indexOf("/") + 1);
  const sigOpts = (rid: string) => runs.filter((r) => r.id === rid).flatMap((r) => r.signals.map((s) => ({ id: s.id, label: s.name, group: fileLabel(runs, r.id) })));

  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog sync-dialog" role="dialog" aria-label={t("syncTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("syncTitle")}</h2>
          <button className="iconbtn" onClick={close} aria-label={t("close")}><Icon.X /></button></div>
        <div className="dialog-pad">
          <p className="hint">{t("syncExplain")}</p>
          <div className="sync-files">
            <div><span className="lbl">{t("syncMove")}</span><b>{fileLabel(runs, me.id)}</b>
              <span className="hint"> · {t("syncCurrent", { s: fmtNum(me.timeOffset ?? 0, lang, 6) })}</span></div>
            <label className="afield"><span>{t("syncReference")}</span>
              <select value={ref} onChange={(e) => setRef(e.target.value)}>
                {refs.map((r) => <option key={r.id} value={r.id}>{fileLabel(runs, r.id)}</option>)}
              </select></label>
          </div>
        </div>
        <div className="dialog-body sync-list">
          {busy && <p className="empty-note">{t("syncSearching")}</p>}
          {!busy && err && <p className="hint err">{err}</p>}
          {!busy && cands?.length === 0 && !err && <p className="empty-note">{t("syncNothing")}</p>}
          {!busy && cands?.map((c, i) => c.error ? (
            <div key={i} className="sync-row q-low"><div className="sync-main">
              <div className="sync-name">{t(`syncM_${c.method}` as "syncM_boot")}</div>
              <div className="sync-detail err">{describe(c)}</div></div></div>
          ) : (
            <div key={i} className={`sync-row q-${c.quality}`}>
              <div className="sync-main">
                <div className="sync-name">{t(`syncM_${c.method}` as "syncM_boot")}
                  <span className={`qbadge ${c.quality}`}>{t(`syncQ_${c.quality}` as "syncQ_high")}</span>
                  {i > 0 && c.agrees !== undefined && <span className={`agree ${c.agrees ? "yes" : "no"}`}>{c.agrees ? t("syncAgrees") : t("syncDisagrees")}</span>}
                </div>
                <div className="sync-detail">{describe(c)}</div>
                <div className="sync-off" dir="ltr">{c.delta >= 0 ? "+" : ""}{c.delta.toFixed(3)} s → {t("timeOffset")} {c.offset.toFixed(3)} s</div>
              </div>
              <div className="sync-actions">
                <button className="btn primary" onClick={async () => { await applySyncOffset(me.id, c.offset); close(); }}>{t("syncApply")}</button>
                {c.check && (c.check.pair || c.check.refMode) && (
                  <button className="btn" onClick={async () => { await applySyncOffset(me.id, c.offset); openSyncCheck(ref, me.id, c); close(); }}
                    title={t("syncCheckHint")}>{t("syncApplyCheck")}</button>
                )}
              </div>
            </div>
          ))}
          <div className="sync-manual">
            <div className="sync-manual-head">{t("syncMore")}</div>
            <div className="seg sync-ways" role="tablist">
              {(["signal", "feature", "cursor"] as const).map((m) => (
                <button key={m} role="tab" aria-selected={manual === m} className={manual === m ? "on" : ""}
                  onClick={() => setManual(manual === m ? "" : m)}>{t(`syncWay_${m}` as "syncWay_signal")}</button>
              ))}
            </div>
            {(manual === "signal" || manual === "feature") && (
              <div className="sync-manual-body">
                <p className="hint">{t(manual === "signal" ? "syncManualHint" : "syncFeatureHint")}</p>
                <label className="afield"><span>{t("syncRefSignal")}</span>
                  <SignalPicker value={sa} options={sigOpts(ref)} ariaLabel={t("syncRefSignal")} placeholder={t("syncPick")} onChange={setSa} /></label>
                <label className="afield"><span>{t("syncOtherSignal")}</span>
                  <SignalPicker value={sb} options={sigOpts(me.id)} ariaLabel={t("syncOtherSignal")} placeholder={t("syncPick")} onChange={setSb} /></label>
                {manual === "signal" ? (
                  <label className="sync-inline"><input type="checkbox" checked={useLag} onChange={(e) => setUseLag(e.target.checked)} />
                    {t("syncLagA")} <input className="num" value={lag} onChange={(e) => setLag(e.target.value)} disabled={!useLag} inputMode="decimal" /> {t("syncLagB")}</label>
                ) : (
                  <div className="sync-feature">
                    <label>{t("syncKind")} <select value={kind} onChange={(e) => setKind(e.target.value)}>
                      {["rise", "fall", "step", "change", "max", "min", "start"].map((k) => <option key={k} value={k}>{t(`syncK_${k}` as "syncK_rise")}</option>)}
                    </select></label>
                    {(kind === "rise" || kind === "fall") && (
                      <label>{t("syncLevel")} <select value={level} onChange={(e) => setLevel(e.target.value)}>
                        {[10, 25, 50, 75, 90].map((v) => <option key={v} value={v}>{v}%</option>)}</select></label>
                    )}
                    {(kind === "rise" || kind === "fall" || kind === "change") && (
                      <label>{t("syncOccurrence")} <select value={occ} onChange={(e) => setOcc(e.target.value)}>
                        <option value="1">{t("syncOcc1")}</option><option value="2">{t("syncOcc2")}</option>
                        <option value="3">{t("syncOcc3")}</option><option value="-1">{t("syncOccLast")}</option></select></label>
                    )}
                  </div>
                )}
                <button className="btn" disabled={!sa || !sb || busy} onClick={() => manual === "signal"
                  ? find([nameOf(sa!), nameOf(sb!)], { maxLag: useLag && Number(lag) > 0 ? Number(lag) : null })
                  : find([nameOf(sa!), nameOf(sb!)], { feature: { kind, levelPct: Number(level), occurrence: Number(occ) } })}>
                  {t(manual === "signal" ? "syncCorrelate" : "syncFindMoment")}</button>
              </div>
            )}
            {manual === "cursor" && (
              <div className="sync-manual-body">
                <p className="hint">{t("syncCursorHint")}</p>
                {cursor.on && cursor.dual && cursor.t1 !== null && cursor.t2 !== null ? (
                  <>
                    <div className="sync-off" dir="ltr">T1 {fmtNum(cursor.t1, lang, 7)} s (ref) · T2 {fmtNum(cursor.t2, lang, 7)} s ({fileLabel(runs, me.id)}) → {(cursor.t1 - cursor.t2) >= 0 ? "+" : ""}{(cursor.t1 - cursor.t2).toFixed(4)} s</div>
                    <button className="btn primary" onClick={async () => {
                      await applySyncOffset(me.id, (me.timeOffset ?? 0) + (cursor.t1! - cursor.t2!)); close();
                    }}>{t("syncCursorApply")}</button>
                  </>
                ) : <p className="hint err">{t("syncCursorNeed")}</p>}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
