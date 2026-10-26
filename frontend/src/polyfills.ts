/* Functions newer than the engines the app is built for (vite.config.ts: Chromium 87 and up).
   Offline computers often keep an old Edge WebView2 for years; without these the app - or the
   3D view, whose CesiumJS calls toSorted - would stop with an error there. Each is added only
   when the engine lacks it, so an up-to-date engine runs its own. */
type AnyObj = Record<string, unknown>;

function cloneDeep(v: unknown, seen: Map<unknown, unknown>): unknown {
  if (v === null || typeof v !== "object") return v;
  if (seen.has(v)) return seen.get(v);
  if (v instanceof Date) return new Date(v.getTime());
  if (v instanceof RegExp) return new RegExp(v.source, v.flags);
  if (ArrayBuffer.isView(v)) return (v as unknown as { slice: () => unknown }).slice();
  if (v instanceof Map) {
    const m = new Map(); seen.set(v, m);
    v.forEach((val, key) => m.set(cloneDeep(key, seen), cloneDeep(val, seen)));
    return m;
  }
  if (v instanceof Set) {
    const s = new Set(); seen.set(v, s);
    v.forEach((val) => s.add(cloneDeep(val, seen)));
    return s;
  }
  if (Array.isArray(v)) {
    const a: unknown[] = []; seen.set(v, a);
    v.forEach((x, i) => { a[i] = cloneDeep(x, seen); });
    return a;
  }
  const o: AnyObj = {}; seen.set(v, o);
  for (const k of Object.keys(v as AnyObj)) o[k] = cloneDeep((v as AnyObj)[k], seen);
  return o;
}

const g = globalThis as unknown as AnyObj;
if (typeof g.structuredClone !== "function") {                       // Chromium 98
  g.structuredClone = (v: unknown) => cloneDeep(v, new Map());
}
const AP = Array.prototype as unknown as AnyObj;
if (typeof AP.toSorted !== "function") {                             // Chromium 110 (CesiumJS)
  Object.defineProperty(Array.prototype, "toSorted", { configurable: true, writable: true,
    value: function (this: unknown[], cmp?: (a: unknown, b: unknown) => number) { return this.slice().sort(cmp); } });
}
if (typeof (Object as unknown as AnyObj).hasOwn !== "function") {    // Chromium 93 (CesiumJS)
  Object.defineProperty(Object, "hasOwn", { configurable: true, writable: true,
    value: (o: object, k: PropertyKey) => Object.prototype.hasOwnProperty.call(o, k) });
}
export {};
