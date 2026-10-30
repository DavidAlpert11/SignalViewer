/* Filters on the axes: a value is kept when it is inside any range of its axis (or one of the
   listed values); a line is kept when every filtered axis keeps it. */
import type { Col, Filter } from "./model";

export function keeps(f: Filter, v: number): boolean {
  if (!Number.isFinite(v)) return false;
  if (f.kind === "values") return f.values.includes(v);
  for (const [a, b] of f.ranges) if (v >= Math.min(a, b) && v <= Math.max(a, b)) return true;
  return false;
}

/** 1 for each row every filter keeps. Filters on columns not in `cols` are ignored. */
export function keptMask(cols: Map<string, Col>, filters: Record<string, Filter>, n: number): Uint8Array {
  const m = new Uint8Array(n).fill(1);
  for (const [name, f] of Object.entries(filters)) {
    const c = cols.get(name);
    if (!c) continue;
    const v = c.values;
    for (let i = 0; i < n; i++) if (m[i] && !keeps(f, v[i])) m[i] = 0;
  }
  return m;
}

export const hasFilter = (f?: Filter) => !!f && (f.kind === "ranges" ? f.ranges.length > 0 : f.values.length > 0);
