/** The welcome screen's examples (backend routes/fs.py EXAMPLE_SETS). */
export type ExampleId = "flight" | "twoFlights" | "car" | "ardupilot";
export interface SignalTransform { expr?: string; scale?: number; offset?: number; dt?: number }
export interface SignalInfo {
  id: string; name: string; discrete?: boolean;
  n?: number; rate?: number;            // T22: samples and mean sample rate (Hz), from the describe
  labels?: Record<string, string>;      // text values: code -> text (states, flight modes)
  transform?: SignalTransform;          // a change made on the signal itself
  // derived signals only
  op?: string; sources?: string[]; params?: Record<string, unknown>; formula?: string; valid?: boolean; samples?: number;
}
/** Live MAVLink receiver (T12): the link is recorded to `path` (.tlog), which live mode follows. */
export interface MavStatus {
  running: boolean; conn?: string; path?: string; frames?: number; bytes?: number; written?: number; rate?: number;
  request?: boolean; sinceData?: number | null; sinceHeartbeat?: number | null; vehicle?: number[] | null; error?: string | null;
}
export interface RunInfo {
  id: string;
  name: string;
  path: string;
  format: "csv" | "mat" | "bin" | "tlog" | "ulg" | "mcap" | "hdf5" | "parquet" | "derived";
  tag?: string;                          // T46: the file's short tag (A, B... or the user's); not for derived
  color?: string;                        // T46: the file's colour
  /** Only for files that carry a flight log's parameters / events (ArduPilot .bin). */
  log?: { params: number; events: number; errors: number; warnings: number };
  samples: number;
  start: number;
  end: number;
  timeOffset: number;
  importSettings: Record<string, unknown>;
  signals: SignalInfo[];
  report?: { skipped?: string[]; skippedColumns?: string[]; droppedRows?: number; sorted?: boolean; fromCache?: boolean; rememberedSettings?: boolean;
    textColumns?: string[]; tooManyTexts?: string[]; timePairs?: number; vehicle?: string | null; corruptBytes?: number; cutOff?: boolean; damagedText?: boolean; damagedObjects?: number; noTime?: boolean; params?: number;
    paramValues?: Record<string, number>; logMessages?: { t: number; text: string }[] };
  description?: string;
  copy?: boolean;                        // opened from a dragged-in copy, not the original file
}
export interface Series {
  id: string;
  missing?: boolean;
  n: number;
  total: number;
  decimated: boolean;
  x: Float64Array;
  y: Float32Array;
}
export interface Stats { min: number; max: number; mean: number; std: number; rms: number; peak_to_peak: number; samples: number; duration: number; segments?: number }
export interface CompareRow { id: string; valid: boolean; matchPct?: number; samples?: number; rmsDiff?: number; maxAbsDiff?: number; meanDiff?: number; rmsPct?: number; correlation?: number; withinPct?: number; pass?: boolean }
export interface CompareFileStats { run: string; mean: number | null; std: number | null; min: number | null; max: number | null; rms: number | null }
export interface CompareDiff { run: string; rmsDiff: number; rmsPct: number; maxAbsDiff: number; meanDiff: number; stdDiff: number; correlation: number; withinPct?: number | null; pass?: boolean | null }
export interface CompareAllRow {
  name: string; runs?: string[]; baseline?: string; error?: string;
  meanSpread?: number | null; stdSpread?: number | null; worstRmsDiff?: number | null; worstRmsPct?: number | null;
  worstMaxAbs?: number | null; minCorrelation?: number | null; pass?: boolean | null;
  matchPct?: number | null; profile?: (number | null)[] | null;
  files?: CompareFileStats[]; diffs?: CompareDiff[];
}
export interface JobInfo { id: string; kind: string; label: string; state: "running" | "done" | "error" | "cancelled"; progress: number; phase: string; error: string | null; result: any; elapsed: number }
/** Why a file could not be opened: `code` (+ params) is translated by the UI; `message` is the English fallback. */
export interface LoadErrorInfo { path: string; message: string; code?: string; params?: Record<string, string | number> }
/** Where templates are kept (the user can choose the folder). */
export interface TemplateFolderInfo { folder: string; default: boolean; exists: boolean; defaultFolder: string }
/** T24: the file dialog's side column. */
export interface FsPlaces {
  open: string[];                                         // folders of the open files
  favourites: { path: string; exists: boolean }[];        // pinned, in the user's order
  recent: { path: string; exists: boolean }[];            // folders of recent files / sessions
  standard: { id: "home" | "desktop" | "documents" | "downloads"; path: string }[];
  drives: string[];
}

