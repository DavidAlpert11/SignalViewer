import { translate, type TKey } from "./i18n";
import { TRACE_COLORS, uid, type MapObject, type Plot } from "./store";
import { createFrameGroup, frameGroupName } from "./frames";
import { trackOfClass } from "./mapObjects";
import { ATT_ROLES, QUAT, VEC_ROLES, type Candidate, type DetRole } from "./objectDetect";

/* N5: what the found list adds, and the words of its *Why?* - shared by the dialog and the template. */

type Lang = "en" | "he";
const bare = (id: string) => id.slice(id.indexOf("/") + 1);

/** Can *Add all* add it without asking? A NED / ENU position needs an origin first (Advanced…). */
export const addable = (c: Candidate) => c.pos === "lla" || c.pos === "ecef";

/** Already on this plot: an object reading the same latitude (or ECEF x through its frame chain). */
export function isAdded(c: Candidate, plot: Plot | undefined): boolean {
  const lat = c.picks.lat?.id;
  return !!lat && !!plot?.objects?.some((o) => o.lat === lat);
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

/** The map object of a candidate (an ECEF position is turned into lat / lon / alt by a frame group first). */
export async function candidateObject(c: Candidate, color: string, name = c.name): Promise<MapObject> {
  const id = (r: DetRole) => c.picks[r]?.id ?? null;
  let lat = id("lat"), lon = id("lon"), alt = id("alt");
  if (c.pos === "ecef") {
    const f = await createFrameGroup(VEC_ROLES.map((r) => id(r)!), { qty: "position", src: "ecef", dst: "lla" }, frameGroupName("ecef", "lla", "position"));
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
export function linkAttitudes(pairs: { c: Candidate; o: MapObject; from?: string }[], all: Candidate[], plot: Plot | undefined) {
  for (const p of pairs) {
    if (!p.from) continue;
    const lat = all.find((x) => x.key === p.from)?.picks.lat?.id;
    const src = pairs.find((x) => x.c.key === p.from)?.o ?? plot?.objects?.find((x) => !!lat && x.lat === lat);
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
  const att = c.attitude === "quaternion" ? QUAT : ATT_ROLES;
  out.push(c.attitude !== "none" ? tr("objWhyAtt", { list: names(att), how: how(att) })
    : borrowedFrom ? tr("objAttBorrowed", { name: borrowedFrom }) + "." : tr("objWhyNoAtt", { prefix: c.prefix || c.name }));
  const u = Object.values(c.picks).find((p) => p?.unit);
  if (u?.unit) out.push(tr("objWhyUnit", { unit: u.unit.unit, from: tr(u.unit.from === "suffix" ? "objWhyUnitSuffix" : "objWhyUnitBrackets") }));
  const cls = tr(`objCls_${c.cls}`);
  out.push(c.clsWhy.known ? tr("objWhyClsKnown", { cls, known: c.clsWhy.known }) : c.clsWhy.word ? tr("objWhyCls", { cls, word: c.clsWhy.word }) : tr("objWhyClsOther"));
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
