import { describe, expect, it } from "vitest";
import { applyRole } from "./messages";
import type { InspectFrame } from "./api";
import type { Structure } from "./store/model";

/* MSG4: a click on a byte in the Messages panel says what it is - the structure changes accordingly. */
const frame: InspectFrame = { t: 0, at: 0, len: 9, id: 0x20, message: "MSG_20", status: "ok", values: [],
  bytes: [0xAA, 0x55, 0x20, 0x04, 0x10, 0x27, 0x01, 0x0D, 0x0A] };
const base = (): Structure => ({ kind: "binary", header: "AA55", length: null, type: null, size: 9, checksum: null,
  messages: [{ id: 0, name: "MSG_20", fields: [{ name: "b4", offset: 4, type: "u8" }] }] });

describe("applyRole", () => {
  it("header, length, footer from the bytes of the shown message", () => {
    expect(applyRole(base(), frame, { kind: "header", upto: 2 }).header).toBe("AA5520");
    const l = applyRole(base(), frame, { kind: "length", at: 3 });
    expect(l.length).toEqual({ offset: 3, add: 5 });
    expect(l.size).toBeNull();
    expect(applyRole(base(), frame, { kind: "footer", from: 7 }).footer).toBe("0D0A");
  });
  it("a type byte: the one message becomes that type", () => {
    const s = applyRole(base(), frame, { kind: "type", at: 2 });
    expect(s.type).toEqual({ offset: 2 });
    expect(s.messages[0].id).toBe(0x20);
  });
  it("a field replaces what it overlaps; not a field removes it", () => {
    const s = applyRole(base(), frame, { kind: "field", at: 4, type: "i16", endian: "le" });
    expect(s.messages[0].fields).toEqual([{ name: "value_4", offset: 4, type: "i16", endian: "le" }]);
    const n = applyRole(s, frame, { kind: "nofield", at: 5 });
    expect(n.messages[0].fields).toEqual([]);
    expect(base().messages[0].fields.length).toBe(1);                // the structure given is not changed
  });
  it("a frame of a type with no message gets one; text parts become fields by place", () => {
    const s: Structure = { ...base(), type: { offset: 2 }, messages: [{ id: 0x10, name: "A", fields: [] }] };
    const r = applyRole(s, { ...frame, message: "" }, { kind: "field", at: 5, type: "u8", endian: "le" });
    expect(r.messages.map((m) => m.name)).toEqual(["A", "MSG_20"]);
    const tx: Structure = { kind: "text", start: "$", sep: ",", messages: [] };
    const tf: InspectFrame = { t: 0, at: 0, id: "GPXYZ", message: "", status: "unknown", values: [], parts: ["GPXYZ", "1.5", "A"] };
    const r2 = applyRole(tx, tf, { kind: "text", index: 1, type: "number" });
    expect(r2.messages).toEqual([{ id: "GPXYZ", name: "GPXYZ", fields: [{ name: "f1", index: 1, type: "number" }] }]);
  });
});
