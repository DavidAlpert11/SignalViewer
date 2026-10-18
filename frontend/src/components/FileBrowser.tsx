import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api, type FsEntry } from "../api";
import { useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { openPaths, recentToOpen, refreshRecent } from "../files";

const LAST_DIR = "sv3.lastDir";        // opening data files (the key since 1.0 - kept)
/** F21: each use of the dialog remembers its own folder (saving a report somewhere else must not
 *  move where Open files starts); a use with no folder yet starts where the data is. */
const lastDirKey = (picker: { mode: string; exts?: string[] } | null) =>
  picker ? `${LAST_DIR}:${picker.mode}:${(picker.exts ?? []).join(",")}` : LAST_DIR;
const dirOfPath = (p: string) => {        // the folder of a file path; a drive or "/" keeps its separator
  const d = p.replace(/[\\/][^\\/]*$/, "");
  return !d ? "/" : /^[a-zA-Z]:$/.test(d) ? `${d}\\` : d;
};
function startFolder(picker: { mode: string; exts?: string[] } | null): string | null {
  const own = localStorage.getItem(lastDirKey(picker));
  if (own) return own;
  const st = useApp.getState();
  const lastRun = [...st.runs].reverse().find((r) => r.format !== "derived" && r.path && !r.copy);
  if (lastRun) return dirOfPath(lastRun.path);
  return localStorage.getItem(LAST_DIR) ?? st.recent.find((x) => x.exists)?.folder ?? null;
}
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
  const [path, setPath] = useState<string>("");          // the folder listed
  const [typed, setTyped] = useState<string>("");        // what is in the path box (may be partial)
  const [sugg, setSugg] = useState<{ name: string; path: string; dir: boolean }[]>([]);
  const [suggAt, setSuggAt] = useState(-1);              // highlighted suggestion (-1: none)
  const [filter, setFilter] = useState("");              // type-to-filter on the folder list
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
  const fq = filter.toLowerCase();
  const shown = entries.filter((e) => !fq || e.name.toLowerCase().includes(fq)).sort((a, b) => sort === "modified"
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
  const userTyped = useRef(false);   // the user typed in the path box: the initial load must not overwrite it
  const dialogRef = useRef<HTMLDivElement>(null);
  const anchor = useRef<string | null>(null);     // F21: where a Shift+click range starts
  const go = async (p?: string | null, initial = false) => {
    if (!initial) navigated.current = true;
    const my = ++seq.current;
    try {
      const r = await api.listDir(p, folderMode ? [".\u0000none"] : picker?.exts);   // folder mode: folders only
      if (my !== seq.current || (initial && navigated.current)) return;
      setPath(r.path); if (!(initial && userTyped.current)) setTyped(r.path); setParent(r.parent); setEntries(r.entries); setPicked([]); anchor.current = null; setError("");
      setSugg([]); setSuggAt(-1); setFilter("");
      if (r.path) localStorage.setItem(lastDirKey(picker), r.path);
    } catch (e) { if (my === seq.current) setError((e as Error).message); }
  };
  // a layout effect: runs before the dialog is painted, so nothing typed in the first moments can be
  // overwritten by this initial load (a plain effect ran after paint and could reset `navigated`)
  useLayoutEffect(() => {
    // "show import options" is a per-open choice: it must not silently stick to the next open
    if (open) {
      setPath(""); setTyped(""); setEntries([]); setSugg([]); setFilter("");   // not the previous open's folder, even for a moment
      navigated.current = false; userTyped.current = false; setWithOptions(false); go(startFolder(picker), true); setName(picker?.defaultName ?? "");
      if (!picker) refreshRecent();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, picker]);

  // path autocomplete: what was typed after the last separator, completed from that folder
  const completeSeq = useRef(0);
  const suggExts = folderMode ? [".\u0000none"] : picker?.exts;
  useEffect(() => {
    const bare = (x: string) => x.replace(/[\\/]+$/, "");
    if (!open || bare(typed) === bare(path)) { setSugg([]); return; }     // the folder shown: the list says it all
    const my = ++completeSeq.current;
    const h = window.setTimeout(() => {
      api.completePath(typed, path || null, suggExts)
        .then((r) => { if (my === completeSeq.current) { setSugg(r.items); setSuggAt(-1); } })
        .catch(() => { if (my === completeSeq.current) setSugg([]); });
    }, 120);
    return () => window.clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typed, path, open]);

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
  // F21: Shift+click selects the range from the last clicked file (in the order shown), Ctrl+click
  // adds / removes one - as in Explorer (Shift used to act like Ctrl)
  const clickFile = (e: FsEntry, ev: { ctrlKey: boolean; metaKey: boolean; shiftKey: boolean }) => {
    if (saving) { setName(e.name); return; }
    const files = shown.filter((x) => !x.dir).map((x) => x.path);
    if (ev.shiftKey && !picker && anchor.current && files.includes(anchor.current)) {
      const [a, b] = [files.indexOf(anchor.current), files.indexOf(e.path)].sort((x, y) => x - y);
      setPicked(files.slice(a, b + 1));
      return;
    }
    anchor.current = e.path;
    setPicked((cur) => ((ev.ctrlKey || ev.metaKey) && !picker ? (cur.includes(e.path) ? cur.filter((x) => x !== e.path) : [...cur, e.path]) : [e.path]));
  };
  const dirOf = dirOfPath;
  /** A suggestion chosen: a folder opens (and completion goes on from it); a file is picked -
   *  opened at once when opening, put in the name box when saving. */
  const choose = async (it: { path: string; dir: boolean; name: string }) => {
    setSugg([]); setSuggAt(-1);
    if (it.dir) { await go(it.path); setTyped(it.path); return; }   // ends with a separator: keep typing inside
    await go(dirOf(it.path));
    if (saving) { setName(it.name); return; }
    if (picker) close(it.path); else confirm([it.path]);
  };
  const tabComplete = async () => {
    const r = await api.completePath(typed, path || null, suggExts).catch(() => null);
    if (!r) return;
    if (r.items.length === 1) { await choose(r.items[0]); return; }
    if (r.common.length > typed.length) setTyped(r.common);
    setSugg(r.items); setSuggAt(-1);
  };
  const pathKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const n = sugg.length;
    if (e.key === "ArrowDown" && n) { e.preventDefault(); setSuggAt((i) => (i + 1) % n); }
    else if (e.key === "ArrowUp" && n) { e.preventDefault(); setSuggAt((i) => (i <= 0 ? n - 1 : i - 1)); }
    else if (e.key === "Tab" && !e.shiftKey && typed) { e.preventDefault(); tabComplete(); }
    else if (e.key === "Escape" && n) { e.stopPropagation(); setSugg([]); }     // first Esc: only the list
    else if (e.key === "Enter") {
      if (suggAt >= 0 && sugg[suggAt]) choose(sugg[suggAt]);
      else if (sugg.length === 1 && !sugg[0].dir && sugg[0].path === typed) choose(sugg[0]);
      else go(typed);
    }
  };
  /** type-to-filter: letters typed while the dialog (not a text box) has focus filter the folder. */
  const filterKey = (e: React.KeyboardEvent) => {
    const tag = (e.target as HTMLElement).tagName;
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a" && !picker) {      // F21: every file shown
      e.preventDefault(); setPicked(shown.filter((x) => !x.dir).map((x) => x.path)); return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    // the focused row may be filtered away: keep the keys coming to the dialog
    const keep = () => dialogRef.current?.focus();
    if (e.key === "Backspace" && filter) { e.preventDefault(); setFilter(filter.slice(0, -1)); keep(); }
    else if (e.key === "Escape" && filter) { e.stopPropagation(); setFilter(""); keep(); }
    else if (e.key.length === 1 && e.key !== " ") { e.preventDefault(); setFilter(filter + e.key); keep(); }
  };
  /** Breadcrumbs: every folder on the way to this one ("C:\\", "Users", ...), each clickable. */
  const crumbs = (() => {
    if (!path) return [] as { label: string; path: string }[];
    const win = /^[a-zA-Z]:/.test(path);
    const parts = path.split(/[\\/]+/).filter(Boolean);
    const out: { label: string; path: string }[] = [];
    let acc = win ? "" : "/";
    if (!win) out.push({ label: "/", path: "/" });
    parts.forEach((p, i) => {
      acc = win ? (i === 0 ? `${p}\\` : `${acc.replace(/\\$/, "")}\\${p}`) : `${acc.replace(/\/$/, "")}/${p}`;
      out.push({ label: p, path: acc });
    });
    return out;
  })();
  const title = picker?.title ?? t("openFiles");

  return (
    // a picker is opened FROM another dialog (templates: import, export, folder; reports...): above it
    <div className={`scrim${picker ? " scrim-top" : ""}`} onMouseDown={() => close()}>
      <div className="dialog" role="dialog" aria-label={title} onMouseDown={(e) => e.stopPropagation()}
        ref={dialogRef} tabIndex={-1}
        onKeyDown={(e) => { filterKey(e); if (e.key === "Escape" && !e.isPropagationStopped()) close(); }}>
        <div className="dialog-head"><h2>{title}</h2>
          <button className="iconbtn" onClick={() => close()} aria-label={t("close")}><Icon.X /></button></div>
        <div className="crumbs">
          <button className="iconbtn" disabled={parent === null} onClick={() => go(parent)} title={t("up")} aria-label={t("up")}><Icon.Up /></button>
          <button className="iconbtn" onClick={() => go(null)} title={t("home")} aria-label={t("home")}><Icon.Home /></button>
          <span className="fs-path">
            <input value={typed} onChange={(e) => { userTyped.current = true; setTyped(e.target.value); }} onKeyDown={pathKey} aria-label={t("folder")}
              title={t("pathHint")} spellCheck={false} autoComplete="off" role="combobox" aria-expanded={sugg.length > 0}
              aria-controls="fs-complete" aria-activedescendant={suggAt >= 0 ? `fs-sugg-${suggAt}` : undefined}
              onBlur={() => window.setTimeout(() => setSugg([]), 150)} />
            {sugg.length > 0 && (
              <ul className="fs-complete" id="fs-complete" role="listbox">
                {sugg.map((it, i) => (
                  <li key={it.path} id={`fs-sugg-${i}`} role="option" aria-selected={i === suggAt} className={i === suggAt ? "on" : ""}
                    onMouseDown={(e) => { e.preventDefault(); choose(it); }} onMouseEnter={() => setSuggAt(i)}>
                    {it.dir ? <Icon.Folder /> : <Icon.File />}<span>{it.name}</span>
                  </li>
                ))}
              </ul>
            )}
          </span>
          <span className="seg fs-sort" role="group" aria-label={t("sortBy")}>
            <button className={sort === "modified" ? "on" : ""} aria-pressed={sort === "modified"} onClick={() => changeSort("modified")}>{t("sortModified")}</button>
            <button className={sort === "name" ? "on" : ""} aria-pressed={sort === "name"} onClick={() => changeSort("name")}>{t("sortName")}</button>
          </span>
        </div>
        {(crumbs.length > 0 || filter) && (
          <div className="fs-crumbs">
            {crumbs.map((c, i) => (
              <span key={c.path} className="fs-crumb">
                {i > 0 && i < crumbs.length && crumbs[i - 1].label !== "/" && <span className="fs-crumb-sep" aria-hidden="true">›</span>}
                <button className="linkbtn" onClick={() => go(c.path)} disabled={i === crumbs.length - 1}>{c.label}</button>
              </span>
            ))}
            {filter && (
              <span className="fs-filter">{t("fsFilter", { q: filter })}
                <button className="iconbtn sm" onClick={() => setFilter("")} aria-label={t("fsFilterClear")}><Icon.X /></button></span>
            )}
          </div>
        )}
        {recent.length > 0 && !filter && (
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
              onClick={(ev) => (e.dir ? go(e.path) : clickFile(e, ev))}
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
