/* L9: "Compare with similar…" - the families of one file's signals whose names are equal but for one
   segment of the path: an instance (GPS[0] / GPS[1]), a number (nav1 / nav2, ekf_2) or a class word
   (truth / nav / gps). Names only (no data read), fast on thousands of names. With `loose`, also a
   segment within 1-2 edits, or the same leaf under different parents - each family says how it matched. */
import { api, type RunInfo } from "./api";
import { pathCuts } from "./signalGroups";
import { ANGLE_WORDS, classOfSegment, type ObjClass } from "./objectDetect";

export type How = "instance" | "number" | "class" | "edit" | "leaf";
export interface Member { id: string; name: string; seg: string; unit: string; cls?: ObjClass }
/** key: unique; leaf: what is compared, with "*" for the segment that differs ("*.att.roll", "XKF1[*].Roll") */
export interface Family { key: string; leaf: string; how: How; members: Member[]; unitsDiffer: boolean }
interface Sig { id: string; name: string }

const UNIT = /\s*\[([^\]]*)\]\s*$/;
/** The path segments and the unit of a name, or null for a flat name. */
function split(name: string): { segs: string[]; unit: string } | null {
  const p = pathCuts(name);
  if (!p) return null;
  const m = UNIT.exec(name);
  const unit = m && !/^\d*$/.test(m[1]) ? m[1].trim() : "";
  const end = unit ? m!.index : name.length;
  const segs: string[] = [];
  let from = p.start;
  for (const c of p.cuts) { segs.push(name.slice(from, c - 1)); from = c; }
  segs.push(name.slice(from, end).trim());
  return { segs, unit };
}
const INST = /^(.*?)\[(\d+)\]$/, NUM = /^(.*?)[_-]?(\d+)$/;
/** How a set of segments differs, or null when they are not one family. */
function howOf(segs: string[], loose: boolean): { how: How; star: string } | null {
  const inst = segs.map((s) => INST.exec(s));
  if (inst.every(Boolean) && new Set(inst.map((m) => m![1])).size === 1) return { how: "instance", star: `${inst[0]![1]}[*]` };
  const num = segs.map((s) => NUM.exec(s));
  if (num.every((m) => m && m[1]) && new Set(num.map((m) => m![1].toLowerCase())).size === 1) return { how: "number", star: `${num[0]![1]}*` };
  if (segs.every((s) => classOfSegment(s))) return { how: "class", star: "*" };
  if (loose && segs.every((s) => s !== segs[0] && edits(s.toLowerCase(), segs[0].toLowerCase()) <= 2 || s === segs[0])) return { how: "edit", star: "*" };
  return null;
}
/** Levenshtein distance, stopping early above 2. */
function edits(a: string, b: string): number {
  if (Math.abs(a.length - b.length) > 2) return 3;
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    if (Math.min(...cur) > 2) return 3;
    prev = cur;
  }
  return prev[b.length];
}

