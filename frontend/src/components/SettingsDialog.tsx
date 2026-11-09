import { useEffect, useState } from "react";
import { api, type StorageInfo, type StorageKind } from "../api";
import { useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { fmtSize } from "../values";
import { useEscape } from "./Overlays";

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

/* T18: Settings - kept between starts (prefs.ts / settings.ts), and a session file opened later
   does not change them. Each choice has ONE place: the language stays a button in the top bar,
   live mode's choices stay in Live ▾ (both are kept between starts the same way). */
export default function SettingsDialog() {
  const t = useT();
  const theme = useApp((s) => s.theme);
  const uiScale = useApp((s) => s.uiScale);
  const timeFormat = useApp((s) => s.timeFormat);
  const smoothFollow = useApp((s) => s.smoothFollow);
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
          <div className="set-row"><span>{t("theme")}</span>
            {seg(theme, [["light", t("light")], ["dark", t("dark")]], (v) => useApp.setState({ theme: v }), t("theme"))}</div>
          <div className="set-row"><span>{t("hTextSize")}</span>
            {seg(uiScale, [[1, "100%"], [1.12, "112%"], [1.25, "125%"]], (v) => useApp.setState({ uiScale: v }), t("hTextSize"))}</div>
          <div className="set-row"><span>{t("setTime")}<small>{t("setTimeHint")}</small></span>
            {seg(timeFormat, [["seconds", t("setTimeSeconds")], ["clock", t("setTimeClock")]], (v) => useApp.setState({ timeFormat: v }), t("setTime"))}</div>
          <div className="set-row"><span>{t("setTabChoice")}<small>{t("setTabChoiceHint")}</small></span>
            {seg(tplTabChoice, [["ask", t("setTabChoiceAsk")], ["defaults", t("setTabChoiceDefaults")]], (v) => useApp.setState({ tplTabChoice: v }), t("setTabChoice"))}</div>
          <div className="set-row"><span>{t("setOffline")}<small>{t(offlineForced ? "setOfflineForced" : "setOfflineHint")}</small></span>
            {offlineForced
              ? <span className="seg" aria-label={t("setOffline")}><button className="on" disabled aria-checked>{t("setOfflineOn")}</button></span>
              : seg(offlineOnly ? "on" : "off", [["off", t("setOfflineOff")], ["on", t("setOfflineOn")]],
                (v) => useApp.setState({ offlineOnly: v === "on" }), t("setOffline"))}</div>
          <div className="set-row"><span>{t("setSmoothFollow")}<small>{t("setSmoothFollowHint")}</small></span>
            {seg(smoothFollow ? "on" : "off", [["on", t("setSmoothFollowOn")], ["off", t("setSmoothFollowOff")]], (v) => useApp.setState({ smoothFollow: v === "on" }), t("setSmoothFollow"))}</div>
          <p className="hint">{t("setKept")}</p>
          <StorageSection />
        </div>
      </div>
    </div>
  );
}
