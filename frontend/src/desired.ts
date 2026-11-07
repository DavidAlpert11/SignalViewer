/* U4 (owner, 2026-11-07): a setpoint and its measured value in one plot - ArduPilot's DesRoll / Roll
   (and RATE.RDes / RATE.R), PX4's roll_sp / roll and <topic>_setpoint.x / <topic>.x - the setpoint is
   drawn dashed and a little faded by itself, so the eye reads "wanted vs got". A style set by hand
   (PlotSignal.dash true / false) wins. */
import type { PlotSignal } from "./store";

/** A signal id without its file and unit: "a1b2/ATT.DesRoll [deg]" -> "ATT.DesRoll". */
const bare = (sig: string) => sig.slice(sig.indexOf("/") + 1).replace(/ \[[^\]]*\]$/, "");

/** The measured value's name a setpoint name pairs with (several candidates), or [] if it is none. */
export function actualNames(name: string): string[] {
  const dot = name.lastIndexOf(".");
  const msg = dot >= 0 ? name.slice(0, dot + 1) : "", leaf = dot >= 0 ? name.slice(dot + 1) : name;
  const out: string[] = [];
  let m = /^Des([A-Z].*)$/.exec(leaf);                    // ATT.DesRoll -> ATT.Roll
  if (m) out.push(msg + m[1]);
  m = /^(.+)Des$/.exec(leaf);                             // RATE.RDes -> RATE.R
  if (m) out.push(msg + m[1]);
  m = /^(.+)_sp$/.exec(leaf);                             // PX4: roll_sp -> roll
  if (m) out.push(msg + m[1]);
  m = /^(.+)_setpoint(\[\d+\])?\.$/.exec(msg);            // PX4: vehicle_local_position_setpoint.x -> vehicle_local_position.x
  if (m) out.push(`${m[1]}${m[2] ?? ""}.${leaf}`);
  return out;
}

/** The setpoints among a plot's signals: those whose measured partner (same file) is in it too. */
export function setpointsIn(signals: PlotSignal[]): Set<string> {
  const byFile = new Map<string, Set<string>>();
  for (const s of signals) {
    const f = s.sig.slice(0, s.sig.indexOf("/"));
    (byFile.get(f) ?? byFile.set(f, new Set()).get(f)!).add(bare(s.sig));
  }
  const out = new Set<string>();
  for (const s of signals) {
    const names = byFile.get(s.sig.slice(0, s.sig.indexOf("/")))!;
    if (actualNames(bare(s.sig)).some((n) => names.has(n))) out.add(s.sig);
  }
  return out;
}

/** How a line is drawn: dashed (by hand, or a setpoint by itself) and faded (a setpoint by itself only). */
export function lineLook(s: PlotSignal, setpoints: Set<string>): { dashed: boolean; faded: boolean } {
  if (s.dash === true || s.dash === false) return { dashed: s.dash, faded: false };
  const auto = setpoints.has(s.sig);
  return { dashed: auto, faded: auto };
}

/** A #rrggbb colour at this opacity (rgba); anything else as it is. */
export function fade(color: string, alpha: number): string {
  const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(color);
  return m ? `rgba(${parseInt(m[1], 16)}, ${parseInt(m[2], 16)}, ${parseInt(m[3], 16)}, ${alpha})` : color;
}
