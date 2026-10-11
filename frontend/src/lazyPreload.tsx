import { lazy, useState, type ComponentType } from "react";

/* Panels and dialogs whose code loads on demand. React reveals a lazily loaded component only after
   a ~300 ms throttle, so the FIRST open of each felt slow although its code arrived in ~10 ms.
   preloadAll() fetches them in the background once the app is idle; from then on each one renders
   directly, without going through Suspense at all. */
type Loader<P> = () => Promise<{ default: ComponentType<P> }>;
const loaders: (() => Promise<unknown>)[] = [];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function lazyPreload<P extends Record<string, any>>(load: Loader<P>): ComponentType<P> {
  let Loaded: ComponentType<P> | null = null;
  let pending: Promise<{ default: ComponentType<P> }> | null = null;
  const get = () => (pending ??= load().then((m) => { Loaded = m.default; return m; }));
  const Lazy = lazy(get);
  loaders.push(get);
  // each mounted instance keeps the component it started with: switching from Lazy to Loaded while
  // open would remount it and lose what the user typed
  return function Preloadable(props: P) {
    const [C] = useState<ComponentType<P>>(() => Loaded ?? Lazy);
    return <C {...props} />;
  };
}

/** Load every registered panel / dialog in the background (call once the app is up). */
export function preloadAll() {
  const run = () => loaders.forEach((f) => { f().catch(() => { /* loads again when opened */ }); });
  const w = window as unknown as { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => void };
  if (w.requestIdleCallback) w.requestIdleCallback(run, { timeout: 3000 });
  else setTimeout(run, 1500);
}