export interface RecentItem { path: string; kind: "file" | "session"; time: number; name: string; folder: string; exists: boolean }
export interface FsEntry { name: string; path: string; dir: boolean; size?: number | null; mtime?: number }

/* Templates (version 2): a set of tabs whose signals are stored by NAME, each from a file SLOT;
   when a template is opened, every slot is given an open file (or "all files that fit"). A template
   can also include other templates (a collection). One JSON file per template in the templates folder. */
export interface LimitResult { lo: number | null; hi: number | null; samples: number; pass: boolean; violations: number;
  timeOutside: number; first: number | null; worst: number | null; worstT: number | null; spans: [number, number][] }
export interface TplSignal { limits?: { lo?: number | null; hi?: number | null }; name: string; slot?: string; color?: string; width?: number; scale?: number; offset?: number;
  state?: boolean; tOffset?: number; label?: string }
export interface TplPlot { title: string; mode?: string; xSignal?: string | null; xSlot?: string; xyAlign?: string; fftWindow?: string; fftMethod?: string;
  fftLog?: boolean; specN?: number; caption?: string; ylim?: [number, number] | null; signals: TplSignal[]; objects?: TplObject[] }
/** A map object in a template: each of its signals by name (alternatives "a|b" allowed) and file slot. */
export type TplObjectRole = "lat" | "lon" | "alt" | "yaw" | "pitch" | "roll" | "qw" | "qx" | "qy" | "qz";
export interface TplObject { name: string; kind: string; color?: string; roles: Partial<Record<TplObjectRole, { name: string; slot?: string }>>;
  angleUnit?: string; altRef?: string; trail?: boolean; size?: number }
export interface TplTab { name: string; rows: number; cols: number; rowSizes?: number[]; colSizes?: number[]; linkX?: boolean;
  linkY?: boolean; lanes?: { name: string; slot?: string }[]; plots: TplPlot[] }
/** A file the template takes. file / path: the file it was saved from (to find the same file again when opened). */
export interface TplSlot { id: string; name: string; formats?: string[]; file?: string; path?: string }
/** A template tab with real signal ids for the open files (/api/templates/resolve). */
export interface ResolvedTab {
  name: string; rows: number; cols: number; rowSizes?: number[] | null; colSizes?: number[] | null; linkX?: boolean; linkY?: boolean | null;
  sharedStates?: string[] | null;
  plots: { title: string; mode?: string; xSignal?: string | null; xyAlign?: string; fftWindow?: string; fftMethod?: string; fftLog?: boolean;
    specN?: number; caption?: string; ylim?: [number, number] | null;
    signals: { sig: string; color: string | null; width?: number; scale?: number; offset?: number; state?: boolean | null; tOffset?: number | null;
      label?: string | null; limits?: { lo?: number | null; hi?: number | null } }[];
    objects?: { name: string; kind?: string; color?: string | null; lat: string; lon: string; alt?: string | null; yaw?: string | null; pitch?: string | null;
      roll?: string | null; qw?: string | null; qx?: string | null; qy?: string | null; qz?: string | null; angleUnit?: string; altRef?: string;
      trail?: boolean; size?: number }[] }[];
}
export interface Template {
  version: 2; id: string; name: string; description?: string; group?: string;
  slots: TplSlot[]; tabs: TplTab[]; includes?: string[];
  generator?: "quicklook" | "compare" | "objects";   // built-in templates whose tabs are made from the files themselves
  builtin?: boolean; saved?: number; file?: string; broken?: boolean;
}

async function call<T>(url: string, body?: unknown, method = body === undefined ? "GET" : "POST"): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail ?? msg; } catch { /* keep status text */ }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

function decode<T extends Float64Array | Float32Array>(b64: string, Ctor: { new (buf: ArrayBuffer): T }): T {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Ctor(bytes.buffer);
}

