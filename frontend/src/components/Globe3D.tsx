import { declutter, type LabelBox } from "../declutter";
import { countRender } from "../perf";
import { runsDataKey } from "../values";
import { useEffect, useMemo, useRef, useState } from "react";
import "cesium/Build/Cesium/Widgets/CesiumWidget/CesiumWidget.css";
import { api } from "../api";
import { actions, activeTab, pickPath, shownSpan, useApp, type MapObject, type Plot } from "../store";
import { useMapBase } from "../mapBase";
import { globeImage, mapCameraNow, mapFly, mapObjectAt, type FlyTarget } from "../globeBridge";
import { nearestPlace, placeIconSvg, placesBounds, shownPlaces } from "../places";
import { fmtCoord } from "../mapDefaults";
import { fmtNum, useT } from "../i18n";
import { indexSpan } from "./chartUtil";
import { pairOf, relation, type At } from "../relation";
import RelationPanel from "./RelationPanel";
import MapBar from "./MapBar";
import { altAt, angleUnitOf, bearing, colorRuns, derivedAttitude, fmtDistance, groundDistance, objectAt, trackColors, trackKey, trackRequest, trackTime, visualOrder, type ObjTrack, type TrackColors, shownObjects, mapCamera } from "../mapObjects";
import { labelsOf, stateColor } from "../values";
import TrackKeys from "./TrackKeys";
import { hasWebGL } from "../webgl";
import { markNoPosition } from "../noPosition";
import FlightDisplay from "./FlightDisplay";
import MiniMap from "./MiniMap";
import { errorAlong, errorColor } from "../relation";

/* The 3D view: the earth with the app's own terrain (bundled elevation) and map tiles (offline or
   online, as the map plot), the plot's objects as 3D models at the timeline's time - position,
   heading, pitch and roll - with their tracks and names, and a camera that can follow one.
   CesiumJS is loaded only when a 3D plot is shown, and nothing is fetched from the internet: no
   Cesium ion, its workers and data files come with the app (/cesium/). */

type C = typeof import("cesium");
let cesiumP: Promise<C> | null = null;
const loadCesium = () => (cesiumP ??= (async () => {
  (window as unknown as { CESIUM_BASE_URL: string }).CESIUM_BASE_URL = "/cesium/";
  const m = await import("cesium");
  m.Ion.defaultAccessToken = "";
  return m;
})());

/** WebGL drawn by the processor (no graphics acceleration: virtual machines, remote desktop, blocked
 *  drivers). There every full-screen pass is expensive, so the 3D view uses lighter settings - one
 *  sample per pixel instead of 4 (3x the frame rate measured) and less terrain detail. */
function softwareWebGL(): boolean {
  try {
    const gl = document.createElement("canvas").getContext("webgl");
    if (!gl) return false;
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    const name = String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return /swiftshader|llvmpipe|softpipe|basic render|software|gdi generic/i.test(name);
  } catch { return false; }
}

const TILE_MAXZ: Record<string, number> = { osm: 19, esri: 19, light: 16, dark: 16, satellite: 19, satroads: 19, topo: 17 };
const TRACK_POINTS = 3000;                      // drawn track: at most this many points per object
type Track3 = ObjTrack & { alt: Float32Array | null; pitch: Float32Array | null; roll: Float32Array | null; ground: Float32Array | null };

/** Height above sea level of an object at sample i (its altitude signal, by its reference; without
 *  one, on the ground / the sea). */
function heightAt(o: MapObject, tr: Track3, i: number): number {
  const g = tr.ground ? tr.ground[i] : 0;
  const ground = Number.isFinite(g) ? g : 0;
  if (!tr.alt) return ground + (o.kind === "ship" ? 0 : o.kind === "vehicle" ? 0.5 : 2);
  const a = tr.alt[i];
  if (!Number.isFinite(a)) return NaN;
  if (o.altRef === "agl") return ground + a;
  if (o.altRef === "home") {
    let i0 = 0;
    while (i0 < tr.alt.length && !Number.isFinite(tr.alt[i0])) i0++;
    const g0 = tr.ground && Number.isFinite(tr.ground[i0]) ? tr.ground[i0] : 0;
    return g0 + a;
  }
  return a;
}

interface Props { plot: Plot; index: number; onLoading: (b: boolean) => void; emptyText: string; onFlat?: (reason: string) => void }

/** An object's values at the time (for the data box and the relations). */
interface ObjState { id: string; name: string; color: string; pos: import("cesium").Cartesian3; lat: number; lon: number; alt: number;
  agl: number | null; hdg: number | null; pitch: number | null; roll: number | null; gs: number | null; vs: number | null }
interface Readout { primary: ObjState; rel: { name: string; color: string; horiz: number; dz: number; slant: number; brg: number;
  closure: number | null; aspect: number | null; side: "L" | "R" | null }[] }

/** Ground speed and climb rate (m/s) over about a second around t. */
function ratesAt(o: MapObject, tr: Track3, t: number): { gs: number | null; vs: number | null } {
  const n = tr.t.length;
  const at = (x: number) => { let lo = 0, hi = n - 1; while (hi - lo > 1) { const k = (lo + hi) >> 1; if (tr.t[k] <= x) lo = k; else hi = k; } return lo; };
  let i0 = at(t - 0.5), i1 = Math.min(n - 1, at(t + 0.5) + 1);
  if (i1 <= i0) { i0 = Math.max(0, i0 - 1); i1 = Math.min(n - 1, i0 + 1); }
  const dt = tr.t[i1] - tr.t[i0];
  if (!(dt > 0)) return { gs: null, vs: null };
  const d = groundDistance(tr.lat[i0], tr.lon[i0], tr.lat[i1], tr.lon[i1]);
  const dh = tr.alt ? heightAt(o, tr, i1) - heightAt(o, tr, i0) : NaN;
  return { gs: Number.isFinite(d) ? d / dt : null, vs: Number.isFinite(dh) ? dh / dt : null };
}

const FLY_MS = 1200;                            // P9: every camera change flies (~1.2 s, eased)
const reducedMotion = () => { try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; } };

