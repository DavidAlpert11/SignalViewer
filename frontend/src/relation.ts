import { api, type Stats } from "./api";
import { findDerived } from "./peers";
import { translate } from "./i18n";
import { actions, useApp, type MapObject, type Plot } from "./store";
import { attitudeOf, hasOwnAttitude, trackRequest } from "./mapObjects";
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
/** Derived signals of one group ("<secondary>_vs_<primary>.<suffix>.<label>"): one per item; all or nothing.
 *  L8: the same items of the same pair made before are reused (their group's name aside) - no duplicates. */
async function makeGroup(P: MapObject, S: MapObject, all: MapObject[], suffix: string, items: { label: string; params: Record<string, unknown> }[], vel = false) {
  const [p, s] = await Promise.all([layout(P, all, vel), layout(S, all, vel)]);
  const runs = useApp.getState().runs;
  const have = items.map((it) => findDerived(runs, "relate", { ...it.params, p: p.lay, s: s.lay }, [...p.src, ...s.src], ["group"]));
  if (have.every(Boolean)) return { ids: have as string[], att: p.lay.att && s.lay.att };
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
      const ids = await frameOnce(src, { qty: "position", src: "lla", dst: frame, ...ref }, `${safe(o.name)}_${frame}_from_${safe(primary.name)}`);
      ids.forEach((id, k) => per[k].push(id));
    }
    const lbl = frame === "lla" ? ["lat", "lon", "alt"] : AXES[frame];
    actions.plotsInNewTab(lbl.map((l, k) => ({ title: `${l} (${frame.toUpperCase()})`, ids: per[k] })), tr("relTabOverlay", { frame: frame.toUpperCase(), p: primary.name }));
  } catch (e) { fail(e); }
}

/** A frame conversion's three signals - the ones made before for the same sources and choice, else new. */
async function frameOnce(src: string[], params: Record<string, unknown>, group: string): Promise<string[]> {
  const runs = useApp.getState().runs;
  const have = [0, 1, 2].map((axis) => findDerived(runs, "frame", { ...params, axis }, src, ["group"]));
  return have.every(Boolean) ? (have as string[]) : createFrameGroup(src, params, group);
}
/** One formula of one signal (an angle in degrees, wrapped) - reused when it exists. */
async function exprOnce(expr: string, id: string, name: string): Promise<string> {
  const have = findDerived(useApp.getState().runs, "expr", { expr }, [id]);
  if (have) return have;
  const r = await api.createDerived("expr", [id], { expr, text: expr.replace(/v0/g, "x") }, name);
  useApp.setState({ runs: r.runs });
  return r.id;
}

/* ---- L8: Compare objects… - one reference, positions, velocities and angles, values and errors ---- */

export type CmpQty = "position" | "velocity" | "attitude";
export type CmpShow = "values" | "errors" | "both";
export interface CompareChoice { ref: MapObject; others: MapObject[]; qty: CmpQty[]; show: CmpShow; frame: CompareFrame }
/** What each quantity can compare: `reason` when the reference itself cannot (the quantity is off), and
 *  the objects left out with why (an i18n key and its values). */
export interface Comparable { reason?: string; out: { o: MapObject; why: string }[] }

export function comparable(ref: MapObject, others: MapObject[], all: MapObject[]): Record<CmpQty, Comparable> {
  const euler = (o: MapObject) => { const r = trackRequest(o, all); return !!(r.roll && r.pitch && r.yaw); };
  const vel: Comparable = { out: [] }, att: Comparable = { out: [] };
  if (!ref.vel) vel.reason = tr("cmpNoVel", { name: ref.name });
  else for (const o of others) if (!o.vel) vel.out.push({ o, why: tr("cmpNoVel", { name: o.name }) });
  if (!hasOwnAttitude(ref) || !euler(ref)) att.reason = tr(hasOwnAttitude(ref) ? "cmpQuatAtt" : "cmpNoAtt", { name: ref.name });
  else for (const o of others) {
    const a = attitudeOf(o, all);
    if (a.kind === "borrowed" && a.from.id === ref.id) att.out.push({ o, why: tr("relNoAttErr", { s: o.name, p: ref.name }) });
    else if (a.kind === "motion") att.out.push({ o, why: tr("cmpMotionAtt", { name: o.name }) });
    else if (a.kind === "none") att.out.push({ o, why: tr("cmpNoAtt", { name: o.name }) });
    else if (!euler(o)) att.out.push({ o, why: tr("cmpQuatAtt", { name: o.name }) });
  }
  return { position: { out: [] }, velocity: vel, attitude: att };
}

