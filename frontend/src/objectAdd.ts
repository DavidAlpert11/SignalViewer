import { translate, type TKey } from "./i18n";
import { TRACE_COLORS, uid, useApp, type MapObject, type Plot } from "./store";
import { createFrameGroup, frameGroupName } from "./frames";
import { trackOfClass } from "./mapObjects";
import { ATT_ROLES, QUAT, VEC_ROLES, type Candidate, type DetRole } from "./objectDetect";
import type { SignalInfo } from "./api";

/* N5: what the found list adds, and the words of its *Why?* - shared by the dialog and the template. */

type Lang = "en" | "he";
const bare = (id: string) => id.slice(id.indexOf("/") + 1);

/** Can *Add all* add it without asking? A NED / ENU position needs an origin (found or chosen in
 *  Advanced…); a position in metres written in cm / mm / km needs a conversion to metres first (Q6). */
export const addable = (c: Candidate) => !c.badUnit && (c.pos === "lla" || c.pos === "ecef" || !!c.origin);

/** L4: how an object's lat / lon / alt were made - a chain of "vecsmooth" (smoothing) and "frame"
 *  (ECEF / NED / ENU -> LLA) derived signals, walked back to the recorded signals. One walk, used by the
 *  form (reading an object back) and by "already on the map". */
export interface ObjectChain {
  smooth: number;                                  // the smoothing window (s), 0 = none
  lat: string; lon: string; alt: string | null;    // after smoothing is undone: the frame's output or the recorded ones
  frame?: { src: string; sources: string[]; params: Record<string, unknown> };   // the conversion, when there is one
}
export function objectSources(o: Pick<MapObject, "lat" | "lon" | "alt">, derived: SignalInfo[]): ObjectChain {
  const of = (id?: string | null) => (id && id.startsWith("derived/") ? derived.find((s) => s.id === id) : undefined);
  const out: ObjectChain = { smooth: 0, lat: o.lat, lon: o.lon, alt: o.alt ?? null };
  const sm = of(o.lat);
  if (sm?.op === "vecsmooth" && sm.params?.kind === "lla" && sm.sources && sm.sources.length >= 2) {
    out.smooth = Number(sm.params.window) || 0;
    [out.lat, out.lon] = sm.sources;
    out.alt = sm.sources[2] ?? null;
  }
  const fr = of(out.lat);
  const p = fr?.params ?? {};
  if (fr?.op === "frame" && p.qty === "position" && p.dst === "lla" && ["ecef", "ned", "enu"].includes(String(p.src)) && fr.sources) {
    out.frame = { src: String(p.src), sources: fr.sources, params: p };
  }
  return out;
}
/** The recorded signal an object's position starts from: its latitude, or the frame's first source (x / north). */
export const firstSource = (o: Pick<MapObject, "lat" | "lon" | "alt">, derived: SignalInfo[]) => {
  const c = objectSources(o, derived);
  return c.frame ? c.frame.sources[0] : c.lat;
};
/** A candidate's identity: its first position source (latitude, or x / north in metres). */
export const candidateSource = (c: Candidate) => (c.pos === "lla" ? c.picks.lat?.id : c.picks.px?.id);
/** L4: already on this plot - an object whose position starts from the same recorded signal, however
 *  it was converted or smoothed. `derived`: the derived file's signals (the chain is read from them). */
export function isAdded(c: Candidate, plot: Plot | undefined, derived: SignalInfo[]): boolean {
  const id = candidateSource(c);
  return !!id && !!plot?.objects?.some((o) => firstSource(o, derived) === id);
}

/** Colours for new objects: the trace colours not yet used by this plot's objects, in order. */
export function objectColors(plot: Plot | undefined): () => string {
  const used = new Set((plot?.objects ?? []).map((o) => o.color.toLowerCase()));
  let i = 0;
  return () => {
    for (let k = 0; k < TRACE_COLORS.length; k++) {
      const c = TRACE_COLORS[(i + k) % TRACE_COLORS.length];
      if (!used.has(c.toLowerCase())) { used.add(c.toLowerCase()); i += k + 1; return c; }
    }
    return TRACE_COLORS[i++ % TRACE_COLORS.length];
  };
}

/** The map object of a candidate. A position in metres is turned into lat / lon / alt by a frame group
 *  first: ECEF by itself, NED / ENU through its origin (the origin's first valid sample, "signals"). */
export async function candidateObject(c: Candidate, color: string, name = c.name): Promise<MapObject> {
  const id = (r: DetRole) => c.picks[r]?.id ?? null;
  let lat = id("lat"), lon = id("lon"), alt = id("alt");
  if (c.pos !== "lla") {
    if (c.pos !== "ecef" && !c.origin) throw new Error(translate(useApp.getState().lang, "objNeedsOriginErr", { name }));
    const vec = VEC_ROLES.map((r) => id(r)!);
    const f = c.pos === "ecef" ? await createFrameGroup(vec, { qty: "position", src: "ecef", dst: "lla" }, frameGroupName("ecef", "lla", "position"))
      : await createFrameGroup([...vec, ...c.origin!.ids], { qty: "position", src: c.pos, dst: "lla", ref: "signals" }, frameGroupName(c.pos, "lla", "position"));
    [lat, lon, alt] = [f[0], f[1], f[2] ?? null];
  }
  return {
    id: uid("o"), name, kind: "aircraft", color, lat: lat!, lon: lon!, alt,
    yaw: id("yaw"), pitch: id("pitch"), roll: id("roll"), qw: id("qw"), qx: id("qx"), qy: id("qy"), qz: id("qz"),
    angleUnit: "auto", trail: true, cls: c.cls,
    ...(c.picks.vn && c.picks.ve ? { vel: [c.picks.vn.id, c.picks.ve.id, c.picks.vd?.id ?? null] as [string, string, string | null] } : {}),
    ...(trackOfClass(c.cls) ? { track: trackOfClass(c.cls) } : {}),
    // N5 (owner's decision 3): no angles of its own - drawn by its motion until another source is chosen
    ...(c.attitude === "none" ? { attitudeSource: "motion" as const } : {}),
  };
}

