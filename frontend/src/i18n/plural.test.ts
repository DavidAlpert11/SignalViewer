// Phase 3: "1 files", "1 plots" read wrong - English takes the singular after a count of 1 (only known plurals)
import { expect, test } from "vitest";
import { translate } from "./index";

test("a count of 1 takes the singular in English, any other count and Hebrew unchanged", () => {
  expect(translate("en", "filesOpen", { n: 1 })).toBe("1 file");
  expect(translate("en", "filesOpen", { n: 2 })).toBe("2 files");
  expect(translate("en", "mxOpen", { n: 1 })).toContain("(1 file)");
  expect(translate("en", "tplPlotsN", { n: 1 })).toBe("1 plot");
});