/** T41: the fleet index (backend app/fleet.py). */
export interface FleetFolder { folder: string; added: number; last_scan: number | null; logs: number }
export interface FleetKey { key: string; logs: number; min: number; max: number }
export interface FleetFinding { code: string; level: "error" | "warning" | "ok"; t: number | null; vals: Record<string, number | string> }
export interface FleetLog {
  path: string; name: string; format: string; vehicle: string | null; firmware: string | null; date: number;
  date_source: "gps" | "file"; duration: number | null; errors: number; warnings: number; error: string | null;
  findings: FleetFinding[]; metrics: Record<string, number>; modes: Record<string, number>;
}

/** T31: the user's own Python operations (backend app/pyops.py). */
export interface PyOp { id: string; name: string; inputs: number; doc: string; params: Record<string, number | string | boolean> }
export interface PyOpsInfo { folder: string; default: boolean; exists: boolean; ops: PyOp[]; errors: { file: string; error: string }[] }

export const api = {
  listRuns: () => call<RunInfo[]>("/api/runs"),
  clientError: (b: { message: string; stack: string; where: string }) => call<{ logged: boolean }>("/api/client-error", b),
  pyops: () => call<PyOpsInfo>("/api/pyops"),
  pyopsReload: () => call<PyOpsInfo>("/api/pyops/reload", {}),
  pyopsFolder: (path: string | null) => call<PyOpsInfo>("/api/pyops/folder", { path }),
  pyopsExample: () => call<PyOpsInfo & { example: string }>("/api/pyops/example", {}),
  pyopsReveal: () => call<{ folder: string }>("/api/pyops/reveal", {}),
  pushEvents: (since: number, opens = false) => call<{ seq: number; events: { seq: number; kind?: "open"; paths?: string[]; run?: string; name?: string; plot?: boolean; new?: boolean; age: number }[] }>(`/api/push/events?since=${since}${opens ? "&opens=1" : ""}`),
  pushSaveClient: (path: string) => call<{ path: string }>("/api/push/save-client", { path }),
  fleet: () => call<{ folders: FleetFolder[]; keys: FleetKey[] }>("/api/fleet"),
  fleetAdd: (path: string) => call<JobInfo>("/api/fleet/folder", { path }),
  fleetRescan: () => call<JobInfo>("/api/fleet/rescan", {}),
  fleetRemove: (path: string) => call<{ folders: FleetFolder[] }>("/api/fleet/remove", { path }),
  fleetLogs: (q: Record<string, string | number>) => call<{ logs: FleetLog[] }>(`/api/fleet/logs?${new URLSearchParams(Object.entries(q).map(([k, v]) => [k, String(v)]))}`),
  fleetTrend: (key: string) => call<{ points: { path: string; name: string; date: number; date_source: string; value: number }[] }>(`/api/fleet/trend?key=${encodeURIComponent(key)}`),
  diagnostics: () => call<{ text: string; logFile: string; version: string }>("/api/diagnostics"),
  runLog: (id: string) => call<LogInfo>(`/api/runs/${encodeURIComponent(id)}/log`),
  syncSuggest: (ref: string, other: string, refSignal?: string | null, otherSignal?: string | null,
    opts: { feature?: { kind: string; levelPct?: number; occurrence?: number }; maxLag?: number | null } = {}) =>
    call<{ candidates: SyncCandidate[] }>("/api/sync/suggest", { ref, other, refSignal: refSignal ?? null, otherSignal: otherSignal ?? null,
      feature: opts.feature ?? null, maxLag: opts.maxLag ?? null }),
  runHealth: (id: string) => call<HealthReport>(`/api/runs/${encodeURIComponent(id)}/health`),
  spectrogram: (signal: string, x0: number | null, x1: number | null, nfft: number, width: number, height: number, fmax: number | null) =>
    call<SpecData>("/api/spectrogram", { signal, x0, x1, nfft, width, height, fmax }),
  open: (paths: string[], settings?: Record<string, unknown>) =>
    call<{ opened: RunInfo[]; errors: LoadErrorInfo[] }>("/api/files/open", { paths, settings }),
  suggestFiles: (path: string) => call<{ candidates: { path: string; name: string; mtime: number; similar: boolean }[]; best: string | null }>("/api/files/suggest", { path }),
  fileSignals: (path: string, settings?: unknown) => call<{ signals: string[] }>("/api/files/signals", { path, settings }),
  locate: (files: { name: string; size: number; mtime: number }[]) => call<{ paths: (string | null)[] }>("/api/files/locate", { files }),
  upload: async (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    const res = await fetch("/api/files/upload", { method: "POST", body: fd });
    if (!res.ok) throw new Error(res.statusText);
    return (await res.json()) as { paths: string[]; skipped?: string[] };
  },
  preview: (path: string, settings?: Record<string, unknown>) => call<any>("/api/files/preview", { path, settings }),
  remove: (id: string) => call<{ ok: boolean }>(`/api/runs/${id}`, undefined, "DELETE"),
  patchRun: (id: string, patch: { name?: string; timeOffset?: number; description?: string; tag?: string; color?: string }) => call<RunInfo>(`/api/runs/${id}`, patch, "PATCH"),
  replace: (id: string, path: string) => call<RunInfo>(`/api/runs/${id}/replace`, { path }),
  previewDerived: async (op: string, sources: string[], params: Record<string, unknown>, x0: number | null, x1: number | null) => {
    const r = await call<{ n: number; x: string; y: string }>("/api/derived/preview", { op, sources, params, x0, x1 });
    return { x: decode(r.x, Float64Array), y: decode(r.y, Float32Array) };
  },
  reportPreview: (body: Record<string, unknown>) => call<{ html: string }>("/api/report/preview", body),
  reload: (id: string) => call<RunInfo>(`/api/runs/${id}/reload`, {}),
  poll: () => call<{ changed: string[]; runs: RunInfo[] | null; errors?: Record<string, string>;
    activity?: Record<string, number>; newFiles?: { path: string; name: string; size: number; mtime: number }[]; writing?: string[] }>("/api/stream/poll", {}),
  streamStart: (lookBack = 0) => call<{ ok: boolean }>("/api/stream/start", { lookBack }),
  streamStop: () => call<{ ok: boolean }>("/api/stream/stop", {}),
  mavlinkStart: (body: { conn: string; baud?: number; request?: boolean; rate?: number }) => call<MavStatus>("/api/mavlink/start", body),
  mavlinkStop: () => call<MavStatus>("/api/mavlink/stop", {}),
  mavlinkStatus: () => call<MavStatus>("/api/mavlink/status"),
  mavlinkPorts: () => call<{ ports: { device: string; description: string }[]; presets: string[]; folder: string }>("/api/mavlink/ports"),
  data: async (signals: string[], x0: number | null, x1: number | null, points: number): Promise<Series[]> => {
    const r = await call<{ series: any[] }>("/api/data", { signals, x0, x1, points });
    return r.series.map((s) =>
      s.missing ? { id: s.id, missing: true, n: 0, total: 0, decimated: false, x: new Float64Array(), y: new Float32Array() }
        : { ...s, x: decode(s.x, Float64Array), y: decode(s.y, Float32Array) });
  },
  createDerived: (op: string, sources: string[], params: Record<string, unknown>, name?: string) =>
    call<{ id: string; name: string; runs: RunInfo[] }>("/api/derived", { op, sources, params, name: name || null }),
  restoreDerived: (items: { op: string; sources: string[]; params?: unknown; name?: string }[]) =>
    call<{ restored: string[]; failed: { name: string; message: string }[]; runs: RunInfo[] }>("/api/derived/restore", { items }),
  deleteDerived: (name: string) => call<{ runs: RunInfo[] }>(`/api/derived/${encodeURIComponent(name)}`, undefined, "DELETE"),
  fft: async (signals: string[], window: string, t0: number | null, t1: number | null, points: number, method: "fft" | "welch" = "fft") => {
    const r = await call<{ series: any[] }>("/api/fft", { signals, window, method, t0, t1, points });
    return r.series.map((s) => (s.missing ? { id: s.id, missing: true, n: 0, peak: NaN, x: new Float64Array(), y: new Float32Array() }
      : { ...s, x: decode(s.x, Float64Array), y: decode(s.y, Float32Array) })) as { id: string; missing?: boolean; n: number; peak: number; x: Float64Array; y: Float32Array }[];
  },
  xy: async (x: string, ys: string[], alignment: string, t0: number | null, t1: number | null) => {
    const r = await call<{ series: any[] }>("/api/xy", { x, ys, alignment, t0, t1 });
    // t: the time of each point, so the timeline can draw the plot / map up to a time
    return r.series.map((s) => (s.missing ? { id: s.id, missing: true, n: 0, x: new Float64Array(), y: new Float32Array(), t: new Float64Array() }
      : { ...s, x: decode(s.x, Float64Array), y: decode(s.y, Float32Array), t: s.t ? decode(s.t, Float64Array) : new Float64Array() })) as
      { id: string; missing?: boolean; n: number; x: Float64Array; y: Float32Array; t: Float64Array }[];
  },
  /** T17c plain 3D: each track's Y and Z on its X signal's samples. */
  xyz: async (tracks: { x: string; y: string; z: string }[], alignment: string) => {
    const r = await call<{ tracks: any[] }>("/api/xyz", { tracks, alignment });
    return r.tracks.map((s) => (s.missing || s.empty ? { id: s.id as string, missing: !!s.missing, empty: !!s.empty } as const
      : { id: s.id as string, t: decode(s.t, Float64Array), x: decode(s.x, Float32Array), y: decode(s.y, Float32Array), z: decode(s.z, Float32Array) }));
  },
  /** An object on the map: its signals on one time axis (see the server's object_track). */
  objectTrack: async (o: { lat: string; lon: string; alt?: string | null; yaw?: string | null; pitch?: string | null; roll?: string | null;
    qw?: string | null; qx?: string | null; qy?: string | null; qz?: string | null }) => {
    const r = await call<{ n: number; t: string; lat: string; lon: string; alt?: string; yaw?: string; pitch?: string; roll?: string;
      course: string; ground?: string; units: Record<string, "deg" | "rad"> }>("/api/object_track", o);
    const f = (s?: string) => (s ? decode(s, Float32Array) : null);
    return { n: r.n, t: decode(r.t, Float64Array), lat: decode(r.lat, Float64Array), lon: decode(r.lon, Float64Array),
      alt: f(r.alt), yaw: f(r.yaw), pitch: f(r.pitch), roll: f(r.roll), course: decode(r.course, Float32Array), ground: f(r.ground), units: r.units };
  },
  states: (signals: string[], x0: number | null, x1: number | null, bins = 1500) =>
    call<{ states: Record<string, { points: [number, number | null][]; tooMany: boolean; end: number | null }> }>("/api/states", { signals, x0, x1, bins }),
  neighbor: async (signal: string, t: number, steps: number) => {
    const r = await call<{ t: number | null }>("/api/neighbor", { signal, t, steps });
    return r;
  },
  cursor: (signals: string[], t: number) => call<{ values: Record<string, number | null> }>("/api/cursor", { signals, t }),
  sparks: (signals: string[], points = 40) => call<{ sparks: Record<string, { lo: (number | null)[]; hi: (number | null)[] } | null> }>("/api/sparks", { signals, points }),
  stats: (signals: string[], t0: number | null, t1: number | null, where?: { state: string; values: number[]; offset?: number } | null) =>
    call<{ stats: Record<string, Stats> }>("/api/stats", { signals, t0, t1,
      ...(where ? { state: where.state, stateValues: where.values, stateOffset: where.offset ?? 0 } : {}) }),
  limits: (items: { id: string; lo: number | null; hi: number | null; scale: number; offset: number; tOffset: number }[], t0: number | null, t1: number | null) =>
    call<{ results: Record<string, LimitResult> }>("/api/limits", { items, t0, t1 }),
  envelope: async (signals: { id: string; scale: number; offset: number; tOffset: number }[], t0: number | null, t1: number | null, points: number) => {
    const r = await call<{ n: number; empty?: boolean; pct?: number; t?: string; min?: string; max?: string; lo?: string; hi?: string; median?: string;
      runs?: { id: string; deviation: number; outlier: boolean }[] }>("/api/envelope", { signals, t0, t1, points });
    if (r.empty) return { n: r.n, empty: true as const };
    const f = (k: "min" | "max" | "lo" | "hi" | "median") => decode(r[k]!, Float32Array);
    return { n: r.n, empty: false as const, pct: r.pct, runs: r.runs ?? [], t: decode(r.t!, Float64Array),
      min: f("min"), max: f("max"), lo: f("lo"), hi: f("hi"), median: f("median") };
  },
  segments: (signal: string) => call<{ total: number;
    segments: { t0: number; t1: number; value: number; label: string | null }[];
    byValue: { value: number; label: string | null; duration: number; count: number }[] }>("/api/segments", { signal }),
  examples: () => call<{ id: ExampleId; paths: string[] }[]>("/api/examples"),
  completePath: (text: string, base: string | null, exts?: string[]) =>
    call<{ dir: string | null; items: { name: string; path: string; dir: boolean }[]; common: string }>("/api/fs/complete", { text, base, exts }),
  listDir: (path?: string | null, exts?: string[]) => call<{ path: string; parent: string | null; entries: FsEntry[]; hidden?: number }>("/api/fs/list", { path, exts }),
  places: () => call<FsPlaces>("/api/fs/places"),
  setFavourites: (paths: string[]) => call<{ favourites: { path: string; exists: boolean }[] }>("/api/fs/favourites", { paths }, "PUT"),
  compare: (signals: string[], baseline: string, alignment: string, tolAbs: number | null, tolPct: number | null,
    windows?: Record<string, [number, number]> | null) =>
    call<{ overlap: [number, number]; gridPoints: number; baseline: string; rows: CompareRow[] }>("/api/compare", { signals, baseline, alignment, tolAbs, tolPct, windows: windows ?? null }),
  segmentsAcross: (runs: string[], state: string, value: number, occurrence: number) =>
    call<{ windows: import("./segments").SegWindow[] }>("/api/segments/across", { runs, state, value, occurrence }),
  compareAll: (runs: string[], baselineRun: string, alignment: string, tolAbs: number | null, tolPct: number | null) =>
    call<{ signals: CompareAllRow[] }>("/api/compare/all", { runs, baselineRun, alignment, tolAbs, tolPct }),
  shift: (base: string, other: string) => call<{ shift: number }>("/api/compare/shift", { base, other }),
  exportCsv: (path: string, signals: { id: string; label: string; scale: number; offset: number; tOffset?: number }[], t0: number | null, t1: number | null) =>
    call<{ path: string; rows: number }>("/api/export/csv", { path, signals, t0, t1 }),
  report: (body: Record<string, unknown>) => call<{ path: string; size: number }>("/api/report", body),
  image: (path: string, format: "png" | "svg", theme: string, plot: unknown) => call<{ path: string }>("/api/export/image", { path, format, theme, plot }),
  discrete: (sig: string) => call<{ discrete: boolean }>(`/api/discrete?sig=${encodeURIComponent(sig)}`),
  recent: () => call<{ items: RecentItem[] }>("/api/recent"),
  forgetRecent: (path: string) => call<{ items: RecentItem[] }>("/api/recent/forget", { path }),
  forgetImport: (path: string) => call<{ ok: boolean }>("/api/import/forget", { path }),
  templates: () => call<{ templates: Template[]; builtin: Template[] } & TemplateFolderInfo>("/api/templates"),
  // T11b: matching runs in the backend (svcore/templates.py) - the same code the batch reports use
  templateFits: (templates: Template[]) => call<{ fits: Record<string, number | null> }>("/api/templates/fit", { templates }),
  bindTemplate: (template: Template, all: Template[], prefer?: string | null) =>
    call<{ bind: Record<string, string>; slots: { id: string; names: number; counts: Record<string, number> }[] }>("/api/templates/bind", { template, all, prefer: prefer ?? null }),
  resolveTemplate: (template: Template, all: Template[], bind: Record<string, string>, chosen: number[] | null, extraTabs: TplTab[]) =>
    call<{ tabs: ResolvedTab[]; dropped: string[]; missing: string[] }>("/api/templates/resolve", { template, all, bind, chosen, extraTabs }),
  setTemplateFolder: (path: string | null) => call<TemplateFolderInfo & { copied: number }>("/api/templates/folder", { path }),
  saveTemplate: (template: Template, replace = true) => call<{ template: Template }>("/api/templates", { template, replace }),
  deleteTemplate: (id: string) => call<{ ok: boolean }>(`/api/templates/${encodeURIComponent(id)}`, undefined, "DELETE"),
  importTemplates: (path: string) => call<{ templates: Template[] }>("/api/templates/import", { path, ids: [] }),
  exportTemplates: (ids: string[], path: string) => call<{ path: string }>("/api/templates/export", { path, ids }),
  revealTemplates: () => call<{ folder: string }>("/api/templates/reveal", {}),
  setTransforms: (signals: string[], transform: SignalTransform | null) =>
    call<{ previous: Record<string, SignalTransform | null>; runs: RunInfo[] }>("/api/transforms", { signals, transform }),
  setTransformSpecs: (specs: Record<string, SignalTransform | null>) =>
    call<{ previous: Record<string, SignalTransform | null>; runs: RunInfo[] }>("/api/transforms", { specs }),
  startJob: (kind: string, body: unknown, label: string) => call<JobInfo>("/api/jobs", { kind, body, label }),
  job: (id: string) => call<JobInfo>(`/api/jobs/${id}`),
  cancelJob: (id: string) => call<{ cancelled: boolean }>(`/api/jobs/${id}/cancel`, {}),
  saveImage: (path: string, dataUrl: string) => call<{ path: string }>("/api/save/image", { path, data: dataUrl }),
  saveText: (path: string, content: string, ext = ".csv", bom = true) => call<{ path: string }>("/api/save/text", { path, content, ext, bom }),
  saveSession: (path: string, state: unknown) => call<{ path: string }>("/api/session/save", { path, state }),
  loadSession: (path: string) => call<{ state: any; converted: boolean }>("/api/session/load", { path }),
  getAutosave: () => call<{ state: any; damaged?: string }>("/api/autosave"),
  errorSegments: (a: string, b: string, state: string | null, alignment: string) => call<{
    total: ErrStat; rows: (ErrStat & { t0: number; t1: number; value: number; label: string | null; occurrence: number })[] }>("/api/error-segments", { a, b, state, alignment }),
  getSettings: () => call<{ settings: Record<string, unknown> }>("/api/settings"),
  putSettings: (changes: Record<string, unknown>) => call<{ settings: Record<string, unknown> }>("/api/settings", { changes }, "PUT"),
  putAutosave: (state: unknown) => call<{ ok: boolean }>("/api/autosave", state),
  restore: (runs: unknown[]) => call<{ restored: RunInfo[]; missing: any[] }>("/api/session/restore", { runs }),
};

