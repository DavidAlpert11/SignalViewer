import { useEffect, useState } from "react";
import { api } from "./api";

/**
 * T22: small pictures of signals for the file list. Only rows on screen ask, in one batched
 * request (a short wait collects the rows of one scroll), and the answer is kept per signal and
 * per version (its sample count and change), so scrolling back costs nothing.
 */
export type Spark = { lo: (number | null)[]; hi: (number | null)[] } | null;

const cache = new Map<string, Spark>();
const waiting = new Map<string, Set<(s: Spark) => void>>();
let queue: { id: string; key: string }[] = [];
let timer = 0;

function flush() {
  timer = 0;
  const batch = queue.splice(0, 200);
  if (!batch.length) return;
  api.sparks(batch.map((b) => b.id)).then((r) => {
    for (const b of batch) {
      const s = r.sparks[b.id] ?? null;
      cache.set(b.key, s);
      waiting.get(b.key)?.forEach((f) => f(s));
      waiting.delete(b.key);
    }
  }).catch(() => { for (const b of batch) waiting.delete(b.key); });
  if (queue.length) timer = window.setTimeout(flush, 30);
}

/** The picture of signal `id` at `version` (undefined while it is on its way). */
export function useSpark(id: string, version: string): Spark | undefined {
  const key = `${id}@${version}`;
  const [s, setS] = useState<Spark | undefined>(() => cache.get(key));
  useEffect(() => {
    if (cache.has(key)) { setS(cache.get(key)); return; }
    setS(undefined);
    let live = true;
    const done = (v: Spark) => { if (live) setS(v); };
    if (!waiting.has(key)) { waiting.set(key, new Set()); queue.push({ id, key }); }
    waiting.get(key)!.add(done);
    if (!timer) timer = window.setTimeout(flush, 60);
    return () => { live = false; waiting.get(key)?.delete(done); };
  }, [key, id]);
  if (cache.size > 5000) cache.clear();          // a very long session: start over rather than grow
  return s;
}

/** The band between the slices' minimum and maximum, as an SVG path in a w x h box. */
export function sparkPath(sp: NonNullable<Spark>, w: number, h: number): string {
  const vals = [...sp.lo, ...sp.hi].filter((v): v is number => v !== null);
  let mn = Math.min(...vals), mx = Math.max(...vals);
  if (!(mx > mn)) { mn -= 1; mx += 1; }
  const k = sp.lo.length;
  const x = (i: number) => (k > 1 ? (i / (k - 1)) * w : w / 2);
  const y = (v: number) => h - 1 - ((v - mn) / (mx - mn)) * (h - 2);
  // top edge left to right along the maxima, back along the minima: a filled band (spikes show)
  let d = "", pen = false;
  const top: string[] = [], bot: string[] = [];
  const close = () => { if (top.length) d += `M${top.join("L")}L${bot.reverse().join("L")}Z`; top.length = 0; bot.length = 0; };
  for (let i = 0; i < k; i++) {
    const a = sp.hi[i], b = sp.lo[i];
    if (a === null || b === null) { if (pen) close(); pen = false; continue; }
    top.push(`${x(i).toFixed(1)},${y(a).toFixed(1)}`); bot.push(`${x(i).toFixed(1)},${(y(b) + 0.6).toFixed(1)}`); pen = true;
  }
  close();
  return d;
}
