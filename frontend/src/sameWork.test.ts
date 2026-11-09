// T1: sameWork.ts - which signals of a file the work uses (checked on a new file before it is opened)
import { beforeEach, expect, test } from "vitest";
import { useApp } from "./store";
import { reset, run, sig } from "./test/fixtures";
import { usedNames } from "./sameWork";

beforeEach(() => reset([run("a", ["Speed", "RPM", "Lat", "Lon"]), run("b", ["Speed"]),
  { ...run("derived", []), format: "derived", signals: [sig("derived", "twice", { sources: ["a/RPM"] } as never)] }]));

test("plots, an X axis, made signals' sources and map objects - this file's only", () => {
  useApp.getState().commit((ws) => {
    const p = ws.tabs[0].plots[0];
    p.signals = [{ sig: "a/Speed", color: "#000000", width: 1, scale: 1, offset: 0 }, { sig: "b/Speed", color: "#000000", width: 1, scale: 1, offset: 0 },
      { sig: "derived/twice", color: "#000000", width: 1, scale: 1, offset: 0 }];
    p.objects = [{ id: "o", name: "V", kind: "aircraft", color: "#000000", lat: "a/Lat", lon: "a/Lon" } as never];
    return ws;
  });
  expect(usedNames("a").sort()).toEqual(["Lat", "Lon", "RPM", "Speed"]);
  expect(usedNames("b")).toEqual(["Speed"]);
});
