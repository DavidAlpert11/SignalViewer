import { activeTab, useApp } from "../store";
import { fmtInt, fmtNum, useT } from "../i18n";
import { Icon } from "../icons";

export default function StatusBar() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs).filter((r) => r.format !== "derived");
  const tab = useApp((s) => activeTab(s.ws));
  const dec = useApp((s) => s.decimation);
  const cursor = useApp((s) => s.cursor);
  const streaming = useApp((s) => s.streaming);
  const busy = useApp((s) => s.busy);
  const activity = useApp((s) => s.activity);
  const autoStop = useApp((s) => s.liveAutoStop);
  const followed = runs.filter((r) => !r.copy);
  const updating = followed.filter((r) => (activity[r.id] ?? Infinity) < 3).length;
  const idle = useApp((s) => s.liveIdle);
  const plot = tab.plots[tab.active];
  const d = plot ? dec[plot.id] : undefined;
  const samples = runs.reduce((a, r) => a + r.samples, 0);
  return (
    <footer className="status" role="status">
      <span>{t("filesOpen", { n: runs.length })}</span>
      <span>{t("samples", { n: fmtInt(samples, lang) })}</span>
      {d && d.total > 0 && <span>{d.shown < d.total ? t("shownPoints", { n: fmtInt(d.shown, lang), total: fmtInt(d.total, lang) }) : t("allPoints")}</span>}
      {busy > 0 && <span>{t("loading")}</span>}
      <span style={{ flex: 1 }} />
      {streaming && <span className={`live${updating ? " on" : ""}`}>● {t("streamOn")} · {t("liveCount", { n: updating, total: followed.length })}
        {autoStop && idle > 5 ? ` · ${t("liveStopsIn", { s: Math.max(0, Math.ceil(autoStop - idle)) })}` : ""}</span>}
      <button className="status-help" onClick={() => useApp.setState({ helpOpen: true })} title={`${t("shortcuts")} (?)`} aria-label={t("shortcuts")}>
        <Icon.Keyboard width={14} height={14} /> ?
      </button>
      {cursor.on && cursor.t1 !== null && <span className="ct">T1 {fmtNum(cursor.t1, lang, 7)}{cursor.dual && cursor.t2 !== null ? `   T2 ${fmtNum(cursor.t2, lang, 7)}   ΔT ${fmtNum(cursor.t2 - cursor.t1, lang, 6)}` : ""}</span>}
    </footer>
  );
}
