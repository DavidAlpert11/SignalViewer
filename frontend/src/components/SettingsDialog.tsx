import { useEffect, useState, type ReactElement } from "react";
import { api, type StorageInfo, type StorageKind } from "../api";
import { actions, LINE_STYLES, useApp, type LineStyle } from "../store";
import { useT, type TKey } from "../i18n";
import { Icon } from "../icons";
import { fmtSize } from "../values";
import { useEscape } from "./Overlays";
import { elevationFolder, MAP_CHOICES, resetMapPrefs, setElevationFolder, setIconFor, setMapPref, type ObjClassKey } from "../mapDefaults";
import { pickPath } from "../store";

/** What the app keeps on disk for speed (the CSV cache, copies of dropped files, map tiles), each
 *  with its size and a Clear button. A choice made once in a while: it lives in Settings. */
function StorageSection() {
  const t = useT();
  const [info, setInfo] = useState<StorageInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  useEffect(() => { api.storage().then(setInfo).catch(() => {}); }, []);
  const clear = async (what: StorageKind[]) => {
    setBusy(true);
    try {
      const r = await api.clearStorage(what);
      setInfo(r);
      const vals = Object.values(r.result);
      const freed = vals.reduce((a, x) => a + (x?.freed ?? 0), 0), kept = vals.reduce((a, x) => a + (x?.kept ?? 0), 0);
      setNote(t("storageFreed", { size: fmtSize(freed) }) + (kept ? " · " + t("storageKept", { n: kept }) : ""));
    } catch (e) {
      useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
    } finally { setBusy(false); }
  };
  const rows: [StorageKind, string][] = [["cache", t("storageCache")], ["uploads", t("storageUploads")], ["tiles", t("storageTiles")], ["memory", t("storageMemory")]];
  const ltr = (x: string) => `\u2066${x}\u2069`;      // each size isolated left-to-right inside a Hebrew sentence
  // P2: the memory cache shows its limit too ("120 MB of 1 GB"); its kinds on hover
  const sizeOf = (k: StorageKind) => !info?.[k] ? "…" : k === "memory" && info[k].limit
    ? t("storageOfLimit", { size: ltr(fmtSize(info[k].bytes)), limit: ltr(fmtSize(info[k].limit!)) }) : fmtSize(info[k].bytes);
  const titleOf = (k: StorageKind) => k === "memory" ? Object.entries(info?.[k]?.kinds ?? {}).map(([kind, v]) => `${t(("memKind_" + kind) as never)}: ${fmtSize(v.bytes)}`).join("\n") || undefined : info?.[k].path;
  return (
    <div className="set-storage">
      <div className="set-row"><span>{t("storage")}<small>{t("storageHint")}</small></span>
        <button className="btn outline" disabled={busy || !info} onClick={() => clear(["cache", "uploads"])}>{t("storageClearAll")}</button></div>
      {rows.map(([k, label]) => (
        <div className="set-row sub" key={k}>
          <span>{label}<small title={titleOf(k)}><bdi>{sizeOf(k)}</bdi></small></span>
          <button className="btn outline" disabled={busy || !info?.[k] || !info[k].bytes} onClick={() => clear([k])}>{t("storageClear")}</button>
        </div>
      ))}
      {note && <p className="hint" role="status">{note}</p>}
    </div>
  );
}

