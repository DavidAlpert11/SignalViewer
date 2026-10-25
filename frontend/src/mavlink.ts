import { api, type MavStatus } from "./api";
import { useApp } from "./store";
import { translate } from "./i18n";
import { openPaths } from "./files";
import { startLive } from "./live";

/**
 * Live MAVLink (T12). The backend records the link to a .tlog; here the UI waits for the first
 * data in that file, opens it like any file and turns live mode on, which then reads what is
 * added (one code path for live and recorded data). Disconnecting keeps the file open and saved.
 */
let timer = 0;
let opened: string | null = null;            // the recording already opened as a file

export async function mavlinkConnect(conn: string, opts: { baud?: number; request?: boolean; rate?: number }) {
  const st = useApp.getState();
  try {
    const s = await api.mavlinkStart({ conn, ...opts });
    opened = null;
    useApp.setState({ mavlink: s });
    watch();
    return true;
  } catch (e) {
    st.toast({ kind: "error", text: String((e as Error).message) });
    return false;
  }
}

export async function mavlinkDisconnect() {
  const st = useApp.getState();
  try {
    const s = await api.mavlinkStop();
    useApp.setState({ mavlink: s });
    if (s.path && opened) st.toast({ kind: "info", text: translate(st.lang, "mavSaved", { path: s.path }), ms: 12000 });
  } catch (e) {
    st.toast({ kind: "error", text: String((e as Error).message) });
  }
  stopWatch();
}

function stopWatch() { window.clearInterval(timer); timer = 0; }

/** Status once a second while connected; opens the recording when its first data is written. */
function watch() {
  stopWatch();
  let asking = false;                     // one status request at a time (a busy server answers late)
  timer = window.setInterval(async () => {
    if (asking) return;
    asking = true;
    try {
      let s: MavStatus;
      try { s = await api.mavlinkStatus(); } catch { return; }
      useApp.setState({ mavlink: s });
      if (!s.running) { stopWatch(); return; }
      if (s.path && !opened && (s.written ?? 0) > 0) {
        opened = s.path;
        await openPaths([s.path]);
        if (!useApp.getState().streaming && !useApp.getState().liveStarting) await startLive();
      }
    } finally { asking = false; }
  }, 1000);
}

/** After a page reload the link may still be running in the backend: show it again. */
export async function mavlinkResume() {
  try {
    const s = await api.mavlinkStatus();
    if (s.running) {
      opened = useApp.getState().runs.some((r) => r.path === s.path) ? s.path! : null;
      useApp.setState({ mavlink: s });
      watch();
    }
  } catch { /* backend not up yet: nothing to resume */ }
}
