import { api } from "./api";
import { translate } from "./i18n";
import { actions, useApp, type MapObject, type Plot } from "./store";
import { attitudeOf, trackRequest } from "./mapObjects";
import { createFrameGroup, freeGroup } from "./frames";

/* N7 (Tacview-like): a primary and a secondary object and what is between them - at the cursor (the
   panel on the map, computed here from the tracks) and over time (derived signals: svcore/relate.py,
   the same definitions; relation.test.ts checks the two agree on the same geometry). */

/* ---- which objects ----------------------------------------------------------------------------- */

const rankP: Record<string, number> = { truth: 0, navigation: 1, receiver: 2, other: 3 };
/** The default pair from the classes (N5): the primary is the truth, else the first navigation
 *  solution (a flight log's EKF), else the first; the secondary the first navigation solution, else
 *  the first receiver, else the next object. One object: no secondary. */
export function defaultPair(objects: MapObject[]): { primary: string | null; secondary: string | null } {
  if (!objects.length) return { primary: null, secondary: null };
  const by = (o: MapObject) => rankP[o.cls ?? "other"] ?? 3;
  const primary = [...objects].sort((a, b) => by(a) - by(b))[0];
  const rest = objects.filter((o) => o.id !== primary.id);
  const sec = rest.find((o) => o.cls === "navigation") ?? rest.find((o) => o.cls === "receiver") ?? rest[0] ?? null;
  return { primary: primary.id, secondary: sec?.id ?? null };
}
/** The plot's pair: its own choice (Plot.primaryObject, the first of Plot.relatedObjects) where it is
 *  still an object of the plot, else the default. */
export function pairOf(plot: Pick<Plot, "objects" | "primaryObject" | "relatedObjects">) {
  const objs = plot.objects ?? [];
  const has = (id?: string | null) => !!id && objs.some((o) => o.id === id);
  const d = defaultPair(objs);
  const primary = has(plot.primaryObject) ? plot.primaryObject! : d.primary;
  const own = (plot.relatedObjects ?? []).find((x) => x !== primary && has(x));
  const secondary = own ?? (d.secondary !== primary ? d.secondary : defaultPair(objs.filter((o) => o.id !== primary)).primary);
  return { primary, secondary: objs.length > 1 ? secondary : null };
}

/* ---- the geometry (WGS84, the primary's NED - as svcore) ---------------------------------------- */

const A = 6378137.0, F = 1 / 298.257223563, E2 = F * (2 - F);
const rad = (d: number) => (d * Math.PI) / 180, deg = (r: number) => (r * 180) / Math.PI;
export const wrap180 = (a: number) => ((((a + 180) % 360) + 360) % 360) - 180;
function ecef(lat: number, lon: number, alt: number): [number, number, number] {
  const la = rad(lat), lo = rad(lon), n = A / Math.sqrt(1 - E2 * Math.sin(la) ** 2);
  return [(n + alt) * Math.cos(la) * Math.cos(lo), (n + alt) * Math.cos(la) * Math.sin(lo), (n * (1 - E2) + alt) * Math.sin(la)];
}
function toNed(lat: number, lon: number, d: [number, number, number]): [number, number, number] {
  const la = rad(lat), lo = rad(lon), sla = Math.sin(la), cla = Math.cos(la), slo = Math.sin(lo), clo = Math.cos(lo);
  return [-sla * clo * d[0] - sla * slo * d[1] + cla * d[2], -slo * d[0] + clo * d[1], -cla * clo * d[0] - cla * slo * d[1] - sla * d[2]];
}
export interface At { lat: number; lon: number; alt: number | null; hdg: number | null }
export interface Relation {
  horiz: number; slant: number | null; dalt: number | null; bearing: number; relBearing: number | null;
  closure: number | null; tca: number | null; hdgDiff: number | null; aspect: number | null; aspectSide: "L" | "R" | null;
}
/** What is between P and S at one moment; P2 / S2 a moment `dt` s later give the closure rate and the
 *  time to closest approach (as svcore: closure = -d(range)/dt; tca = -r·v / |v|² while closing). */