/** P8: Settings > Map and objects - choices for new objects, new Maps and the next export (mapDefaults.ts). */
function MapSection({ seg }: { seg: <V extends string | number>(value: V, opts: [V, string][], set: (v: V) => void, label: string) => ReactElement }) {
  const t = useT();
  const m = useApp((s) => s.mapPrefs);
  const [elev, setElev] = useState(elevationFolder());
  const row = (label: TKey, ctl: ReactElement, hint?: TKey) => <div className="set-row"><span>{t(label)}{hint && <small>{t(hint)}</small>}</span>{ctl}</div>;
  return (
    <section className="set-map" aria-label={t("setMap")}>
      <div className="set-group-head"><h3>{t("setMap")}</h3>
        <button className="linkbtn set-map-reset" onClick={() => { resetMapPrefs(); setElev(""); }}>{t("setMapReset")}</button></div>
      <p className="hint">{t("setMapNew")}</p>
      <div className="set-row set-map-icons"><span>{t("setMapIcon")}<small>{t("setMapIconHint")}</small></span>
        <span className="set-icons">{(["truth", "navigation", "receiver", "other"] as ObjClassKey[]).map((c) => (
          <label key={c}>{t(`setCls_${c}` as TKey)} <select className={`set-icon-${c}`} value={m.icon[c]} onChange={(e) => setIconFor(c, e.target.value as never)}>
            {MAP_CHOICES.kinds.map((k) => <option key={k} value={k}>{t(`obj_${k}` as TKey)}</option>)}</select></label>
        ))}</span></div>
      {row("setMapCamera", seg(m.camera, [["free", t("g3CamFree")], ["top", t("g3CamTop")], ["centre", t("g3CamCentre")], ["chase", t("g3CamChase")]], (v) => setMapPref("camera", v), t("setMapCamera")))}
      {row("setMapDrawing", seg(m.drawing, [["auto", t("setMapDrawAuto")], ["flat", t("setMapDrawFlat")]], (v) => setMapPref("drawing", v), t("setMapDrawing")), "setMapDrawingHint")}
      {row("setMapRelation", seg(m.relation, [["shown", t("setShown")], ["hidden", t("setHidden")]], (v) => setMapPref("relation", v), t("setMapRelation")))}
      {row("setMapNames", seg(m.names, [["shown", t("setShown")], ["hidden", t("setHidden")]], (v) => setMapPref("names", v), t("setMapNames")))}
      {row("setMapTrack", seg(m.trackWidth, MAP_CHOICES.trackWidth.map((w) => [w, `\u2066${w} px\u2069`] as [number, string]), (v) => setMapPref("trackWidth", v), t("setMapTrack")))}
      {row("setMapModel", seg(m.modelSize, [[26, t("setSizeMedium")], [18, t("setSizeSmall")], [36, t("setSizeLarge")]], (v) => setMapPref("modelSize", v), t("setMapModel")))}
      {row("setMapUnits", seg(m.units, [["metric", t("setUnitsMetric")], ["imperial", t("setUnitsImperial")]], (v) => setMapPref("units", v), t("setMapUnits")))}
      {row("setMapCoords", seg(m.coords, [["dd", t("setCoordsDd")], ["dms", t("setCoordsDms")], ["mgrs", t("setCoordsMgrs")]], (v) => setMapPref("coords", v), t("setMapCoords")), "setMapCoordsHint")}
      {row("setMapElev", <span className="set-elev">
        <input dir="ltr" value={elev} placeholder="~/.signalviewer/terrain" aria-label={t("setMapElev")} onChange={(e) => setElev(e.target.value)} onBlur={() => setElevationFolder(elev)} />
        <button className="btn sm" onClick={async () => { const f = await pickPath({ mode: "folder", title: t("setMapElev") }); if (f) { setElev(f); setElevationFolder(f); } }}>{t("setMapElevPick")}</button>
      </span>, "setMapElevHint")}
      {row("setMapRate", seg(m.rate, MAP_CHOICES.rate.map((r) => [r, `\u2066${r}${t("setMapRateUnit")}\u2069`] as [number, string]), (v) => setMapPref("rate", v), t("setMapRate")))}
      {row("setMapStory", <span className="set-story">
        {seg(m.story, [["on", t("setOn")], ["off", t("setOff")]], (v) => setMapPref("story", v), t("setMapStory"))}
        {m.story === "on" && seg(m.storyLength, [[90, t("setStory90")], [45, t("setStory45")], [180, t("setStory180")]], (v) => setMapPref("storyLength", v), t("setMapStory"))}
      </span>, "setMapStoryHint")}
    </section>
  );
}

/* T18: Settings - kept between starts (prefs.ts / settings.ts), and a session file opened later
   does not change them. Each choice has ONE place: the language stays a button in the top bar,
   live mode's choices stay in Live ▾ (both are kept between starts the same way). */
