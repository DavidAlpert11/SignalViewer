// W9: the 3D view's labels declutter by priority - object name > mode > events
import { describe, expect, test } from "vitest";
import { declutter } from "./declutter";

describe("declutter", () => {
  test("the higher priority wins an overlap, whatever the order", () => {
    const ev = { x: 10, y: 10, w: 60, h: 14, prio: 2 };
    const name = { x: 30, y: 12, w: 50, h: 14, prio: 0 };
    expect(declutter([ev, name])).toEqual([false, true]);
  });
  test("mode before events; apart boxes all kept", () => {
    const mode = { x: 0, y: 0, w: 40, h: 14, prio: 1 };
    const event = { x: 20, y: 5, w: 40, h: 14, prio: 2 };
    const far = { x: 300, y: 300, w: 40, h: 14, prio: 2 };
    expect(declutter([event, mode, far])).toEqual([false, true, true]);
  });
  test("off-screen (not finite) is never shown", () => {
    expect(declutter([{ x: NaN, y: 0, w: 1, h: 1, prio: 0 }])).toEqual([false]);
  });
});
