import { api, type SignalTransform } from "./api";
import { useApp } from "./store";
import { translate } from "./i18n";
import { withEditPeers } from "./peers";
import { displayX } from "./xRefs";

/** Human-readable form of a change made on a signal: "y = 2·abs(x) + 1, t + 0.5". */
export function describeTransform(tf?: SignalTransform | null): string {
  if (!tf) return "";
  let f = displayX(tf.expr || "x", useApp.getState().runs);     // Q90: {@id:Name} as {file:Name}
  if (tf.scale !== undefined && tf.scale !== 1) f = `${tf.scale}·${wrap(f)}`;
  if (tf.offset) f += tf.offset > 0 ? ` + ${tf.offset}` : ` − ${-tf.offset}`;
  return `y = ${f}` + (tf.dt ? `,  t ${tf.dt > 0 ? "+" : "−"} ${Math.abs(tf.dt)}` : "") + (tf.unit ? `  [${tf.unit}]` : "");
}

/** Apply (or clear with null) the same change on many signals; one toast offers Undo. */
export async function applyTransform(ids: string[], tf: SignalTransform | null) {
  ids = withEditPeers(ids);                                   // Link operations: the other files too
  const st = useApp.getState();
  const L = st.lang;
  const r = await api.setTransforms(ids, tf);
  const bump = (runs: typeof r.runs) => useApp.setState({ runs, dataVersion: useApp.getState().dataVersion + 1 });
  bump(r.runs);
  st.toast({
    kind: "info", text: translate(L, tf ? "tfApplied" : "tfRemoved", { n: ids.length }),
    action: { label: translate(L, "undo"), run: async () => bump((await api.setTransformSpecs(r.previous)).runs) },
  });
}

/* ------------------------------------------------------------------------
   Editing a signal in place, step by step. Each step applies to the result of
   the previous ones ("abs" then "smooth" = smooth(abs(x))), and the whole stack
   stays ONE change on the signal, shown by its ƒ mark.
------------------------------------------------------------------------- */
export interface Step { expr?: string; scale?: number; offset?: number; dt?: number; unit?: string }

/** Analysis operation -> an in-place step (every one-signal operation has one). */
export function opToStep(op: string, p: { window?: number; cutoff?: number; gain?: number; bias?: number; expr?: string }): Step | null {
  const n = Math.max(2, Math.round(p.window ?? 10)), fc = p.cutoff ?? 10;
  switch (op) {
    case "derivative": return { expr: "deriv(x)" };
    case "integral": return { expr: "integ(x)" };
    case "abs": return { expr: "abs(x)" };
    case "negate": return { expr: "-x" };
    case "normalize": return { expr: "norm01(x)" };
    case "smooth": return { expr: `smooth(x, ${n})` };
    case "rms": return { expr: `sqrt(smooth(x*x, ${n}))` };
    case "lowpass": return { expr: `lowpass(x, ${fc})` };
    case "highpass": return { expr: `highpass(x, ${fc})` };
    case "affine": return { scale: p.gain ?? 1, offset: p.bias ?? 0 };
    case "exprx": return p.expr?.trim() ? { expr: p.expr.trim() } : null;     // the user's own f(x), e.g. x*8, sin(x)
    default: return null;
  }
}

const SIMPLE = /^(?:[\w.[\]]+|\w+\((?:[^()]|\([^()]*\))*\))$/;      // a name, or one function call
const wrap = (e: string) => (SIMPLE.test(e) ? e : `(${e})`);

/** Replace every x in `expr` by `inner`, with parentheses only where they are needed. */
function substitute(expr: string, inner: string): string {
  return expr.replace(/\bx\b/g, (_m, at: number) => {
    const before = expr.slice(0, at).trimEnd().slice(-1), after = expr.slice(at + 1).trimStart()[0];
    const wholeArgument = (before === "(" || before === ",") && (after === ")" || after === ",");
    return wholeArgument ? inner : wrap(inner);
  });
}

