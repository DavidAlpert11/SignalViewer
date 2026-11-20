import { api } from "./api";
import { useApp } from "./store";
import type { Structure } from "./store/model";
import { translate } from "./i18n";
import { openPaths } from "./files";
import { startLive } from "./live";

/**
 * LINK1 (owner, 2026-11-20: "listen to a UART and parse the variables from there, or to UDP; save it to a file and show
 * it"): the backend records a serial port / UDP / TCP link to a .svraw file (the messages' structure beside it); here
 * the UI waits for the first bytes, opens the file like any file and turns live mode on - it is read again as it grows,
 * decoded by its structure. Stopping keeps the file: a recording that opens again any time. As Live MAVLink (mavlink.ts).
 */
let timer = 0;
let opened: string | null = null;

export async function linkListen(conn: string, opts: { baud?: number; structure?: Structure | null }) {
  const st = useApp.getState();
  try {
    const s = await api.linkStart({ conn, ...opts });
    opened = null;
    useApp.setState({ rawlink: s });
    watch();
    return true;
  } catch (e) {
    st.toast({ kind: "error", text: String((e as Error).message) });
    return false;
  }
}

export async function linkStop() {
  const st = useApp.getState();
  try {
    const s = await api.linkStop();
    useApp.setState({ rawlink: s });
    if (s.path) st.toast({ kind: "info", text: translate(st.lang, "linkSaved", { path: s.path }), ms: 12000 });
  } catch (e) {
    st.toast({ kind: "error", text: String((e as Error).message) });
  }
  window.clearInterval(timer);
  timer = 0;
}

function watch() {
  window.clearInterval(timer);
  let asking = false;
  timer = window.setInterval(async () => {
    if (asking) return;
    asking = true;
    try {
      let s;
      try { s = await api.linkStatus(); } catch { return; }
      useApp.setState({ rawlink: s });
      if (!s.running) { window.clearInterval(timer); timer = 0; return; }
      if (s.path && !opened && (s.written ?? 0) > 0) {
        opened = s.path;
        await openPaths([s.path]);
        if (!useApp.getState().streaming && !useApp.getState().liveStarting) await startLive();
      }
    } finally { asking = false; }
  }, 1000);
}

/** After a page reload the link may still be running in the backend: show it again. */
export async function linkResume() {
  try {
    const s = await api.linkStatus();
    if (s.running) {
      opened = useApp.getState().runs.some((r) => r.path === s.path) ? s.path! : null;
      useApp.setState({ rawlink: s });
      watch();
    }
  } catch { /* backend not up yet */ }
}
