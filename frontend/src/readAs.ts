/* 26.A5: how a numeric signal is read between its samples - a state (held: the value in force) or a
   value (interpolated). The backend detects it (a few whole-number levels: a state); the user's
   correction, by signal NAME (every file, as "Always as a state"), lives in the workspace (Undo,
   sessions) and is sent to the backend whenever it changes - the backend's map is always the
   workspace's (cursor values, formulas, conditions, operations follow it). */
import { api } from "./api";
import { useApp, type MenuItem } from "./store";
import { translate } from "./i18n";

export type ReadAs = "state" | "value";

let started = false;
let sent: string | null = null;

/** Keep the backend's map equal to the workspace's (the first call starts it; later ones do nothing). */
export function watchReadAs() {
  if (started) return;
  started = true;
  const push = async () => {
    const map = useApp.getState().ws.readAs ?? {};
    const key = JSON.stringify(map);
    if (key === sent) return;
    sent = key;
    try {
      const r = await api.readAs(map);
      if (sent === key) useApp.setState({ runs: r.runs, dataVersion: useApp.getState().dataVersion + 1 });
    } catch { sent = null; /* the server is busy or gone: sent again on the next change */ }
  };
  let last = useApp.getState().ws.readAs;
  useApp.subscribe((s) => { if (s.ws.readAs !== last) { last = s.ws.readAs; void push(); } });
  void push();
}

/** "Read as ▸" in a numeric signal's menu: what was detected, and the choice (null: no such item). */
export function readAsItem(sig: { id: string; name: string; discrete?: boolean | null; labels?: unknown }): MenuItem | null {
  if (sig.id.startsWith("derived/") || sig.labels) return null;    // texts are always states; a made signal follows its sources
  const st = useApp.getState();
  const t = (k: Parameters<typeof translate>[1]) => translate(st.lang, k);
  const fix = st.ws.readAs?.[sig.name] ?? null;
  // with a correction, `discrete` is the correction; null: not checked yet (a wide file, a big log)
  const detectedState = fix === null && sig.discrete != null ? !!sig.discrete : null;
  const set = (v: ReadAs | null) => () => st.commit((ws) => {
    const m = { ...(ws.readAs ?? {}) };
    if (v === null) delete m[sig.name]; else m[sig.name] = v;
    ws.readAs = Object.keys(m).length ? m : undefined;
    return ws;
  });
  const auto = detectedState === null ? t("readAsAuto") : `${t("readAsAuto")} - ${t(detectedState ? "readAsDetectedState" : "readAsDetectedValue")}`;
  return {
    label: fix === null ? t("readAsMenu") : `${t("readAsMenu")} (${t(fix === "state" ? "readAsStateShort" : "readAsValueShort")})`, run: () => {},
    items: [
      { label: auto, run: set(null), checked: fix === null },
      { label: t("readAsState"), run: set("state"), checked: fix === "state" },
      { label: t("readAsValue"), run: set("value"), checked: fix === "value" },
    ],
  };
}