export function relation(P: At, S: At, P2?: At, S2?: At, dt = 0): Relation {
  const vert = P.alt !== null && S.alt !== null;
  const ep = ecef(P.lat, P.lon, P.alt ?? 0), es = ecef(S.lat, S.lon, S.alt ?? 0);
  const d: [number, number, number] = [es[0] - ep[0], es[1] - ep[1], es[2] - ep[2]];
  const ned = toNed(P.lat, P.lon, d);
  const horiz = Math.hypot(ned[0], ned[1]);
  const rng = vert ? Math.hypot(horiz, ned[2]) : horiz;
  const b = ((deg(Math.atan2(ned[1], ned[0])) % 360) + 360) % 360;
  let closure: number | null = null, tca: number | null = null;
  if (P2 && S2 && dt > 0) {
    const r2 = relation(P2, S2);
    const rng2 = vert ? r2.slant! : r2.horiz;
    closure = -(rng2 - rng) / dt;
    const ep2 = ecef(P2.lat, P2.lon, P2.alt ?? 0), es2 = ecef(S2.lat, S2.lon, S2.alt ?? 0);
    const v = [0, 1, 2].map((k) => (es2[k] - ep2[k] - d[k]) / dt);
    const v2 = v[0] ** 2 + v[1] ** 2 + v[2] ** 2;
    const t = v2 > 0 ? -(d[0] * v[0] + d[1] * v[1] + d[2] * v[2]) / v2 : NaN;
    tca = closure > 0 && t >= 0 ? t : null;
  }
  let aspect: number | null = null, side: "L" | "R" | null = null;
  if (S.hdg !== null) {
    const toP = toNed(S.lat, S.lon, [-d[0], -d[1], -d[2]]);
    const a = wrap180(deg(Math.atan2(toP[1], toP[0])) - (S.hdg + 180));
    aspect = Math.abs(a);
    // seen from above, clockwise from the tail is the secondary's left (its tail points back)
    side = aspect < 1e-6 || aspect > 180 - 1e-6 ? null : a > 0 ? "L" : "R";
  }
  return {
    horiz, slant: vert ? rng : null, dalt: vert ? S.alt! - P.alt! : null, bearing: b >= 360 ? 0 : b,
    relBearing: P.hdg !== null ? wrap180(b - P.hdg) : null, closure, tca,
    hdgDiff: P.hdg !== null && S.hdg !== null ? Math.abs(wrap180(S.hdg - P.hdg)) : null, aspect, aspectSide: side,
  };
}

/* ---- over time: derived signals (svcore "relate") ---------------------------------------------- */

const bare = (id: string) => id.slice(id.indexOf("/") + 1);
const safe = (s: string) => s.replace(/[^\w-]+/g, "_").replace(/^_+|_+$/g, "") || "obj";
/** An object's sources and layout for "relate": latitude, longitude, [altitude], [roll, pitch, yaw]
 *  (its own angles, or the borrowed ones; a motion attitude: none - the heading is its course). */
async function layout(o: MapObject, all: MapObject[], withVel = false) {
  const r = trackRequest(o, all);
  const att = !!(r.roll && r.pitch && r.yaw);
  let unit: "deg" | "rad" = r.angleUnit === "rad" ? "rad" : "deg";
  if (att && (r.angleUnit ?? "auto") === "auto") {
    try { const u = await api.angleUnits({ yaw: r.yaw, pitch: r.pitch, roll: r.roll }); unit = u.units.yaw?.unit === "rad" ? "rad" : "deg"; } catch { /* degrees */ }
  }
  const vel = withVel && o.vel ? (o.vel.filter((x): x is string => !!x)) : [];
  const src = [o.lat, o.lon, ...(o.alt ? [o.alt] : []), ...(att ? [r.roll!, r.pitch!, r.yaw!] : []), ...vel];
  return { src, lay: { alt: !!o.alt, att, unit, ...(vel.length ? { vel: vel.length } : {}) } };
}
/** Derived signals of one group ("<secondary>_vs_<primary>.<suffix>.<label>"): one per item; all or nothing. */
async function makeGroup(P: MapObject, S: MapObject, all: MapObject[], suffix: string, items: { label: string; params: Record<string, unknown> }[], vel = false) {
  const [p, s] = await Promise.all([layout(P, all, vel), layout(S, all, vel)]);
  const runs = useApp.getState().runs;
  const g = freeGroup(`${safe(S.name)}_vs_${safe(P.name)}.${suffix}`, runs, items.map((i) => i.label));
  const made: string[] = [];
  try {
    for (const it of items) {
      const r = await api.createDerived("relate", [...p.src, ...s.src], { ...it.params, p: p.lay, s: s.lay, group: g }, `${g}.${it.label}`);
      useApp.setState({ runs: r.runs });
      made.push(r.id);
    }
  } catch (e) {
    for (const id of made) await api.deleteDerived(id.slice("derived/".length)).catch(() => {});
    if (made.length) useApp.setState({ runs: await api.listRuns() });
    throw e;
  }
  return { ids: made, att: p.lay.att && s.lay.att };
}
const fail = (e: unknown) => useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
const tr = (k: string, v: Record<string, string | number> = {}) => translate(useApp.getState().lang, k as never, v);

/** *Plot the relation*: range, Δalt, bearing and closure rate of the pair, in a new time tab. */
export async function plotRelation(P: MapObject, S: MapObject, all: MapObject[]) {
  try {
    const { ids } = await makeGroup(P, S, all, "rel", ["range", "dalt", "bearing", "closure"].map((w) => ({ label: w, params: { what: w } })));
    actions.plotsInNewTab(ids.map((id) => ({ title: bare(id), ids: [id] })), tr("relTabRelation", { s: S.name, p: P.name }));
  } catch (e) { fail(e); }
}

/** *Error signals vs the primary*: horizontal / vertical / 3D error and the heading error - with both
 *  objects' angles also roll and pitch; no angle errors for an attitude borrowed from the primary
 *  itself (zero by construction - said in a message). Returns the new signals. */
