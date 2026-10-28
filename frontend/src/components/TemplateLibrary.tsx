import { useEffect, useMemo, useState } from "react";
import { api, type RunInfo, type Template, type TemplateFolderInfo, type TplSlot, type TplTab } from "../api";
import { tabHasContent, activeTab, fileLabel, pickPath, useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { confirmAsk, openMenu, useEscape } from "./Overlays";
import { openPaths, refreshRecent } from "../files";
import {
  ALL, applyTemplate, baseName, expand, fits as templateFits, includers, rankTemplates, slotNames, suggestTabName, templateFromTabs, tx,
} from "../templates";

/** A new template's draft; src: for each of its tabs, the workspace tab it was made from (editor only, not saved). */
type Draft = { t: Template; isNew: boolean; src?: (string | null)[]; slotRuns?: Record<string, string> };

/* The template library: every template (built-in and the user's own, one JSON file each), grouped,
   with how well the open files fit; open one (a file per slot, which tabs), edit it, make one from
   open tabs or as a collection of templates, import / export, open the folder. */

const GROUPS = ["mine", "general", "ardupilot", "mavlink", "px4", "compare"];

export default function TemplateLibrary() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const ws = useApp((s) => s.ws);
  const prefer = useApp((s) => s.templatesTarget);
  const startNew = useApp((s) => s.templatesNew);
  const close = () => useApp.setState({ templatesOpen: false, templatesTarget: null, templatesNew: null, templatesSelect: null });
  useEscape(close);
  const [mine, setMine] = useState<Template[]>([]);
  const [builtin, setBuiltin] = useState<Template[]>([]);
  const [folder, setFolder] = useState<TemplateFolderInfo | null>(null);
  const [q, setQ] = useState("");
  const [onlyFit, setOnlyFit] = useState(true);
  // opened from a suggestion in the file panel: start on that template
  const [sel, setSel] = useState<string | null>(() => useApp.getState().templatesSelect);
  const [draft, setDraft] = useState<Draft | null>(null);
  /** A new template from workspace tabs: the tabs keep a relevant name, and remember where they came from. */
  const fromTabs = (tabs: typeof ws.tabs, name?: string): Draft => {
    const made = templateFromTabs(tabs, name ?? (tabs.length === 1 ? suggestTabName(tabs[0], ws.tabs.indexOf(tabs[0])) : t("templateNew")));
    return { t: made.template, isNew: true, src: tabs.map((x) => x.id), slotRuns: made.slotRuns };
  };
  const newCollection = (): Draft => ({ t: { version: 2, id: "", name: t("tplCollectionNew"), slots: [{ id: "main", name: "@tplSlotFile" }], tabs: [], includes: [] }, isNew: true });
  const all = useMemo(() => [...builtin, ...mine.map((m) => ({ ...m, group: m.group || "mine" }))], [builtin, mine]);
  const data = runs.filter((r) => r.format !== "derived");

  const reload = async (select?: string) => {
    const r = await api.templates().catch(() => null);
    setMine(r?.templates ?? []);
    if (r) setBuiltin(r.builtin);
    if (r) setFolder({ folder: r.folder, default: r.default, exists: r.exists, defaultFolder: r.defaultFolder });
    if (select) setSel(select);
  };
  const fail = (e: unknown) => useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
  /** Delete one of the user's templates (asks first; names the collections that include it). */
  const deleteTpl = async (x: Template) => {
    if (x.builtin) { useApp.getState().toast({ kind: "info", text: t("tplBuiltinNoDelete") }); return; }
    const users = all.filter((y) => y.id !== x.id && (y.includes ?? []).includes(x.id)).map((y) => tx(y.name, lang));
    if (!(await confirmAsk(t("tplDelete"), t("tplDeleteAsk", { name: tx(x.name, lang) }) + (users.length ? " " + t("tplUsedBy", { list: users.join(", ") }) : "")))) return;
    try { await api.deleteTemplate(x.id); } catch (e) { fail(e); return; }
    if (sel === x.id) setSel(null);
    if (draft?.t.id === x.id) setDraft(null);
    await reload();
  };
  /** Keep templates in another folder (a shared drive, say); the current ones are copied there. */
  const changeFolder = async (reset = false) => {
    const path = reset ? null : await pickPath({ mode: "folder", title: t("tplChooseFolder") });
    if (!reset && !path) return;
    try {
      const r = await api.setTemplateFolder(path);
      useApp.getState().toast({ kind: "info", text: t("tplFolderChanged", { folder: r.folder }) + (r.copied ? " " + t("tplFolderCopied", { n: r.copied }) : "") });
      setSel(null); await reload();
    } catch (e) { fail(e); }
  };
  const itemMenu = (e: React.MouseEvent, x: Template) => openMenu(e, x.builtin
    ? [{ label: t("tplBuiltinNoDelete"), run: () => {}, disabled: true }]
    : [{ label: t("tplEditFromList"), run: () => setDraft({ t: structuredClone(x), isNew: false }) },
      { label: "", run: () => {}, sep: true },
      { label: t("tplDeleteFromList"), run: () => deleteTpl(x), danger: true }]);
  useEffect(() => { reload(); }, []);

  // what fits the open files, for the list (and the first selection)
  const [fits, setFits] = useState<Map<string, number>>(new Map());
  const runsKey = runs.map((r) => `${r.id}:${r.signals.length}`).join("|");
  useEffect(() => {
    if (!all.length) return;
    let off = false;
    templateFits(all, runs).then((m) => { if (!off) setFits(m); }).catch(() => {});
    return () => { off = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [all, runsKey]);
  useEffect(() => {
    if (sel || draft || !all.length || (data.length && !fits.size)) return;     // wait for the fits
    const pick = rankTemplates(all, fits, runs.find((r) => r.id === prefer)?.format)[0];
    if (pick) setSel(pick.id);
  }, [all, fits, sel, draft, prefer, runs]);

  // "save as template" from a tab's menu: start a new template with that tab
  useEffect(() => {
    if (!startNew) return;
    if (startNew === "collection") setDraft(newCollection());
    else setDraft(fromTabs(startNew === "all" ? ws.tabs.filter(tabHasContent) : [activeTab(ws)]));
    useApp.setState({ templatesNew: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startNew]);

  const ql = q.trim().toLowerCase();
  const shown = all.filter((x) => (!ql || tx(x.name, lang).toLowerCase().includes(ql) || tx(x.description, lang).toLowerCase().includes(ql))
    && (!onlyFit || !data.length || (fits.get(x.id) ?? 0) > 0.15 || x.group === "mine" || mine.some((m) => m.id === x.id)));
  const groups = Array.from(new Set([...GROUPS, ...shown.map((x) => x.group || "mine")]))
    .map((g) => [g, shown.filter((x) => (x.group || "mine") === g)] as const).filter(([, l]) => l.length);
  const cur = all.find((x) => x.id === sel) ?? null;

  const newMenu = (e: React.MouseEvent) => openMenu(e, [
    { label: t("tplNewTab"), run: () => setDraft(fromTabs([activeTab(ws)])) },
    { label: t("tplNewTabs"), run: () => setDraft(fromTabs(ws.tabs.filter(tabHasContent))) },
    { label: t("tplNewCollection"), run: () => setDraft(newCollection()) },
    { label: "", run: () => {}, sep: true },
    { label: t("tplImport") + "…", run: async () => {
      const path = await pickPath({ mode: "open", title: t("tplImport"), exts: [".json"] });
      if (!path) return;
      try {
        const r = await api.importTemplates(path);
        await reload(r.templates[0]?.id);
        useApp.getState().toast({ kind: "info", text: t("tplImported", { n: r.templates.length }) });
      } catch (err) { useApp.getState().toast({ kind: "error", text: String((err as Error).message) }); }
    } },
  ]);

  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog tpl-lib" role="dialog" aria-label={t("templates")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("templates")}</h2>
          <button className="iconbtn" onClick={close} aria-label={t("close")}><Icon.X /></button></div>
        <div className="tpl-body">
          <aside className="tpl-side">
            <div className="tpl-side-top">
              <label className="filter"><Icon.Search />
                <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("tplSearch")} aria-label={t("tplSearch")} /></label>
              {/* only while browsing: inside the editor a new template is already being made */}
              {!draft && <button className="btn primary" aria-haspopup="menu" onClick={newMenu}><Icon.Plus /> {t("tplNew")} <Icon.Chevron width={12} height={12} /></button>}
            </div>
            {data.length > 0 && (
              <label className="tpl-fitonly"><input type="checkbox" checked={onlyFit} onChange={(e) => setOnlyFit(e.target.checked)} /> {t("tplOnlyFit")}</label>
            )}
            <div className="tpl-list" role="listbox" aria-label={t("templates")}>
              {groups.map(([g, list]) => (
                <div key={g}>
                  <div className="tpl-group">{GROUPS.includes(g) ? t(`tplGroup_${g}` as "tplGroup_mine") : g}</div>
                  {list.map((x) => {
                    const f = fits.get(x.id) ?? 0;
                    const e = expand(x, all);
                    return (
                      <div key={x.id} className="tpl-item-row" onContextMenu={(ev) => itemMenu(ev, x)}>
                      <button role="option" aria-selected={sel === x.id && !draft} className={`tpl-item${sel === x.id && !draft ? " on" : ""}`}
                        onClick={() => { setDraft(null); setSel(x.id); }}>
                        <span className={`fitdot ${data.length ? (f > 0.6 ? "good" : f > 0.15 ? "part" : "none") : "none"}`}
                          title={data.length ? t("tplFit", { p: Math.round(f * 100) }) : ""} />
                        <span className="tpl-item-name">{tx(x.name, lang)}</span>
                        <span className="tpl-item-meta">
                          {x.generator ? t("tplAuto") : x.includes?.length ? t("tplCollectionN", { n: x.includes.length }) : (e.tabs.length === 1 ? t("tplTabsOne") : t("tplTabsN", { n: e.tabs.length }))}
                        </span>
                      </button>
                      {!x.builtin && <button className="iconbtn sm tpl-item-del" onClick={() => deleteTpl(x)}
                        aria-label={`${t("tplDelete")} ${tx(x.name, lang)}`} title={t("tplDelete")}><Icon.Trash /></button>}
                      </div>
                    );
                  })}
                </div>
              ))}
              {!groups.length && <p className="empty-note">{t("tplNoneFit")}</p>}
            </div>
          </aside>
          <section className="tpl-main">
            {draft ? <Editor key={draft.t.id || "new"} draft={draft.t} src={draft.src} slotRuns={draft.slotRuns} isNew={draft.isNew} all={all}
              onCancel={() => setDraft(null)} onDelete={draft.isNew ? undefined : () => deleteTpl(draft.t)}
              onSaved={async (id) => { setDraft(null); await reload(id); }} />
              : cur ? <Details key={cur.id} tpl={cur} all={all} runs={runs} prefer={prefer}
                onEdit={() => setDraft({ t: structuredClone(cur), isNew: false })}
                onCopy={() => setDraft({ t: { ...structuredClone(cur), id: "", builtin: undefined, file: undefined, group: "mine",
                  name: `${tx(cur.name, lang)} (${t("tplCopy")})`, description: tx(cur.description, lang) }, isNew: true })}
                onDeleted={async () => { setSel(null); await reload(); }} onOpened={close} />
              : <p className="empty-note">{t("tplPick")}</p>}
          </section>
        </div>
        <div className="dialog-foot tpl-foot">
          <span className={`hint${folder && !folder.exists ? " err" : ""}`} title={folder?.folder}>
            {folder && !folder.exists ? t("tplFolderMissing", { folder: folder.folder })
              : <>{t("tplFolder")}: <code>{folder?.folder}</code></>}</span>
          <span className="spacer" />
          <button className="btn" onClick={() => changeFolder()}>{t("tplChangeFolder")}</button>
          {folder && !folder.default && <button className="btn" onClick={() => changeFolder(true)} title={folder.defaultFolder}>{t("tplDefaultFolder")}</button>}
          <button className="btn" onClick={() => api.revealTemplates().catch(fail)}>
            <Icon.Folder /> {t("tplOpenFolder")}</button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ details & open */
function Details({ tpl, all, runs, prefer, onEdit, onCopy, onDeleted, onOpened }: {
  tpl: Template; all: Template[]; runs: RunInfo[]; prefer: string | null;
  onEdit: () => void; onCopy: () => void; onDeleted: () => void; onOpened: () => void;
}) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const e = useMemo(() => expand(tpl, all), [tpl, all]);
  const data = runs.filter((r) => r.format !== "derived");
  // a file for each slot, and how many of its signals each file has (backend: svcore/templates.py);
  // again when a file is opened or closed (e.g. "Open run_a.csv" below)
  const [bind, setBind] = useState<Record<string, string>>({});
  const [found, setFound] = useState<Record<string, Record<string, number>>>({});
  const [boundKey, setBoundKey] = useState("");          // for which template + files `bind` was made
  const runKey = data.map((r) => `${r.id}:${r.signals.length}`).join(",");
  const wantKey = `${tpl.id}|${runKey}|${prefer ?? ""}`;
  useEffect(() => {
    let off = false;
    api.bindTemplate(tpl, all, prefer).then((r) => {
      if (off) return;
      setBind(r.bind); setFound(Object.fromEntries(r.slots.map((x) => [x.id, x.counts]))); setBoundKey(wantKey);
    }).catch(() => {});
    return () => { off = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tpl, all, runKey, prefer]);
  const recent = useApp((s) => s.recent);
  useEffect(() => { refreshRecent(); }, []);
  /** The original file of a slot, if it still exists on disk (from the template, or the recent list). */
  const original = (sl: TplSlot) => {
    if (!sl.file) return null;
    const want = sl.file.toLowerCase();
    const hit = recent.find((x) => x.kind === "file" && x.exists && (x.path === sl.path || baseName(x.path).toLowerCase() === want));
    return hit?.path ?? null;
  };
  const [chosen, setChosen] = useState<Set<number>>(() => new Set(e.tabs.map((_x, i) => i)));
  const mineT = !tpl.builtin;

  const open = async () => {
    let r;
    try { r = await applyTemplate(tpl, all, bind, e.tabs.map((_x, i) => i).filter((i) => chosen.has(i))); }
    catch (err) { useApp.getState().toast({ kind: "error", text: String((err as Error).message) }); return; }
    const st = useApp.getState();
    if (!r.tabs) { st.toast({ kind: "error", text: t("tplNothing2", { names: r.missing.slice(0, 5).join(", ") }), ms: 12000 }); return; }
    st.toast({ kind: "info", ms: r.dropped.length ? 12000 : 4000, text: t("tplOpened", { name: tx(tpl.name, lang), n: r.tabs, p: r.plots })
      + (r.dropped.length ? " " + t("tplLeftOut", { list: r.dropped.slice(0, 4).join(", ") + (r.dropped.length > 4 ? "…" : "") }) : "")
      + (r.conditions ? " " + t("tplCondsAdded", { n: r.conditions }) : "") });
    onOpened();
  };

  return (
    <div className="tpl-details">
      <h3>{tx(tpl.name, lang)}</h3>
      <div className="tpl-badges">
        <span className="badge">{tpl.builtin ? t("tplBuiltinBadge") : t("tplMineBadge")}</span>
        {tpl.includes?.length ? <span className="badge">{t("tplCollectionN", { n: tpl.includes.length })}</span> : null}
        {tpl.conditions?.length ? <span className="badge tpl-conds" title={tpl.conditions.map((c) => `${c.name}: ${c.text || c.combine?.op}`).join("\n")}>{t("tplCondsN", { n: tpl.conditions.length })}</span> : null}
        {tpl.file && <span className="hint tpl-file" title={tpl.file}>{tpl.file.split(/[\\/]/).pop()}</span>}
      </div>
      {tpl.description && <p className="tpl-desc">{tx(tpl.description, lang)}</p>}
      {tpl.broken && <p className="hint err">{t("tplBroken")}</p>}
      {e.missing.length > 0 && <p className="hint err">{t("tplMissingIncludes", { list: e.missing.join(", ") })}</p>}

      <h4>{t("tplFiles")}</h4>
      {!data.length && <p className="hint">{t("tplOpenFilesFirst")}</p>}
      {data.length > 0 && e.slots.map((s) => {
        const names = slotNames(s.id, e.slots, e.tabs);
        const b = bind[s.id] ?? "";
        const run = data.find((r) => r.id === b);
        const cnt = found[s.id] ?? {};
        const hits = b === ALL ? Math.max(0, ...Object.values(cnt)) : run ? cnt[run.id] ?? 0 : 0;
        // was it given the same file as when the template was saved?
        const same = !!s.file && !!run && baseName(run.path).toLowerCase() === s.file.toLowerCase();
        const orig = s.file && !same && b !== ALL ? original(s) : null;
        return (
          <div key={s.id} className="tpl-slot">
            <span className="tpl-slot-name" title={s.path ?? ""}>{s.file ?? tx(s.name, lang)}{s.formats?.length ? <span className="hint"> · {s.formats.join(", ")}</span> : null}</span>
            <select value={b} onChange={(ev) => setBind({ ...bind, [s.id]: ev.target.value })} aria-label={tx(s.name, lang)}>
              {data.map((r) => <option key={r.id} value={r.id}>{fileLabel(runs, r.id)}{r.format !== "csv" ? ` (${r.format})` : ""}</option>)}
              <option value={ALL}>{t("tplAllFiles")}</option>
              <option value="">{t("tplNoFile")}</option>
            </select>
            {names.length > 0 && b && <span className={`tpl-found ${hits === names.length ? "good" : hits ? "part" : "none"}`}>
              {t("tplFound", { n: hits, of: names.length })}</span>}
            {s.file && b !== ALL && (
              <span className={`tpl-slot-note hint${same ? " ok" : ""}`}>
                {same ? t("tplSameFile") : b ? t("tplFileMissing", { file: s.file }) : t("tplFileMissingNone", { file: s.file })}
                {orig && <button className="linkbtn" onClick={() => openPaths([orig])}>{t("tplOpenOriginal", { file: s.file })}</button>}
              </span>
            )}
          </div>
        );
      })}

      <h4>{t("tplTabs")}</h4>
      {e.generators.length > 0 && <p className="hint">{t("tplAutoTabs")}</p>}
      <ul className="tpl-tabs">
        {e.tabs.map((x, i) => (
          <li key={i}><label>
            <input type="checkbox" checked={chosen.has(i)} onChange={(ev) => {
              const n = new Set(chosen); if (ev.target.checked) n.add(i); else n.delete(i); setChosen(n);
            }} />
            <span>{tx(x.name, lang)}</span>
            <span className="hint">{(x.plots.length === 1 ? t("tplPlotsOne") : t("tplPlotsN", { n: x.plots.length }))}{x.from !== tpl.name ? ` · ${tx(x.from, lang)}` : ""}</span>
          </label></li>
        ))}
      </ul>

      <div className="tpl-actions">
        {/* the files for the slots come from the server: not before they are there for THIS template */}
        <button className="btn primary" disabled={!data.length || (!chosen.size && !e.generators.length) || boundKey !== wantKey} onClick={open}>{t("tplOpen")}</button>
        {mineT ? <button className="btn" onClick={onEdit}><Icon.Edit /> {t("tplEdit")}</button>
          : <button className="btn" onClick={onCopy} title={t("tplCopyHint")}><Icon.Copy /> {t("tplCopyToMine")}</button>}
        {mineT && <button className="btn" onClick={async () => {
          const path = await pickPath({ mode: "save", title: t("tplExport"), exts: [".json"], defaultName: `${tpl.id}.json` });
          if (!path) return;
          try { const r = await api.exportTemplates([tpl.id], path); useApp.getState().toast({ kind: "info", text: t("savedTo", { path: r.path }) }); }
          catch (err) { useApp.getState().toast({ kind: "error", text: String((err as Error).message) }); }
        }}>{t("tplExport")}</button>}
        {mineT && <button className="btn danger" onClick={async () => {
          const users = all.filter((x) => x.id !== tpl.id && (x.includes ?? []).includes(tpl.id)).map((x) => tx(x.name, lang));
          if (!(await confirmAsk(t("tplDelete"), t("tplDeleteAsk", { name: tpl.name }) + (users.length ? " " + t("tplUsedBy", { list: users.join(", ") }) : "")))) return;
          await api.deleteTemplate(tpl.id); onDeleted();
        }}><Icon.Trash /> {t("tplDelete")}</button>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ editor */
function Editor({ draft, src: src0, slotRuns: slotRuns0, isNew, all, onCancel, onSaved, onDelete }: {
  draft: Template; src?: (string | null)[]; slotRuns?: Record<string, string>; isNew: boolean; all: Template[]; onCancel: () => void; onSaved: (id: string) => void;
  onDelete?: () => void;
}) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const ws = useApp((s) => s.ws);
  const [d, setD] = useState<Template>(draft);
  // the workspace tab each template tab came from (same order as d.tabs), to offer only tabs not added yet
  const [src, setSrc] = useState<(string | null)[]>(() => draft.tabs.map((_x, i) => src0?.[i] ?? null));
  // the open file each file slot was made from (editor only): tabs added from the SAME file share its
  // slot, tabs from another file get their own - never merged just because both are CSV
  const [slotRun, setSlotRun] = useState<Record<string, string>>(() => ({ ...(slotRuns0 ?? {}) }));
  const [open, setOpen] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (patch: Partial<Template>) => setD({ ...d, ...patch });
  const setTab = (i: number, tab: TplTab) => set({ tabs: d.tabs.map((x, k) => (k === i ? tab : x)) });
  const move = (i: number, by: number) => {
    const tabs = [...d.tabs]; const j = i + by;
    if (j < 0 || j >= tabs.length) return;
    [tabs[i], tabs[j]] = [tabs[j], tabs[i]]; set({ tabs });
    const ss = [...src]; [ss[i], ss[j]] = [ss[j], ss[i]]; setSrc(ss);
  };
  const removeTab = (i: number) => { set({ tabs: d.tabs.filter((_x, k) => k !== i) }); setSrc(src.filter((_x, k) => k !== i)); };
  // which workspace tabs can still be added: tabs with plotted signals, not already in this template
  // (by origin, or - for a template being edited - by having the very same signals in the same plots)
  const sigKey = (tab: TplTab) => JSON.stringify(tab.plots.map((p) => p.signals.map((x) => x.name).sort()));
  const haveKeys = new Set(d.tabs.map(sigKey));
  const candidates = ws.tabs.map((tab, i) => {
    const key = sigKey(templateFromTabs([tab], "").template.tabs[0]);
    return { tab, name: suggestTabName(tab, i, lang), plots: tab.plots.length, added: src.includes(tab.id) || haveKeys.has(key) };
  }).filter((c) => tabHasContent(c.tab));
  const remaining = candidates.filter((c) => !c.added);
  const groups = Array.from(new Set(all.filter((x) => !x.builtin).map((x) => x.group).filter(Boolean))) as string[];
  const blocked = includers(d.id || "\u0000new", all);
  const canInclude = all.filter((x) => x.id !== d.id && !blocked.has(x.id) && !(d.includes ?? []).includes(x.id));
  const usedSlots = new Set(d.tabs.flatMap((tab) => [...tab.plots.flatMap((p) => [...p.signals.map((s) => s.slot ?? d.slots[0]?.id), p.xSlot]),
    ...(tab.lanes ?? []).map((l) => l.slot)]));
  const incSlots = new Set((d.includes ?? []).flatMap((id) => all.find((x) => x.id === id)?.slots.map((s) => s.id) ?? []));
  // a slot nothing uses any more (its tabs were removed) is dropped by itself
  const liveSlots = d.slots.filter((s) => usedSlots.has(s.id) || incSlots.has(s.id));
  const shownSlots = liveSlots.length ? liveSlots : d.slots.slice(0, 1);
  const used = expand({ ...d, slots: shownSlots }, all);
  const usedFiles = used.slots;

  /** Tabs of the workspace into this template: their files become this template's slots where the
   *  file kind matches (else new slots). */
  const addTabs = (tabs: typeof ws.tabs) => {
    const res = templateFromTabs(tabs, d.name);
    const made = res.template;
    const slots = [...d.slots];
    const remap = new Map<string, string>();
    const sr = { ...slotRun };
    const taken = new Set<string>();
    for (const s of made.slots) {
      const rid = res.slotRuns[s.id];
      // 1) the slot already made from this same file; 2) for a saved template (slots of unknown origin),
      // a slot that takes the same kind of file; 3) otherwise a new slot, named after its file
      const same = slots.find((x) => rid && sr[x.id] === rid)
        ?? slots.find((x) => !sr[x.id] && !taken.has(x.id) && !!x.formats?.length && !!s.formats?.length && x.formats.some((f) => s.formats!.includes(f)));
      if (same) { remap.set(s.id, same.id); taken.add(same.id); if (rid) sr[same.id] = rid; continue; }
      let k = slots.length + 1, id = `f${k}`;
      while (slots.some((x) => x.id === id)) id = `f${++k}`;
      slots.push({ ...s, id });
      remap.set(s.id, id); taken.add(id);
      if (rid) sr[id] = rid;
    }
    setSlotRun(sr);
    const fix = (sl?: string) => remap.get(sl ?? made.slots[0].id) ?? sl;
    const newTabs = made.tabs.map((tab) => ({ ...tab, lanes: tab.lanes?.map((l) => ({ ...l, slot: fix(l.slot) })),
      plots: tab.plots.map((p) => ({ ...p, xSlot: p.xSignal ? fix(p.xSlot) : undefined, signals: p.signals.map((s) => ({ ...s, slot: fix(s.slot) })) })) }));
    set({ slots, tabs: [...d.tabs, ...newTabs] });
    setSrc([...src, ...tabs.map((x) => x.id)]);
  };

  const save = async () => {
    if (!d.name.trim()) { useApp.getState().toast({ kind: "error", text: t("tplNeedName") }); return; }
    if (!d.tabs.length && !(d.includes ?? []).length) { useApp.getState().toast({ kind: "error", text: t("tplNeedTabs") }); return; }
    setBusy(true);
    // a single tab that never got a name of its own takes the template's name
    const autoName = new RegExp(`^(${t("tab")}|Tab) \\d+$`);
    // (also a name the editor only suggested from the plots, for a workspace tab that had none)
    const srcTab = ws.tabs.find((x) => x.id === src[0]);
    const suggested = !!srcTab && !(srcTab.name || "").trim() && d.tabs[0]?.name === suggestTabName(srcTab, ws.tabs.indexOf(srcTab), lang);
    const tabs = d.tabs.length === 1 && (!d.tabs[0].name || autoName.test(d.tabs[0].name) || suggested) ? [{ ...d.tabs[0], name: d.name.trim() }] : d.tabs;
    try {
      const r = await api.saveTemplate({ ...d, tabs, slots: shownSlots.length ? shownSlots : [{ id: "main", name: "@tplSlotFile" }] }, !isNew);
      useApp.getState().toast({ kind: "info", text: t("tplSaved", { name: r.template.name }) });
      onSaved(r.template.id);
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
    finally { setBusy(false); }
  };

  return (
    <div className="tpl-editor">
      <h3>{isNew ? t("tplNewTitle") : t("tplEditTitle")}</h3>
      <label className="afield"><span>{t("tplName")}</span>
        <input value={d.name} onChange={(e) => set({ name: e.target.value })} autoFocus /></label>
      <label className="afield"><span>{t("tplDescription")}</span>
        <textarea rows={2} value={tx(d.description, lang)} onChange={(e) => set({ description: e.target.value })} /></label>
      <label className="afield"><span>{t("tplGroupLabel")}</span>
        <input list="tpl-groups" value={d.group && d.group !== "mine" ? d.group : ""} placeholder={t("tplGroup_mine")}
          onChange={(e) => set({ group: e.target.value || undefined })} />
        <datalist id="tpl-groups">{groups.map((g) => <option key={g} value={g} />)}</datalist></label>

      <h4>{t("tplUsedFiles")} <span className="hint">{t("tplUsedFilesHint")}</span></h4>
      <ul className="tpl-used-files">
        {usedFiles.map((s) => (
          <li key={s.id}>
            <Icon.File />
            <span className="tpl-used-name" title={s.path ?? ""}>{s.file ?? tx(s.name, lang)}</span>
            {s.formats?.length ? <span className="badge">{s.formats.join(", ").toUpperCase()}</span> : null}
            <span className="hint">{(() => {
              const n = slotNames(s.id, used.slots, used.tabs).length;
              return n === 1 ? t("tplSignalOne") : n ? t("tplSlotSignals", { n }) : t("tplSlotIncluded");
            })()}</span>
          </li>
        ))}
        {!usedFiles.length && <li className="hint">{t("tplNoOwnTabs")}</li>}
      </ul>

      <h4>{t("tplTabs")}</h4>
      {!d.tabs.length && <p className="hint">{t("tplNoOwnTabs")}</p>}
      <ol className="tpl-edit-tabs">
        {d.tabs.map((tab, i) => (
          <li key={i}>
            <div className="tpl-edit-tab">
              <input value={tab.name} onChange={(e) => setTab(i, { ...tab, name: e.target.value })} aria-label={t("tplTabName")} />
              <button className="linkbtn" aria-expanded={open === i} onClick={() => setOpen(open === i ? null : i)}>{(tab.plots.length === 1 ? t("tplPlotsOne") : t("tplPlotsN", { n: tab.plots.length }))}</button>
              <button className="iconbtn sm" disabled={i === 0} onClick={() => move(i, -1)} aria-label={t("moveUp")}>▲</button>
              <button className="iconbtn sm" disabled={i === d.tabs.length - 1} onClick={() => move(i, 1)} aria-label={t("moveDown")}>▼</button>
              <button className="iconbtn sm" onClick={() => removeTab(i)} aria-label={t("remove")}><Icon.Trash /></button>
            </div>
            {open === i && (
              <ul className="tpl-edit-plots">
                {tab.plots.map((p, pi) => (
                  <li key={pi}>
                    <b>{p.title || `${t("plot")} ${pi + 1}`}</b>{p.mode && p.mode !== "time" ? <span className="hint"> · {p.mode}</span> : null}
                    {p.signals.map((s, si) => (
                      <div key={si} className="tpl-edit-sig">
                        <span>{s.name}</span>
                        {d.slots.length > 1 && (
                          <select value={s.slot ?? d.slots[0].id} aria-label={t("tplFromFile")} onChange={(e) => setTab(i, { ...tab, plots: tab.plots.map((pp, k) => k !== pi ? pp
                            : { ...pp, signals: pp.signals.map((ss, kk) => (kk === si ? { ...ss, slot: e.target.value } : ss)) }) })}>
                            {d.slots.map((sl) => <option key={sl.id} value={sl.id}>{tx(sl.name, lang)}</option>)}
                          </select>
                        )}
                      </div>
                    ))}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
      {candidates.length > 0 && (
        <div className="tpl-add-row">
          <select className="tpl-add-tab" value="" aria-label={t("tplAddTab")} disabled={!remaining.length}
            size={1} onChange={(e) => {
              const v = e.target.value;
              if (v === "*rest") addTabs(remaining.map((c) => c.tab));
              else { const c = remaining.find((x) => x.tab.id === v); if (c) addTabs([c.tab]); }
            }}>
            <option value="">{t("tplAddTab")}</option>
            {candidates.map((c) => (
              <option key={c.tab.id} value={c.tab.id} disabled={c.added}>
                {c.name} ({c.added ? t("tplAdded") : c.plots === 1 ? t("tplPlotsOne") : t("tplPlotsShort", { n: c.plots })})
              </option>
            ))}
            {remaining.length > 1 && <option value="*rest">{t("tplAddRemaining", { n: remaining.length })}</option>}
          </select>
        </div>
      )}

      <h4>{t("tplIncludes")} <span className="hint">{t("tplIncludesHint")}</span></h4>
      <ul className="tpl-includes">
        {(d.includes ?? []).map((id) => {
          const x = all.find((y) => y.id === id);
          return <li key={id}><span>{x ? tx(x.name, lang) : <span className="err">{id}</span>}</span>
            <button className="iconbtn sm" aria-label={t("remove")} onClick={() => set({ includes: (d.includes ?? []).filter((y) => y !== id) })}><Icon.Trash /></button></li>;
        })}
      </ul>
      {canInclude.length > 0 && (
        <select value="" aria-label={t("tplAddInclude")} onChange={(e) => {
          const inc = all.find((x) => x.id === e.target.value);
          if (!inc) return;
          // the included template's file slots join this one's (by id)
          const slots = [...d.slots];
          for (const s of inc.slots) if (!slots.some((x) => x.id === s.id)) slots.push(s);
          set({ includes: [...(d.includes ?? []), inc.id], slots });
        }}>
          <option value="">+ {t("tplAddInclude")}…</option>
          {canInclude.map((x) => <option key={x.id} value={x.id}>{tx(x.name, lang)}</option>)}
        </select>
      )}

      <div className="tpl-actions">
        <button className="btn primary" disabled={busy} onClick={save}>{t("save")}</button>
        <button className="btn" onClick={onCancel}>{t("cancel")}</button>
        {onDelete && <button className="btn danger" onClick={onDelete}><Icon.Trash /> {t("tplDelete")}</button>}
      </div>
    </div>
  );
}

export type { TplSlot };
