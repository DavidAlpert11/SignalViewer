/**
 * Prefix grouping for files with many signals (S-03).
 * "grp01.sensor_0003" -> group "grp01"; separators tried in order: . / : then _ .
 * Groups are used only when they actually organise the list (enough signals,
 * at least two groups, and not one group per signal).
 */
export interface SigGroup<T> { key: string; items: T[] }

const SEPS = [".", "/", ":", "_"];
/** N1: in a file whose names are not a flight log's, "." and "/" are explicit (nameTree) - the
 *  heuristics below are kept only for "_" and ":" (ArduPilot-style MOT_1_PWM must not shatter). */
export const HEURISTIC_SEPS = [":", "_"];
export const GROUP_MIN = 40;

export function groupByPrefix<T>(items: T[], name: (t: T) => string, min = GROUP_MIN, seps = SEPS): SigGroup<T>[] | null {
  if (items.length < min) return null;
  for (const sep of seps) {
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
export function subGroups<T>(key: string, items: T[], name: (t: T) => string, seps = SEPS): SigGroup<T>[] | null {
  const rest = (t: T) => { const n = name(t); return n.length > key.length + 1 && n.startsWith(key) ? n.slice(key.length + 1) : n; };
  return groupByPrefix(items, rest, SUBGROUP_MIN, seps);
}

/* ---- N1: explicit nesting by "." and "/", always and at any depth -------------------------------- */

/** Flight logs keep the grouping they had (their names "GPS[0].Alt [m]" are message.field, and the
 *  heuristics above nest them IMU[0] > ...): nameTree is not used for these formats. */
export const LOG_FORMATS = new Set(["bin", "tlog", "ulg", "can"]);

/** A unit at the end of a name ("GPS.Lat [deg]", "vel (m/s)") - ignored when splitting, kept in the label. */
const UNIT_TAIL = /\s*[[(][^[\]()]*[\])]\s*$/;
/** One segment of an explicit path: starts with a letter or "_", then letters, digits, "_", "-" or inner
 *  spaces, optionally indexed ("IMU[0]", "q[2]"). "5V" (from "bus_1.5V") or "1" (from "v2.1") is not one,
 *  so a number with a decimal point is never split. */
const SEGMENT = /^[\p{L}_](?:[\p{L}\p{N}_\- ]*[\p{L}\p{N}_\-])?(?:\[[^\]]*\])*$/u;

/** Where each segment after the first starts in `name` (the index just after its separator), or null
 *  when the name is not an explicit path of two or more segments. A leading "/" (ROS topics) is skipped. */
export function pathCuts(name: string): { start: number; cuts: number[] } | null {
  const m = UNIT_TAIL.exec(name);
  const end = m && !/^\[\d*\]$/.test(m[0].trim()) ? m.index : name.length;   // "q[0]" is an index, not a unit
  let start = 0;
  while (start < end && (name[start] === "." || name[start] === "/")) start++;
  const cuts: number[] = [];
  let from = start;
  for (let i = start; i < end; i++) {
    const c = name[i];
    if (c !== "." && c !== "/") continue;
    if (!SEGMENT.test(name.slice(from, i))) return null;
    cuts.push(i + 1); from = i + 1;
  }
  if (!cuts.length || !SEGMENT.test(name.slice(from, end))) return null;
  return { start, cuts };
}

export type TreeEntry<T> = { kind: "group"; node: NameNode<T> } | { kind: "item"; t: T; label: string };
/** A group of the name tree. key: its full path ("phys.att"; "~MOT" for a heuristic "_" / ":" group),
 *  label: what the row shows - the part of the path below its parent row ("att", or "phys.att" when a
 *  chain of single-child levels was folded), all: every signal under it. */
export interface NameNode<T> { key: string; label: string; entries: TreeEntry<T>[]; all: T[] }

interface Raw<T> { segs: number; first: { name: string; p: { start: number; cuts: number[] } }; kids: Map<string, Raw<T>>; entries: RawEntry<T>[]; all: T[] }
type RawEntry<T> = { kind: "group"; node: Raw<T> } | { kind: "item"; t: T; p: { start: number; cuts: number[] } | null };

/**
 * The signal list's tree for one file (N1). Names with "." / "/" between identifier-like segments nest
 * by them at any depth, whatever the number of signals; a chain of single-child levels is one row
 * ("phys.att"); no group holds a single signal; inside a group a signal shows only the rest of its
 * name. The other names stay at the top, grouped by "_" / ":" with the old heuristics when they are
 * many. Returns null when no name is an explicit path (the caller keeps the old grouping).
 */
export function nameTree<T>(items: T[], name: (t: T) => string): TreeEntry<T>[] | null {
  const root: Raw<T> = { segs: 0, first: { name: "", p: { start: 0, cuts: [] } }, kids: new Map(), entries: [], all: [] };
  const loose: T[] = [];
  let explicit = 0;
  for (const t of items) {
    const n = name(t);
    const p = pathCuts(n);
    if (!p) { root.entries.push({ kind: "item", t, p: null }); loose.push(t); continue; }
    explicit++;
    let node = root;
    for (let k = 0; k < p.cuts.length; k++) {
      const seg = n.slice(k ? p.cuts[k - 1] : p.start, p.cuts[k] - 1);
      let kid = node.kids.get(seg);
      if (!kid) {
        kid = { segs: k + 1, first: { name: n, p }, kids: new Map(), entries: [], all: [] };
        node.kids.set(seg, kid); node.entries.push({ kind: "group", node: kid });
      }
      kid.all.push(t);
      node = kid;
    }
    node.entries.push({ kind: "item", t, p });
  }
  if (!explicit) return null;

  // the rest of the name below a level of `segs` segments ("phys.att.roll" below phys -> "att.roll")
  const rest = (n: string, p: { start: number; cuts: number[] } | null, segs: number) => (p ? n.slice(segs ? p.cuts[segs - 1] : p.start) : n);
  const build = (raw: Raw<T>): TreeEntry<T>[] => {
    const out: TreeEntry<T>[] = [];
    for (const e of raw.entries) {
      if (e.kind === "item") { out.push({ kind: "item", t: e.t, label: rest(name(e.t), e.p, raw.segs) }); continue; }
      let kid = e.node;
      if (kid.all.length === 1) {                       // no group of one signal: the signal itself, named from here
        const t = kid.all[0];
        out.push({ kind: "item", t, label: rest(name(t), pathCuts(name(t)), raw.segs) });
        continue;
      }
      // a chain of levels with one sub-level and nothing else is one row
      while (kid.kids.size === 1 && kid.entries.length === 1 && kid.entries[0].kind === "group") kid = kid.entries[0].node;
      const f = kid.first;
      const from = raw.segs ? f.p.cuts[raw.segs - 1] : f.p.start;
      const key = f.name.slice(f.p.start, f.p.cuts[kid.segs - 1] - 1);
      out.push({ kind: "group", node: { key, label: f.name.slice(from, f.p.cuts[kid.segs - 1] - 1), entries: build(kid), all: kid.all } });
    }
    return out;
  };
  const top = build(root);

  // the names that are not paths: the old heuristics, "_" / ":" only, a group at its first member's place
  const legacy = groupByPrefix(loose, name, GROUP_MIN, HEURISTIC_SEPS);
  if (!legacy) return top;
  const groupOfItem = new Map<T, SigGroup<T>>();
  for (const g of legacy) if (g.key) for (const t of g.items) groupOfItem.set(t, g);
  const done = new Set<SigGroup<T>>();
  const out: TreeEntry<T>[] = [];
  for (const e of top) {
    const g = e.kind === "item" ? groupOfItem.get(e.t) : undefined;
    if (!g) { out.push(e); continue; }
    if (done.has(g)) continue;
    done.add(g);
    out.push({ kind: "group", node: { key: `~${g.key}`, label: g.key, entries: g.items.map((t) => ({ kind: "item", t, label: name(t) })), all: g.items } });
  }
  return out;
}
