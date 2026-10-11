import { useLayoutEffect, useRef, useState } from "react";
import { api, type FsEntry } from "../api";
import { useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { openPaths, recentToOpen, refreshRecent } from "../files";

const LAST_DIR = "sv3.lastDir";
const SORT_KEY = "sv3.fsSort";          // "modified" (default: newest first) or "name"

function fmtSize(n?: number | null) {
  if (n == null) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1073741824) return `${(n / 1048576).toFixed(1)} MB`;
  return `${(n / 1073741824).toFixed(2)} GB`;
}

/** Built-in file browser (works on every OS).
 *  Two uses: opening data files (multi-select, import options) and a generic
 *  open/save picker for sessions, reports and exports (see pickPath). */
export default function FileBrowser() {
  const t = useT();
  const dataOpen = useApp((s) => s.browserOpen);
  const picker = useApp((s) => s.picker);
  const open = dataOpen || !!picker;
  const saving = picker?.mode === "save";
  const folderMode = picker?.mode === "folder";
  const [path, setPath] = useState<string>("");
  const [parent, setParent] = useState<string | null>(null);
  const [entries, setEntries] = useState<FsEntry[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [withOptions, setWithOptions] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [sort, setSort] = useState<"modified" | "name">(() => (localStorage.getItem(SORT_KEY) === "name" ? "name" : "modified"));
  const lang = useApp((st) => st.lang);
  // recent files that are not open now: shown above the folder when opening data files
  useApp((st) => st.recent);
  useApp((st) => st.runs);
  const recent = dataOpen && !picker ? recentToOpen(6) : [];
  const changeSort = (v: "modified" | "name") => { setSort(v); localStorage.setItem(SORT_KEY, v); };
  // last modified: folders and files mixed, newest first (whatever it is);
  // by name: folders first, as in Explorer, then A-Z with numbers in order (run_2 before run_10)
  const shown = [...entries].sort((a, b) => sort === "modified"
    ? (b.mtime ?? 0) - (a.mtime ?? 0)
    : a.dir !== b.dir ? (a.dir ? -1 : 1) : a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" }));
  const fmtDate = (t?: number) => {
    if (!t) return "";
    const d = new Date(t * 1000), now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    return sameDay ? d.toLocaleTimeString(lang === "he" ? "he-IL" : "en-GB", { hour: "2-digit", minute: "2-digit" })
      : d.toLocaleDateString(lang === "he" ? "he-IL" : "en-GB", { day: "2-digit", month: "2-digit", year: "2-digit" }) + " " +
        d.toLocaleTimeString(lang === "he" ? "he-IL" : "en-GB", { hour: "2-digit", minute: "2-digit" });
  };

  // only the latest listing request may update the view (a slow initial load must
  // not overwrite a folder the user typed in the meantime)
  const seq = useRef(0);
  const navigated = useRef(false);   // the user moved on: the initial load must not apply
  const go = async (p?: string | null, initial = false) => {
    if (!initial) navigated.current = true;
    const my = ++seq.current;
    try {
      const r = await api.listDir(p, folderMode ? [".\u0000none"] : picker?.exts);   // folder mode: folders only
      if (my !== seq.current || (initial && navigated.current)) return;
      setPath(r.path); setParent(r.parent); setEntries(r.entries); setPicked([]); setError("");
      if (r.path) localStorage.setItem(LAST_DIR, r.path);
    } catch (e) { if (my === seq.current) setError((e as Error).message); }
  };
  // a layout effect: runs before the dialog is painted, so nothing typed in the first moments can be
  // overwritten by this initial load (a plain effect ran after paint and could reset `navigated`)
  useLayoutEffect(() => {
    // "show import options" is a per-open choice: it must not silently stick to the next open
    if (open) {
      setPath(""); setEntries([]);                  // not the folder of the previous open, even for a moment
      navigated.current = false; setWithOptions(false); go(localStorage.getItem(LAST_DIR), true); setName(picker?.defaultName ?? "");
      if (!picker) refreshRecent();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, picker]);

  if (!open) return null;
  const sep = path.includes("\\") ? "\\" : "/";
  const close = (result: string | null = null) => {
    if (picker) { picker.resolve(result); useApp.setState({ picker: null }); }
    else useApp.setState({ browserOpen: false });
  };
  // nameNow: what is in the name box at Enter (the state may not have caught up with the last keys)
  const confirm = (paths = picked, nameNow = name) => {
    if (folderMode) { if (path) close(path); return; }
    if (picker) {
      if (saving) {
        const n = nameNow.trim();
        if (!n) return;
        let full = /^([a-zA-Z]:)?[\\/]/.test(n) ? n : `${path.replace(/[\\/]$/, "")}${sep}${n}`;
        const ext = picker.exts?.[0];
        if (ext && !full.toLowerCase().endsWith(ext)) full += ext;
        close(full);
      } else if (paths[0]) close(paths[0]);
      return;
    }
    if (!paths.length) return;
    close();
    if (withOptions) useApp.setState({ importPaths: paths });
    else openPaths(paths);
  };
  const clickFile = (e: FsEntry, multi: boolean) => {
    if (saving) { setName(e.name); return; }
    setPicked((cur) => (multi && !picker ? (cur.includes(e.path) ? cur.filter((x) => x !== e.path) : [...cur, e.path]) : [e.path]));
  };
  const title = picker?.title ?? t("openFiles");

  return (
    // a picker is opened FROM another dialog (templates: import, export, folder; reports...): above it
    <div className={`scrim${picker ? " scrim-top" : ""}`} onMouseDown={() => close()}>
      <div className="dialog" role="dialog" aria-label={title} onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={(e) => { if (e.key === "Escape") close(); }}>
        <div className="dialog-head"><h2>{title}</h2>
          <button className="iconbtn" onClick={() => close()} aria-label={t("close")}><Icon.X /></button></div>
        <div className="crumbs">
          <button className="iconbtn" disabled={parent === null} onClick={() => go(parent)} title={t("up")} aria-label={t("up")}><Icon.Up /></button>
          <button className="iconbtn" onClick={() => go(null)} title={t("home")} aria-label={t("home")}><Icon.Home /></button>
          <input value={path} onChange={(e) => setPath(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") go((e.target as HTMLInputElement).value); }} aria-label={t("folder")} />
          <span className="seg fs-sort" role="group" aria-label={t("sortBy")}>
            <button className={sort === "modified" ? "on" : ""} aria-pressed={sort === "modified"} onClick={() => changeSort("modified")}>{t("sortModified")}</button>
            <button className={sort === "name" ? "on" : ""} aria-pressed={sort === "name"} onClick={() => changeSort("name")}>{t("sortName")}</button>
          </span>
        </div>
        {recent.length > 0 && (
          <div className="fs-recent" role="group" aria-label={t("recentOpen")}>
            <h3>{t("recentOpen")}</h3>
            {recent.map((x) => (
              <button key={x.path} className={`fs-row${picked.includes(x.path) ? " on" : ""}${x.exists ? "" : " gone"}`} disabled={!x.exists}
                title={x.path}
                onClick={(ev) => setPicked((cur) => (ev.ctrlKey || ev.metaKey || ev.shiftKey
                  ? (cur.includes(x.path) ? cur.filter((p) => p !== x.path) : [...cur, x.path]) : [x.path]))}
                onDoubleClick={() => confirm([x.path])}>
                <Icon.File /><span>{x.name}</span>
                <span className="mtime fs-folder">{x.exists ? x.folder : t("notFound")}</span><span className="size" />
              </button>
            ))}
          </div>
        )}
        <div className="dialog-body" style={{ minHeight: 260 }}>
          {error && <p className="empty-note">{error}</p>}
          {shown.map((e) => (
            <button key={e.path} className={`fs-row${picked.includes(e.path) ? " on" : ""}`}
              onClick={(ev) => (e.dir ? go(e.path) : clickFile(e, ev.ctrlKey || ev.metaKey || ev.shiftKey))}
              onDoubleClick={() => !e.dir && !saving && confirm([e.path])}>
              {e.dir ? <Icon.Folder /> : <Icon.File />}<span>{e.name}</span>
              <span className="mtime">{fmtDate(e.mtime)}</span><span className="size">{fmtSize(e.size)}</span>
            </button>
          ))}
        </div>
        <div className="dialog-foot">
          {saving ? (
            <label className="savename"><span>{t("fileName")}</span>
              <input autoFocus value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") confirm(picked, (e.target as HTMLInputElement).value); }} />
            </label>
          ) : !picker ? (
            <label style={{ display: "flex", gap: 6, alignItems: "center", color: "var(--muted)" }}>
              <input type="checkbox" checked={withOptions} onChange={(e) => setWithOptions(e.target.checked)} /> {t("openWithOptions")}
            </label>
          ) : null}
          <span className="spacer" />
          <button className="btn outline" onClick={() => close()}>{t("cancel")}</button>
          <button className="btn primary" disabled={folderMode ? !path : saving ? !name.trim() : !picked.length} onClick={() => confirm()}>
            {folderMode ? t("chooseThisFolder") : saving ? t("save") : t("open")}{!saving && !folderMode && picked.length > 1 ? ` (${picked.length})` : ""}</button>
        </div>
      </div>
    </div>
  );
}
