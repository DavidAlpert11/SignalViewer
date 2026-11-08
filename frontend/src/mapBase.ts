/* O1: which map layer is really drawn. "Automatic" is the offline map the app draws from bundled
   data - nothing leaves the PC unless an online layer is chosen by hand. With "Never use the
   network" (Settings, or SV_OFFLINE=1 for the app) an online layer falls back to the offline map;
   the backend refuses to download in that case too (app/tiles.py). */
import { useApp } from "./store";

export type GeoBase = "auto" | "osm" | "esri" | "light" | "dark" | "satellite" | "topo" | "offline";
export const GEO_BASES: GeoBase[] = ["auto", "offline", "osm", "esri", "light", "dark", "satellite", "topo"];

export const isOnlineBase = (b: GeoBase): boolean => b !== "auto" && b !== "offline";

/** The layer drawn for the chosen one: "offline" or an online source. */
export function effectiveBase(chosen: GeoBase, networkOff: boolean): Exclude<GeoBase, "auto"> {
  if (chosen === "auto" || (networkOff && isOnlineBase(chosen))) return "offline";
  return chosen;
}

/** The layer drawn now (hook): the chosen layer and the network setting together. */
export function useMapBase(): Exclude<GeoBase, "auto"> {
  const chosen = useApp((s) => s.geoBase);
  const off = useApp((s) => s.offlineOnly || s.offlineForced);
  return effectiveBase(chosen, off);
}
