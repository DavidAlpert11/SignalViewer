import { describe, expect, test } from "vitest";
import { byPosition, positionNote } from "./objectAdd";

/* P2: an object with no position (0, 0 for the whole file: ArduPilot's EAHR) is no object */
describe("byPosition / positionNote", () => {
  const c = (key: string) => ({ key, name: key });
  test("none left out, few kept with a note, unknown kept", () => {
    const counts = { EAHR: { valid: 0, total: 550 }, GPS: { valid: 5, total: 550 }, POS: { valid: 550, total: 550 } };
    const r = byPosition([c("EAHR"), c("GPS"), c("POS"), c("NED")], counts);
    expect(r.none.map((x) => x.key)).toEqual(["EAHR"]);
    expect(r.keep.map((x) => x.key)).toEqual(["GPS", "POS", "NED"]);
    expect(r.few.map((x) => x.key)).toEqual(["GPS"]);
    expect(positionNote(r.none, r.few, "en")).toBe("EAHR left out – it has no position in this file (always 0, 0). Few positions in this file (under 2 %): GPS.");
    expect(positionNote(r.none, r.few, "he")).toContain("EAHR");
  });
  test("nothing to say", () => {
    expect(positionNote([], [], "en")).toBe("");
    expect(byPosition([c("A")], {}).keep).toHaveLength(1);
  });
});
