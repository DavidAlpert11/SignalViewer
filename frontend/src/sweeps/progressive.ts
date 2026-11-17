/* Drawing many lines without holding the page (1.29): the work is cut into chunks, drawn a few
   milliseconds per animation frame, and dropped as soon as what it draws changes. The first frame is
   drawn at once (no frame's wait for the first picture). Pure: the clock and the frames are given. */

export interface Pass {
  /** how many items (lines) this pass draws */
  n: number;
  /** before its first chunk (a colour, a width) */
  begin?: () => void;
  /** draw items [from, to) */
  draw: (from: number, to: number) => void;
}

export interface Clock {
  now: () => number;
  frame: (cb: () => void) => number;
  cancel: (h: number) => void;
}

export const browserClock: Clock = {
  now: () => performance.now(),
  frame: (cb) => requestAnimationFrame(cb),
  cancel: (h) => cancelAnimationFrame(h),
};

/** Run the passes in order, `chunk` items at a time, at most `budgetMs` per frame; `onFrame` after
 *  each frame's work (to show it), `onDone` once all is drawn. Returns the cancel. */
export function runProgressive(passes: Pass[], opts: {
  budgetMs?: number; chunk?: number; clock?: Clock; onFrame?: () => void; onDone?: () => void;
  /** after each chunk: make the work really happen now (a canvas records strokes and draws them only when
   *  it is shown - without this the budget measures the recording and the frame that shows it is long) */
  flush?: () => void;
} = {}): () => void {
  const budget = opts.budgetMs ?? 8, chunk = Math.max(1, opts.chunk ?? 2000), clock = opts.clock ?? browserClock;
  let pass = 0, at = 0, begun = -1, handle = 0, stopped = false;
  const step = () => {
    if (stopped) return;
    const t0 = clock.now();
    while (pass < passes.length) {
      const ps = passes[pass];
      if (at >= ps.n) { pass++; at = 0; continue; }
      if (begun !== pass) { ps.begin?.(); begun = pass; }
      const to = Math.min(ps.n, at + chunk);
      ps.draw(at, to);
      opts.flush?.();
      at = to;
      if (clock.now() - t0 >= budget) break;
    }
    opts.onFrame?.();
    if (pass < passes.length) handle = clock.frame(step);
    else { stopped = true; opts.onDone?.(); }
  };
  step();
  return () => { if (!stopped) { stopped = true; clock.cancel(handle); } };
}

/** A fixed shuffle of 0..n-1: drawn in this order, the picture after the first frames already looks like
 *  the whole (rows of a sweep come in grid order - drawn in order, the first frames show one corner). */
export function drawOrder(n: number, seed = 1): Int32Array {
  const o = new Int32Array(n);
  for (let i = 0; i < n; i++) o[i] = i;
  let s = seed >>> 0 || 1;
  for (let i = n - 1; i > 0; i--) {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    const j = s % (i + 1);
    const t = o[i]; o[i] = o[j]; o[j] = t;
  }
  return o;
}