export async function errorSignals(P: MapObject, S: MapObject, all: MapObject[], plot = true): Promise<string[]> {
  const a = attitudeOf(S, all);
  const fromP = a.kind === "borrowed" && a.from.id === P.id;
  const items = [["horiz", "err_horiz"], ["vert", "err_vert"], ["3d", "err_3d"]].map(([l, w]) => ({ label: l, params: { what: w } }));
  if (!fromP) items.push({ label: a.kind === "motion" ? "hdg_cog" : "hdg", params: { what: "err_hdg" } });
  try {
    const p = await layout(P, all), s = await layout(S, all);
    if (!fromP && p.lay.att && s.lay.att) items.push({ label: "roll", params: { what: "err_roll" } }, { label: "pitch", params: { what: "err_pitch" } });
    const { ids } = await makeGroup(P, S, all, "err", items);
    if (fromP) useApp.getState().toast({ kind: "info", text: tr("relNoAttErr", { s: S.name, p: P.name }) });
    if (plot) actions.plotsInNewTab([{ title: tr("relErrPos"), ids: ids.slice(0, 3) }, ...(ids.length > 3 ? [{ title: tr("relErrAng"), ids: ids.slice(3) }] : [])],
      tr("relTabErrors", { s: S.name, p: P.name }));
    return ids;
  } catch (e) { fail(e); return []; }
}

export type CompareFrame = "ned" | "enu" | "ecef" | "lla" | "track";
const AXES: Record<CompareFrame, string[]> = { ned: ["north", "east", "down"], enu: ["east", "north", "up"], ecef: ["x", "y", "z"],
  lla: ["north", "east", "up"], track: ["along", "cross", "up"] };
/** *Compare objects* in a frame: one time tab with, per component, the differences of every object
 *  (or `only`) against the primary (in the primary's local frame at each sample for NED / ENU), plus
 *  the horizontal / vertical / 3D errors. One click, one tab. */
export async function compareObjects(primary: MapObject, objects: MapObject[], frame: CompareFrame, only?: MapObject) {
  const others = only ? [only] : objects.filter((o) => o.id !== primary.id);
  if (!others.length) return;
  try {
    const per: string[][] = [[], [], []];
    const errs: string[] = [], vels: string[] = [];
    for (const S of others) {
      // N7: the velocities too, when both have them
      if (primary.vel && S.vel) {
        const v = await makeGroup(primary, S, objects, `dv${frame}`, AXES[frame].map((l, axis) => ({ label: l, params: { what: "vdiff", frame, axis } })), true);
        vels.push(...v.ids);
      }
      const { ids } = await makeGroup(primary, S, objects, `d${frame}`, AXES[frame].map((l, axis) => ({ label: l, params: { what: "diff", frame, axis } })));
      ids.forEach((id, k) => per[k].push(id));
      const e = await makeGroup(primary, S, objects, "err", [["horiz", "err_horiz"], ["vert", "err_vert"], ["3d", "err_3d"]].map(([l, w]) => ({ label: l, params: { what: w } })));
      errs.push(...e.ids);
    }
    actions.plotsInNewTab([...AXES[frame].map((l, k) => ({ title: `Δ${l} (${frame.toUpperCase()}, ${tr("relVs", { p: primary.name })})`, ids: per[k] })),
      { title: tr("relErrPos"), ids: errs }, ...(vels.length ? [{ title: tr("relVelDiff", { frame: frame.toUpperCase() }), ids: vels }] : [])],
      tr("relTabCompare", { frame: frame.toUpperCase(), p: primary.name }));
  } catch (e) { fail(e); }
}

/** *Compare* (overlay): the same component of every object on one plot - NED / ENU from ONE origin
 *  (the primary's first valid position, so the curves are comparable), ECEF, or LLA as recorded. The
 *  track frame is relative to the primary: differences only. Objects without an altitude are left out
 *  of NED / ENU / ECEF (a position needs all three). */
export async function overlayObjects(primary: MapObject, objects: MapObject[], frame: Exclude<CompareFrame, "track">) {
  const order = [primary, ...objects.filter((o) => o.id !== primary.id)];
  const per: string[][] = [[], [], []];
  try {
    for (const o of order) {
      if (frame === "lla") { [o.lat, o.lon, o.alt].forEach((id, k) => { if (id) per[k].push(id); }); continue; }
      if (!o.alt) continue;
      const ref = frame === "ecef" ? {} : { ref: "signals" };
      const src = [o.lat, o.lon, o.alt, ...(frame === "ecef" ? [] : [primary.lat, primary.lon, primary.alt ?? o.alt])];
      const ids = await createFrameGroup(src, { qty: "position", src: "lla", dst: frame, ...ref }, `${safe(o.name)}_${frame}_from_${safe(primary.name)}`);
      ids.forEach((id, k) => per[k].push(id));
    }
    const lbl = frame === "lla" ? ["lat", "lon", "alt"] : AXES[frame];
    actions.plotsInNewTab(lbl.map((l, k) => ({ title: `${l} (${frame.toUpperCase()})`, ids: per[k] })), tr("relTabOverlay", { frame: frame.toUpperCase(), p: primary.name }));
  } catch (e) { fail(e); }
}