export default function Globe3D({ plot, onLoading, emptyText, onFlat }: Props) {
  countRender("Globe3D");
  const t = useT();
  const lang = useApp((s) => s.lang);
  const theme = useApp((s) => s.theme);
  const base = useMapBase();
  // U6: the time under the pointer over a time plot of this tab - a faint point for each object there
  const pointerT = useApp((s) => (s.pointer && activeTab(s.ws).plots.some((p) => p.id === s.pointer!.plotId) ? s.pointer.t : null));
  const pointerRef = useRef<number | null>(null);
  pointerRef.current = pointerT;
  const playMode = useApp((s) => s.playMode);
  const windowSec = useApp((s) => s.windowSec);
  const dataVersion = useApp((s) => s.dataVersion);
  const logs = useApp((s) => s.logs);
  const runsKey = useApp((s) => runsDataKey(s.runs));
  const hostRef = useRef<HTMLDivElement>(null);
  const creditRef = useRef<HTMLDivElement>(null);
  const [cz, setCz] = useState<C | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [lightMode, setLightMode] = useState(false);
  const widgetRef = useRef<import("cesium").CesiumWidget | null>(null);
  const terrainV = useRef(0);
  // P4: the mouse's position, as the 2D map's readout had it - lat / lon (decimals by the camera's height),
  // the ground there, and distance / bearing from the reference
  const refState = useRef<{ name: string; lat: number; lon: number } | null>(null);
  const [mouseAt, setMouseAt] = useState<{ lat: number; lon: number; ground: number | null; prec: number; from: { name: string; d: number; brg: number } | null;
    place: { name: string; d: number } | null } | null>(null);                                    // P5: the terrain version the tiles were asked with
  const terrainMake = useRef<((v: number) => import("cesium").CustomHeightmapTerrainProvider) | null>(null);
  const offline = useApp((s) => s.offlineOnly || s.offlineForced);   // no fetching: nothing finer can arrive
  // P6: `objects` are the ones drawn (and fitted); `allObjs` every one, for lookups (a borrowed attitude)
  const allObjs: MapObject[] = useMemo(() => plot.objects ?? [], [plot.objects]);
  const objects: MapObject[] = useMemo(() => shownObjects(plot), [plot.objects]);   // eslint-disable-line react-hooks/exhaustive-deps
  const objKey = objects.map((o) => trackKey(o, allObjs)).join("|");
  const tw = useApp((s) => s.mapPrefs.trackWidth);          // P8: the track's width
  const mapNames = useApp((s) => s.mapPrefs.names);
  useApp((s) => s.mapPrefs.coords);                         // the readout re-renders with it
  useApp((s) => s.mapPrefs.units);
  // P7: the places drawn on this Map (the session's and My places, shown ones)
  useApp((s) => s.ws.places);
  useApp((s) => s.myPlaces);
  const places = shownPlaces();
  const placesKey = JSON.stringify(places.map((p) => [p.id, p.kind, p.lat, p.lon, p.alt, p.icon, p.color, p.name, p.points]));
  const placesRef = useRef(places);
  placesRef.current = places;
  /* what the models, lines and labels are built from: they are rebuilt only when this changes - not
     for every change of the plot (time of its own, camera, primary object...), which gives a new
     objects array each time and made the models vanish while they loaded again */
  const objLook = objects.map((o) => [o.id, o.kind, o.color, o.name, o.size, o.trail, o.altRef, angleUnitOf(o, allObjs), o.track, derivedAttitude(o, allObjs)].join(":")).join("|");
  const [tracks, setTracks] = useState<Record<string, Track3>>({});
  /* per object, built once (when the objects or their data change) and only moved as time passes:
     rebuilding lines, colours (materials) and labels every frame held playback below 1 fps */
  interface Drawn { idx: number[]; pos: import("cesium").Cartesian3[]; full: import("cesium").Polyline | null; part: import("cesium").Polyline | null;
    fullMat: import("cesium").Material | null; label: import("cesium").Label | null;
    recent?: import("cesium").Polyline | null; drop?: import("cesium").Polyline | null; disc?: import("cesium").PointPrimitive | null }
  // two line collections: the whole tracks (only rebuilt with the data) and the parts shown (change as time passes)
  const scene3 = useRef<{ models: Map<string, import("cesium").Model>; lines: import("cesium").PolylineCollection | null; parts: import("cesium").PolylineCollection | null;
    labels: import("cesium").LabelCollection | null; links: import("cesium").PolylineCollection | null; linkLabels: import("cesium").LabelCollection | null;
    events: import("cesium").PointPrimitiveCollection | null; eventLabels: import("cesium").LabelCollection | null;
    measure: import("cesium").PolylineCollection | null; measurePts: import("cesium").PointPrimitiveCollection | null;
    ghosts: import("cesium").PointPrimitiveCollection | null;      // U6: each object at the time under the pointer
    drops: import("cesium").PolylineCollection | null; discs: import("cesium").PointPrimitiveCollection | null; recent: import("cesium").PolylineCollection | null;   // P9
    rings: import("cesium").PointPrimitiveCollection | null;       // N7: the primary and the secondary marked
    drawn: Map<string, Drawn>; fitted: boolean }>({ models: new Map(), lines: null, parts: null, labels: null, links: null, linkLabels: null,
      events: null, eventLabels: null, measure: null, measurePts: null, ghosts: null, rings: null, drops: null, discs: null, recent: null, drawn: new Map(), fitted: false });
  /* the dashed line material of each colour, made once (a new material per frame is costly) */
  const linkMats = useRef(new Map<string, import("cesium").Material>());
  const linkMat = (c: import("cesium").Color) => {
    const k = c.toCssColorString();
    let m = linkMats.current.get(k);
    if (!m && cz) { m = cz.Material.fromType("PolylineDash", { color: c, dashLength: 14 }); linkMats.current.set(k, m); }
    return m!;
  };
  const [readout, setReadout] = useState<Readout | null>(null);
  /* measuring a distance on the ground: on / off, and the points clicked */
  const [measuring, setMeasuring] = useState(false);
  const measuringRef = useRef(false);
  measuringRef.current = measuring;
  const [measurePts, setMeasurePts] = useState<import("cesium").Cartesian3[]>([]);
  /* its own time: shown and played here (every frame), written to the plot only when it settles
     (pause, end of a drag, detaching) - not into the undo history at 60 per second */
  const detached = plot.ownTime !== null && plot.ownTime !== undefined;
  const [ownT, setOwnT] = useState<number | null>(detached ? plot.ownTime! : null);
  const ownRef = useRef<number | null>(ownT);
  ownRef.current = detached ? ownT : null;
  const ownTRef = useRef(ownT);
  ownTRef.current = ownT;
  const [ownPlaying, setOwnPlaying] = useState(false);
  const [ownSpeed, setOwnSpeed] = useState(1);
  useEffect(() => { if (!detached) { setOwnT(null); setOwnPlaying(false); } else if (ownT === null) setOwnT(plot.ownTime!); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [detached]);

  /* ------------------------------------------------------------- the globe */
  useEffect(() => {
    let alive = true;
    const mats = linkMats.current;                     // (the same map for the whole life of the view)
    if (!hasWebGL()) {                                  // no point loading CesiumJS: the simplified view instead
      setFailed("WebGL is not available in this browser.");
      return () => { alive = false; };
    }
    onLoading(true);
    loadCesium().then((Cz) => {
      if (!alive || !hostRef.current) return;
      const light = softwareWebGL();
      setLightMode(light);
      try {
        // P5: the tiles' URL carries the terrain version - when finer heights arrive (fetched in the
        // background) the provider is made again and the browser's cache does not keep the coarse tile
        const makeTerrain = (v: number) => new Cz.CustomHeightmapTerrainProvider({
          width: 65, height: 65, tilingScheme: new Cz.GeographicTilingScheme(),
          callback: (x: number, y: number, level: number) => fetch(`/api/terrain/${level}/${x}/${y}?v=${v}`)
            .then((r) => (r.ok ? r.arrayBuffer() : null)).then((b) => (b ? new Float32Array(b) : new Float32Array(65 * 65))),
        });
        terrainMake.current = makeTerrain;
        const terrain = makeTerrain(terrainV.current);
        const w = new Cz.CesiumWidget(hostRef.current, {
          baseLayer: false, terrainProvider: terrain, skyBox: false, skyAtmosphere: false, scene3DOnly: true,
          requestRenderMode: true, maximumRenderTimeChange: Infinity, creditContainer: creditRef.current ?? undefined,
          useBrowserRecommendedResolution: true, shadows: false,
          // the faint whole track is the only see-through thing: no order-independent translucency
          // (its shader variants were rebuilt every frame while the shown part of a track changed)
          orderIndependentTranslucency: false,
          msaaSamples: light ? 1 : 4,
        });
        if (light) w.scene.globe.maximumScreenSpaceError = 4;
        else {
          // P9: sky, sunlight and shadows. The viewer was made without the sky atmosphere (with the sun and the
          // moon, whose textures are not shipped, and to keep software rendering light); the atmosphere is a
          // shader - no files - so it is on outside the light mode, with lighting from the sun of the scene's
          // clock and soft shadows of the models on the ground
          w.scene.skyAtmosphere = new Cz.SkyAtmosphere();
          w.scene.globe.enableLighting = true;
          w.scene.globe.dynamicAtmosphereLighting = true;
          w.scene.shadowMap.enabled = false;              // on while the camera is near an object (update)
          w.scene.shadowMap.softShadows = true;
          w.scene.shadowMap.size = 2048;
          w.scene.shadowMap.maximumDistance = 20000;
          w.scene.globe.shadows = Cz.ShadowMode.RECEIVE_ONLY;
        }
        if (w.scene.sun) w.scene.sun.show = false;          // (their textures are not shipped)
        if (w.scene.moon) w.scene.moon.show = false;
        w.scene.globe.depthTestAgainstTerrain = true;
        w.scene.globe.showGroundAtmosphere = !light;
        w.scene.fog.enabled = !light;
        widgetRef.current = w;
        const S0 = scene3.current;
        S0.measure = w.scene.primitives.add(new Cz.PolylineCollection());
        S0.measurePts = w.scene.primitives.add(new Cz.PointPrimitiveCollection());
        // measuring: two clicks on the ground (a third starts again)
        const h = new Cz.ScreenSpaceEventHandler(w.scene.canvas);
        // N7: not measuring - a click on an object makes it the primary, with Shift the secondary
        const pickAt = (e: { position: import("cesium").Cartesian2 }, second: boolean) => {
          const got = w.scene.pick(e.position) as { id?: unknown; primitive?: { id?: unknown } } | undefined;
          const id = typeof got?.id === "string" ? got.id : typeof got?.primitive?.id === "string" ? got.primitive.id : null;
          if (id) pickRef.current(id.startsWith("ring-") ? id.slice(5) : id, second);
          rootFocus.current();                              // its keys (Q / X) work after a click
        };
        h.setInputAction((e: { position: import("cesium").Cartesian2 }) => pickAt(e, true), Cz.ScreenSpaceEventType.LEFT_CLICK, Cz.KeyboardEventModifier.SHIFT);
        h.setInputAction((e: { position: import("cesium").Cartesian2 }) => {
          if (!measuringRef.current) { pickAt(e, false); return; }
          const ray = w.camera.getPickRay(e.position);
          const p = (ray && w.scene.globe.pick(ray, w.scene)) || w.camera.pickEllipsoid(e.position);
          if (!p) return;
          setMeasurePts((cur) => (cur.length >= 2 ? [p] : [...cur, p]));
        }, Cz.ScreenSpaceEventType.LEFT_CLICK);
        // for the tests, next to window.__sv (the app's state)
        (window as unknown as { __svGlobe?: unknown }).__svGlobe = { widget: w, Cesium: Cz };
        setCz(Cz);
      } catch (e) {
        setFailed(String((e as Error).message || e));
      } finally { onLoading(false); }
    }).catch((e) => { if (alive) { setFailed(String((e as Error).message || e)); onLoading(false); } });
    return () => {
      alive = false;
      const w = widgetRef.current;
      widgetRef.current = null;
      scene3.current = { models: new Map(), lines: null, parts: null, labels: null, links: null, linkLabels: null,
        events: null, eventLabels: null, measure: null, measurePts: null, ghosts: null, rings: null, drops: null, discs: null, recent: null, drawn: new Map(), fitted: false };
      mats.clear();
      if (w && !w.isDestroyed()) w.destroy();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* map tiles on the ground: the offline map always underneath (it fills in where online tiles fail) */
  useEffect(() => {
    const w = widgetRef.current;
    if (!cz || !w) return;
    const dark = theme === "dark";
    w.imageryLayers.removeAll();
    w.scene.backgroundColor = cz.Color.fromCssColorString(dark ? "#0e1620" : "#cfdbe6");
    w.scene.globe.baseColor = cz.Color.fromCssColorString(dark ? "#1f3346" : "#aacbe6");
    const merc = new cz.WebMercatorTilingScheme();
    const off = dark ? "offline_topo_dark" : "offline_topo";
    w.imageryLayers.addImageryProvider(new cz.UrlTemplateImageryProvider({ url: `/api/tiles/${off}/{z}/{x}/{y}`, maximumLevel: 14, tilingScheme: merc,
      credit: "Natural Earth · Terrain Tiles (Mapzen: SRTM, GMTED2010, ETOPO1) · © OpenStreetMap contributors" }));
    const online = base;                                        // O1: "offline" unless an online layer is chosen
    if (online !== "offline" && TILE_MAXZ[online]) {
      w.imageryLayers.addImageryProvider(new cz.UrlTemplateImageryProvider({ url: `/api/tiles/${online}/{z}/{x}/{y}`, maximumLevel: TILE_MAXZ[online], tilingScheme: merc }));
    }
    w.scene.requestRender();
  }, [cz, base, theme]);

  /* P5: finer ground arrived (terrarium fetched in the background): ask the terrain again */
  useEffect(() => {
    if (!cz || offline) return;
    const h = window.setInterval(() => {
      void fetch("/api/terrain/version").then((r) => (r.ok ? r.json() : null)).then((d: { version: number } | null) => {
        const w = widgetRef.current;
        if (!d || d.version === terrainV.current || !w || !terrainMake.current) return;
        terrainV.current = d.version;
        w.scene.terrainProvider = terrainMake.current(d.version);
        w.scene.requestRender();
      }).catch(() => {});
    }, 4000);
    return () => window.clearInterval(h);
  }, [cz, offline]);

  /* ------------------------------------------------------------- objects */
  useEffect(() => {
    if (failed) return;                                 // the simplified view (no WebGL) fetches its own
    let cancelled = false;
    (async () => {
      const out: Record<string, Track3> = {};
      const empty: string[] = [];
      for (const o of shownObjects(plot)) {
        try {
          const r = await api.objectTrack(trackRequest(o, plot.objects ?? []));
          if (r.valid === 0) { empty.push(o.id); continue; }           // P2: no position - drawn as nothing, not in Fit
          out[o.id] = { t: r.t, lat: r.lat, lon: r.lon, yaw: r.yaw, course: r.course, units: r.units, alt: r.alt, pitch: r.pitch, roll: r.roll, ground: r.ground, color: r.color };
        } catch { /* a signal no longer open */ }
      }
      if (!cancelled) { setTracks(out); markNoPosition(shownObjects(plot).map((o) => o.id), empty); }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [objKey, dataVersion, runsKey, failed]);

  /* a track coloured by a mode or a value (as on the map) */
  const allRuns = useApp((s) => s.runs);
  const objColors = useMemo(() => {
    const out: Record<string, TrackColors> = {};
    for (const o of objects) {
      const tr = tracks[o.id];
      if (!tr?.color || !o.trackColor || o.trackColor === "object" || !o.colorSig) continue;
      const c = trackColors(o.trackColor, tr.color, labelsOf(allRuns, o.colorSig) ?? null, (x) => fmtNum(x, lang, 4), (x) => stateColor(x, theme));
      if (c) out[o.id] = c;
    }
    return out;
  }, [objects, tracks, allRuns, lang, theme]);

  /* models (one per object; rebuilt when the objects change) */
  useEffect(() => {
    const w = widgetRef.current;
    if (!cz || !w) return;
    const S = scene3.current;
    for (const m of S.models.values()) w.scene.primitives.remove(m);
    S.models.clear();
    if (S.lines) w.scene.primitives.remove(S.lines);
    if (S.parts) w.scene.primitives.remove(S.parts);
    if (S.labels) w.scene.primitives.remove(S.labels);
    S.lines = w.scene.primitives.add(new cz.PolylineCollection());
    S.parts = w.scene.primitives.add(new cz.PolylineCollection());
    if (S.links) w.scene.primitives.remove(S.links);
    if (S.linkLabels) w.scene.primitives.remove(S.linkLabels);
    S.links = w.scene.primitives.add(new cz.PolylineCollection());
    S.linkLabels = w.scene.primitives.add(new cz.LabelCollection());
    S.labels = w.scene.primitives.add(new cz.LabelCollection());
    // W9: the log's event labels yield where they would overlap - an object's name first, then a mode, then the
    // events (declutter.ts), checked a few times a second after a frame, not every frame
    let lastDeclutter = 0;
    w.scene.postRender.addEventListener(() => {
      const now = performance.now();
      const G = scene3.current;
      if (now - lastDeclutter < 150 || !G.eventLabels || !G.eventLabels.length) return;
      lastDeclutter = now;
      const labels: import("cesium").Label[] = [];
      const boxes: LabelBox[] = [];
      const box = (l: import("cesium").Label, prio: number) => {
        const p = cz.SceneTransforms.worldToWindowCoordinates(w.scene, l.position);
        const wpx = l.text.length * 6.4 + 8, hpx = 15;
        boxes.push({ x: p ? p.x + l.pixelOffset.x : NaN, y: p ? p.y + l.pixelOffset.y - hpx / 2 : NaN, w: wpx, h: hpx, prio });
      };
      for (const d of G.drawn.values()) { const l = (d as { label?: import("cesium").Label }).label; if (l?.show) box(l, 0); }
      const n0 = boxes.length;
      for (let i = 0; i < G.eventLabels.length; i++) { const l = G.eventLabels.get(i); labels.push(l); box(l, (l as unknown as { svPrio?: number }).svPrio ?? 2); }
      const keep = declutter(boxes);
      let changed = false;
      labels.forEach((l, i) => { const v = keep[n0 + i]; if (l.show !== v) { l.show = v; changed = true; } });
      if (changed) w.scene.requestRender();
    });
    if (S.ghosts) w.scene.primitives.remove(S.ghosts);
    S.ghosts = w.scene.primitives.add(new cz.PointPrimitiveCollection());
    if (S.rings) w.scene.primitives.remove(S.rings);
    S.rings = w.scene.primitives.add(new cz.PointPrimitiveCollection());
    // P9: each object reads in space - a drop line to the ground, a soft dark disc under it, its last 10 s
    for (const c of [S.drops, S.discs, S.recent]) if (c) w.scene.primitives.remove(c);
    S.drops = w.scene.primitives.add(new cz.PolylineCollection());
    S.discs = w.scene.primitives.add(new cz.PointPrimitiveCollection());
    S.recent = w.scene.primitives.add(new cz.PolylineCollection());
    let alive = true;
    (async () => {
      for (const o of objects) {
        try {
          const m = await cz.Model.fromGltfAsync({
            id: o.id,                                       // N7: a click on it picks it (scene.pick)
            url: `/models/${o.kind}.glb`, minimumPixelSize: Math.round((o.size ?? 26) * 1.8), maximumScale: 50000,
            forwardAxis: cz.Axis.X, colorBlendMode: cz.ColorBlendMode.MIX, colorBlendAmount: 0.75,
            shadows: lightMode ? cz.ShadowMode.DISABLED : cz.ShadowMode.ENABLED,                 // P9
            // N5: an attitude not its own (from motion, borrowed) - see-through, with an outline in its colour
            ...(derivedAttitude(o, allObjs)
              ? { color: cz.Color.fromCssColorString(o.color).withAlpha(0.3), silhouetteColor: cz.Color.fromCssColorString(o.color), silhouetteSize: 2 }
              : { color: cz.Color.fromCssColorString(o.color) }),
          });
          if (!alive || w.isDestroyed()) return;
          m.show = false;
          w.scene.primitives.add(m);
          S.models.set(o.id, m);
        } catch { /* model file missing: the object shows as its track and name */ }
      }
      if (alive) update();
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cz, objKey, objLook]);

  /* tracks (precomputed positions, two lines: whole / the part shown) and labels, once per data */
  useEffect(() => {
    const S = scene3.current;
    const w = widgetRef.current;
    if (!cz || !w || !S.lines || !S.parts || !S.labels) return;
    S.lines.removeAll();
    S.parts.removeAll();
    S.labels.removeAll();
    S.drawn.clear();
    const font = `600 13px ${getComputedStyle(document.body).fontFamily}`;
    for (const o of objects) {
      const tr = tracks[o.id];
      if (!tr || !tr.t.length) continue;
      const col = cz.Color.fromCssColorString(o.color);
      const step = Math.max(1, Math.ceil(tr.t.length / TRACK_POINTS));
      const idx: number[] = [], pos: import("cesium").Cartesian3[] = [];
      for (let i = 0; i < tr.t.length; i += step) {
        const h = heightAt(o, tr, i);
        if (Number.isFinite(tr.lat[i]) && Number.isFinite(tr.lon[i]) && Number.isFinite(h)) { idx.push(i); pos.push(cz.Cartesian3.fromDegrees(tr.lon[i], tr.lat[i], h)); }
      }
      const d: Drawn = { idx, pos, full: null, part: null, fullMat: null, label: null };
      const cols = objColors[o.id];
      if (o.trail !== false && pos.length > 1 && cols) {
        // coloured: a line per stretch of one colour, the whole track (no faint / shown parts)
        const at = idx.map((i) => cols.at[i]);
        for (const r of colorRuns(at, 0, at.length)) if (r.b - r.a > 0)
          S.lines.add({ positions: pos.slice(r.a, Math.min(pos.length, r.b + 1)), width: tw + 0.5, material: cz.Material.fromType("Color", { color: cz.Color.fromCssColorString(r.color) }) });
      } else if (o.trail !== false && pos.length > 1) {
        // N5: a navigation solution dashed, a receiver as points (short dashes: one per fix at most zooms)
        const mat = () => (o.track === "dash" ? cz.Material.fromType("PolylineDash", { color: col, dashLength: 18 })
          : o.track === "points" ? cz.Material.fromType("PolylineDash", { color: col, dashLength: 8, dashPattern: 0x000f })
          : cz.Material.fromType("Color", { color: col }));
        const wd = o.track === "points" ? tw * 1.6 : tw;
        d.fullMat = mat();
        d.full = S.lines.add({ positions: pos, width: wd, material: d.fullMat });
        d.part = S.parts.add({ positions: pos, width: wd, material: mat(), show: false });
      }
      if (!lightMode && S.recent && S.drops && S.discs && pos.length > 1) {
        // P9: the last 10 s brighter and wider over the whole track (a glow that fades to its sides), the drop
        // line and the disc - moved as the time passes (update)
        d.recent = S.recent.add({ positions: pos.slice(0, 2), width: tw + 5, show: false,
          material: cz.Material.fromType("PolylineGlow", { color: col.brighten(0.35, new cz.Color()), glowPower: 0.22, taperPower: 1 }) });
        d.drop = S.drops.add({ positions: pos.slice(0, 2), width: 1.2, show: false, material: cz.Material.fromType("PolylineDash", { color: col.withAlpha(0.8), dashLength: 8 }) });
        d.disc = S.discs.add({ position: pos[0], pixelSize: 18, color: cz.Color.BLACK.withAlpha(0.3), show: false });
      }
      d.label = S.labels.add({ position: pos[0] ?? cz.Cartesian3.ZERO, text: visualOrder(o.name), font, fillColor: cz.Color.WHITE, show: false,
        outlineColor: cz.Color.fromCssColorString("#0b1118"), outlineWidth: 3, style: cz.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new cz.Cartesian2(22, -22), disableDepthTestDistance: Number.POSITIVE_INFINITY });
      S.drawn.set(o.id, d);
    }
    updateRef.current();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cz, tracks, objKey, objLook, objColors, tw, lightMode]);

  /* the log's events on the tracks: a mark where the object was at each event (errors red, warnings
     amber, mode changes blue), with its text */
  useEffect(() => {
    const w = widgetRef.current;
    const S = scene3.current;
    if (!cz || !w) return;
    if (S.events) w.scene.primitives.remove(S.events);
    if (S.eventLabels) w.scene.primitives.remove(S.eventLabels);
    const pts = new cz.PointPrimitiveCollection(), labs = new cz.LabelCollection();
    S.events = w.scene.primitives.add(pts);
    S.eventLabels = w.scene.primitives.add(labs);
    if (plot.showEvents === false) { w.scene.requestRender(); return; }
    const font = `500 11px ${getComputedStyle(document.body).fontFamily}`;
    const col = { error: "#e5534b", warning: "#f2a93b", mode: "#4f8cff" } as Record<string, string>;
    for (const o of objects) {
      const tr = tracks[o.id];
      const L = logs[o.lat.slice(0, o.lat.indexOf("/"))];
      if (!tr || !L) continue;
      for (const ev of L.events) {
        const kind = ev.kind === "mode" ? "mode" : ev.level === "error" ? "error" : ev.level === "warning" ? "warning" : null;
        if (!kind) continue;
        const te = ev.t + (L.timeOffset || 0);
        const p = objectAt(tr, te, angleUnitOf(o, allObjs));
        if (!p) continue;
        let i = 0;
        while (i < tr.t.length - 1 && tr.t[i + 1] <= te) i++;
        const hh = heightAt(o, tr, i);
        if (!Number.isFinite(hh)) continue;
        const pos = cz.Cartesian3.fromDegrees(p.lon, p.lat, hh);
        pts.add({ position: pos, pixelSize: 9, color: cz.Color.fromCssColorString(col[kind]), outlineColor: cz.Color.WHITE, outlineWidth: 1.5,
          disableDepthTestDistance: Number.POSITIVE_INFINITY });
        const lab = labs.add({ position: pos, text: visualOrder(ev.text.length > 40 ? ev.text.slice(0, 39) + "…" : ev.text), font, fillColor: cz.Color.WHITE,
          outlineColor: cz.Color.fromCssColorString("#0b1118"), outlineWidth: 3, style: cz.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new cz.Cartesian2(8, 10),
          disableDepthTestDistance: Number.POSITIVE_INFINITY, translucencyByDistance: new cz.NearFarScalar(2e3, 1, 6e4, 0) });
        (lab as unknown as { svPrio: number }).svPrio = kind === "mode" ? 1 : 2;      // W9: declutter by priority
      }
    }
    w.scene.requestRender();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cz, tracks, objKey, objLook, logs, plot.showEvents]);
  const hasEvents = objects.some((o) => (logs[o.lat.slice(0, o.lat.indexOf("/"))]?.events.length ?? 0) > 0);

  /* P7: the places - a point is its icon on a thin pole from the ground, with its name; a line / an area is
     draped on the ground (ground primitives; in the light mode, for the frame rate, plain lines 2 m over the
     ground the terrain has under each vertex) */
  const placeGfx = useRef<{ bills: import("cesium").BillboardCollection | null; labels: import("cesium").LabelCollection | null;
    poles: import("cesium").PolylineCollection | null; ground: import("cesium").Primitive[] }>({ bills: null, labels: null, poles: null, ground: [] });
  useEffect(() => {
    const w = widgetRef.current;
    if (!cz || !w) return;
    const G = placeGfx.current;
    for (const c of [G.bills, G.labels, G.poles]) if (c) w.scene.primitives.remove(c);
    for (const g of G.ground) w.scene.primitives.remove(g);
    G.ground = [];
    G.bills = w.scene.primitives.add(new cz.BillboardCollection());
    G.labels = w.scene.primitives.add(new cz.LabelCollection());
    G.poles = w.scene.primitives.add(new cz.PolylineCollection());
    const font = `600 12px ${getComputedStyle(document.body).fontFamily}`;
    const ground = (lat: number, lon: number) => w.scene.globe.getHeight(cz.Cartographic.fromDegrees(lon, lat)) ?? 0;
    const POLE = 30;                                       // m: the icon stands this high over its point
    for (const p of placesRef.current) {
      const col = cz.Color.fromCssColorString(p.color || "#d29922");
      if (p.kind === "point") {
        const h = p.alt ?? ground(p.lat, p.lon);
        const base = cz.Cartesian3.fromDegrees(p.lon, p.lat, h), top = cz.Cartesian3.fromDegrees(p.lon, p.lat, h + POLE);
        G.poles!.add({ positions: [base, top], width: 1.5, material: cz.Material.fromType("Color", { color: col.withAlpha(0.85) }) });
        G.bills!.add({ id: `place-${p.id}`, position: top, image: placeIconSvg(p.icon, p.color, 48), width: 26, height: 26,
          verticalOrigin: cz.VerticalOrigin.BOTTOM, disableDepthTestDistance: Number.POSITIVE_INFINITY });
        G.labels!.add({ position: top, text: visualOrder(p.name), font, fillColor: cz.Color.WHITE, outlineColor: cz.Color.fromCssColorString("#0b1118"),
          outlineWidth: 3, style: cz.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new cz.Cartesian2(16, -14), verticalOrigin: cz.VerticalOrigin.CENTER,
          disableDepthTestDistance: Number.POSITIVE_INFINITY, translucencyByDistance: new cz.NearFarScalar(5e4, 1, 4e5, 0) });
      } else if (p.points && p.points.length > 1) {
        const area = p.kind === "area";
        const deg = p.points.flatMap(([a, b]) => [b, a]);
        if (lightMode) {
          const pos = p.points.map(([a, b]) => cz.Cartesian3.fromDegrees(b, a, ground(a, b) + 2));
          G.poles!.add({ positions: area ? [...pos, pos[0]] : pos, width: 2.5, material: cz.Material.fromType("Color", { color: col }) });
        } else {
          try {
            G.ground.push(w.scene.primitives.add(new cz.GroundPolylinePrimitive({
              geometryInstances: new cz.GeometryInstance({ geometry: new cz.GroundPolylineGeometry({ positions: cz.Cartesian3.fromDegreesArray(deg), width: 3, loop: area }),
                attributes: { color: cz.ColorGeometryInstanceAttribute.fromColor(col) } }),
              appearance: new cz.PolylineColorAppearance() })));
            if (area) G.ground.push(w.scene.primitives.add(new cz.GroundPrimitive({
              geometryInstances: new cz.GeometryInstance({ geometry: new cz.PolygonGeometry({ polygonHierarchy: new cz.PolygonHierarchy(cz.Cartesian3.fromDegreesArray(deg)) }),
                attributes: { color: cz.ColorGeometryInstanceAttribute.fromColor(col.withAlpha(0.2)) } }),
              appearance: new cz.PerInstanceColorAppearance({ flat: true, translucent: true }) })));
          } catch { /* a degenerate shape: left out */ }
        }
        const mid = p.points[Math.floor(p.points.length / 2)];
        G.labels!.add({ position: cz.Cartesian3.fromDegrees(mid[1], mid[0], ground(mid[0], mid[1]) + 5), text: visualOrder(p.name), font, fillColor: cz.Color.WHITE,
          outlineColor: cz.Color.fromCssColorString("#0b1118"), outlineWidth: 3, style: cz.LabelStyle.FILL_AND_OUTLINE,
          disableDepthTestDistance: Number.POSITIVE_INFINITY, translucencyByDistance: new cz.NearFarScalar(5e4, 1, 4e5, 0) });
      }
    }
    (window as unknown as { __svPlacesDrawn?: string[] }).__svPlacesDrawn = placesRef.current.map((p) => p.name);   // for tests
    w.scene.requestRender();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cz, placesKey, lightMode]);

  /* P7 (P9.3 makes every camera change fly): the one camera flight of this view - to a place, a saved view,
     a typed position. A flight leaves the object-bound cameras for General (the user then looks around). */
  const flyTo = (to: FlyTarget) => {
    const w = widgetRef.current;
    if (!cz || !w) return;
    if (plot.followObject || (plot.camera && plot.camera !== "free")) {
      ownFlight.current = true;
      actions.updatePlot(plot.id, { followObject: null, camera: "free" });
    }
    w.camera.lookAtTransform(cz.Matrix4.IDENTITY);
    const duration = reducedMotion() ? 0 : 1.2;
    const rad = cz.Math.toRadians;
    if (to.range === 0 && to.heading !== undefined) {
      // a saved view: the camera where it was, looking where it looked
      w.camera.flyTo({ destination: cz.Cartesian3.fromDegrees(to.lon, to.lat, to.alt ?? 1000), orientation: { heading: rad(to.heading), pitch: rad(to.pitch ?? -35), roll: 0 }, duration });
    } else {
      const h = to.alt ?? w.scene.globe.getHeight(cz.Cartographic.fromDegrees(to.lon, to.lat)) ?? 0;
      w.camera.flyToBoundingSphere(new cz.BoundingSphere(cz.Cartesian3.fromDegrees(to.lon, to.lat, h), 1), { duration,
        offset: new cz.HeadingPitchRange(to.heading !== undefined ? rad(to.heading) : w.camera.heading, rad(to.pitch ?? -35), to.range ?? 1500) });
    }
    (window as unknown as { __svFly?: FlyTarget }).__svFly = to;          // for tests
    w.scene.requestRender();
  };
  const flyRef2 = useRef(flyTo);
  flyRef2.current = flyTo;
  useEffect(() => {
    if (!cz) return;
    mapFly.set(plot.id, (to) => flyRef2.current(to));
    mapCameraNow.set(plot.id, () => {
      const w = widgetRef.current, c = w?.camera.positionCartographic;
      if (!w || !c) return null;
      return { lat: cz.Math.toDegrees(c.latitude), lon: cz.Math.toDegrees(c.longitude), alt: c.height, heading: cz.Math.toDegrees(w.camera.heading),
        pitch: cz.Math.toDegrees(w.camera.pitch), range: 0 };
    });
    mapObjectAt.set(plot.id, (id) => { const q = lastStates.current.get(id); return q ? { lat: q.lat, lon: q.lon, alt: Number.isFinite(q.alt) ? q.alt : null } : null; });
    return () => { mapFly.delete(plot.id); mapCameraNow.delete(plot.id); mapObjectAt.delete(plot.id); };
  }, [cz, plot.id]);

  /* the measured points: a line and the distances */
  const measured = useMemo(() => {
    if (!cz || measurePts.length < 2) return null;
    const [a, b] = measurePts;
    const ca = cz.Cartographic.fromCartesian(a), cb = cz.Cartographic.fromCartesian(b);
    return { ground: new cz.EllipsoidGeodesic(ca, cb).surfaceDistance, straight: cz.Cartesian3.distance(a, b), dh: cb.height - ca.height };
  }, [cz, measurePts]);
  useEffect(() => {
    const w = widgetRef.current;
    const S = scene3.current;
    if (!cz || !w || !S.measure || !S.measurePts) return;
    S.measure.removeAll();
    S.measurePts.removeAll();
    for (const p of measurePts) S.measurePts.add({ position: p, pixelSize: 10, color: cz.Color.YELLOW, outlineColor: cz.Color.BLACK, outlineWidth: 2,
      disableDepthTestDistance: Number.POSITIVE_INFINITY });
    if (measurePts.length === 2) S.measure.add({ positions: measurePts, width: 3, material: cz.Material.fromType("Color", { color: cz.Color.YELLOW }) });
    w.scene.requestRender();
  }, [cz, measurePts]);
  useEffect(() => {
    if (!measuring) return;
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") { setMeasurePts([]); setMeasuring(false); } };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [measuring]);

  /* the view as a PNG (drawn here and read back at once - the drawing buffer is not kept) */
  // scale 2: drawn at twice the pixels for a report, then back to the screen's
  const saveImage = async (scale = 1) => {
    const w = widgetRef.current;
    if (!w) return;
    const path = await pickPath({ mode: "save", title: t("saveImage"), exts: [".png"], defaultName: scale > 1 ? "3d-view_hires.png" : "3d-view.png" });
    if (!path) return;
    const was = w.resolutionScale;
    if (scale > 1) { w.resolutionScale = was * scale; w.resize(); }
    w.scene.requestRender();
    w.render();
    const url = w.scene.canvas.toDataURL("image/png");
    if (scale > 1) { w.resolutionScale = was; w.resize(); w.scene.requestRender(); }
    try {
      const r = await api.saveImage(path, url);
      useApp.getState().toast({ kind: "info", text: t("savedTo", { path: r.path }) });
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
  };
  // 26.U3: the picture and removing the view are in the plot's ⋯ menu (PlotView), not two more buttons here
  useEffect(() => {
    globeImage.set(plot.id, (scale) => { void saveImage(scale); });
    return () => { globeImage.delete(plot.id); };
  });

  /* P9: the error, drawn - when the relation box is shown and its pair is one vehicle (median distance under
     20 m: truth and a navigation solution), a see-through surface between the two tracks coloured by the
     distance (green, amber, red at its 95th percentile); off in the light mode */
  const pairNow = pairOf(plot);
  const errKey = `${pairNow.primary}|${pairNow.secondary}|${plot.relHidden ? 1 : 0}|${plot.errorSurface === false ? 0 : 1}|${plot.relPlace ?? ""}`;
  const errPrim = useRef<import("cesium").Primitive | null>(null);
  const [errInfo, setErrInfo] = useState<{ p95: number; shown: boolean } | null>(null);
  useEffect(() => {
    const w = widgetRef.current;
    if (!cz || !w) return;
    if (errPrim.current) { w.scene.primitives.remove(errPrim.current); errPrim.current = null; }
    const P = objects.find((o) => o.id === pairNow.primary), Q = objects.find((o) => o.id === pairNow.secondary);
    const tp = P && tracks[P.id], tq = Q && tracks[Q.id];
    if (!P || !Q || !tp || !tq || plot.relPlace) { setErrInfo(null); w.scene.requestRender(); return; }
    const e = errorAlong(tp, (i) => heightAt(P, tp, i), tq, (j) => heightAt(Q, tq, j));
    if (!e || !e.same) { setErrInfo(null); w.scene.requestRender(); return; }
    const on = !plot.relHidden && plot.errorSurface !== false && !lightMode;
    setErrInfo({ p95: e.p95, shown: on });
    if (on) {
      const inst: import("cesium").GeometryInstance[] = [];
      for (let k = 1; k < e.rows.length; k++) {
        const a = e.rows[k - 1], b = e.rows[k];
        const pa = cz.Cartesian3.fromDegrees(tp.lon[a.i], tp.lat[a.i], heightAt(P, tp, a.i)), pb = cz.Cartesian3.fromDegrees(tp.lon[b.i], tp.lat[b.i], heightAt(P, tp, b.i));
        const qa = cz.Cartesian3.fromDegrees(a.lon, a.lat, Number.isFinite(a.h) ? a.h : heightAt(P, tp, a.i)), qb = cz.Cartesian3.fromDegrees(b.lon, b.lat, Number.isFinite(b.h) ? b.h : heightAt(P, tp, b.i));
        if (![pa, pb, qa, qb].every((v) => Number.isFinite(v.x))) continue;
        const pos = new Float64Array([pa.x, pa.y, pa.z, qa.x, qa.y, qa.z, pb.x, pb.y, pb.z, qb.x, qb.y, qb.z]);
        inst.push(new cz.GeometryInstance({
          geometry: new cz.Geometry({ attributes: { position: new cz.GeometryAttribute({ componentDatatype: cz.ComponentDatatype.DOUBLE, componentsPerAttribute: 3, values: pos }) } as never,
            indices: new Uint16Array([0, 1, 2, 1, 3, 2]), primitiveType: cz.PrimitiveType.TRIANGLES, boundingSphere: cz.BoundingSphere.fromPoints([pa, pb, qa, qb]) }),
          attributes: { color: cz.ColorGeometryInstanceAttribute.fromColor(cz.Color.fromCssColorString(errorColor(e.p95 > 0 ? (a.d + b.d) / 2 / e.p95 : 0)).withAlpha(0.45)) },
        }));
      }
      try {
        if (inst.length) errPrim.current = w.scene.primitives.add(new cz.Primitive({ geometryInstances: inst, asynchronous: false,
          appearance: new cz.PerInstanceColorAppearance({ flat: true, translucent: true, closed: false }) }));
      } catch { /* a degenerate track: no surface */ }
    }
    updateRef.current();                                  // shown or not by the camera's distance
    w.scene.requestRender();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cz, tracks, errKey, lightMode]);

  /* fit the camera to the tracks the first time they arrive */
  useEffect(() => {
    const w = widgetRef.current;
    if (!cz || !w || scene3.current.fitted) return;
    const pts: import("cesium").Cartesian3[] = [];
    for (const o of objects) {
      const tr = tracks[o.id];
      if (!tr) continue;
      const step = Math.max(1, Math.floor(tr.t.length / 400));
      for (let i = 0; i < tr.t.length; i += step) {
        const h = heightAt(o, tr, i);
        if (Number.isFinite(tr.lat[i]) && Number.isFinite(tr.lon[i]) && Number.isFinite(h)) pts.push(cz.Cartesian3.fromDegrees(tr.lon[i], tr.lat[i], h));
      }
    }
    if (!pts.length && !objects.length) {
      // P7: places take part in Fit only when the Map has no objects
      const b = placesBounds(placesRef.current);
      if (b) for (const [la, lo] of [[b[0], b[1]], [b[2], b[3]], [b[0], b[3]], [b[2], b[1]]]) pts.push(cz.Cartesian3.fromDegrees(lo, la, 0));
    }
    if (!pts.length) return;
    const bs = cz.BoundingSphere.fromPoints(pts);
    // P4: From above - straight down, north up, the whole flight framed; General - from the south-west
    const top = mapCamera(plot) === "top";
    w.camera.flyToBoundingSphere(bs, { duration: fitFlies.current && !reducedMotion() ? 1.2 : 0, offset: new cz.HeadingPitchRange(0, cz.Math.toRadians(top ? -89.9 : -35), Math.max(bs.radius * (top ? 3.2 : 2.6), 1500)) });
    scene3.current.fitted = true;
    fitFlies.current = true;                              // P9: every later Fit flies there
    w.scene.requestRender();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cz, tracks, objects.length ? "" : placesKey]);

  /* the time (the cursor), the timeline's mode, following: place everything */
  const update = () => {
    const w = widgetRef.current;
    const S = scene3.current;
    if (!cz || !w || w.isDestroyed() || !S.lines || !S.labels) return;
    const st = useApp.getState();
    // its own time (detached from the timeline) or the shared one
    const own = ownRef.current;
    const cur = own !== null ? { ...st.cursor, on: true, t1: own } : st.cursor;
    const span = shownSpan({ playMode: st.playMode, windowSec: st.windowSec, cursor: cur });
    const states = new Map<string, ObjState>();
    const follow = plot.followObject;
    S.ghosts?.removeAll();
    const pt = pointerRef.current;
    for (const o of objects) {
      const tr = tracks[o.id];
      const d = S.drawn.get(o.id);
      if (!tr || !tr.t.length || !d) continue;
      if (d.full && d.part && d.fullMat) {
        // the timeline's mode: the whole track faint and the part shown in full colour - only the
        // part's points change (a slice of the precomputed ones)
        if (span) {
          const [a, b] = indexSpan(tr.t, span);
          let j0 = 0, j1 = d.idx.length;
          while (j0 < d.idx.length && d.idx[j0] < a) j0++;
          while (j1 > j0 && d.idx[j1 - 1] >= b) j1--;
          d.fullMat.uniforms.color = cz.Color.fromCssColorString(o.color).withAlpha(0.3);
          const part = d.pos.slice(j0, Math.min(d.pos.length, j1 + 1));
          d.part.show = part.length > 1;
          if (part.length > 1) d.part.positions = part;
        } else {
          d.fullMat.uniforms.color = cz.Color.fromCssColorString(o.color);
          d.part.show = false;
        }
      }
      const tNow = trackTime(tr, cur.on ? cur.t1 : null, st.streaming && own === null);
      const gp = pt !== null && own === null && Math.abs(pt - tNow) > 1e-9 ? objectAt(tr, pt, angleUnitOf(o, allObjs)) : null;
      if (gp && S.ghosts) {
        let a = 0, z = tr.t.length - 1;
        while (z - a > 1) { const k = (a + z) >> 1; if (tr.t[k] <= pt!) a = k; else z = k; }
        const gh = heightAt(o, tr, tr.t[z] - pt! < pt! - tr.t[a] ? z : a);
        if (Number.isFinite(gh)) S.ghosts.add({ position: cz.Cartesian3.fromDegrees(gp.lon, gp.lat, gh), pixelSize: 13,
          color: cz.Color.fromCssColorString(o.color).withAlpha(0.45), outlineColor: cz.Color.WHITE.withAlpha(0.6), outlineWidth: 1.5,
          disableDepthTestDistance: Number.POSITIVE_INFINITY });
      }
      const p = objectAt(tr, tNow, angleUnitOf(o, allObjs));
      const m = S.models.get(o.id);
      if (!p) { if (m) m.show = false; if (d.label) d.label.show = false; continue; }
      // values at the time, by the nearest samples (altitude / attitude)
      let lo = 0, hi = tr.t.length - 1;
      while (hi - lo > 1) { const k = (lo + hi) >> 1; if (tr.t[k] <= tNow) lo = k; else hi = k; }
      const f = tr.t[hi] > tr.t[lo] ? (tNow - tr.t[lo]) / (tr.t[hi] - tr.t[lo]) : 0;
      const lerp = (a: number, b: number) => (Number.isFinite(a) && Number.isFinite(b) ? a + (b - a) * f : Number.isFinite(a) ? a : b);
      const h = lerp(heightAt(o, tr, lo), heightAt(o, tr, hi));
      if (!Number.isFinite(h)) { if (m) m.show = false; if (d.label) d.label.show = false; continue; }
      const rad = (arr: Float32Array | null, key: string) => {
        if (!arr) return 0;
        const v = lerp(arr[lo], arr[hi]);
        const u = angleUnitOf(o, allObjs);
        const isRad = u === "rad" || ((u ?? "auto") === "auto" && tr.units[key] === "rad");
        return Number.isFinite(v) ? (isRad ? v : cz.Math.toRadians(v)) : 0;
      };
      const pitch = rad(tr.pitch, "pitch"), roll = rad(tr.roll, "roll");
      const pos = cz.Cartesian3.fromDegrees(p.lon, p.lat, h);
      const hdg = cz.Math.toRadians(p.heading ?? 0);
      if (m) {
        // local frame: x north, y west, z up - the model's nose (+X) north at heading 0. Cesium's
        // heading turns about -z, i.e. clockwise from north as in navigation; pitch + = nose up,
        // roll + = right wing down (checked numerically: tests/e2e/test_globe3d.py)
        m.modelMatrix = cz.Transforms.headingPitchRollToFixedFrame(pos, new cz.HeadingPitchRoll(hdg, pitch, roll), cz.Ellipsoid.WGS84,
          cz.Transforms.localFrameToFixedFrameGenerator("north", "west"));
        m.show = true;
      }
      const g = tr.ground ? lerp(tr.ground[lo], tr.ground[hi]) : NaN;
      const agl = Number.isFinite(g) ? h - g : null;
      if (d.label) { d.label.position = pos; d.label.show = useApp.getState().mapPrefs.names !== "hidden"; }   // P8: Names on the Map
      const { gs, vs } = ratesAt(o, tr, tNow);
      states.set(o.id, { id: o.id, name: o.name, color: o.color, pos, lat: p.lat, lon: p.lon, alt: h, agl, hdg: p.heading,
        pitch: tr.pitch ? cz.Math.toDegrees(pitch) : null, roll: tr.roll ? cz.Math.toDegrees(roll) : null, gs, vs });
      // P9: the drop line to the ground and the disc under it; the last 10 s
      if (d.drop && d.disc) {
        const gp = cz.Cartesian3.fromDegrees(p.lon, p.lat, Number.isFinite(g) ? g : 0);
        const up = agl === null || agl > 3;
        d.drop.positions = [pos, gp]; d.drop.show = up; d.disc.position = gp; d.disc.show = up;
      }
      if (d.recent) {
        let a = 0, b = d.idx.length;
        while (a < b && tr.t[d.idx[a]] < tNow - 10) a++;
        while (b > a && tr.t[d.idx[b - 1]] > tNow) b--;
        const seg = [...d.pos.slice(a, b), pos];
        d.recent.show = seg.length > 1;
        if (seg.length > 1) d.recent.positions = seg;
      }
    }
    lastStates.current = states;
    // the camera on the followed object (N6: chase it, or look from it at the second one), flying to a
    // new mode / object over a moment instead of jumping
    const fs = follow ? states.get(follow) : undefined;
    const cam = w.camera;
    const fly = flyRef.current;
    const from = fly ? { pos: cam.positionWC.clone(), dir: cam.directionWC.clone(), up: cam.upWC.clone() } : null;
    const camMode = mapCamera(plot);
    if (camMode === "top") {
      // P4: From above - on the chosen object (track up: its heading points up), straight down at the user's height
      if (fs) {
        const range = Math.max(60, cz.Cartesian3.distance(cam.positionWC, fs.pos));
        const hdg = plot.mapUp === "track" && fs.hdg !== null && fs.hdg !== undefined ? cz.Math.toRadians(fs.hdg) : 0;
        cam.lookAt(fs.pos, new cz.HeadingPitchRange(hdg, cz.Math.toRadians(-89.9), range));
      }
    } else if (fs) {
      const range = cam.positionCartographic ? Math.max(30, cz.Cartesian3.distance(cam.positionWC, fs.pos)) : 2000;
      const second = plot.camera === "lookat" ? states.get((plot.relatedObjects ?? []).find((x) => x !== fs.id) ?? "") : undefined;
      if (plot.camera === "cockpit") {
        // P9: the cockpit - at the object, looking along its heading and pitch, rolling with it
        cam.lookAtTransform(cz.Matrix4.IDENTITY);
        cam.setView({ destination: fs.pos, orientation: { heading: cz.Math.toRadians(fs.hdg ?? 0), pitch: cz.Math.toRadians(fs.pitch ?? 0), roll: cz.Math.toRadians(fs.roll ?? 0) } });
      } else if (plot.camera === "chase") {
        // behind and a little above, along its heading (eased while playing, so noise does not shake it)
        const goal = fs.hdg ?? 0, now = performance.now(), last = chaseHdg.current;
        let hdg = goal;
        if (st.smoothFollow && st.playing && last && now - last.t < 250) {
          const d = ((goal - last.h + 540) % 360) - 180;
          hdg = last.h + d * (1 - Math.exp(-(now - last.t) / 200));
        }
        chaseHdg.current = { t: now, h: hdg };
        // its distance: on entering, near enough to see it (60-600 m); then the user's (the wheel)
        if (fly?.fresh || chaseRange.current === null) chaseRange.current = Math.min(Math.max(range, 60), 600);
        else if (!fly) chaseRange.current = range;
        const r0 = chaseRange.current;
        cam.lookAt(fs.pos, new cz.HeadingPitchRange(cz.Math.toRadians(hdg), cz.Math.toRadians(-12), r0));
      } else if (second) {
        // from just behind and above the primary, looking at the second object
        const dir = cz.Cartesian3.normalize(cz.Cartesian3.subtract(second.pos, fs.pos, new cz.Cartesian3()), new cz.Cartesian3());
        const up = cz.Ellipsoid.WGS84.geodeticSurfaceNormal(fs.pos, new cz.Cartesian3());
        const eye = cz.Cartesian3.add(cz.Cartesian3.multiplyByScalar(dir, -40, new cz.Cartesian3()), cz.Cartesian3.multiplyByScalar(up, 12, new cz.Cartesian3()), new cz.Cartesian3());
        cz.Cartesian3.add(eye, fs.pos, eye);
        const look = cz.Cartesian3.normalize(cz.Cartesian3.subtract(second.pos, eye, new cz.Cartesian3()), new cz.Cartesian3());
        cam.lookAtTransform(cz.Matrix4.IDENTITY);
        cam.setView({ destination: eye, orientation: { direction: look, up } });
      } else {
        // keep the followed object in the middle; the user's angle and distance stay
        cam.lookAt(fs.pos, new cz.HeadingPitchRange(cam.heading, cam.pitch, range));
      }
    }
    if (!follow) cam.lookAtTransform(cz.Matrix4.IDENTITY);
    if (fly && from) {
      // where the mode puts the camera now, reached from where it was when the mode changed
      fly.fresh = false;
      const f = Math.min(1, (performance.now() - fly.t0) / FLY_MS), e = 1 - (1 - f) ** 3;
      if (fly.start === null) fly.start = from;
      if (f < 1 && (fs || !follow)) {
        const to = { pos: cam.positionWC.clone(), dir: cam.directionWC.clone(), up: cam.upWC.clone() };
        const s0 = fly.start;
        const mix = (a: import("cesium").Cartesian3, b: import("cesium").Cartesian3, norm: boolean) => {
          const v = cz.Cartesian3.lerp(a, b, e, new cz.Cartesian3());
          return norm ? cz.Cartesian3.normalize(v, v) : v;
        };
        cam.lookAtTransform(cz.Matrix4.IDENTITY);
        cam.setView({ destination: mix(s0.pos, to.pos, false), orientation: { direction: mix(s0.dir, to.dir, true), up: mix(s0.up, to.up, true) } });
        if (fs && !plot.camera) {
          // back on the object for the next frame (its own transform: turning goes around it)
          const r = cz.Cartesian3.distance(cam.positionWC, fs.pos);
          cam.lookAt(fs.pos, new cz.HeadingPitchRange(cam.heading, cam.pitch, r));
        }
        if (!fly.raf) fly.raf = requestAnimationFrame(() => { fly.raf = 0; updateRef.current(); });
      } else flyRef.current = null;
    }
    // P9: the cockpit hides its own model (and any within 20 m - a solution of the same vehicle would fill
    // the view) and widens the view to 70°
    const ck = plot.camera === "cockpit" && fs ? fs : null;
    for (const [id, q] of states) {
      const m = S.models.get(id);
      if (m && ck) m.show = !(id === ck.id || cz.Cartesian3.distance(q.pos, ck.pos) < 20);
      const dr = S.drawn.get(id);
      if (dr?.label && ck && id === ck.id) dr.label.show = false;
    }
    // P9: the models' shadows only while the camera is near an object (On the object, Chase, Cockpit, Look at):
    // from far they are a pixel, and the shadow pass is the effects' largest cost
    const nearCam = !lightMode && !!fs && camMode !== "top" && camMode !== "free";
    if (w.scene.shadowMap.enabled !== nearCam) w.scene.shadowMap.enabled = nearCam;
    const fr = cam.frustum as import("cesium").PerspectiveFrustum;
    const fov = cz.Math.toRadians(ck ? 70 : 60);
    if (fr.fov !== undefined && Math.abs(fr.fov - fov) > 1e-6) fr.fov = fov;
    // P9: the sun where it was - the recording's own time when it has real dates (Unix seconds), else a
    // mid-morning sun (10:00 local solar time at an equinox, over the scene)
    if (!lightMode) {
      const any = states.values().next().value as ObjState | undefined;
      const tr0 = Object.values(tracks)[0];
      if (any && tr0) {
        const tt = trackTime(tr0, cur.on ? cur.t1 : null, st.streaming && own === null);
        const ms = tt > 1e9 ? tt * 1000 : Date.UTC(2026, 2, 20, 10, 0, 0) - (any.lon / 15) * 3600_000;
        if (!(Math.abs(ms - sunMs.current) <= 20_000)) { sunMs.current = ms; w.clock.currentTime = cz.JulianDate.fromDate(new Date(ms)); }
      }
    }
    // the primary object, and the related ones: a dashed line from it to each, with the distance on it
    const pair = pairOf(plot);                              // N7: the plot's choice, else by class
    const primary = states.get(pair.primary ?? "") ?? null;
    refState.current = primary ? { name: primary.name, lat: primary.lat, lon: primary.lon } : null;   // P4: the readout's "from"
    const rel: Readout["rel"] = [];
    const related = (plot.relatedObjects?.length ? plot.relatedObjects : pair.secondary ? [pair.secondary] : []).filter((id) => id !== primary?.id).slice(0, 2);
    S.links?.removeAll();
    S.linkLabels?.removeAll();
    if (primary) {
      for (const id of related) {
        const q = states.get(id);
        if (!q) continue;
        // on the WGS84 ellipsoid, like the slant range (a sphere was ~0.2 % off from it)
        const horiz = new cz.EllipsoidGeodesic(cz.Cartographic.fromDegrees(primary.lon, primary.lat), cz.Cartographic.fromDegrees(q.lon, q.lat)).surfaceDistance;
        const slant = cz.Cartesian3.distance(primary.pos, q.pos);
        // N7: closure and aspect as on the map (relation.ts - one set of maths), over the next half second
        const at = (oid: string, dt: number): At | null => {
          const tr = tracks[oid], o = objects.find((x) => x.id === oid);
          if (!tr || !o) return null;
          const tt = trackTime(tr, cur.on ? cur.t1 : null, st.streaming && own === null) + dt;
          const p = objectAt(tr, tt, angleUnitOf(o, allObjs));
          return p ? { lat: p.lat, lon: p.lon, alt: o.alt ? altAt(tr, tt) : null, hdg: p.heading } : null;
        };
        const p0 = at(primary.id, 0), q0 = at(id, 0), p1 = at(primary.id, 0.5), q1 = at(id, 0.5);
        const rr = p0 && q0 ? relation(p0, q0, p1 ?? undefined, q1 ?? undefined, p1 && q1 ? 0.5 : 0) : null;
        rel.push({ name: q.name, color: q.color, horiz, dz: q.alt - primary.alt, slant, brg: bearing(primary.lat, primary.lon, q.lat, q.lon),
          closure: rr?.closure ?? null, aspect: rr?.aspect ?? null, side: rr?.aspectSide ?? null });
        S.links?.add({ positions: [primary.pos, q.pos], width: 2, material: linkMat(cz.Color.fromCssColorString(q.color)) });
        S.linkLabels?.add({ position: cz.Cartesian3.midpoint(primary.pos, q.pos, new cz.Cartesian3()), text: fmtDistance(slant, st.lang),
          font: `600 12px ${getComputedStyle(document.body).fontFamily}`, fillColor: cz.Color.WHITE, outlineColor: cz.Color.fromCssColorString("#0b1118"),
          outlineWidth: 3, style: cz.LabelStyle.FILL_AND_OUTLINE, disableDepthTestDistance: Number.POSITIVE_INFINITY });
      }
    }
    // P9: the error surface is metres wide - drawn while the camera is within 3 km of the reference (from
    // further it is under a pixel, and a see-through surface is not free on a slow graphics card)
    if (errPrim.current) errPrim.current.show = !!primary && cz.Cartesian3.distance(cam.positionWC, primary.pos) < 3000;
    setReadout(primary ? { primary, rel } : null);
    // N7: a ring round the primary, a fainter one round the secondary
    S.rings?.removeAll();
    const amber = cz.Color.fromCssColorString(getComputedStyle(document.documentElement).getPropertyValue("--amber").trim() || "#d29922");
    for (const [id, second] of [[pair.primary, false], [pair.secondary, true]] as const) {
      const q = id ? states.get(id) : undefined;
      if (!q) continue;
      S.rings?.add({ id: `ring-${id}`, position: q.pos, pixelSize: second ? 40 : 46, color: cz.Color.TRANSPARENT,
        outlineColor: second ? amber.withAlpha(0.55) : amber, outlineWidth: second ? 2 : 3, disableDepthTestDistance: Number.POSITIVE_INFINITY });
    }
    w.scene.requestRender();
  };
  const updateRef = useRef(update);
  updateRef.current = update;
  const lastStates = useRef<Map<string, ObjState>>(new Map());
  const fitFlies = useRef(false);
  const sunMs = useRef(NaN);
  /** N7: an object made the primary (or the secondary) - shared with the tab's map. */
  const pick = (id: string, second: boolean) => {
    if (!objects.some((o) => o.id === id)) return;
    const cur = pairOf(plot);
    if (second) { if (id !== cur.primary) actions.setObjectPair(plot.id, cur.primary, id); }
    else if (id !== cur.primary) actions.setObjectPair(plot.id, id, id === cur.secondary ? cur.primary : cur.secondary);
  };
  const pickRef = useRef(pick);
  pickRef.current = pick;
  /** Q / Shift+Q: the next / previous primary; X: swap them - while the 3D view has the focus. */
  const onKey = (e: React.KeyboardEvent) => {
    if (e.ctrlKey || e.metaKey || e.altKey || objects.length < 2) return;
    const k = e.key.toLowerCase(), cur = pairOf(plot);
    if (k === "q") {
      const i = objects.findIndex((o) => o.id === cur.primary);
      const next = objects[(i + (e.shiftKey ? -1 : 1) + objects.length) % objects.length].id;
      actions.setObjectPair(plot.id, next, next === cur.secondary ? cur.primary : cur.secondary);
    } else if (k === "x" && cur.secondary) actions.setObjectPair(plot.id, cur.secondary, cur.primary);
    else return;
    e.preventDefault(); e.stopPropagation();
  };
  const rootRef = useRef<HTMLDivElement>(null);
  const rootFocus = useRef(() => rootRef.current?.focus({ preventScroll: true }));
  // N6: a change of camera mode or of the object it is on flies there (FLY_MS) instead of jumping
  const flyRef = useRef<{ t0: number; fresh: boolean; raf: number; start: { pos: import("cesium").Cartesian3; dir: import("cesium").Cartesian3; up: import("cesium").Cartesian3 } | null } | null>(null);
  const chaseHdg = useRef<{ t: number; h: number } | null>(null);
  const chaseRange = useRef<number | null>(null);
  const camKey = `${plot.followObject ?? ""}|${plot.camera ?? ""}|${plot.camera === "lookat" ? (plot.relatedObjects ?? [])[0] ?? "" : ""}`;
  const camKeyRef = useRef(camKey);
  const ownFlight = useRef(false);          // P7: flyTo set the camera free itself - no blend from the old mode
  if (camKeyRef.current !== camKey) {
    camKeyRef.current = camKey;
    if (ownFlight.current) { ownFlight.current = false; flyRef.current = null; }
    else if (!reducedMotion()) { if (flyRef.current?.raf) cancelAnimationFrame(flyRef.current.raf); flyRef.current = { t0: performance.now(), fresh: true, raf: 0, start: null }; }
    chaseHdg.current = null; chaseRange.current = null;
  }
  useEffect(() => {
    const w = widgetRef.current, host = hostRef.current;
    if (!w || !host || !cz) return;
    let raf = 0, last: { x: number; y: number } | null = null;
    const pick = () => {
      raf = 0;
      if (!last || w.isDestroyed()) return;
      const ray = w.camera.getPickRay(new cz.Cartesian2(last.x, last.y));
      // the terrain under the mouse; where its tiles are not drawn yet, the ellipsoid
      const p = (ray ? w.scene.globe.pick(ray, w.scene) : undefined) ?? w.camera.pickEllipsoid(new cz.Cartesian2(last.x, last.y));
      if (!p) { setMouseAt(null); return; }
      const c = cz.Cartographic.fromCartesian(p);
      const lat = cz.Math.toDegrees(c.latitude), lon = cz.Math.toDegrees(c.longitude);
      const g = w.scene.globe.getHeight(c);
      const h = w.camera.positionCartographic?.height ?? 1000;
      const prec = Math.max(1, Math.min(8, Math.ceil(-Math.log10(Math.max(h, 1) / 1000 / 111_000))));
      const r = refState.current;
      let from = null;
      if (r) {
        const g1 = cz.Cartographic.fromDegrees(r.lon, r.lat), g2 = cz.Cartographic.fromDegrees(lon, lat);
        const geo = new cz.EllipsoidGeodesic(g1, g2);
        from = { name: r.name, d: geo.surfaceDistance, brg: (cz.Math.toDegrees(geo.startHeading) + 360) % 360 };
      }
      const np = nearestPlace(lat, lon, placesRef.current);         // P7: "1.24 km from Runway 27"
      setMouseAt({ lat, lon, ground: g === undefined ? null : g, prec, from, place: np ? { name: np.place.name, d: np.d } : null });
      (window as unknown as { __svReadout?: object }).__svReadout = { lat, lon, ground: g ?? null };   // for tests
    };
    const move = (e: PointerEvent) => {
      const b = host.getBoundingClientRect();
      last = { x: e.clientX - b.left, y: e.clientY - b.top };
      if (!raf) raf = requestAnimationFrame(pick);                       // one update a frame
    };
    const leave = () => { last = null; setMouseAt(null); };
    // P7: a right-click on the ground: its position rides on the event to the plot's menu (Add a place here…)
    const ctx = (e: MouseEvent) => {
      const b = host.getBoundingClientRect(), xy = new cz.Cartesian2(e.clientX - b.left, e.clientY - b.top);
      const ray = w.camera.getPickRay(xy);
      const p = (ray ? w.scene.globe.pick(ray, w.scene) : undefined) ?? w.camera.pickEllipsoid(xy);
      if (!p) return;
      const c = cz.Cartographic.fromCartesian(p), g = w.scene.globe.getHeight(c);
      (e as MouseEvent & { svGeo?: unknown }).svGeo = { lat: cz.Math.toDegrees(c.latitude), lon: cz.Math.toDegrees(c.longitude), ground: g === undefined ? null : Math.round(g * 10) / 10 };
    };
    host.addEventListener("contextmenu", ctx);
    host.addEventListener("pointermove", move);
    host.addEventListener("pointerleave", leave);
    return () => { host.removeEventListener("pointermove", move); host.removeEventListener("pointerleave", leave); host.removeEventListener("contextmenu", ctx); if (raf) cancelAnimationFrame(raf); };
  }, [cz]);
  // P4: choosing From above (no object) frames the whole flight from straight above; tilting there turns the
  // camera to General (middle-drag or Ctrl+drag are Cesium's tilt)
  const camTop = mapCamera(plot) === "top";
  useEffect(() => { if (camTop && !plot.followObject && cz) reFit(); }, [camTop, plot.followObject, cz]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const w = widgetRef.current, host = hostRef.current;
    if (!w || !host || !cz) return;
    w.scene.screenSpaceCameraController.enableTilt = !camTop;
    if (!camTop) return;
    const down = (e: PointerEvent) => { if (e.button === 1 || e.ctrlKey) actions.updatePlot(plot.id, { camera: "free", followObject: null }); };
    host.addEventListener("pointerdown", down, true);
    return () => host.removeEventListener("pointerdown", down, true);
  }, [camTop, cz]);   // eslint-disable-line react-hooks/exhaustive-deps
  // N6: the time moves the scene without a React render (playback re-rendered this 2-3 times a frame)
  useEffect(() => useApp.subscribe((s, p) => { if (s.cursor !== p.cursor) updateRef.current(); }), []);
  useEffect(() => { updateRef.current(); }, [cz, tracks, playMode, windowSec, plot.followObject, plot.camera, plot.primaryObject, plot.relatedObjects, objects, lang, ownT, pointerT, mapNames]);

  /* the span of the objects' own tracks (the independent time runs over that) */
  const ownExt = useMemo((): [number, number] | null => {
    let lo = Infinity, hi = -Infinity;
    for (const tr of Object.values(tracks)) if (tr.t.length) { lo = Math.min(lo, tr.t[0]); hi = Math.max(hi, tr.t[tr.t.length - 1]); }
    return hi > lo ? [lo, hi] : null;
  }, [tracks]);
  useEffect(() => {
    if (!ownPlaying || !ownExt) return;
    let raf = 0, last = performance.now();
    let v = ownTRef.current ?? ownExt[0];
    const step = (now: number) => {
      const dt = (now - last) / 1000; last = now;
      v = Math.min(ownExt[1], v + dt * ownSpeed);
      setOwnT(v);
      if (v >= ownExt[1]) { setOwnPlaying(false); actions.updatePlot(plot.id, { ownTime: v }); return; }   // at the end: stop, keep it
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ownPlaying, ownSpeed, ownExt]);
  const detach = () => {
    const c = useApp.getState().cursor;
    const t0 = c.on && c.t1 !== null ? c.t1 : ownExt?.[0] ?? 0;
    setOwnT(t0);
    actions.updatePlot(plot.id, { ownTime: t0 });
  };
  const attach = () => { setOwnPlaying(false); actions.updatePlot(plot.id, { ownTime: null }); };
  const keepOwn = (v: number) => actions.updatePlot(plot.id, { ownTime: v });

  const primaryId = pairOf(plot).primary ?? "";
  // P9: the camera's object - its flight display (a toggle; by default in Chase and Cockpit) and the mini-map
  const camNowMode = mapCamera(plot);
  const close = camNowMode === "centre" || camNowMode === "chase" || camNowMode === "cockpit" || camNowMode === "lookat";
  const dispOn = !!plot.followObject && (plot.display ?? (camNowMode === "chase" || camNowMode === "cockpit"));
  const dispSrc = plot.followObject ? lastStates.current.get(plot.followObject) : undefined;
  const dispState = dispOn && dispSrc ? { name: dispSrc.name, roll: dispSrc.roll, pitch: dispSrc.pitch, hdg: dispSrc.hdg, gs: dispSrc.gs, alt: dispSrc.alt, agl: dispSrc.agl } : null;
  const miniTracks = useMemo(() => objects.filter((o) => tracks[o.id]).map((o) => ({ color: o.color, lat: tracks[o.id].lat, lon: tracks[o.id].lon })), [objects, tracks]);
  const wc = widgetRef.current && !widgetRef.current.isDestroyed() ? widgetRef.current : null, cc = wc ? wc.camera.positionCartographic : null;
  const fovNow = wc ? ((wc.camera.frustum as import("cesium").PerspectiveFrustum).fov ?? 1) : 1;
  const camNow = cz && wc && cc ? { lat: cz.Math.toDegrees(cc.latitude), lon: cz.Math.toDegrees(cc.longitude), heading: wc.camera.heading,
    fov: fovNow * Math.max(1, wc.canvas.clientWidth / Math.max(1, wc.canvas.clientHeight)) } : null;
  // for tests: what the wow shows (P9) - every GPU effect is off in the light mode
  const wowAll = (window as unknown as { __svWow?: Record<string, unknown> });
  wowAll.__svWow = { ...wowAll.__svWow, [plot.id]: {
    light: lightMode, sky: !!wc?.scene.skyAtmosphere && !lightMode, lighting: !!wc?.scene.globe.enableLighting, shadows: !!wc?.scene.shadowMap?.enabled,
    sunMs: Number.isFinite(sunMs.current) ? sunMs.current : null, drop: [...scene3.current.drawn.values()].some((d) => d.drop?.show),
    recent: [...scene3.current.drawn.values()].some((d) => d.recent?.show), cockpit: camNowMode === "cockpit", fov: (fovNow * 180) / Math.PI,
    display: !!dispState, mini: close && miniTracks.length > 0, errorSurface: errInfo } };
  const centred = !!plot.followObject;
  const showBox = plot.showReadout !== false;
  const secondaryName = plot.relHidden ? null : objects.find((o) => o.id === pairOf(plot).secondary)?.name;
  const reFit = () => { scene3.current.fitted = false; setTracks((x) => ({ ...x })); };
  /** + / − of the map bar: towards / away from what the camera is on (the followed object, else the ground) */
  const zoom3d = (dir: 1 | -1) => {
    const w = widgetRef.current, cz0 = cz;
    if (!w || !cz0) return;
    const fs = plot.followObject ? scene3.current.drawn.get(plot.followObject) : undefined;
    const c = w.camera, h = c.positionCartographic?.height ?? 1000;
    const d = fs && fs.label ? cz0.Cartesian3.distance(c.positionWC, fs.label.position) : h;
    c.zoomIn(dir * Math.max(5, d * 0.35));
    if (plot.camera === "chase") chaseRange.current = Math.max(20, (chaseRange.current ?? d) * (dir > 0 ? 0.65 : 1.5));
    updateRef.current();
  };

  // P4: 3D cannot draw here (no WebGL, the context lost): the Map is drawn flat by the plot (GeoChart)
  useEffect(() => { if (failed) onFlat?.(failed); }, [failed]);   // eslint-disable-line react-hooks/exhaustive-deps
  if (failed) return null;
  return (
    <div ref={rootRef} className={`globe3d${detached ? " own-time" : ""}`} onDoubleClick={reFit} tabIndex={-1} onKeyDown={onKey}
      onPointerDownCapture={(e) => { if (!(e.target as HTMLElement).closest("button, select, input, a")) rootRef.current?.focus({ preventScroll: true }); }}>
      <div ref={hostRef} className="globe3d-host" />
      <div ref={creditRef} className="globe3d-credits" />
      {!cz && <div className="plot-empty">{t("globeLoading")}</div>}
      <TrackKeys objects={objects} colors={objColors} />
      {cz && !objects.length && !places.length && <div className="plot-empty">{emptyText}</div>}
      {lightMode && <div className="globe3d-light" title={t("globeLightHint")}>{t("globeLight")}</div>}
      {/* the camera, the primary object and the related ones, the data box */}
      {cz && objects.length > 0 && (
        <MapBar plot={plot} objects={objects} className="globe3d-bar" chaseHint="g3CamChaseHint" onZoom={zoom3d}
          onFit={() => { actions.updatePlot(plot.id, { followObject: null, camera: undefined }); reFit(); }}>
          {/* 3D only: from the reference, looking at the compared object */}
          {objects.length > 1 && <button aria-pressed={centred && plot.camera === "lookat"} className={`g3-toggle g3-cam-lookat${centred && plot.camera === "lookat" ? " on" : ""}`}
              title={t("g3CamLookAtHint")} onClick={() => actions.updatePlot(plot.id, { followObject: primaryId, camera: "lookat",
                // looking needs something to look at: the first other object when none is chosen
                ...((plot.relatedObjects ?? []).some((x) => x !== primaryId) ? {} : { relatedObjects: [objects.find((o) => o.id !== primaryId)!.id] }) })}>{t("g3CamLookAt")}</button>}
          {objects.length > 2 && (() => {
            // a third object: a second dashed line from the reference (the compared one is chosen in the picker)
            const sec = pairOf(plot).secondary;
            return (
              <label><span>{t("g3Third")}</span>
                <select value={(plot.relatedObjects ?? [])[1] ?? ""} aria-label={t("g3Third")}
                  onChange={(e) => actions.updatePlot(plot.id, { relatedObjects: [sec, e.target.value].filter((x, n, a): x is string => !!x && x !== primaryId && a.indexOf(x) === n) })}>
                  <option value="">—</option>
                  {objects.filter((o) => o.id !== primaryId && o.id !== sec).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select></label>
            );
          })()}
          <button className={`g3-toggle${showBox ? " on" : ""}`} aria-pressed={showBox} onClick={() => actions.updatePlot(plot.id, { showReadout: !showBox })}>{t("g3Data")}</button>
          {/* P9: the flight display of the object the camera is on - by default in Chase and Cockpit */}
          {centred && <button className={`g3-toggle g3-display${dispOn ? " on" : ""}`} aria-pressed={dispOn} title={t("g3DisplayHint")}
            onClick={() => actions.updatePlot(plot.id, { display: !dispOn })}>{t("g3Display")}</button>}
          {hasEvents && <button className={`g3-toggle${plot.showEvents !== false ? " on" : ""}`} aria-pressed={plot.showEvents !== false}
            onClick={() => actions.updatePlot(plot.id, { showEvents: plot.showEvents === false })} title={t("g3EventsHint")}>{t("g3Events")}</button>}
          <button className={`g3-toggle${measuring ? " on" : ""}`} aria-pressed={measuring} title={t("g3MeasureHint")}
            onClick={() => { setMeasuring(!measuring); setMeasurePts([]); }}>{t("g3Measure")}</button>
          <span className="g3-seg" role="radiogroup" aria-label={t("g3Time")}>
            <span className="g3-seg-label">{t("g3Time")}</span>
            <button role="radio" aria-checked={!detached} className={!detached ? "on" : ""} onClick={attach} title={t("g3TimeSharedHint")}>{t("g3TimeShared")}</button>
            <button role="radio" aria-checked={detached} className={detached ? "on" : ""} onClick={() => { if (!detached) detach(); }} title={t("g3TimeOwnHint")}>{t("g3TimeOwn")}</button>
          </span>
        </MapBar>
      )}
      {mouseAt && (
        <div className="geo-readout g3-readout" role="status">
          {fmtCoord(mouseAt.lat, mouseAt.lon, mouseAt.prec)}
          {mouseAt.ground !== null && <> · {t("mapReadoutGround")} {fmtDistance(mouseAt.ground, lang)}</>}
          {mouseAt.from && <> · {t("mapReadoutFrom", { name: mouseAt.from.name })} {fmtDistance(mouseAt.from.d, lang)} {Math.round(mouseAt.from.brg)}°</>}
          {mouseAt.place && <> · {t("plFrom", { d: fmtDistance(mouseAt.place.d, lang), name: mouseAt.place.name })}</>}
        </div>
      )}
      {cz && objects.length > 0 && !measuring && !detached && (
        <div className="g3-cam-hint" role="note">{camTop ? t("g3CamTopHint") : t(!centred ? "g3HintFree" : plot.camera === "chase" ? "g3HintChase" : plot.camera === "cockpit" ? "g3CamCockpitHint" : plot.camera === "lookat" ? "g3HintLookAt" : "g3HintCentre")}</div>
      )}
      {measuring && (
        <div className="g3-measure" dir={lang === "he" ? "rtl" : "ltr"} role="status">
          {!measured ? t(measurePts.length ? "g3MeasureSecond" : "g3MeasureFirst") : <>
            {t("g3MeasureGround")} <bdi dir="ltr">{fmtDistance(measured.ground, lang)}</bdi> · {t("g3Slant")} <bdi dir="ltr">{fmtDistance(measured.straight, lang)}</bdi>
            {" "}· Δh <bdi dir="ltr">{measured.dh >= 0 ? "+" : ""}{fmtDistance(measured.dh, lang)}</bdi></>}
        </div>
      )}
      {detached && ownExt && (
        <div className="g3-own" role="group" aria-label={t("g3TimeOwn")} onDoubleClick={(e) => e.stopPropagation()}>
          <span className="g3-own-badge">{t("g3TimeOwn")}</span>
          <button className="iconbtn" aria-label={ownPlaying ? t("pause") : t("play")} onClick={() => {
            if (ownPlaying) { setOwnPlaying(false); if (ownT !== null) keepOwn(ownT); }
            else { if ((ownT ?? ownExt[0]) >= ownExt[1]) setOwnT(ownExt[0]); setOwnPlaying(true); }
          }}>{ownPlaying ? "❚❚" : "▶"}</button>
          <input type="range" dir="ltr" aria-label={t("g3TimeOwn")} min={ownExt[0]} max={ownExt[1]} step={(ownExt[1] - ownExt[0]) / 2000}
            value={ownT ?? ownExt[0]} onChange={(e) => { setOwnPlaying(false); setOwnT(Number(e.target.value)); }}
            onPointerUp={(e) => keepOwn(Number((e.target as HTMLInputElement).value))} onKeyUp={(e) => keepOwn(Number((e.target as HTMLInputElement).value))} />
          <bdi dir="ltr" className="g3-own-clock">{fmtNum((ownT ?? ownExt[0]) - ownExt[0], lang, 6)} s</bdi>
          <select value={ownSpeed} dir="ltr" aria-label={t("tlSpeed")} onChange={(e) => setOwnSpeed(Number(e.target.value))}>
            {[0.25, 0.5, 1, 2, 5, 10, 30, 60].map((v) => <option key={v} value={v}>×{v}</option>)}
          </select>
        </div>
      )}
      {dispState && <div className="g3-fd"><FlightDisplay s={dispState} /></div>}
      {close && miniTracks.length > 0 && <div className="g3-mini"><MiniMap tracks={miniTracks} camera={camNow}
        focus={dispSrc ? { lat: dispSrc.lat, lon: dispSrc.lon, hdg: dispSrc.hdg, color: dispSrc.color } : null}
        onPick={(lat, lon) => flyTo({ lat, lon, range: 1500, pitch: -40 })} /></div>}
      {(allObjs.length > 1 || (allObjs.length > 0 && places.length > 0)) && <RelationPanel plot={plot} objects={allObjs} tracks={tracks} />}
      {readout && showBox && (
        // in the UI's direction; every number set left-to-right on its own (Hebrew names around them)
        <div className="globe3d-readout" dir={lang === "he" ? "rtl" : "ltr"} aria-live="off">
          <b style={{ color: readout.primary.color }}>{readout.primary.name}</b>
          <span><bdi dir="ltr">{fmtNum(readout.primary.lat, lang, 7)}°, {fmtNum(readout.primary.lon, lang, 7)}°</bdi></span>
          <span>{t("globeAlt")} <bdi dir="ltr">{fmtNum(readout.primary.alt, lang, 5)} m</bdi>
            {readout.primary.agl !== null && <> · {t("globeAgl")} <bdi dir="ltr">{fmtNum(readout.primary.agl, lang, 5)} m</bdi></>}</span>
          {readout.primary.hdg !== null && <span>{t("g3Hdg")} <bdi dir="ltr">{fmtNum((readout.primary.hdg + 360) % 360, lang, 4)}°</bdi>
            {readout.primary.pitch !== null && <> · {t("g3Pitch")} <bdi dir="ltr">{fmtNum(readout.primary.pitch, lang, 3)}°</bdi></>}
            {readout.primary.roll !== null && <> · {t("g3Roll")} <bdi dir="ltr">{fmtNum(readout.primary.roll, lang, 3)}°</bdi></>}</span>}
          {(readout.primary.gs !== null || readout.primary.vs !== null) && <span>
            {readout.primary.gs !== null && <>{t("g3Gs")} <bdi dir="ltr">{fmtNum(readout.primary.gs, lang, 4)} m/s</bdi></>}
            {readout.primary.vs !== null && <> · {t("g3Vs")} <bdi dir="ltr">{fmtNum(readout.primary.vs, lang, 3)} m/s</bdi></>}</span>}
          {/* 1.26: the compared object is in the relation box; a third one stays here */}
          {readout.rel.filter((r) => r.name !== secondaryName).map((r) => (
            <span key={r.name} className="g3-rel">
              <i style={{ background: r.color }} />{r.name}: <bdi dir="ltr">{fmtDistance(r.horiz, lang)}</bdi>
              {" "}· Δh <bdi dir="ltr">{r.dz >= 0 ? "+" : ""}{fmtDistance(r.dz, lang)}</bdi>
              {" "}· {t("g3Slant")} <bdi dir="ltr">{fmtDistance(r.slant, lang)}</bdi> · <bdi dir="ltr">{fmtNum(r.brg, lang, 4)}°</bdi>
              {r.closure !== null && <>{" "}· {t("relClosure")} <bdi dir="ltr">{fmtNum(r.closure, lang, 4)} m/s</bdi></>}
              {r.aspect !== null && <>{" "}· {t("relAspect")} <bdi dir="ltr">{fmtNum(r.aspect, lang, 4)}°{r.side ? ` ${r.side}` : ""}</bdi></>}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
