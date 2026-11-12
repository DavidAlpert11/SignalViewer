import { beforeEach, describe, expect, test, vi } from "vitest";
import { actions, initialWorkspace, useApp, type Place } from "./store";
import { allPlaces, nearestPlace, placesBounds, shownPlaces } from "./places";
import { currentState, legacyUnitNames } from "./files";

/* P7: places - the session's travel with it (Undo), My places are the app's (no Undo), an old session has none */
vi.mock("./api", async (orig) => {
  const m = await orig<typeof import("./api")>();
  return { ...m, api: { ...m.api, putMyPlaces: vi.fn(async (places: Place[]) => ({ places })) } };
});

const pt = (name: string, lat: number, lon: number, extra: Partial<Place> = {}): Omit<Place, "id"> => ({ name, kind: "point", lat, lon, ...extra });

beforeEach(() => { useApp.setState({ ws: initialWorkspace(), past: [], future: [], myPlaces: [] }); });

describe("places in a session", () => {
  test("a place of the session survives save / load, with Undo", () => {
    actions.addPlace(pt("Megiddo", 32.5973, 35.2286, { icon: "airfield", alt: 60 }));
    expect(useApp.getState().past).toHaveLength(1);
    const saved = JSON.parse(JSON.stringify(currentState()));
    useApp.setState({ ws: initialWorkspace() });
    const back = legacyUnitNames(saved, []);
    useApp.setState({ ws: back.ws });
    expect(allPlaces().map((p) => [p.name, p.icon, p.alt, p.mine])).toEqual([["Megiddo", "airfield", 60, false]]);
    useApp.getState().undo();
  });
  test("an old session has none, and nothing breaks", () => {
    const old = JSON.parse('{"tabs":[{"id":"t","name":"","rows":1,"cols":1,"plots":[],"active":0,"linkX":true}],"activeTab":"t"}');
    useApp.setState({ ws: old });
    expect(allPlaces()).toEqual([]);
    expect(shownPlaces()).toEqual([]);
  });
  test("My places: not in the session, no Undo; moving one keeps it once", () => {
    const id = actions.addPlace(pt("Home", 32.1, 34.8), "mine");
    expect(useApp.getState().past).toHaveLength(0);
    expect(currentState().ws.places).toBeUndefined();
    actions.movePlace(id, "session");
    expect(useApp.getState().myPlaces).toHaveLength(0);
    expect(useApp.getState().ws.places?.map((p) => p.id)).toEqual([id]);
    actions.movePlace(id, "mine");
    expect(allPlaces().map((p) => [p.id, p.mine])).toEqual([[id, true]]);
  });
  test("hidden places and saved views are not drawn", () => {
    const a = actions.addPlace(pt("A", 1, 1));
    actions.addPlace({ kind: "view", name: "V", lat: 1, lon: 1, view: { heading: 0, pitch: -30, range: 0 } });
    actions.togglePlaceHidden(a);
    expect(shownPlaces()).toEqual([]);
    actions.togglePlaceHidden(a);
    expect(shownPlaces().map((p) => p.name)).toEqual(["A"]);
  });
  test("removing a place clears a relation box that compared with it", () => {
    const id = actions.addPlace(pt("A", 1, 1));
    useApp.getState().commit((ws) => { ws.tabs[0].plots[0].relPlace = id; return ws; });
    actions.removePlace(id);
    expect(useApp.getState().ws.tabs[0].plots[0].relPlace).toBeUndefined();
    expect(useApp.getState().ws.places).toBeUndefined();
  });
});

describe("nearestPlace / placesBounds", () => {
  const P = (n: string, lat: number, lon: number, extra: Partial<Place> = {}): Place => ({ id: n, ...pt(n, lat, lon), ...extra });
  test("the nearest within 50 km; a line by its nearest vertex", () => {
    const list = [P("far", 33.5, 35.3), P("near", 32.70, 35.30), P("rwy", 0, 0, { kind: "line", points: [[32.60, 35.20], [32.6, 35.25]] })];
    const n = nearestPlace(32.601, 35.25, list)!;
    expect(n.place.name).toBe("rwy");
    expect(n.d).toBeCloseTo(111, -1);
    expect(nearestPlace(40, 40, list)).toBeNull();
  });
  test("bounds over points and vertices", () => {
    expect(placesBounds([P("a", 1, 2), P("b", 0, 0, { kind: "area", points: [[3, 4], [-1, 5]] })])).toEqual([-1, 2, 3, 5]);
    expect(placesBounds([])).toBeNull();
  });
});
