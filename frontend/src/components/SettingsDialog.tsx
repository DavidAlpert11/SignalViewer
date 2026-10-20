import { useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { useEscape } from "./Overlays";

/* T18: Settings - kept between starts (prefs.ts / settings.ts), and a session file opened later
   does not change them. Each choice has ONE place: the language stays a button in the top bar,
   live mode's choices stay in Live ▾ (both are kept between starts the same way). */
export default function SettingsDialog() {
  const t = useT();
  const theme = useApp((s) => s.theme);
  const uiScale = useApp((s) => s.uiScale);
  const timeFormat = useApp((s) => s.timeFormat);
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
          <p className="hint">{t("setKept")}</p>
        </div>
      </div>
    </div>
  );
}
