import type uPlot from "uplot";

/** P3: uPlot.join for the time plot's tables - the same result, much faster when there are many.

    Each signal comes decimated on its own x (min/max picks other samples per signal, and flight-log
    messages have their own times), so 30 signals of ~6,400 points make a table of ~190,000 rows.
    uPlot.join builds that with a Map and generic arrays: ~185 ms per redraw for 30 signals (measured,
    node); here the x values are merged as one sorted Float64Array and each signal is placed with a
    linear walk: ~15-20 ms.

    Same meaning as uPlot.join(tables, tables.map(() => [1])) (NULL_RETAIN): a value of null (a gap in
    the signal) stays null; a row where a signal has no sample is left undefined, which uPlot spans. */
export function joinTables(tables: uPlot.AlignedData[]): uPlot.AlignedData {
  if (tables.length === 1) return tables[0];
  const xsOf = tables.map((t) => t[0] as ArrayLike<number>);
  // one shared x (signals of one file decimated without decimation, or the same table twice)
  const first = xsOf[0];
  if (xsOf.every((x) => x === first || sameValues(x, first)))
    return [first as number[], ...tables.map((t) => t[1] as (number | null)[])] as uPlot.AlignedData;
  let total = 0;
  for (const x of xsOf) total += x.length;
  const all = new Float64Array(total);
  let at = 0;
  for (const x of xsOf) { all.set(x, at); at += x.length; }
  all.sort();
  let u = 0;
  for (let i = 0; i < total; i++) if (i === 0 || all[i] !== all[i - 1]) all[u++] = all[i];
  const xs = Array.from(all.subarray(0, u));
  const out: (number[] | (number | null | undefined)[])[] = [xs];
  for (let k = 0; k < tables.length; k++) {
    const x = xsOf[k], y = tables[k][1] as ArrayLike<number | null>;
    const col: (number | null | undefined)[] = new Array(u);
    let j = 0;
    for (let i = 0; i < x.length; i++) {
      const v = x[i];
      while (j < u && xs[j] < v) j++;
      if (j < u) col[j] = y[i];
    }
    out.push(col);
  }
  return out as uPlot.AlignedData;
}

function sameValues(a: ArrayLike<number>, b: ArrayLike<number>): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}
