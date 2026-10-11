import { api, type LogInfo } from "./api";
import { useApp } from "./store";

/** Fetch the log data of every open file that has some (once per change of that file). */
export async function ensureLogs() {
  const st = useApp.getState();
  const want = st.runs.filter((r) => r.log);
  const next: Record<string, LogInfo> = {};
  let changed = Object.keys(st.logs).length !== want.length;
  await Promise.all(want.map(async (r) => {
    const have = st.logs[r.id] as (LogInfo & { _key?: string }) | undefined;
    const key = `${r.log!.events}:${r.log!.params}:${r.timeOffset}:${r.samples}`;
    if (have && have._key === key) { next[r.id] = have; return; }
    try {
      const info = await api.runLog(r.id) as LogInfo & { _key?: string };
      info._key = key;
      next[r.id] = info;
      changed = true;
    } catch { /* file closed meanwhile */ }
  }));
  if (changed) useApp.setState({ logs: next });
}

