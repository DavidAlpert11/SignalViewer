import { describe, expect, it } from "vitest";
import { nameValues } from "./investigation";

// review C11: a derived signal's parameters in a report read as a person writes them, not as JSON
describe("nameValues", () => {
  it("writes name=value pairs, lists with spaces, and leaves out what is empty", () => {
    expect(nameValues({ window: 5, kind: "mean" })).toBe("window=5, kind=mean");
    expect(nameValues({ freqs: [1, 2.5], skip: undefined, note: "", off: null })).toBe("freqs=1 2.5");
    expect(nameValues({ nested: { a: 1 } })).toBe('nested={"a":1}');
  });
});