export type LogLevel = "info" | "warning" | "error";
export interface LogEvent { t: number; kind: "msg" | "mode" | "event" | "error"; text: string; level: LogLevel }
export interface LogParam { name: string; value: number; first: number; default: number | null; changes: [number, number][] }
export interface LogInfo {
  vehicle: string | null; firmware: string | null; hasDefaults: boolean; timeOffset: number;
  params: LogParam[]; events: LogEvent[];
}

export interface HealthFinding {
  code: string; level: "ok" | "warning" | "error"; vals: Record<string, any>; t: number | null;
  spans: [number, number][]; signals: string[];
}
export interface HealthReport { findings: HealthFinding[]; errors: number; warnings: number }
/** T25: the error A − B over some time. */
export interface ErrStat { n: number; rms?: number; mean?: number; maxAbs?: number; tMaxAbs?: number }
export interface SpecData {
  nf: number; nt: number; f0: number; f1: number; t0: number; t1: number; img: string;
  dbLo: number; dbHi: number; fs: number; nfft: number; df: number; dt: number;
  sigT0?: number; sigT1?: number;     // F24: the signal's own first / last time
}

export interface SyncCandidate {
  method: "boot" | "events" | "signal" | "feature"; delta: number; error?: string; found?: [boolean, boolean]; kind?: string;
  at?: [number, number]; sameNames?: boolean; offset: number; current: number; quality: "high" | "medium" | "low";
  agrees?: boolean; spread?: number; pairs?: number; overlap?: number; reboots?: number; matched?: number; examples?: string[];
  corr?: number; pair?: [string, string]; scale?: number;
  check?: { pair: [string, string] | null; scale: number; refMode: string | null; otherMode: string | null };
}
