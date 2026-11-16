/* U4 (owner, 2026-11-07): a setpoint and its measured value in one plot - ArduPilot's DesRoll / Roll
   (and RATE.RDes / RATE.R), PX4's roll_sp / roll and <topic>_setpoint.x / <topic>.x, roll_cmd, AltTarget... - the setpoint is
   drawn dashed and a little faded by itself, so the eye reads "wanted vs got". A style set by hand
   (PlotSignal.dash true / false) wins. */
import type { LineStyle, PlotSignal } from "./store";

/** A signal id without its file and unit: "a1b2/ATT.DesRoll [deg]" -> "ATT.DesRoll". */
const bare = (sig: string) => sig.slice(sig.indexOf("/") + 1).replace(/ \[[^\]]*\]$/, "");

// P (owner, 2026-11-16): the words that make a name a setpoint - a prefix or a suffix, after a separator or in
// camel case. Longest first, so "Commanded" is not read as "Command" + "ed".
const WORDS = ["commanded", "reference", "setpoint", "command", "desired", "demand", "target", "des", "dem", "cmd", "tgt", "ref", "set", "sp"];
const cap = (w: string) => w[0].toUpperCase() + w.slice(1);
const ALT = WORDS.join("|");
const CAMEL = [...WORDS.map(cap), "SetPoint", "SP"].sort((a, b) => b.length - a.length).join("|");
const SEP_SUFFIX = new RegExp(`^(.+?)[_\\-. ](?:${ALT})$`, "i");          // roll_sp, Roll_CMD, roll.target
const SEP_PREFIX = new RegExp(`^(?:${ALT})[_\\-. ](.+)$`, "i");           // sp_roll, cmd.roll
const CAMEL_PREFIX = new RegExp(`^(?:${CAMEL}|${ALT})([A-Z].*)$`);        // DesRoll, cmdRoll, TargetAlt
const CAMEL_SUFFIX = new RegExp(`^(.+)(?:${CAMEL})$`);                    // RDes, RollCmd, AltTarget
const LOWER_SUFFIX = /^([a-z][a-z0-9]*?)dem$/;                            // ArduPlane TECS: hdem -> h, spdem -> sp
const TOPIC = new RegExp(`^(.+)_(?:${ALT})(\\[\\d+\\])?\\.$`, "i");     // PX4: vehicle_local_position_setpoint.x -> vehicle_local_position.x

/** The measured value's names a setpoint name pairs with (several candidates), or [] if it is none. */
export function actualNames(name: string): string[] {
  const dot = name.lastIndexOf(".");
  const msg = dot >= 0 ? name.slice(0, dot + 1) : "", leaf = dot >= 0 ? name.slice(dot + 1) : name;
  const out: string[] = [];
  for (const re of [SEP_SUFFIX, SEP_PREFIX, CAMEL_PREFIX, CAMEL_SUFFIX, LOWER_SUFFIX]) {
    const m = re.exec(leaf);
    if (!m || !m[1]) continue;
    out.push(msg + m[1]);
    if (re === CAMEL_PREFIX) out.push(msg + m[1][0].toLowerCase() + m[1].slice(1));   // desiredRoll -> roll
  }
  const m = TOPIC.exec(msg);
  if (m) out.push(`${m[1]}${m[2] ?? ""}.${leaf}`);
  return out.filter((n) => n !== name);
}

/** The setpoint / measured pairs among signal ids ("<runId>/<name>"), each in the same file, in the order of the
 *  setpoints - the one detector for drawing a setpoint dashed and for *Plot the commanded / measured pairs*. */
export function setpointPairs(ids: string[]): { setpoint: string; measured: string }[] {
  const file = (id: string) => id.slice(0, id.indexOf("/"));
  const byKey = new Map<string, string>();
  for (const id of ids) if (!byKey.has(file(id) + "/" + bare(id))) byKey.set(file(id) + "/" + bare(id), id);
  const out: { setpoint: string; measured: string }[] = [];
  for (const id of ids) {
    const measured = actualNames(bare(id)).map((n) => byKey.get(file(id) + "/" + n)).find((x) => x && x !== id);
    if (measured) out.push({ setpoint: id, measured });
  }
  return out;
}

/** The setpoints among a plot's signals: those whose measured partner (same file) is in it too. */
export function setpointsIn(signals: PlotSignal[]): Set<string> {
  return new Set(setpointPairs(signals.map((s) => s.sig)).map((p) => p.setpoint));
}

/** How a line is drawn (N3: `lineStyle` by hand > the old `dash` by hand > automatic - a setpoint
 *  beside its measured value dashed and faded). dashed: any style but solid. */
export function lineLook(s: PlotSignal, setpoints: Set<string>): { dashed: boolean; faded: boolean; style: LineStyle } {
  if (s.lineStyle) return { dashed: s.lineStyle !== "solid", faded: false, style: s.lineStyle };
  if (s.dash === true || s.dash === false) return { dashed: s.dash, faded: false, style: s.dash ? "dash" : "solid" };
  const auto = setpoints.has(s.sig);
  return { dashed: auto, faded: auto, style: auto ? "dash" : "solid" };
}
/** The dash pattern of a style, in CSS px (scale by the device pixel ratio for a canvas). */
export const DASH: Record<LineStyle, number[]> = { solid: [], dash: [6, 4], dot: [1.5, 3], dashdot: [6, 3, 1.5, 3] };

/** A #rrggbb colour at this opacity (rgba); anything else as it is. */
export function fade(color: string, alpha: number): string {
  const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(color);
  return m ? `rgba(${parseInt(m[1], 16)}, ${parseInt(m[2], 16)}, ${parseInt(m[3], 16)}, ${alpha})` : color;
}
