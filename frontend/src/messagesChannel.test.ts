import { describe, expect, it } from "vitest";
import { linkCandidates } from "./messages";

/* CH1: a file's TX-like and RX-like streams are offered as one channel - only when it is clear which is which. */
const row = (id: string, extra: Record<string, unknown> = {}) => ({ key: id, rid: id.split("/")[0], ids: [id], params: {}, ...extra });

describe("linkCandidates", () => {
  it("one TX-like and one RX-like stream of a file: one channel", () => {
    expect(linkCandidates([row("a/tx_byte"), row("a/rx_byte")], [])).toEqual([{ rid: "a", tx: "a/tx_byte", rx: "a/rx_byte" }]);
    expect(linkCandidates([row("a/uplink"), row("a/downlink"), row("a/sensor_byte")], [])).toEqual([{ rid: "a", tx: "a/uplink", rx: "a/downlink" }]);
  });
  it("not across files, not when held by a definition, not when ambiguous, not a direction-column split", () => {
    expect(linkCandidates([row("a/tx_byte"), row("b/rx_byte")], [])).toEqual([]);
    expect(linkCandidates([row("a/tx_byte"), row("a/rx_byte")], [{ id: "m", sources: ["a/tx_byte"], carries: "tx" }])).toEqual([]);
    expect(linkCandidates([row("a/tx1"), row("a/tx2"), row("a/rx")], [])).toEqual([]);
    expect(linkCandidates([row("a/byte", { params: { dir: 0 } }), row("a/rx_byte")], [])).toEqual([]);
    expect(linkCandidates([row("a/tx_byte", { error: "x" }), row("a/rx_byte")], [])).toEqual([]);
  });
});
