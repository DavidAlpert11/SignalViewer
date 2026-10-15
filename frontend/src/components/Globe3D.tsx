import { useEffect, useMemo, useRef, useState } from "react";
import "cesium/Build/Cesium/Widgets/CesiumWidget/CesiumWidget.css";
import { api } from "../api";
import { actions, pickPath, shownSpan, useApp, type MapObject, type Plot } from "../store";
import { fmtNum, useT } from "../i18n";
import { indexSpan } from "./chartUtil";
import { bearing, fmtDistance, groundDistance, objectAt, visualOrder, type ObjTrack } from "../mapObjects";
import Globe3DFallback from "./Globe3DFallback";

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

/** Can this browser make a WebGL context at all? (No: an old / blocked graphics driver, a virtual
 *  machine or remote desktop - and Chrome / Edge 139+ no longer fall back to software WebGL.) */
function hasWebGL(): boolean {
  try {
    const c = document.createElement("canvas");
    const gl = (c.getContext("webgl2") || c.getContext("webgl")) as WebGLRenderingContext | null;
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    return !!gl;
  } catch { return false; }
}

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

const TILE_MAXZ: Record<string, number> = { osm: 19, esri: 19, light: 16, dark: 16, satellite: 19, topo: 17 };
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

interface Props { plot: Plot; index: number; onLoading: (b: boolean) => void; emptyText: string }

/** An object's values at the time (for the data box and the relations). */
interface ObjState { id: string; name: string; color: string; pos: import("cesium").Cartesian3; lat: number; lon: number; alt: number;
  agl: number | null; hdg: number | null; pitch: number | null; roll: number | null; gs: number | null; vs: number | null }
interface Readout { primary: ObjState; rel: { name: string; color: string; horiz: number; dz: number; slant: number; brg: number }[] }

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

