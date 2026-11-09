/* 26.U7: a file's data quality, signal by signal (svcore/quality.py). */
import { useEffect, useState } from "react";
import { api } from "../api";
import { actions, fileLabel, useApp } from "../store";
import { fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { useEscape } from "./Overlays";
import { signalLines } from "../quality";

export default function QualityDialog() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runId = useApp((s) => s.qualityFor)!;
  const runs = useApp((s) => s.runs);
  const q = useApp((s) => s.quality[runId]);
  const [all, setAll] = useState(false);
  const close = () => useApp.setState({ qualityFor: null });
  useEscape(close);
  useEffect(() => {                          // opened from the file's menu before (or without) the check
    if (q) return;
    api.runQuality(runId).then((r) => useApp.setState((s) => ({ quality: { ...s.quality, [runId]: r } }))).catch(() => {});
  }, [runId, q]);
  if (!runs.some((r) => r.id === runId)) return null;
  const rows = q ? q.signals.filter((s) => all || s.issues.length) : [];
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog dq-dialog" role="dialog" aria-label={t("dqTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head">
          <h2>{t("dqTitle")} <span className="muted">· {fileLabel(runs, runId)}</span></h2>
          <button className="iconbtn" onClick={close} aria-label={t("close")}><Icon.X /></button>
        </div>
        <p className="hint rt-lead">{t("dqLead")}</p>
        {q?.sorted && <p className="hint rt-lead dq-sorted">{t("dqSorted")}</p>}
        {!q ? <p className="hint rt-lead">{t("loading")}</p> : !q.withIssues && !all ? <p className="rt-lead dq-none">{t("dqNone")}</p> : (
          <div className="dialog-body dq-body">
            <table className="vals dq-table">
              <thead><tr><th>{t("signal")}</th><th>{t("dqRateCol")}</th><th>{t("dqWhat")}</th></tr></thead>
              <tbody>{rows.map((s) => {
                const lines = signalLines(s, lang);
                return (
                  <tr key={s.name} className={s.issues.length ? "bad" : ""}>
                    <td><button className="linklike" onClick={() => { actions.addSignalLinked(`${runId}/${s.name}`); close(); }}>{s.name}</button></td>
                    <td className="num">{s.rate ? `${fmtNum(s.rate, lang, 4)} Hz` : "–"}</td>
                    <td>{lines.length ? <ul>{lines.map((l, i) => <li key={i}>{l}</li>)}</ul> : <span className="muted">✓</span>}</td>
                  </tr>
                );
              })}</tbody>
            </table>
          </div>
        )}
        <div className="dialog-foot">
          {q && <button className="linklike" onClick={() => setAll(!all)}>{all ? t("dqOnlyIssues") : `${t("dqAll")} (${q.checked})`}</button>}
          <span style={{ flex: 1 }} />
          <button className="btn primary" onClick={close}>{t("close")}</button>
        </div>
      </div>
    </div>
  );
}
