// RE2: the ready-made parts' library and the ready reports - made from what the open files have, in both languages
import { expect, test } from "vitest";
import "./store";                  // the store first (its modules import each other)
import type { ReportScan } from "./api";
import { partCategories, readyInsert, readyReports, readyText } from "./reportReady";
import { rowsToMarkdown, tsvToMarkdown, usedAssets } from "./reportPaste";

const SCAN: ReportScan = {
  files: [{ id: "a", name: "mission_ref.csv" }, { id: "b", name: "mission_gust.csv" }],
  pairs: [{ setpoint: "ctrl.roll_cmd [deg]", measured: "ctrl.roll [deg]", file: "mission_ref.csv" },
    { setpoint: "ctrl.roll_cmd [deg]", measured: "ctrl.roll [deg]", file: "mission_gust.csv" }],
  objects: [{ name: "sim", cls: "truth", pos: "lla" }, { name: "nav", cls: "navigation", pos: "lla" }],
  reference: "sim", base: "mission_ref.csv", states: [{ name: "mission.phase", file: "mission_ref.csv" }], tracks: 2,
};
const ONE: ReportScan = { files: [{ id: "a", name: "bench.csv" }], pairs: [], objects: [], reference: null, base: "bench.csv", states: [], tracks: 0 };

test("the categories: each part one insert, a pair once however many files have it, the choices written only when changed", () => {
  const c = partCategories(SCAN, "en");
  expect(c.map((x) => x.id)).toEqual(["requirements", "tracking", "navigation", "scenario", "compare", "messages", "summary"]);
  expect(c[5].empty).toBeTruthy();                                  // no byte stream: the category says so
  const trk = c[1].parts.map((p) => p.insert);
  expect(trk).toContain("[[tracking]]");
  expect(trk.filter((x) => x.startsWith("[[tracking ctrl.roll"))).toEqual(["[[tracking ctrl.roll | top 1]]"]);
  expect(c[2].parts[0].insert).toBe("[[navigation]]");
  expect(partCategories(SCAN, "en", { reference: "nav" })[2].parts.map((p) => p.insert)).toContain("[[navigation | ref nav, position]]");
  expect(partCategories(SCAN, "en", { base: "mission_gust.csv" })[4].parts[0].insert).toBe("[[differences | base mission_gust.csv]]");
  const none = partCategories(ONE, "he");
  expect(none[1].empty).toBeTruthy();
  expect(c[0].empty).toBeTruthy();                                  // no checks file: no requirements part
  expect(none[4].parts).toEqual([]);
});

test("MSG1: byte streams found - the Messages category, the Link review, the automatic report's section", () => {
  const scan = { ...ONE, streams: [{ name: "tx_byte", file: "link.csv", count: 1829 }, { name: "byte RX", file: "mixed.csv", count: 1738 }] };
  const cat = partCategories(scan, "en").find((x) => x.id === "messages")!;
  expect(cat.empty).toBeUndefined();
  expect(cat.parts.map((p) => p.insert)).toEqual(["[[messages]]", "[[messages | table]]", "[[messages tx_byte]]", "[[messages byte RX]]"]);
  expect(readyReports(scan, "en").map((r) => r.id)).toContain("messages");
  const text = readyText("messages", scan, "en");
  expect(text).toContain("[[messages]]");
  expect(text).not.toContain("[[tracking]]");
  expect(readyText("auto", scan, "en")).toContain("[[messages]]");
  expect(readyText("auto", ONE, "en")).not.toContain("[[messages]]");
});

test("ready reports: only the ones that fit; the automatic one has only parts that found something", () => {
  expect(readyReports(SCAN, "en").map((r) => r.id)).toEqual(["auto", "control", "navigation", "compare"]);
  expect(readyReports(ONE, "en").map((r) => r.id)).toEqual(["auto"]);
  const full = readyText("auto", SCAN, "en");
  for (const p of ["[[summary]]", "[[states]]", "[[trajectory]]", "[[moments]]", "[[tracking]]", "[[navigation]]", "[[differences]]"]) expect(full).toContain(p);
  const bare = readyText("auto", ONE, "he");
  expect(bare).toContain("[[moments]]");
  expect(bare).toContain("[[overview]]");                                  // any recording: its overview
  for (const p of ["[[tracking]]", "[[navigation]]", "[[differences]]", "[[states]]"]) expect(bare).not.toContain(p);
  expect(bare.startsWith("# דוח ניסוי - bench.csv")).toBe(true);
  expect(readyText("compare", SCAN, "en", { base: "mission_gust.csv" })).toContain("[[differences | base mission_gust.csv]]");
});

test("a ready report replaces an untouched report, else goes in without its title", () => {
  expect(readyInsert("# T\n\n[[summary]]\n", true)).toEqual({ replace: true, text: "# T\n\n[[summary]]\n" });
  expect(readyInsert("# T\n\n[[summary]]\n", false)).toEqual({ replace: false, text: "[[summary]]\n" });
});

test("tables pasted from a spreadsheet; pipes escaped; only the pictures the text uses are kept", () => {
  expect(tsvToMarkdown("Run\tMax roll\nA\t12.5\nB\t9|1\n")).toBe("| Run | Max roll |\n|---|---|\n| A | 12.5 |\n| B | 9\\|1 |");
  expect(tsvToMarkdown("just a line\nand another")).toBeNull();
  expect(rowsToMarkdown([["a", "b", "c"], ["1"]])).toBe("| a | b | c |\n|---|---|---|\n| 1 |  |  |");
  const a = { name: "x", mime: "image/png", data: "AAAA", w: 1, h: 1 };
  expect(Object.keys(usedAssets("![x](asset:ab12) text", { ab12: a, cd34: a }))).toEqual(["ab12"]);
});

test("CC15: a checks file with the files - the Requirements category and the Verification report", () => {
  const scan = { ...ONE, checks: 1 };
  const cat = partCategories(scan, "en")[0];
  expect(cat.id).toBe("requirements");
  expect(cat.parts.map((p) => p.insert)).toEqual(["[[requirements]]", "[[requirements | table]]"]);
  expect(readyReports(scan, "en").map((r) => r.id)).toEqual(["auto", "verification"]);
  expect(readyReports(ONE, "en").map((r) => r.id)).not.toContain("verification");
  const text = readyText("verification", scan, "en");
  expect(text.startsWith("# Verification report - bench.csv")).toBe(true);
  expect(text.indexOf("[[requirements]]")).toBeLessThan(text.indexOf("[[overview | table]]"));
  expect(text).toContain("signalviewer-cli check bench.csv");
  expect(readyText("verification", scan, "he")).toContain("# דוח אימות");
});