/** One statistics row: an error signal of one object and component. */
export interface CmpStat { object: string; qty: string; comp: string; id: string; s?: Stats }
interface Cell { title: string; ids: string[] }

/** The layout of one quantity's tab (pure - tested): one row per component, values left and errors right
 *  with *Both* (one column otherwise), then the extra row (position: horizontal / 3D and vertical error;
 *  velocity: speed error). Values missing (the track frame) leave errors alone in one column. */
export function cmpLayout(show: CmpShow, values: Cell[] | null, errors: Cell[], extra: Cell[]): { plots: Cell[]; cols: number } {
  const v = show !== "errors" && values?.some((c) => c.ids.length) ? values : null;
  const e = show !== "values" ? errors : null;
  if (v && e) return { plots: [...v.flatMap((c, k) => [c, e[k]]), ...extra], cols: 2 };
  if (v) return { plots: v, cols: 1 };
  return { plots: [...errors, ...extra], cols: 1 };
}

/** *Make*: one tab per quantity (one commit, one Undo, one toast with Undo), and the error statistics on
 *  full-resolution data. Signals made before for the same choice are reused. */
export async function makeComparison(c: CompareChoice, all: MapObject[]): Promise<{ tabs: number; stats: CmpStat[] }> {
  const { ref, frame } = c;
  const F = frame.toUpperCase();
  const can = comparable(ref, c.others, all);
  const tabs: { name: string; plots: Cell[]; cols: number }[] = [];
  const stats: CmpStat[] = [];
  // every line is named by its object and wears the object's colour - the one it has on the map - in
  // every plot of the comparison (the plot's title says what is compared; the names were
  // "XKF1_0_vs_POS.dned.north", and an object was blue in the values and orange in the errors)
  const look: Record<string, { label: string; color: string; lineStyle?: "dash" }> = {};
  const mark = (o: MapObject, id: string, what = "", dash = false) => {
    look[id] = { label: what ? `${o.name} · ${what}` : o.name, color: o.color, ...(dash ? { lineStyle: "dash" as const } : {}) };
  };
  const vs = tr("relVs", { p: ref.name });
  const errLbl = AXES[frame];
  for (const q of c.qty) {
    const cq = can[q];
    if (cq.reason) continue;
    const others = c.others.filter((o) => o.id !== ref.id && !cq.out.some((x) => x.o.id === o.id));
    if (!others.length) continue;
    const errs: string[][] = [[], [], []];
    const extra: Cell[] = [];
    const note = (o: MapObject, comp: string, id: string) => stats.push({ object: o.name, qty: q, comp, id });
    let values: Cell[] | null = null;
    if (q === "position") {
      const hz: string[] = [], vt: string[] = [];
      for (const S of others) {
        const d = await makeGroup(ref, S, all, `d${frame}`, errLbl.map((l, axis) => ({ label: l, params: { what: "diff", frame, axis } })));
        d.ids.forEach((id, k) => { errs[k].push(id); note(S, `Δ${errLbl[k]}`, id); mark(S, id); });
        const e = await makeGroup(ref, S, all, "err", [["horiz", "err_horiz"], ["vert", "err_vert"], ["3d", "err_3d"]].map(([l, w]) => ({ label: l, params: { what: w } })));
        hz.push(e.ids[0], e.ids[2]); vt.push(e.ids[1]);
        mark(S, e.ids[0], "horiz"); mark(S, e.ids[2], "3D", true); mark(S, e.ids[1]);
        note(S, tr("cmpHoriz"), e.ids[0]); note(S, tr("cmpVert"), e.ids[1]); note(S, tr("cmp3d"), e.ids[2]);
      }
      extra.push({ title: tr("cmpHoriz3d"), ids: hz }, { title: tr("cmpVert"), ids: vt });
      if (frame !== "track") {
        const per: string[][] = [[], [], []];
        for (const o of [ref, ...others]) {
          if (frame === "lla") { [o.lat, o.lon, o.alt].forEach((id, k) => { if (id) { per[k].push(id); mark(o, id); } }); continue; }
          if (!o.alt) continue;
          const src = [o.lat, o.lon, o.alt, ...(frame === "ecef" ? [] : [ref.lat, ref.lon, ref.alt ?? o.alt])];
          (await frameOnce(src, { qty: "position", src: "lla", dst: frame, ...(frame === "ecef" ? {} : { ref: "signals" }) }, `${safe(o.name)}_${frame}_from_${safe(ref.name)}`))
            .forEach((id, k) => { per[k].push(id); mark(o, id); });
        }
        const lbl = frame === "lla" ? ["lat", "lon", "alt"] : errLbl;
        values = lbl.map((l, k) => ({ title: `${l} (${F})`, ids: per[k] }));
      }
    } else if (q === "velocity") {
      const sp: string[] = [];
      for (const S of others) {
        const d = await makeGroup(ref, S, all, `dv${frame}`, errLbl.map((l, axis) => ({ label: l, params: { what: "vdiff", frame, axis } })), true);
        d.ids.forEach((id, k) => { errs[k].push(id); note(S, `Δv ${errLbl[k]}`, id); mark(S, id); });
        const e = await makeGroup(ref, S, all, "dspeed", [{ label: "speed", params: { what: "err_speed" } }], true);
        sp.push(e.ids[0]); note(S, tr("cmpSpeed"), e.ids[0]); mark(S, e.ids[0]);
      }
      extra.push({ title: tr("cmpSpeed"), ids: sp });
      // values: the recorded north / east / down; ENU turned by the frame op when there are three of them
      const per: string[][] = [[], [], []];
      const enu = frame === "enu";
      for (const o of [ref, ...others]) {
        const v = ([...(o.vel ?? [])] as (string | null)[]).filter((x): x is string => !!x);
        if (enu && v.length === 3) (await frameOnce(v, { qty: "vector", src: "ned", dst: "enu" }, `${safe(o.name)}_vel_enu`)).forEach((id, k) => { per[k].push(id); mark(o, id); });
        else v.forEach((id, k) => { per[k].push(id); mark(o, id); });
      }
      const vl = enu ? ["east", "north", "up"] : ["north", "east", "down"];
      values = vl.map((l, k) => ({ title: `v ${l} (${enu ? "ENU" : "NED"})`, ids: per[k] }));
    } else {
      const names = ["roll", "pitch", "yaw"];
      for (const S of others) {
        const e = await makeGroup(ref, S, all, "datt", [["roll", "err_roll"], ["pitch", "err_pitch"], ["yaw", "err_hdg"]].map(([l, w]) => ({ label: l, params: { what: w } })));
        e.ids.forEach((id, k) => { errs[k].push(id); note(S, `Δ${names[k]}`, id); mark(S, id); });
      }
      // values in degrees; every yaw wrapped as the reference's is (0..360 or -180..180), so no jumps between them
      const lay = async (o: MapObject) => { const r = trackRequest(o, all); const l = await layout(o, all); return { ids: [r.roll!, r.pitch!, r.yaw!], rad: l.lay.unit === "rad" }; };
      const R = await lay(ref);
      let wrap = "wrap360";
      try { const st = (await api.stats([R.ids[2]], null, null)).stats[R.ids[2]]; if (st && st.min < (R.rad ? -0.02 : -1)) wrap = "wrap180"; } catch { /* 0..360 */ }
      const per: string[][] = [[], [], []];
      for (const o of [ref, ...others]) {
        const L = o.id === ref.id ? R : await lay(o);
        for (let k = 0; k < 3; k++) {
          const x = L.rad ? "deg(v0)" : "v0";
          const expr = k === 2 ? `${wrap}(${x})` : x;
          const id = expr === "v0" ? L.ids[k] : await exprOnce(expr, L.ids[k], `${safe(o.name)}_${names[k]}_deg`);
          per[k].push(id); mark(o, id);
        }
      }
      values = names.map((l, k) => ({ title: `${l} (°)`, ids: per[k] }));
    }
    const errors = errLbl.map((l, k) => ({ title: q === "attitude" ? `Δ${["roll", "pitch", "yaw"][k]} (°, ${vs})` : `Δ${q === "velocity" ? "v " : ""}${l} (${F}, ${vs})`, ids: errs[k] }));
    const lay = cmpLayout(c.show, values, errors, q === "attitude" ? [] : extra);
    tabs.push({ name: tr(`cmpTab_${q}`, { frame: q === "attitude" ? "" : F, p: ref.name }), ...lay });
  }
  if (c.show !== "values" && stats.length) {
    try {
      const st = (await api.stats(stats.map((x) => x.id), null, null)).stats;
      for (const row of stats) row.s = st[row.id];
    } catch { /* the plots are still made */ }
  }
  const n = tabs.length ? actions.plotTabs(tabs.map((tb) => ({ ...tb, look }))) : 0;
  if (n) {
    const st = useApp.getState();
    st.toast({ kind: "info", undoesWs: true, text: tr("cmpMade", { n }), action: { label: tr("undo"), run: () => useApp.getState().undo() } });
  }
  return { tabs: n, stats: c.show === "values" ? [] : stats };
}