const cache = new WeakMap<object, Map<string, Family[]>>();
/** The families of one file's signals (cached per signal list). */
export function findFamilies(signals: Sig[], loose = false): Family[] {
  let byOpt = cache.get(signals);
  if (!byOpt) cache.set(signals, (byOpt = new Map()));
  const k = loose ? "loose" : "strict";
  const hit = byOpt.get(k);
  if (hit) return hit;
  const parsed = signals.map((s) => ({ s, p: split(s.name) })).filter((x): x is { s: Sig; p: { segs: string[]; unit: string } } => !!x.p);
  // every name once per inner segment: the name with that segment as "*" is the family's key
  const buckets = new Map<string, { s: Sig; p: { segs: string[]; unit: string }; i: number }[]>();
  for (const x of parsed) {
    const n = x.p.segs.length;
    for (let i = 0; i < n - 1; i++) {
      const key = `${i}|${x.p.segs.map((g, j) => (j === i ? "*" : g)).join(".")}`;
      let b = buckets.get(key);
      if (!b) buckets.set(key, (b = []));
      b.push({ ...x, i });
    }
  }
  const out: Family[] = [];
  const inFamily = new Set<string>();
  for (const [key, all] of buckets) {
    if (all.length < 2) continue;
    // one bucket (the names equal but for segment i) can hold several families: XKF1[0] / XKF1[1] beside ATT
    const left = new Set(all);
    const groups: { b: typeof all; how: How; star: string }[] = [];
    const take = (b: typeof all, how: How, star: string) => { if (b.length >= 2) { groups.push({ b, how, star }); b.forEach((x) => left.delete(x)); } };
    const by = (re: RegExp, how: How, star: (base: string) => string) => {
      const m = new Map<string, typeof all>();
      for (const x of left) { const r = re.exec(x.p.segs[x.i]); if (r && r[1]) { const k = r[1].toLowerCase(); m.set(k, [...(m.get(k) ?? []), x]); } }
      for (const b of m.values()) take(b, how, star(INST === re ? INST.exec(b[0].p.segs[b[0].i])![1] : NUM.exec(b[0].p.segs[b[0].i])![1]));
    };
    by(INST, "instance", (base) => `${base}[*]`);
    by(NUM, "number", (base) => `${base}*`);
    take([...left].filter((x) => classOfSegment(x.p.segs[x.i])), "class", "*");
    if (loose && left.size >= 2) {
      const rest = [...left];
      const h = howOf(rest.map((x) => x.p.segs[x.i]), true);
      if (h) take(rest, h.how, h.star);
    }
    for (const { b, how, star } of groups) {
      const segs = b.map((x) => x.p.segs[x.i]);
      if (new Set(segs).size !== segs.length) continue;
      const i = b[0].i;
      const leaf = b[0].p.segs.map((g, j) => (j === i ? star : g)).join(".");
      const members = b.map((x) => ({ id: x.s.id, name: x.s.name, seg: x.p.segs[i], unit: x.p.unit, cls: classOfSegment(x.p.segs[i]) }));
      members.forEach((m) => inFamily.add(m.id));
      out.push({ key: `${key}|${how}|${star}`, leaf, how, members, unitsDiffer: new Set(members.map((m) => m.unit.toLowerCase())).size > 1 });
    }
  }
  if (loose) {
    // the same leaf under different parents (a.b.roll / c.roll), not already in a family
    const byLeaf = new Map<string, typeof parsed>();
    for (const x of parsed) {
      if (inFamily.has(x.s.id)) continue;
      const l = x.p.segs[x.p.segs.length - 1].toLowerCase();
      let b = byLeaf.get(l);
      if (!b) byLeaf.set(l, (b = []));
      b.push(x);
    }
    for (const [l, b] of byLeaf) {
      if (b.length < 2 || b.length > 12) continue;
      const members = b.map((x) => ({ id: x.s.id, name: x.s.name, seg: x.p.segs.slice(0, -1).join("."), unit: x.p.unit, cls: classOfSegment(x.p.segs[0]) }));
      out.push({ key: `leaf|${l}`, leaf: `*.${b[0].p.segs[b[0].p.segs.length - 1]}`, how: "leaf", members, unitsDiffer: new Set(members.map((m) => m.unit.toLowerCase())).size > 1 });
    }
  }
  byOpt.set(k, out);
  return out;
}

/** The families with a member among `ids` (a signal, or every signal of a group: one family per leaf). */
export function familiesOf(families: Family[], ids: string[]): Family[] {
  const want = new Set(ids);
  return families.filter((f) => f.members.some((m) => want.has(m.id)));
}

/** The default reference of a family: a truth-class member, else the first. */
export function referenceOf(f: Family): Member {
  return f.members.find((m) => m.cls === "truth") ?? f.members[0];
}

/** L9 (one rule for every difference of two lines - here and errors.ts): an angle's difference is wrapped
 *  when its leaf is an angle (roll / pitch / yaw and aliases) and its unit says degrees or radians: 360 /
 *  "2pi"; an angle without a unit: "ask" (the caller asks the backend what unit it is); else null. */
export function angleWrap(name: string): 360 | "2pi" | "ask" | null {
  const m = UNIT.exec(name);
  const unit = m ? m[1].trim().toLowerCase() : "";
  const base = (m ? name.slice(0, m.index) : name).split(/[./]/).pop() ?? "";
  const word = base.toLowerCase().replace(/\[\d+\]$/, "").split("_").pop() ?? "";
  if (!ANGLE_WORDS.has(word)) return null;
  if (/^(deg|degs|degree|degrees|°)$/.test(unit)) return 360;
  if (/^(rad|rads|radian|radians)$/.test(unit)) return "2pi";
  return unit ? null : "ask";
}

/** The wrap of the difference "b - a" (the "sub" op's / error-segments' `wrap`), by angleWrap's rule on b's
 *  name; an angle without a unit: the backend's angle-unit guess (from the values). Undefined: no wrap. */
export async function wrapFor(runs: RunInfo[], b: string): Promise<360 | "2pi" | undefined> {
  const name = runs.flatMap((r) => r.signals).find((s) => s.id === b)?.name ?? "";
  const w = angleWrap(name);
  if (w === 360 || w === "2pi") return w;
  if (w !== "ask") return undefined;
  try { return (await api.angleUnits({ yaw: b })).units.yaw?.unit === "rad" ? "2pi" : 360; } catch { return undefined; }
}
