import { describe, expect, test } from "vitest";
import { shownObjects } from "./mapObjects";
import type { MapObject } from "./store";

/* P6: a hidden object is not drawn and not fitted; it keeps its place in the list */
const o = (id: string, hidden?: boolean): MapObject => ({ id, name: id, kind: "aircraft", color: "#000000", lat: "r/lat", lon: "r/lon", ...(hidden ? { hidden } : {}) });

describe("shownObjects", () => {
  test("the hidden ones are left out, the order kept", () => {
    expect(shownObjects({ objects: [o("a"), o("b", true), o("c")] }).map((x) => x.id)).toEqual(["a", "c"]);
  });
  test("an old session (no `hidden` anywhere) shows every object", () => {
    const old = JSON.parse('{"objects":[{"id":"a","name":"POS","kind":"aircraft","color":"#000","lat":"r/x","lon":"r/y"}]}');
    expect(shownObjects(old)).toHaveLength(1);
    expect(shownObjects({})).toEqual([]);
  });
});
