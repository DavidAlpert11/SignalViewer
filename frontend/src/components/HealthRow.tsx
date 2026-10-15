import type { HealthFinding } from "../api";
import { actions, useApp } from "../store";
import { fmtNum, useT } from "../i18n";

const fmtTime = (t: number, lang: "en" | "he") => fmtNum(t, lang, Math.abs(t) >= 1000 ? 7 : 5);

/** One finding of a flight log's health check: what was found, where (jump / zoom to it) and a
 *  plot of the signals behind it. Shared by the Log panel and the start card (T29). */
export default function HealthRow({ f, runId, maxSpans = 4 }: { f: HealthFinding; runId: string; maxSpans?: number }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const ids = f.signals.map((n) => `${runId}/${n}`).filter((id) => runs.some((r) => r.signals.some((x) => x.id === id)));
  const fmtT = (v: number) => fmtTime(v, lang);
  const vals = Object.fromEntries(Object.entries(f.vals).map(([k, v]) => [k, Array.isArray(v) ? v.join(", ") : String(v)]));
  return (
    <li className={`hrow ${f.level}`}>
      <span className={`hicon ${f.level}`} aria-label={t(`level_${f.level}` as "level_ok")}>{f.level === "ok" ? "✓" : f.level === "warning" ? "!" : "✕"}</span>
      <div className="hbody">
        <div className="htext">{t(`h_${f.code}_${f.level}` as "h_vibration_ok", vals)}</div>
        <div className="hlinks">
          {f.t !== null && <button className="pchange" onClick={() => actions.goToTime(f.t!)} title={t("logGoTo")}>@ {fmtT(f.t)}</button>}
          {f.spans.slice(0, maxSpans).map(([a, b], k) => b > a && (
            <button key={k} className="pchange span" onClick={() => actions.showSpan(a, b)} title={t("healthSpan")}>
              {fmtT(a)}–{fmtT(b)}</button>
          ))}
          {f.spans.length > maxSpans && <span className="at">+{f.spans.length - maxSpans}</span>}
          {ids.length > 0 && (
            <button className="pchange plot" onClick={() => actions.plotSignalsInNewTab(ids, t(`hTitle_${f.code}` as "hTitle_vibration"))}
              title={t("healthPlotHint")}>{t("healthPlot")}</button>
          )}
        </div>
      </div>
    </li>
  );
}
