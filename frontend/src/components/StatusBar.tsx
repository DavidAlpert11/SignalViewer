import { countRender } from "../perf";
import { activeTab, useApp } from "../store";
import { fmtInt, fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { effectiveBase, isOnlineBase } from "../mapBase";

export default function StatusBar() {
  countRender("StatusBar");
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
  const eventAt = useApp((s) => s.eventAt);
  // 26.U6 (O1): what leaves the PC - map tiles while a map / 3D view on screen uses an online layer;
  // "Network off" when the setting forbids it. Nothing is said in the default (nothing is sent).
  const netOff = useApp((s) => s.offlineOnly || s.offlineForced);
  const geoBase = useApp((s) => s.geoBase);
  const online = !netOff && isOnlineBase(effectiveBase(geoBase, netOff)) && tab.plots.some((p) => p.mode === "geo" || p.mode === "3d");
  return (
    <footer className="status" role="status">
      <span>{runs.length === 1 ? t("filesOpenOne") : t("filesOpen", { n: runs.length })}</span>
      <span>{t("samples", { n: fmtInt(samples, lang) })}</span>
      {d && d.total > 0 && <span title={d.shown < d.total ? t("shownPointsHint") : undefined}>{d.shown < d.total ? t("shownPoints", { n: fmtInt(d.shown, lang), total: fmtInt(d.total, lang) }) : t("allPoints")}</span>}
      {busy > 0 && <span>{t("loading")}</span>}
      <span style={{ flex: 1 }} />
      {/* 26.U8: the event ] / [ went to, while the cursor is on it */}
      {eventAt && cursor.on && cursor.t1 === eventAt.t && (
        <span className={`ev-at ${eventAt.level}`} title={t("hEvents")}>◆ {eventAt.n}/{eventAt.of} · {eventAt.text}</span>
      )}
      {online && <span className="net-state online" title={t("netOnlineHint")}>● {t("netOnline")}</span>}
      {netOff && <span className="net-state off" title={t("netOffHint")}>{t("netOff")}</span>}
      {streaming && <span className={`live${updating ? " on" : ""}`}>● {t("streamOn")} · {t("liveCount", { n: updating, total: followed.length })}
        {autoStop && idle > 5 ? ` · ${t("liveStopsIn", { s: Math.max(0, Math.ceil(autoStop - idle)) })}` : ""}</span>}
      <button className="status-help" onClick={() => useApp.setState({ helpOpen: true })} title={`${t("shortcuts")} (?)`} aria-label={t("shortcuts")}>
        <Icon.Keyboard width={14} height={14} /> ?
      </button>
      {cursor.on && cursor.t1 !== null && <span className="ct">T1 {fmtNum(cursor.t1, lang, 7)}{cursor.dual && cursor.t2 !== null ? `   T2 ${fmtNum(cursor.t2, lang, 7)}   ΔT ${fmtNum(cursor.t2 - cursor.t1, lang, 6)}` : ""}</span>}
    </footer>
  );
}