export default function Globe3D({ plot, index, onLoading, emptyText }: Props) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const theme = useApp((s) => s.theme);
  const base = useApp((s) => s.geoBase);
  const cursor = useApp((s) => s.cursor);
  const playMode = useApp((s) => s.playMode);
  const windowSec = useApp((s) => s.windowSec);
  const dataVersion = useApp((s) => s.dataVersion);
  const logs = useApp((s) => s.logs);
  const runsKey = useApp((s) => s.runs.map((r) => r.id).join(","));
  const hostRef = useRef<HTMLDivElement>(null);
  const creditRef = useRef<HTMLDivElement>(null);
  const [cz, setCz] = useState<C | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [lightMode, setLightMode] = useState(false);
  const widgetRef = useRef<import("cesium").CesiumWidget | null>(null);
  const objects: MapObject[] = useMemo(() => plot.objects ?? [], [plot.objects]);
  const objKey = objects.map((o) => [o.id, o.lat, o.lon, o.alt, o.yaw, o.pitch, o.roll, o.qw, o.qx, o.qy, o.qz].join(":")).join("|");
  /* what the models, lines and labels are built from: they are rebuilt only when this changes - not
     for every change of the plot (time of its own, camera, primary object...), which gives a new
     objects array each time and made the models vanish while they loaded again */
  const objLook = objects.map((o) => [o.id, o.kind, o.color, o.name, o.size, o.trail, o.altRef, o.angleUnit].join(":")).join("|");
  const [tracks, setTracks] = useState<Record<string, Track3>>({});
  /* per object, built once (when the objects or their data change) and only moved as time passes:
     rebuilding lines, colours (materials) and labels every frame held playback below 1 fps */
  interface Drawn { idx: number[]; pos: import("cesium").Cartesian3[]; full: import("cesium").Polyline | null; part: import("cesium").Polyline | null;
    fullMat: import("cesium").Material | null; label: import("cesium").Label | null }
  // two line collections: the whole tracks (only rebuilt with the data) and the parts shown (change as time passes)
  const scene3 = useRef<{ models: Map<string, import("cesium").Model>; lines: import("cesium").PolylineCollection | null; parts: import("cesium").PolylineCollection | null;
    labels: import("cesium").LabelCollection | null; links: import("cesium").PolylineCollection | null; linkLabels: import("cesium").LabelCollection | null;
    events: import("cesium").PointPrimitiveCollection | null; eventLabels: import("cesium").LabelCollection | null;
    measure: import("cesium").PolylineCollection | null; measurePts: import("cesium").PointPrimitiveCollection | null;
    drawn: Map<string, Drawn>; fitted: boolean }>({ models: new Map(), lines: null, parts: null, labels: null, links: null, linkLabels: null,
      events: null, eventLabels: null, measure: null, measurePts: null, drawn: new Map(), fitted: false });
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
        const terrain = new Cz.CustomHeightmapTerrainProvider({
          width: 65, height: 65, tilingScheme: new Cz.GeographicTilingScheme(),
          callback: (x: number, y: number, level: number) => fetch(`/api/terrain/${level}/${x}/${y}`)
            .then((r) => (r.ok ? r.arrayBuffer() : null)).then((b) => (b ? new Float32Array(b) : new Float32Array(65 * 65))),
        });
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
        if (w.scene.sun) w.scene.sun.show = false;          // (their textures are not shipped)
        if (w.scene.moon) w.scene.moon.show = false;
        w.scene.globe.depthTestAgainstTerrain = true;
        w.scene.globe.showGroundAtmosphere = false;
        w.scene.fog.enabled = false;
        widgetRef.current = w;
        const S0 = scene3.current;
        S0.measure = w.scene.primitives.add(new Cz.PolylineCollection());
        S0.measurePts = w.scene.primitives.add(new Cz.PointPrimitiveCollection());
        // measuring: two clicks on the ground (a third starts again)
        const h = new Cz.ScreenSpaceEventHandler(w.scene.canvas);
        h.setInputAction((e: { position: import("cesium").Cartesian2 }) => {
          if (!measuringRef.current) return;
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
        events: null, eventLabels: null, measure: null, measurePts: null, drawn: new Map(), fitted: false };
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
    const online = base === "auto" ? (dark ? "dark" : "osm") : base;
    if (online !== "offline" && TILE_MAXZ[online]) {
      w.imageryLayers.addImageryProvider(new cz.UrlTemplateImageryProvider({ url: `/api/tiles/${online}/{z}/{x}/{y}`, maximumLevel: TILE_MAXZ[online], tilingScheme: merc }));
    }
    w.scene.requestRender();
  }, [cz, base, theme]);

  /* ------------------------------------------------------------- objects */
  useEffect(() => {
    if (failed) return;                                 // the simplified view (no WebGL) fetches its own
    let cancelled = false;
    (async () => {
      const out: Record<string, Track3> = {};
      for (const o of plot.objects ?? []) {
        try {
          const r = await api.objectTrack(o);
          out[o.id] = { t: r.t, lat: r.lat, lon: r.lon, yaw: r.yaw, course: r.course, units: r.units, alt: r.alt, pitch: r.pitch, roll: r.roll, ground: r.ground };
        } catch { /* a signal no longer open */ }
      }
      if (!cancelled) setTracks(out);
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [objKey, dataVersion, runsKey, failed]);

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
    let alive = true;
    (async () => {
      for (const o of objects) {
        try {
          const m = await cz.Model.fromGltfAsync({
            url: `/models/${o.kind}.glb`, minimumPixelSize: Math.round((o.size ?? 26) * 1.8), maximumScale: 50000,
            forwardAxis: cz.Axis.X, color: cz.Color.fromCssColorString(o.color), colorBlendMode: cz.ColorBlendMode.MIX, colorBlendAmount: 0.75,
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
      if (o.trail !== false && pos.length > 1) {
        d.fullMat = cz.Material.fromType("Color", { color: col });
        d.full = S.lines.add({ positions: pos, width: 2.5, material: d.fullMat });
        d.part = S.parts.add({ positions: pos, width: 2.5, material: cz.Material.fromType("Color", { color: col }), show: false });
      }
      d.label = S.labels.add({ position: pos[0] ?? cz.Cartesian3.ZERO, text: visualOrder(o.name), font, fillColor: cz.Color.WHITE, show: false,
        outlineColor: cz.Color.fromCssColorString("#0b1118"), outlineWidth: 3, style: cz.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new cz.Cartesian2(22, -22), disableDepthTestDistance: Number.POSITIVE_INFINITY });
      S.drawn.set(o.id, d);
    }
    updateRef.current();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cz, tracks, objKey, objLook]);

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
        const p = objectAt(tr, te, o.angleUnit);
        if (!p) continue;
        let i = 0;
        while (i < tr.t.length - 1 && tr.t[i + 1] <= te) i++;
        const hh = heightAt(o, tr, i);
        if (!Number.isFinite(hh)) continue;
        const pos = cz.Cartesian3.fromDegrees(p.lon, p.lat, hh);
        pts.add({ position: pos, pixelSize: 9, color: cz.Color.fromCssColorString(col[kind]), outlineColor: cz.Color.WHITE, outlineWidth: 1.5,
          disableDepthTestDistance: Number.POSITIVE_INFINITY });
        labs.add({ position: pos, text: visualOrder(ev.text.length > 40 ? ev.text.slice(0, 39) + "…" : ev.text), font, fillColor: cz.Color.WHITE,
          outlineColor: cz.Color.fromCssColorString("#0b1118"), outlineWidth: 3, style: cz.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new cz.Cartesian2(8, 10),
          disableDepthTestDistance: Number.POSITIVE_INFINITY, translucencyByDistance: new cz.NearFarScalar(2e3, 1, 6e4, 0) });
      }
    }
    w.scene.requestRender();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cz, tracks, objKey, objLook, logs, plot.showEvents]);
  const hasEvents = objects.some((o) => (logs[o.lat.slice(0, o.lat.indexOf("/"))]?.events.length ?? 0) > 0);

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
  const saveImage = async () => {
    const w = widgetRef.current;
    if (!w) return;
    const path = await pickPath({ mode: "save", title: t("saveImage"), exts: [".png"], defaultName: "3d-view.png" });
    if (!path) return;
    w.scene.requestRender();
    w.render();
    const url = w.scene.canvas.toDataURL("image/png");
    try {
      const r = await api.saveImage(path, url);
      useApp.getState().toast({ kind: "info", text: t("savedTo", { path: r.path }) });
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
  };

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
    if (!pts.length) return;
    const bs = cz.BoundingSphere.fromPoints(pts);
    w.camera.flyToBoundingSphere(bs, { duration: 0, offset: new cz.HeadingPitchRange(0, cz.Math.toRadians(-35), Math.max(bs.radius * 2.6, 1500)) });
    scene3.current.fitted = true;
    w.scene.requestRender();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cz, tracks]);

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
      const tNow = cur.on && cur.t1 !== null ? cur.t1 : tr.t[tr.t.length - 1];
      const p = objectAt(tr, tNow, o.angleUnit);
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
        const isRad = o.angleUnit === "rad" || ((o.angleUnit ?? "auto") === "auto" && tr.units[key] === "rad");
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
      if (d.label) { d.label.position = pos; d.label.show = true; }
      const { gs, vs } = ratesAt(o, tr, tNow);
      states.set(o.id, { id: o.id, name: o.name, color: o.color, pos, lat: p.lat, lon: p.lon, alt: h, agl, hdg: p.heading,
        pitch: tr.pitch ? cz.Math.toDegrees(pitch) : null, roll: tr.roll ? cz.Math.toDegrees(roll) : null, gs, vs });
      if (o.id === follow) {
        // keep the followed object in the middle; the user's angle and distance stay
        const cam = w.camera;
        const range = cam.positionCartographic ? Math.max(30, cz.Cartesian3.distance(cam.positionWC, pos)) : 2000;
        cam.lookAt(pos, new cz.HeadingPitchRange(cam.heading, cam.pitch, range));
      }
    }
    if (!follow) w.camera.lookAtTransform(cz.Matrix4.IDENTITY);
    // the primary object, and the related ones: a dashed line from it to each, with the distance on it
    const primary = states.get(plot.primaryObject ?? "") ?? states.get(objects[0]?.id ?? "") ?? null;
    const rel: Readout["rel"] = [];
    const related = (plot.relatedObjects ?? []).filter((id) => id !== primary?.id).slice(0, 2);
    S.links?.removeAll();
    S.linkLabels?.removeAll();
    if (primary) {
      for (const id of related) {
        const q = states.get(id);
        if (!q) continue;
        // on the WGS84 ellipsoid, like the slant range (a sphere was ~0.2 % off from it)
        const horiz = new cz.EllipsoidGeodesic(cz.Cartographic.fromDegrees(primary.lon, primary.lat), cz.Cartographic.fromDegrees(q.lon, q.lat)).surfaceDistance;
        const slant = cz.Cartesian3.distance(primary.pos, q.pos);
        rel.push({ name: q.name, color: q.color, horiz, dz: q.alt - primary.alt, slant, brg: bearing(primary.lat, primary.lon, q.lat, q.lon) });
        S.links?.add({ positions: [primary.pos, q.pos], width: 2, material: linkMat(cz.Color.fromCssColorString(q.color)) });
        S.linkLabels?.add({ position: cz.Cartesian3.midpoint(primary.pos, q.pos, new cz.Cartesian3()), text: fmtDistance(slant, st.lang),
          font: `600 12px ${getComputedStyle(document.body).fontFamily}`, fillColor: cz.Color.WHITE, outlineColor: cz.Color.fromCssColorString("#0b1118"),
          outlineWidth: 3, style: cz.LabelStyle.FILL_AND_OUTLINE, disableDepthTestDistance: Number.POSITIVE_INFINITY });
      }
    }
    setReadout(primary ? { primary, rel } : null);
    w.scene.requestRender();
  };
  const updateRef = useRef(update);
  updateRef.current = update;
  useEffect(() => { updateRef.current(); }, [cz, tracks, cursor, playMode, windowSec, plot.followObject, plot.primaryObject, plot.relatedObjects, objects, lang, ownT]);

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

  const primaryId = (plot.primaryObject && objects.some((o) => o.id === plot.primaryObject) ? plot.primaryObject : objects[0]?.id) ?? "";
  const centred = !!plot.followObject;
  const showBox = plot.showReadout !== false;
  const reFit = () => { scene3.current.fitted = false; setTracks((x) => ({ ...x })); };

  if (failed) return <Globe3DFallback plot={plot} index={index} onLoading={onLoading} reason={failed} />;
  return (
    <div className={`globe3d${detached ? " own-time" : ""}`} onDoubleClick={reFit}>
      <div ref={hostRef} className="globe3d-host" />
      <div ref={creditRef} className="globe3d-credits" />
      {!cz && <div className="plot-empty">{t("globeLoading")}</div>}
      {cz && !objects.length && <div className="plot-empty">{emptyText}</div>}
      {lightMode && <div className="globe3d-light" title={t("globeLightHint")}>{t("globeLight")}</div>}
      {/* the camera, the primary object and the related ones, the data box */}
      {cz && objects.length > 0 && (
        <div className="globe3d-bar" role="toolbar" aria-label={t("g3Bar")}>
          <label><span>{t("g3Primary")}</span>
            <select value={primaryId} aria-label={t("g3Primary")}
              onChange={(e) => actions.updatePlot(plot.id, { primaryObject: e.target.value, ...(centred ? { followObject: e.target.value } : {}),
                relatedObjects: (plot.relatedObjects ?? []).filter((x) => x !== e.target.value) })}>
              {objects.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select></label>
          <span className="g3-seg" role="radiogroup" aria-label={t("g3Camera")}>
            <span className="g3-seg-label">{t("g3Camera")}</span>
            <button role="radio" aria-checked={!centred} className={!centred ? "on" : ""} onClick={() => actions.updatePlot(plot.id, { followObject: null })}>{t("g3CamFree")}</button>
            <button role="radio" aria-checked={centred} className={centred ? "on" : ""} title={t("g3CamCentreHint")}
              onClick={() => actions.updatePlot(plot.id, { followObject: primaryId })}>{t("g3CamCentre")}</button>
          </span>
          {[0, 1].map((k) => (objects.length > k + 1 && (
            <label key={k}><span>{t(k === 0 ? "g3Second" : "g3Third")}</span>
              <select value={(plot.relatedObjects ?? [])[k] ?? ""} aria-label={t(k === 0 ? "g3Second" : "g3Third")}
                onChange={(e) => {
                  const cur = [...(plot.relatedObjects ?? [])];
                  cur[k] = e.target.value;
                  actions.updatePlot(plot.id, { relatedObjects: cur.filter((x, i) => !!x && x !== primaryId && cur.indexOf(x) === i) });
                }}>
                <option value="">—</option>
                {objects.filter((o) => o.id !== primaryId && (k === 0 || o.id !== (plot.relatedObjects ?? [])[0])).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select></label>
          )))}
          <button className={`g3-toggle${showBox ? " on" : ""}`} aria-pressed={showBox} onClick={() => actions.updatePlot(plot.id, { showReadout: !showBox })}>{t("g3Data")}</button>
          {hasEvents && <button className={`g3-toggle${plot.showEvents !== false ? " on" : ""}`} aria-pressed={plot.showEvents !== false}
            onClick={() => actions.updatePlot(plot.id, { showEvents: plot.showEvents === false })} title={t("g3EventsHint")}>{t("g3Events")}</button>}
          <button className={`g3-toggle${measuring ? " on" : ""}`} aria-pressed={measuring} title={t("g3MeasureHint")}
            onClick={() => { setMeasuring(!measuring); setMeasurePts([]); }}>{t("g3Measure")}</button>
          <button className="g3-toggle" onClick={saveImage} title={t("saveImage")}>{t("g3Image")}</button>
          <button className="g3-toggle g3-remove" onClick={() => actions.remove3d(plot.id)} title={t("g3RemoveHint")} aria-label={t("g3Remove")}>✕</button>
          <span className="g3-seg" role="radiogroup" aria-label={t("g3Time")}>
            <span className="g3-seg-label">{t("g3Time")}</span>
            <button role="radio" aria-checked={!detached} className={!detached ? "on" : ""} onClick={attach} title={t("g3TimeSharedHint")}>{t("g3TimeShared")}</button>
            <button role="radio" aria-checked={detached} className={detached ? "on" : ""} onClick={() => { if (!detached) detach(); }} title={t("g3TimeOwnHint")}>{t("g3TimeOwn")}</button>
          </span>
        </div>
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
          {readout.rel.map((r) => (
            <span key={r.name} className="g3-rel">
              <i style={{ background: r.color }} />{r.name}: <bdi dir="ltr">{fmtDistance(r.horiz, lang)}</bdi>
              {" "}· Δh <bdi dir="ltr">{r.dz >= 0 ? "+" : ""}{fmtDistance(r.dz, lang)}</bdi>
              {" "}· {t("g3Slant")} <bdi dir="ltr">{fmtDistance(r.slant, lang)}</bdi> · <bdi dir="ltr">{fmtNum(r.brg, lang, 4)}°</bdi>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
