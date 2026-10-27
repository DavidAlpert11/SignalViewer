/* Named conditions (investigation spec, step 2): kept in the session (ws.conditions), looked for in
   every open file by the server (svcore/conditions.py), drawn on the time plots (TimeChart) and
   listed in the Investigate panel. Combined conditions ("and" / "or") are worked out here from
   their parts' stretches. */
import { api } from "./api";
import { translate } from "./i18n";
import { actions, uid, useApp, type Condition, type CondResult } from "./store";
import { record } from "./investigation";

/** A small fixed palette: conditions never take the signals' colours. */
export const COND_COLORS = ["#D4A72C", "#B392F0", "#2DA44E", "#E16F24", "#1F6FEB", "#BF3989"];

type Iv = [number, number][];
function intersect(a: Iv, b: Iv): Iv {
  const out: Iv = [];
  let i = 0, j = 0;
  while (i < a.length && j < b.length) {
    const lo = Math.max(a[i][0], b[j][0]), hi = Math.min(a[i][1], b[j][1]);
    if (lo <= hi) out.push([lo, hi]);
    if (a[i][1] < b[j][1]) i++; else j++;
  }
  return out;
}
function union(a: Iv, b: Iv): Iv {
  const all = [...a, ...b].sort((x, y) => x[0] - y[0]);
  const out: Iv = [];
  for (const iv of all) {
    if (out.length && iv[0] <= out[out.length - 1][1]) out[out.length - 1][1] = Math.max(out[out.length - 1][1], iv[1]);
    else out.push([iv[0], iv[1]]);
  }
  return out;
}
const summary = (iv: Iv): CondResult => ({ intervals: iv, count: iv.length, total: iv.reduce((s, [a, b]) => s + b - a, 0) });

function combined(c: Condition, res: Record<string, Record<string, CondResult>>): Record<string, CondResult> {
  const parts = (c.combine?.ids ?? []).map((id) => res[id]).filter(Boolean);
  if (!parts.length) return {};
  const out: Record<string, CondResult> = {};
  for (const rid of Object.keys(parts[0])) {
    const ivs = parts.map((p) => p[rid]);
    const missing = ivs.flatMap((r) => r?.missing ?? []);
    const err = ivs.find((r) => r?.error)?.error;
    if (missing.length || err || ivs.some((r) => !r)) { out[rid] = { missing: [...new Set(missing)], ...(err ? { error: err } : {}) }; continue; }
    const iv = ivs.map((r) => r!.intervals ?? []).reduce((acc, x) => (c.combine!.op === "and" ? intersect(acc, x) : union(acc, x)));
    out[rid] = summary(iv);
  }
  return out;
}

/** Look for one condition the way it is written now (the editor's preview uses this too). */
export async function evaluateOne(c: Pick<Condition, "text" | "exit" | "minDur" | "mergeGap">): Promise<Record<string, CondResult>> {
  return (await api.evalCondition(c.text, { exit: c.exit, minDur: c.minDur, mergeGap: c.mergeGap })).results;
}

let pending = 0;
/** Every condition of the session, again (files, data or conditions changed). */
export async function evaluateAll() {
  const my = ++pending;
  const conds = useApp.getState().ws.conditions ?? [];
  const res: Record<string, Record<string, CondResult>> = {};
  for (const c of conds.filter((x) => !x.combine)) {
    try { res[c.id] = await evaluateOne(c); } catch (e) { res[c.id] = { "": { error: String((e as Error).message) } }; }
    if (my !== pending) return;                      // a newer round started
  }
  for (const c of conds.filter((x) => x.combine)) res[c.id] = combined(c, res);
  useApp.setState({ condResults: res });
}

/** The stretches of a condition across the files open now, in time order (with their file). */
export function occurrences(id: string): { rid: string; a: number; b: number }[] {
  const r = useApp.getState().condResults[id] ?? {};
  return Object.entries(r).flatMap(([rid, x]) => (x.intervals ?? []).map(([a, b]) => ({ rid, a, b }))).sort((p, q) => p.a - q.a);
}

/** Zoom to the next (dir 1) or previous (-1) stretch of the condition after the current view. */
export function stepOccurrence(id: string, dir: 1 | -1) {
  const all = occurrences(id);
  if (!all.length) return;
  const st = useApp.getState();
  const mid = st.cursor.on && st.cursor.t1 !== null ? st.cursor.t1 : -Infinity;
  const k = dir > 0 ? all.findIndex((o) => o.a > mid + 1e-9) : findLast(all, (o) => o.a < mid - 1e-9);
  const o = all[k < 0 ? (dir > 0 ? 0 : all.length - 1) : k];
  const pad = Math.max((o.b - o.a) * 0.5, 0.5);
  actions.showSpan(o.a - pad, o.b + pad);
  useApp.setState({ condFocus: id, cursor: { ...useApp.getState().cursor, on: true, dual: true, t1: o.a, t2: o.b, active: 1 } });
}
function findLast<T>(a: T[], f: (x: T) => boolean): number {
  for (let i = a.length - 1; i >= 0; i--) if (f(a[i])) return i;
  return -1;
}