export default function SettingsDialog() {
  const t = useT();
  const theme = useApp((s) => s.theme);
  const uiScale = useApp((s) => s.uiScale);
  const timeFormat = useApp((s) => s.timeFormat);
  const smoothFollow = useApp((s) => s.smoothFollow);
  const askBeforeClose = useApp((s) => s.askBeforeClose);
  const clickPlacesCursor = useApp((s) => s.clickPlacesCursor);
  const lineWidth = useApp((s) => s.lineWidth);
  const lineStyle = useApp((s) => s.lineStyle);
  const tplTabChoice = useApp((s) => s.tplTabChoice);
  const offlineOnly = useApp((s) => s.offlineOnly);
  const offlineForced = useApp((s) => s.offlineForced);
  const close = () => useApp.setState({ settingsOpen: false });
  useEscape(close, true);
  const seg = <V extends string | number>(value: V, opts: [V, string][], set: (v: V) => void, label: string) => (
    <span className="seg" role="radiogroup" aria-label={label}>
      {opts.map(([v, l]) => <button key={String(v)} role="radio" aria-checked={value === v} className={value === v ? "on" : ""} onClick={() => set(v)}>{l}</button>)}
    </span>
  );
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog settings" role="dialog" aria-label={t("settings")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("settings")}</h2>
          <button className="iconbtn" autoFocus onClick={close} aria-label={t("close")}><Icon.X /></button></div>
        <div className="dialog-body settings-body">
          <h3 className="set-group-title">{t("setGrpLook")}</h3>
          <div className="set-row"><span>{t("theme")}</span>
            {seg(theme, [["light", t("light")], ["dark", t("dark")]], (v) => useApp.setState({ theme: v }), t("theme"))}</div>
          <div className="set-row"><span>{t("hTextSize")}</span>
            {seg(uiScale, [[1, "100%"], [1.12, "112%"], [1.25, "125%"]], (v) => useApp.setState({ uiScale: v }), t("hTextSize"))}</div>
          {/* N3: the width and style of new lines, and a button to give them to the lines already drawn */}
          <div className="set-row set-lines"><span>{t("setLines")}<small>{t("setLinesHint")}</small></span>
            <span className="set-lines-ctl">
              <label>{t("setLineWidth")} <input type="number" className="set-line-width" min={0.5} max={6} step={0.5} value={lineWidth}
                onChange={(e) => { const v = Number(e.target.value); if (Number.isFinite(v) && v >= 0.5 && v <= 6) useApp.setState({ lineWidth: v }); }} /></label>
              <label>{t("setLineStyle")} <select className="set-line-style" value={lineStyle} onChange={(e) => useApp.setState({ lineStyle: e.target.value as LineStyle })}>
                {LINE_STYLES.map((k) => <option key={k} value={k}>{t(`lineStyle_${k}` as TKey)}</option>)}</select></label>
              <button className="btn sm outline set-lines-apply" onClick={() => actions.applyLineDefaults()}>{t("setLinesApply")}</button>
            </span></div>
          <h3 className="set-group-title">{t("setGrpTime")}</h3>
          <div className="set-row"><span>{t("setTime")}<small>{t("setTimeHint")}</small></span>
            {seg(timeFormat, [["seconds", t("setTimeSeconds")], ["clock", t("setTimeClock")]], (v) => useApp.setState({ timeFormat: v }), t("setTime"))}</div>
                    <div className="set-row"><span>{t("setClickCursor")}<small>{t("setClickCursorHint")}</small></span>
            {seg(clickPlacesCursor ? "on" : "off", [["on", t("setClickCursorOn")], ["off", t("setClickCursorOff")]], (v) => useApp.setState({ clickPlacesCursor: v === "on" }), t("setClickCursor"))}</div>
          <div className="set-row"><span>{t("setSmoothFollow")}<small>{t("setSmoothFollowHint")}</small></span>
            {seg(smoothFollow ? "on" : "off", [["on", t("setSmoothFollowOn")], ["off", t("setSmoothFollowOff")]], (v) => useApp.setState({ smoothFollow: v === "on" }), t("setSmoothFollow"))}</div>
          <h3 className="set-group-title">{t("setGrpWork")}</h3>
          <div className="set-row"><span>{t("setTabChoice")}<small>{t("setTabChoiceHint")}</small></span>
            {seg(tplTabChoice, [["ask", t("setTabChoiceAsk")], ["defaults", t("setTabChoiceDefaults")]], (v) => useApp.setState({ tplTabChoice: v }), t("setTabChoice"))}</div>
                    <div className="set-row"><span>{t("setAskClose")}<small>{t("setAskCloseHint")}</small></span>
            {seg(askBeforeClose ? "on" : "off", [["on", t("setAskCloseOn")], ["off", t("setAskCloseOff")]], (v) => useApp.setState({ askBeforeClose: v === "on" }), t("setAskClose"))}</div>
          <h3 className="set-group-title">{t("setGrpNet")}</h3>
          <div className="set-row"><span>{t("setOffline")}<small>{t(offlineForced ? "setOfflineForced" : "setOfflineHint")}</small></span>
            {offlineForced
              ? <span className="seg" aria-label={t("setOffline")}><button className="on" disabled aria-checked>{t("setOfflineOn")}</button></span>
              : seg(offlineOnly ? "on" : "off", [["off", t("setOfflineOff")], ["on", t("setOfflineOn")]],
                (v) => useApp.setState({ offlineOnly: v === "on" }), t("setOffline"))}</div>

          <MapSection seg={seg} />
          <p className="hint">{t("setKept")}</p>
          {/* W16: what the app keeps on disk is looked at rarely - folded */}
          <details className="set-fold"><summary>{t("storage")}</summary><StorageSection /></details>
        </div>
      </div>
    </div>
  );
}
