/* P7: places - the session's through `commit` (Undo), My places through places.ts (the app's file, no Undo:
   they are not part of the session). */
import { uid, type Place } from "../model";
import { useApp } from "../state";
import { setMyPlaces } from "../../places";

const inSession = (id: string) => (useApp.getState().ws.places ?? []).some((p) => p.id === id);

export const placeActions = {
  /** A new place in the session (default) or in My places; returns its id. */
  addPlace(p: Omit<Place, "id"> & { id?: string }, where: "session" | "mine" = "session"): string {
    const place = { ...p, id: p.id || uid("pl") } as Place;
    if (where === "mine") setMyPlaces([...useApp.getState().myPlaces, place]);
    else useApp.getState().commit((ws) => { ws.places = [...(ws.places ?? []), place]; return ws; });
    return place.id;
  },
  /** Many at once (an imported file) - one Undo. */
  addPlaces(list: Place[], where: "session" | "mine" = "session") {
    const fresh = list.map((p) => ({ ...p, id: uid("pl") }));
    if (where === "mine") setMyPlaces([...useApp.getState().myPlaces, ...fresh]);
    else useApp.getState().commit((ws) => { ws.places = [...(ws.places ?? []), ...fresh]; return ws; });
  },
  updatePlace(id: string, patch: Partial<Place>) {
    const apply = (p: Place): Place => {
      const out = { ...p, ...patch } as Place;
      for (const k of Object.keys(out) as (keyof Place)[]) if (out[k] === undefined) delete out[k];
      return out;
    };
    if (inSession(id)) useApp.getState().commit((ws) => { ws.places = (ws.places ?? []).map((p) => (p.id === id ? apply(p) : p)); return ws; });
    else setMyPlaces(useApp.getState().myPlaces.map((p) => (p.id === id ? apply(p) : p)));
  },
  removePlace(id: string) {
    if (inSession(id)) useApp.getState().commit((ws) => {
      ws.places = (ws.places ?? []).filter((p) => p.id !== id);
      if (!ws.places.length) delete ws.places;
      for (const tb of ws.tabs) for (const pl of tb.plots) if (pl.relPlace === id) delete pl.relPlace;
      return ws;
    });
    else setMyPlaces(useApp.getState().myPlaces.filter((p) => p.id !== id));
  },
  togglePlaceHidden(id: string) {
    const p = [...(useApp.getState().ws.places ?? []), ...useApp.getState().myPlaces].find((x) => x.id === id);
    if (p) placeActions.updatePlace(id, { hidden: p.hidden ? undefined : true });
  },
  /** *Keep in My places* / *Only this session*: the same place moves to the other list. */
  movePlace(id: string, to: "session" | "mine") {
    const st = useApp.getState();
    if (to === "mine" && inSession(id)) {
      const p = st.ws.places!.find((x) => x.id === id)!;
      st.commit((ws) => { ws.places = (ws.places ?? []).filter((x) => x.id !== id); if (!ws.places.length) delete ws.places; return ws; });
      setMyPlaces([...useApp.getState().myPlaces, p]);
    } else if (to === "session" && !inSession(id)) {
      const p = st.myPlaces.find((x) => x.id === id);
      if (!p) return;
      setMyPlaces(st.myPlaces.filter((x) => x.id !== id));
      useApp.getState().commit((ws) => { ws.places = [...(ws.places ?? []), p]; return ws; });
    }
  },
};