function nextColor(conds: Condition[]): string {
  const used = new Set(conds.map((c) => c.color));
  return COND_COLORS.find((c) => !used.has(c)) ?? COND_COLORS[conds.length % COND_COLORS.length];
}
/** Add or change a condition (one undo step), then look for it. */
export function saveCondition(c: Omit<Condition, "id" | "color" | "visible"> & Partial<Condition>) {
  useApp.getState().commit((ws) => {
    const list = ws.conditions ?? [];
    const i = c.id ? list.findIndex((x) => x.id === c.id) : -1;
    const given = Object.fromEntries(Object.entries(c).filter(([, v]) => v !== undefined));   // a copy: new id, colour
    const full: Condition = { visible: true, color: nextColor(list), id: uid("c"), ...(i >= 0 ? list[i] : {}), ...given } as Condition;
    ws.conditions = i >= 0 ? list.map((x, k) => (k === i ? full : x)) : [...list, full];
    return ws;
  });
  const saved = useApp.getState().ws.conditions?.find((x) => x.name === c.name && (c.id ? x.id === c.id : true));
  void evaluateAll();
  // the journal: what was asked and how many stretches it found (its own look - evaluateAll rounds
  // can be overtaken by newer ones)
  if (saved && !saved.combine) {
    void evaluateOne(saved).then((r) => {
      const n = Object.values(r).reduce((s, x) => s + (x.count ?? 0), 0);
      record(translate(useApp.getState().lang, "jCondition", { name: saved.name, text: saved.text, n }), false);
    }).catch(() => {});
  }
}
export function updateCondition(id: string, patch: Partial<Condition>) {
  useApp.getState().commit((ws) => {
    ws.conditions = (ws.conditions ?? []).map((x) => (x.id === id ? { ...x, ...patch } : x));
    return ws;
  });
}
/** Conditions combined from this one (they would lose a part). */
export function usedBy(id: string): Condition[] {
  return (useApp.getState().ws.conditions ?? []).filter((c) => c.combine?.ids.includes(id));
}
export function deleteCondition(id: string) {
  const st = useApp.getState();
  const name = st.ws.conditions?.find((c) => c.id === id)?.name ?? "";
  st.commit((ws) => {
    ws.conditions = (ws.conditions ?? []).filter((c) => c.id !== id && !c.combine?.ids.includes(id));
    return ws;
  });
  if (st.condFocus === id) useApp.setState({ condFocus: null });
  st.toast({ kind: "info", text: translate(st.lang, "condDeleted", { name }), action: { label: translate(st.lang, "undo"), run: () => { useApp.getState().undo(); void evaluateAll(); } } });
}
export function combineConditions(a: Condition, b: Condition, op: "and" | "or") {
  saveCondition({ name: `${a.name} ${op === "and" ? "∧" : "∨"} ${b.name}`, text: "", combine: { op, ids: [a.id, b.id] } });
}

/** The intervals of a condition by file (for the occurrence tools). */
export function intervalsByRun(id: string): Record<string, [number, number][]> {
  const r = useApp.getState().condResults[id] ?? {};
  return Object.fromEntries(Object.entries(r).filter(([, x]) => x.intervals?.length).map(([rid, x]) => [rid, x.intervals!]));
}

/** The signals a condition reads (what its result reports a range for), in every file. */
export function condSignals(id: string): string[] {
  const r = useApp.getState().condResults[id] ?? {};
  return [...new Set(Object.values(r).flatMap((x) => Object.keys(x.ranges ?? {})))];
}

/** Investigation step 3: a new tab with the condition's stretches of this signal on top of each
 *  other (an "occ" plot), one colour per file. */
export function overlayInNewTab(id: string, name: string) {
  const st = useApp.getState();
  const cond = st.ws.conditions?.find((c) => c.id === id);
  const runsWith = Object.keys(intervalsByRun(id)).filter((rid) => st.runs.find((r) => r.id === rid)?.signals.some((s) => s.name === name));
  if (!cond || !runsWith.length) return;
  st.commit((ws) => {
    const p = { id: uid("p"), title: `${cond.name} · ${name}`, mode: "occ" as const,
      occ: { cond: id, align: "start" as const, pad: 0.5 },
      signals: runsWith.map((rid, i) => ({ sig: `${rid}/${name}`, color: COND_PALETTE_FILES[i % COND_PALETTE_FILES.length], width: 1.5, scale: 1, offset: 0 })) };
    const tab = { id: uid("t"), name: cond.name, rows: 1, cols: 1, plots: [p], active: 0, linkX: false };
    ws.tabs.push(tab);
    ws.activeTab = tab.id;
    return ws;
  });
}
const COND_PALETTE_FILES = ["#3D8BFD", "#E8590C", "#2F9E44", "#AE3EC9", "#F08C00", "#0CA678"];