/** N5: the objects of a found list with their attitude sources: a row borrowing from another row
 *  (`from`: that row's candidate key) takes that row's new object, or the object already on the plot for it. */
export function linkAttitudes(pairs: { c: Candidate; o: MapObject; from?: string }[], all: Candidate[], plot: Plot | undefined, derived: SignalInfo[] = []) {
  for (const p of pairs) {
    if (!p.from) continue;
    const c = all.find((x) => x.key === p.from);
    const first = c && candidateSource(c);
    const src = pairs.find((x) => x.c.key === p.from)?.o ?? plot?.objects?.find((x) => !!first && firstSource(x, derived) === first);
    if (src) p.o.attitudeSource = { object: src.id };
  }
  return pairs.map((p) => p.o);
}

/** "phys (truth), nav (navigation), gps (receiver)" - for a toast. */
export function addedSummary(cs: { name: string; cls: Candidate["cls"] }[], lang: Lang): string {
  const list = cs.map((c) => `${c.name} (${translate(lang, `objCls_${c.cls}` as TKey)})`).join(", ");
  return translate(lang, cs.length === 1 ? "objAddedOne" : "objAddedN", { n: cs.length, list });
}

/** *Why?* in plain words, one line per point: position, attitude, units, class, what is missing, near misses. */
export function whyLines(c: Candidate, lang: Lang, borrowedFrom?: string): string[] {
  const tr = (k: string, v: Record<string, string | number> = {}) => translate(lang, k as TKey, v);
  const how = (roles: DetRole[]) => {
    const p = c.picks[roles.find((r) => c.picks[r])!]!;
    if (p.rule === "known") return tr("objWhyHowKnown", { via: p.via ?? "" });
    if (p.rule === "subgroup") return tr("objWhyHowSub", { sub: p.via ?? "", prefix: c.prefix });
    return c.prefix ? tr("objWhyHowPrefix", { prefix: c.prefix }) : tr("objWhyHowRoot");
  };
  const names = (roles: DetRole[]) => roles.filter((r) => c.picks[r]).map((r) => {
    const p = c.picks[r]!;
    return p.exact || p.word.toLowerCase() === r ? bare(p.id) : `${bare(p.id)} (${tr("objWhyAlias", { word: p.word, role: tr(`objRoleName_${r}`) })})`;
  }).join(" / ");
  const out: string[] = [];
  const posRoles: DetRole[] = c.pos === "lla" ? ["lat", "lon", "alt"] : VEC_ROLES;
  out.push(c.pos === "lla" ? tr("objWhyPos", { list: names(posRoles), how: how(posRoles) })
    : tr("objWhyPosVec", { frame: c.pos.toUpperCase(), list: names(posRoles), how: how(posRoles) }));
  // L3: where a local position is placed on Earth
  if (c.pos === "ned" || c.pos === "enu") {
    const o = c.origin;
    const fields = o ? o.ids.map(bare).map((n) => n.slice(n.lastIndexOf(".") + 1)).join(" / ") : "";
    out.push(!o ? tr("objWhyOriginNone")
      : o.via.replace(/\[\d+\]$/, "") === "ORGN" ? tr("objWhyOriginOrgn", { via: o.via, fields })
      : tr(`objWhyOrigin_${o.rule}`, { via: o.via, fields }) + (o.moves ? " " + tr("objWhyOriginMoves") : ""));
  }
  if (c.badUnit) out.push(tr("objWhyBadUnit", { unit: c.badUnit }));
  const att = c.attitude === "quaternion" ? QUAT : ATT_ROLES;
  out.push(c.attitude !== "none" ? tr("objWhyAtt", { list: names(att), how: how(att) })
    : borrowedFrom ? tr("objAttBorrowed", { name: borrowedFrom }) + "." : tr("objWhyNoAtt", { prefix: c.prefix || c.name }));
  const u = Object.values(c.picks).find((p) => p?.unit);
  if (u?.unit) out.push(tr("objWhyUnit", { unit: u.unit.unit, from: tr(u.unit.from === "suffix" ? "objWhyUnitSuffix" : "objWhyUnitBrackets") }));
  const cls = tr(`objCls_${c.cls}`);
  out.push(c.clsWhy.known ? tr("objWhyClsKnown", { cls, known: c.clsWhy.known }) : c.clsWhy.word ? tr("objWhyCls", { cls, word: c.clsWhy.word }) : tr("objWhyClsOther"));
  if (c.lane) out.push(tr("objWhyLane", { ekf: c.lane.ekf, n: c.lane.n }));
  if (c.missing.length) out.push(tr("objWhyMissing", { list: c.missing.map((r) => tr(`objRoleName_${r}`)).join(", ") }));
  for (const m of c.nearMisses) out.push(tr("objWhyNear", { name: m.name, why: tr(`objNear_${m.why}`, { detail: m.detail }) }));
  return out;
}

/** The copyable example of the naming convention: three objects. */
export const NAMING_EXAMPLE = [
  "time, truth.lat, truth.lon, truth.alt, truth.att.roll, truth.att.pitch, truth.att.yaw,",
  "nav.lat, nav.lon, nav.alt, nav.att.roll, nav.att.pitch, nav.att.yaw,",
  "gps.lat, gps.lon, gps.alt",
].join("\n");
