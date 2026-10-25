/**
 * Units from signal names (N-14): "Speed [km/h]", "Temp (°C)", "P_kPa" is left alone.
 * The bracket must contain a letter or a unit symbol, so "imu[1]" is not a unit.
 */
const UNIT = /\s*[[(]([^[\]()]*[A-Za-z%°µΩ‰/][^[\]()]*)[\])]\s*$/;

export function unitOf(name: string): string | null {
  const m = UNIT.exec(name);
  return m ? m[1].trim() : null;
}

export function withUnit(text: string, unit: string | null): string {
  return unit ? `${text} ${unit}` : text;
}

/* ------------------------------------------------------------------ unit conversions
   Each one is a change of the values (y = scale·x + offset) and of the unit shown. They are made as
   an in-place edit of the signal (transforms.ts: composed with any change already there, undoable,
   saved in the session), so a log in radians is read in degrees without a formula. */
export interface UnitConversion { from: string; to: string; scale: number; offset?: number; group: ConvGroup }
export type ConvGroup = "angle" | "rate" | "speed" | "length" | "accel" | "temp" | "pressure" | "time" | "coord";

const D = 180 / Math.PI;
export const CONVERSIONS: UnitConversion[] = [
  { group: "angle", from: "rad", to: "deg", scale: D },
  { group: "angle", from: "deg", to: "rad", scale: 1 / D },
  { group: "angle", from: "cdeg", to: "deg", scale: 0.01 },
  { group: "rate", from: "rad/s", to: "deg/s", scale: D },
  { group: "rate", from: "deg/s", to: "rad/s", scale: 1 / D },
  { group: "speed", from: "m/s", to: "km/h", scale: 3.6 },
  { group: "speed", from: "km/h", to: "m/s", scale: 1 / 3.6 },
  { group: "speed", from: "m/s", to: "kn", scale: 3600 / 1852 },
  { group: "speed", from: "kn", to: "m/s", scale: 1852 / 3600 },
  { group: "speed", from: "km/h", to: "kn", scale: 1 / 1.852 },
  { group: "speed", from: "kn", to: "km/h", scale: 1.852 },
  { group: "speed", from: "m/s", to: "mph", scale: 3600 / 1609.344 },
  { group: "speed", from: "m/s", to: "ft/min", scale: 60 / 0.3048 },
  { group: "speed", from: "ft/min", to: "m/s", scale: 0.3048 / 60 },
  { group: "speed", from: "cm/s", to: "m/s", scale: 0.01 },
  { group: "length", from: "m", to: "ft", scale: 1 / 0.3048 },
  { group: "length", from: "ft", to: "m", scale: 0.3048 },
  { group: "length", from: "m", to: "km", scale: 0.001 },
  { group: "length", from: "km", to: "m", scale: 1000 },
  { group: "length", from: "m", to: "NM", scale: 1 / 1852 },
  { group: "length", from: "NM", to: "m", scale: 1852 },
  { group: "length", from: "cm", to: "m", scale: 0.01 },
  { group: "length", from: "mm", to: "m", scale: 0.001 },
  { group: "accel", from: "m/s²", to: "g", scale: 1 / 9.80665 },
  { group: "accel", from: "g", to: "m/s²", scale: 9.80665 },
  { group: "temp", from: "°C", to: "°F", scale: 1.8, offset: 32 },
  { group: "temp", from: "°F", to: "°C", scale: 1 / 1.8, offset: -32 / 1.8 },
  { group: "temp", from: "K", to: "°C", scale: 1, offset: -273.15 },
  { group: "temp", from: "°C", to: "K", scale: 1, offset: 273.15 },
  { group: "pressure", from: "Pa", to: "hPa", scale: 0.01 },
  { group: "pressure", from: "hPa", to: "Pa", scale: 100 },
  { group: "pressure", from: "Pa", to: "psi", scale: 1 / 6894.757293 },
  { group: "pressure", from: "psi", to: "Pa", scale: 6894.757293 },
  { group: "pressure", from: "bar", to: "Pa", scale: 1e5 },
  { group: "time", from: "ms", to: "s", scale: 0.001 },
  { group: "time", from: "µs", to: "s", scale: 1e-6 },
  { group: "time", from: "s", to: "ms", scale: 1000 },
  { group: "coord", from: "deg·1e7", to: "deg", scale: 1e-7 },
];

/** The ways one unit is written in logs and file headers, as the table above writes it. */
const ALIAS: Record<string, string> = {
  radian: "rad", radians: "rad", "rad": "rad", degree: "deg", degrees: "deg", "°": "deg", deg: "deg", centideg: "cdeg", cdeg: "cdeg",
  "rad/s": "rad/s", "deg/s": "deg/s", "°/s": "deg/s", dps: "deg/s",
  "m/s": "m/s", mps: "m/s", "km/h": "km/h", kmh: "km/h", kph: "km/h", kn: "kn", kt: "kn", kts: "kn", knot: "kn", knots: "kn",
  mph: "mph", "ft/min": "ft/min", fpm: "ft/min", "cm/s": "cm/s",
  m: "m", meter: "m", meters: "m", ft: "ft", feet: "ft", km: "km", nm: "NM", cm: "cm", mm: "mm",
  "m/s/s": "m/s²", "m/s²": "m/s²", "m/s^2": "m/s²", "m/s2": "m/s²", g: "g",
  "°c": "°C", degc: "°C", c: "°C", "°f": "°F", degf: "°F", f: "°F", k: "K",
  pa: "Pa", hpa: "hPa", mbar: "hPa", psi: "psi", bar: "bar",
  ms: "ms", "µs": "µs", us: "µs", s: "s", sec: "s",
  deglatitude: "deg", deglongitude: "deg", "degE7": "deg·1e7", "deg·1e7": "deg·1e7", "1e-7deg": "deg·1e7",
};

/** "deg" for "Yaw [degrees]", null when the unit is not one of the table's. */
export function canonUnit(u: string | null | undefined): string | null {
  if (!u) return null;
  const k = u.trim();
  return ALIAS[k] ?? ALIAS[k.toLowerCase()] ?? (CONVERSIONS.some((c) => c.from === k || c.to === k) ? k : null);
}

/** The conversions that start from `unit` (all of them when the unit is not known: a name often
 *  does not say - exactly the case of angles that turn out to be radians). */
export function conversionsFrom(unit: string | null | undefined): UnitConversion[] {
  const c = canonUnit(unit);
  const from = c ? CONVERSIONS.filter((x) => x.from === c) : [];
  return from.length ? from : CONVERSIONS;
}

/** The unit a signal is shown in: the one a conversion set, else its user label's, else its name's. */
export function signalUnit(runs: { id: string; signals: { id: string; name: string; transform?: { unit?: string } }[] }[],
  sigId: string, label?: string | null): string | null {
  const rid = sigId.slice(0, sigId.indexOf("/"));
  const s = runs.find((r) => r.id === rid)?.signals.find((x) => x.id === sigId);
  return s?.transform?.unit || (label ? unitOf(label) : null) || unitOf(s?.name ?? sigId.slice(sigId.indexOf("/") + 1));
}
