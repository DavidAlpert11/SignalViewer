/**
 * Prefix grouping for files with many signals (S-03).
 * "grp01.sensor_0003" -> group "grp01"; separators tried in order: . / : then _ .
 * Groups are used only when they actually organise the list (enough signals,
 * at least two groups, and not one group per signal).
 */
export interface SigGroup<T> { key: string; items: T[] }

const SEPS = [".", "/", ":", "_"];
export const GROUP_MIN = 40;

export function groupByPrefix<T>(items: T[], name: (t: T) => string, min = GROUP_MIN): SigGroup<T>[] | null {
  if (items.length < min) return null;
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

/**
 * Derived signals made together (the three axes of a frame conversion) carry params.group and
 * are named "<group>.<axis>": they are listed as ONE nested entry, at the place of the first
 * member. Every other derived signal stays on its own (key "").
 */
export function groupDerived<T extends { params?: Record<string, unknown> }>(items: T[]): SigGroup<T>[] {
  const out: SigGroup<T>[] = [];
  const at = new Map<string, SigGroup<T>>();
  for (const t of items) {
    const g = groupOf(t);
    if (!g) { out.push({ key: "", items: [t] }); continue; }
    let e = at.get(g);
    if (!e) { e = { key: g, items: [] }; at.set(g, e); out.push(e); }
    e.items.push(t);
  }
  return out;
}

export const groupOf = (t: { params?: Record<string, unknown> }) => (typeof t.params?.group === "string" ? t.params.group : "");

/** "ned_Pos_lla.N" in group "ned_Pos_lla" -> "N" (the name shown inside the group). */
export const memberLabel = (name: string, group: string) => (group && name.startsWith(group + ".") ? name.slice(group.length + 1) : name);

/** A group's own sub-groups (owner, 2026-11-03: nested by the name, more than one level): the part of
 *  each name after the group's key and its separator, grouped again - for big groups only. */
export const SUBGROUP_MIN = 12;
export function subGroups<T>(key: string, items: T[], name: (t: T) => string): SigGroup<T>[] | null {
  const rest = (t: T) => { const n = name(t); return n.length > key.length + 1 && n.startsWith(key) ? n.slice(key.length + 1) : n; };
  return groupByPrefix(items, rest, SUBGROUP_MIN);
}