/** prev, then step  ->  one transform. */
export function composeTransform(prev: SignalTransform | undefined | null, step: Step): SignalTransform {
  const k1 = prev?.scale ?? 1, c1 = prev?.offset ?? 0, dt = (prev?.dt ?? 0) + (step.dt ?? 0);
  if (step.expr) {
    let inner = prev?.expr || "x";
    if (k1 !== 1) inner = `${k1}*${wrap(inner)}`;
    if (c1) inner = `${inner} ${c1 > 0 ? "+" : "-"} ${Math.abs(c1)}`;
    return { expr: inner === "x" ? step.expr : substitute(step.expr, inner), scale: step.scale ?? 1, offset: step.offset ?? 0, dt,
      ...(step.unit ?? prev?.unit ? { unit: step.unit ?? prev?.unit } : {}) };
  }
  const k2 = step.scale ?? 1, c2 = step.offset ?? 0;
  // a unit conversion names the new unit; any other step keeps the one there was
  return { expr: prev?.expr, scale: k1 * k2, offset: k2 * c1 + c2, dt, ...(step.unit ?? prev?.unit ? { unit: step.unit ?? prev?.unit } : {}) };
}

async function setSpecs(specs: Record<string, SignalTransform | null>, message: string) {
  const st = useApp.getState();
  const r = await api.setTransformSpecs(specs);
  const bump = (runs: typeof r.runs) => useApp.setState({ runs, dataVersion: useApp.getState().dataVersion + 1 });
  bump(r.runs);
  st.toast({ kind: "info", text: message,
    action: { label: translate(st.lang, "undo"), run: async () => bump((await api.setTransformSpecs(r.previous)).runs) } });
}

/** Edit many signals in place with the same step (derived signals are skipped: they are formulas). */
export async function editInPlace(ids: string[], step: Step) {
  const st = useApp.getState();
  const all = st.runs.flatMap((r) => r.signals);
  const targets = withEditPeers(ids).filter((id) => !id.startsWith("derived/"));   // each composes on its own edit
  const specs = Object.fromEntries(targets.map((id) => [id, composeTransform(all.find((s) => s.id === id)?.transform, step)]));
  if (!targets.length) throw new Error(translate(st.lang, "editNoOriginals"));
  await setSpecs(specs, translate(st.lang, "tfApplied", { n: targets.length }));
}

/** One action: every in-place edit removed (Undo brings them all back). */
export async function clearAllEdits() {
  const st = useApp.getState();
  const ids = st.runs.flatMap((r) => r.signals.filter((s) => s.transform).map((s) => s.id));
  if (!ids.length) return;
  await setSpecs(Object.fromEntries(ids.map((id) => [id, null])), translate(st.lang, "tfRemoved", { n: ids.length }));
}

/** One action: every derived signal deleted. Undo recreates them from their formulas
 *  and puts them back in the plots. */
export async function deleteAllDerived() {
  const st = useApp.getState();
  const d = st.runs.find((r) => r.format === "derived");
  if (!d || !d.signals.length) return;
  const items = d.signals.map((s) => ({ name: s.name, op: s.op!, sources: s.sources!, params: s.params }));
  for (const s of d.signals) await api.deleteDerived(s.name).catch(() => {});
  const wsBefore = st.ws;
  st.commit((ws) => {
    ws.tabs.forEach((tb) => tb.plots.forEach((p) => { p.signals = p.signals.filter((x) => !x.sig.startsWith("derived/")); }));
    return ws;
  });
  useApp.setState({ runs: await api.listRuns() });
  // F12: the Undo puts back the workspace as it was before the delete, so it is valid only until the
  // next workspace change (undoesWs) - it once stayed and wiped later changes - and it is a commit
  // (an undo step like any other), not a direct write
  st.toast({ kind: "info", text: translate(st.lang, "derivedAllDeleted", { n: items.length }), undoesWs: true,
    action: { label: translate(st.lang, "undo"), run: async () => {
      const r = await api.restoreDerived(items);
      useApp.setState({ runs: r.runs, dataVersion: useApp.getState().dataVersion + 1 });
      useApp.getState().commit(() => structuredClone(wsBefore));
    } } });
}

/** A unit conversion as an in-place step (rad -> deg: x·57.2958, unit "deg"). */
export function conversionStep(c: { to: string; scale: number; offset?: number }): Step {
  return { scale: c.scale, offset: c.offset ?? 0, unit: c.to };
}