/** The statistics as CSV (one row per object and component; numbers as recorded, "." decimal). */
export function statsCsv(rows: CmpStat[]): string {
  const f = (v?: number) => (v === undefined || !Number.isFinite(v) ? "" : String(+v.toPrecision(8)));
  return ["object,quantity,component,rms,mean,max_abs,p95_abs,t_max_abs,samples",
    ...rows.map((r) => [r.object, r.qty, r.comp].map((x) => `"${x.replace(/"/g, '""')}"`).join(",") + "," +
      [r.s?.rms, r.s?.mean, r.s?.abs_max, r.s?.p95_abs, r.s?.t_abs_max, r.s?.samples].map(f).join(","))].join("\n") + "\n";
}


/** P9: the error between two tracks of one vehicle (truth and a navigation solution): at each of the first's
 *  samples (at most `max`), the second's position at that time and the distance (local metres - the two
 *  are metres apart). null when they do not overlap in time. `same`: the median under 20 m - one vehicle,
 *  not two. The 3D view draws a surface between them coloured by d / p95; the flat drawing colours the
 *  second track. */
export interface ErrorAlong { rows: { i: number; lat: number; lon: number; h: number; d: number }[]; median: number; p95: number; same: boolean }
type Tr = { t: ArrayLike<number>; lat: ArrayLike<number>; lon: ArrayLike<number> };
export function errorAlong(P: Tr, ph: (i: number) => number, S: Tr, sh: (j: number) => number, max = 600): ErrorAlong | null {
  const n = P.t.length, m = S.t.length;
  if (n < 3 || m < 2) return null;
  const step = Math.max(1, Math.floor(n / max)), rows: ErrorAlong["rows"] = [];
  let j = 0;
  for (let i = 0; i < n; i += step) {
    const t = P.t[i];
    if (!(t >= S.t[0] && t <= S.t[m - 1]) || !Number.isFinite(P.lat[i]) || !Number.isFinite(P.lon[i])) continue;
    while (j < m - 2 && S.t[j + 1] <= t) j++;
    const f = S.t[j + 1] > S.t[j] ? (t - S.t[j]) / (S.t[j + 1] - S.t[j]) : 0;
    const L = (a: ArrayLike<number>, b: number, c: number) => a[b] + (a[c] - a[b]) * f;
    const lat = L(S.lat, j, j + 1), lon = L(S.lon, j, j + 1), h0 = sh(j), h1 = sh(j + 1);
    const h = Number.isFinite(h0) && Number.isFinite(h1) ? h0 + (h1 - h0) * f : Number.isFinite(h0) ? h0 : h1;
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
    const kN = 111_320, kE = 111_320 * Math.cos((P.lat[i] * Math.PI) / 180), hp = ph(i);
    const dz = Number.isFinite(h) && Number.isFinite(hp) ? h - hp : 0;
    rows.push({ i, lat, lon, h, d: Math.hypot((lat - P.lat[i]) * kN, (lon - P.lon[i]) * kE, dz) });
  }
  if (rows.length < 3) return null;
  const ds = rows.map((r) => r.d).sort((a, b) => a - b);
  const median = ds[ds.length >> 1], p95 = ds[Math.min(ds.length - 1, Math.floor(ds.length * 0.95))];
  return { rows, median, p95, same: median < 20 };
}
/** The colour of an error of `q` (= d / p95): green, amber at half, red at the 95th percentile. */
export function errorColor(q: number): string {
  const c = [[45, 164, 78], [242, 169, 59], [229, 83, 75]], x = Math.max(0, Math.min(1, q)) * 2, k = Math.min(1, Math.floor(x)), f = x - k;
  const v = c[k].map((a, i) => Math.round(a + (c[k + 1][i] - a) * f));
  return `rgb(${v[0]}, ${v[1]}, ${v[2]})`;
}
