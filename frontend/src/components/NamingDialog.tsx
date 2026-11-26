import { useState } from "react";
import { useApp } from "../store";
import { useT, type TKey } from "../i18n";
import { Icon } from "../icons";
import { useEscape } from "./Overlays";
import { copyText } from "../errorReport";
import { api } from "../api";
import { openExample } from "./Welcome";
import { SETPOINT_WORDS } from "../desired";
import { CLASS_WORDS } from "../objectDetect";
import type { FindId } from "../found";
import NAMES from "../../../backend/svcore/object_names.json";

/* AU4 (owner, 2026-11-26: "suggest to the user what to record, so he knows it is worth producing such variables"):
   Help -> Name your signals (and every *Why?* of the Found line) - each automatic find, the names it recognises (read
   from the same tables the finders use, so the page cannot drift from them), an example, a CSV header that unlocks
   all of them and the example recording made that way (examples/automations). */
const ROWS: { id: FindId; rule: TKey; ex: string }[] = [
  { id: "pairs", rule: "nmPairsRule", ex: "ctrl.roll_cmd / ctrl.roll · DesRoll / Roll · alt.target / alt" },
  { id: "objects", rule: "nmObjectsRule", ex: "uav.lat, uav.lon, uav.alt, uav.att.roll" },
  { id: "truthnav", rule: "nmTruthNavRule", ex: "6dof.lat / ins.lat · physics.lat / nav.lat · uav1.truth.lat / uav1.nav.lat" },
  { id: "states", rule: "nmStatesRule", ex: "mode = TAKEOFF, CLIMB, CRUISE" },
  { id: "copies", rule: "nmCopiesRule", ex: "imu[0].ax / imu[1].ax · baro1.alt / baro2.alt" },
  { id: "effort", rule: "nmEffortRule", ex: "act.servo_elevator, act.throttle, motor1_pwm" },
  { id: "bytes", rule: "nmBytesRule", ex: "byte_0, byte_1, … byte_7" },
  { id: "envelope", rule: "nmEnvelopeRule", ex: "run_001.csv, run_002.csv, run_003.csv" },
];
/** The example recording's header (svcore/example_data/make_automations_example.py) - every find at once. */
export const NAMING_HEADER = "time,mode,6dof.lat,6dof.lon,6dof.alt,6dof.att.roll,6dof.att.pitch,6dof.att.yaw,6dof.vel.n,6dof.vel.e,6dof.vel.d,"
  + "ins.lat,ins.lon,ins.alt,ins.att.roll,ins.att.pitch,ins.att.yaw,ins.vel.n,ins.vel.e,ins.vel.d,"
  + "ctrl.roll_cmd,ctrl.roll,ctrl.alt_cmd,ctrl.alt,ctrl.speed_cmd,ctrl.speed,imu[0].ax,imu[0].ay,imu[0].az,imu[1].ax,imu[1].ay,imu[1].az,"
  + "act.servo_elevator,act.throttle";

export default function NamingDialog() {
  const t = useT();
  const close = () => useApp.setState({ namingOpen: false });
  useEscape(close, true);
  const [copied, setCopied] = useState(false);
  const vars: Record<string, string> = {
    words: SETPOINT_WORDS.join(", "), lat: NAMES.aliases.lat.join(", "), lon: NAMES.aliases.lon.join(", "),
    truth: CLASS_WORDS.truth.join(", "), nav: CLASS_WORDS.navigation.join(", "),
  };
  const example = async () => {
    try {
      const ex = (await api.examples()).find((x) => x.id === "automations");
      if (ex) { close(); openExample(ex); }
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
  };
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog naming" role="dialog" aria-modal="true" aria-label={t("nmTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("nmTitle")}</h2>
          <button className="iconbtn" autoFocus onClick={close} aria-label={t("close")}><Icon.X /></button></div>
        <div className="dialog-body naming-body">
          <p className="naming-intro">{t("nmIntro").replace(/\*/g, "")}</p>
          <table className="naming-table">
            <thead><tr><th>{t("nmFind")}</th><th>{t("nmRule")}</th><th>{t("nmExample")}</th></tr></thead>
            <tbody>
              {ROWS.map((r) => (
                <tr key={r.id} className={`naming-row naming-${r.id}`}>
                  <td>{t(`nmName_${r.id}`)}</td>
                  <td>{t(r.rule, vars)}</td>
                  <td><code dir="ltr">{r.ex}</code></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="naming-head-label">{t("nmHeader")}</p>
          <pre className="naming-header" dir="ltr">{NAMING_HEADER.replace(/,/g, ", ")}</pre>
        </div>
        <div className="dialog-foot">
          <button className="btn naming-copy" onClick={async () => { if (await copyText(NAMING_HEADER)) setCopied(true); }}>{copied ? t("nmCopied") : t("nmCopy")}</button>
          <button className="btn primary naming-example" onClick={() => void example()}>{t("nmOpenExample")}</button>
        </div>
      </div>
    </div>
  );
}
