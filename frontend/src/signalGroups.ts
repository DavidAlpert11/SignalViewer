/**
 * Prefix grouping for files with many signals (S-03).
 * "grp01.sensor_0003" -> group "grp01"; separators tried in order: . / : then _ .
 * Groups are used only when they actually organise the list (enough signals,
 * at least two groups, and not one group per signal).
 */
export interface SigGroup<T> { key: string; items: T[] }

const SEPS = [".", "/", ":", "_"];
export const GROUP_MIN = 40;

export function groupByPrefix<T>(items: T[], name: (t: T) => string): SigGroup<T>[] | null {
  if (items.length < GROUP_MIN) return null;
  for (const sep of SEPS) {
    const withSep = items.filter((t) => name(t).includes(sep)).length;
    if (withSep < items.length * 0.6) continue;
    const map = new Map<string, T[]>();
    for (const t of items) {
      const n = name(t);
      const i = n.indexOf(sep);
      const key = i > 0 ? n.slice(0, i) : "";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(t);
    }
    if (map.size >= 2 && map.size <= items.length / 3) {
      return Array.from(map, ([key, its]) => ({ key, items: its }));
    }
  }
  return null;
}
