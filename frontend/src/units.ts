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
