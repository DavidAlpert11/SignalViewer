import { describe, expect, it } from "vitest";
import { drawOrder, runProgressive, type Clock } from "./progressive";

/** a clock where each chunk drawn costs 1 ms and frames run when asked */
function fakeClock() {
  let t = 0;
  const queue: (() => void)[] = [];
  const clock: Clock = { now: () => t, frame: (cb) => queue.push(cb), cancel: (h) => { queue[h - 1] = () => {}; } };
  return { clock, tick: (ms = 1) => { t += ms; }, flush: () => { while (queue.length) queue.shift()!(); }, frames: () => queue.length };
}

describe("drawing a frame at a time (1.29)", () => {
  it("draws every item once, in order, the first frame at once, within the budget per frame", () => {
    const f = fakeClock();
    const drawn: number[] = [], begun: string[] = [];
    let frames = 0, done = 0;
    runProgressive([
      { n: 5, begin: () => begun.push("a"), draw: (a, b) => { for (let i = a; i < b; i++) drawn.push(i); f.tick(); } },
      { n: 3, begin: () => begun.push("b"), draw: (a, b) => { for (let i = a; i < b; i++) drawn.push(100 + i); f.tick(); } },
    ], { chunk: 2, budgetMs: 2, clock: f.clock, onFrame: () => frames++, onDone: () => done++ });
    expect(drawn).toEqual([0, 1, 2, 3]);               // the first frame, before any wait: two chunks of two
    f.flush();
    expect(drawn).toEqual([0, 1, 2, 3, 4, 100, 101, 102]);
    expect(begun).toEqual(["a", "b"]);
    expect(done).toBe(1);
    expect(frames).toBeGreaterThanOrEqual(3);
  });

  it("stops when cancelled (what it draws changed)", () => {
    const f = fakeClock();
    const drawn: number[] = [];
    let done = 0;
    const stop = runProgressive([{ n: 10, draw: (a, b) => { for (let i = a; i < b; i++) drawn.push(i); f.tick(); } }],
      { chunk: 2, budgetMs: 1, clock: f.clock, onDone: () => done++ });
    stop();
    f.flush();
    expect(drawn).toEqual([0, 1]);
    expect(done).toBe(0);
  });

  it("a fixed shuffle: every row once, the same each time", () => {
    const o = drawOrder(1000);
    expect([...o].sort((a, b) => a - b)).toEqual([...Array(1000).keys()]);
    expect([...drawOrder(1000)]).toEqual([...o]);
    expect([...o.slice(0, 10)]).not.toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  });
});
