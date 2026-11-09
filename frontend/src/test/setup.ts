// T1: the little of a browser the store reads when it is created (no DOM library: the tests are of
// logic; the e2e tests drive the real page)
const g = globalThis as Record<string, unknown>;
const mem = new Map<string, string>();
g.window ??= globalThis;
g.localStorage ??= {
  getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => { mem.set(k, String(v)); },
  removeItem: (k: string) => { mem.delete(k); }, clear: () => mem.clear(), key: (i: number) => [...mem.keys()][i] ?? null,
  get length() { return mem.size; },
};
(g.window as Record<string, unknown>).matchMedia ??= () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
g.document ??= { documentElement: { style: {}, dataset: {} }, body: {}, addEventListener() {}, removeEventListener() {} };
g.getComputedStyle ??= () => ({ getPropertyValue: () => "", fontFamily: "sans-serif" });
