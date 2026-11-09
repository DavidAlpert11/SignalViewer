/* N6: measuring smoothness - off unless a test or benchmark turns it on (window.__svRenders = {}).
   Each component that may re-render per frame counts its renders here; the benchmark divides by the
   frames it recorded (tools/browser_benchmark.py, group "smooth"). Costs one property read when off. */
type PerfWindow = Window & { __svRenders?: Record<string, number> };

/** Count a render of `name` (call at the top of a component body). */
export function countRender(name: string): void {
  const r = (window as PerfWindow).__svRenders;
  if (r) r[name] = (r[name] ?? 0) + 1;
}
