// T1: what a trust badge says (26.U6)
import { expect, test } from "vitest";
import { trustNotes } from "./TrustBadge";
import { translate } from "../i18n";

const t = ((k: Parameters<typeof translate>[1], v?: Record<string, string | number>) => translate("en", k, v)) as never;

test("nothing assumed: no badge", () => {
  expect(trustNotes(undefined, t)).toBeNull();
  expect(trustNotes({}, t)).toBeNull();
});
test("missing data is loud, how values were read is quiet; every note is in the tooltip", () => {
  const n = trustNotes({ skipped: 10, interpolated: { method: "linear", sources: [1] } }, t)!;
  expect(n.level).toBe("warn");
  expect(n.short).toBe("skipped missing");
  expect(n.lines).toHaveLength(2);
  const i = trustNotes({ filter: { gaps: 2, resampled: false } }, t)!;
  expect(i.level).toBe("info");
  expect(i.lines[0]).toContain("3 stretches");
});
