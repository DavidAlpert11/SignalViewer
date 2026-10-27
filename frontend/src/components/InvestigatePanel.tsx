import { useEffect, useMemo, useState } from "react";
import { actions, activeTab, fileLabel, useApp, type Condition, type CondResult, type MenuItem } from "../store";
import { fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { openMenu } from "./Overlays";
import ExprInput, { type SigOption } from "./ExprInput";
import WhatChanged from "./WhatChanged";
import { combineConditions, condSignals, deleteCondition, evaluateOne, intervalsByRun, overlayInNewTab, saveCondition, stepOccurrence, updateCondition, usedBy } from "../conditions";
import { api } from "../api";

/** Investigation spec, step 2: the session's named conditions - shown or hidden, stepped through,
 *  edited in place with a live count, combined, deleted (one undo). */
export default function InvestigatePanel() {
  const t = useT();
  const conds = useApp((s) => s.ws.conditions) ?? [];
  const results = useApp((s) => s.condResults);
  const focus = useApp((s) => s.condFocus);
  const edit = useApp((s) => s.condEdit);
  const runs = useApp((s) => s.runs);
  const lang = useApp((s) => s.lang);
  const files = runs.filter((r) => r.format !== "derived");
  const whatChanged = useApp((s) => s.whatChanged);

  const count = (id: string) => {
    const r = results[id] ?? {};
    const vals = Object.values(r);
    return { n: vals.reduce((s, x) => s + (x.count ?? 0), 0), missing: vals.length > 0 && vals.every((x) => x.missing?.length || x.error),
      tip: files.map((f) => { const x = r[f.id]; return `${f.name}: ${x?.missing?.length ? t("condMissing", { names: x.missing.join(", ") }) : x?.error ?? (x?.count ?? 0)}`; }).join("\n") };
  };
  const rowMenu = (e: React.MouseEvent, c: Condition) => {
    e.stopPropagation();
    const others = conds.filter((x) => x.id !== c.id);
    const items: MenuItem[] = [
      ...(c.combine ? [] : [{ label: t("condEdit"), run: () => useApp.setState({ condEdit: { id: c.id } }) }]),
      { label: t("condDuplicate"), run: () => saveCondition({ ...c, id: undefined, name: `${c.name} (2)`, color: undefined } as unknown as Condition) },
      ...(others.length ? [{ label: "", run: () => {}, sep: true },
        ...others.map((o) => ({ label: t("condAndWith", { name: o.name }), run: () => combineConditions(c, o, "and") })),
        ...others.map((o) => ({ label: t("condOrWith", { name: o.name }), run: () => combineConditions(c, o, "or") }))] : []),
      { label: "", run: () => {}, sep: true },
      { label: usedBy(c.id).length ? t("condDeleteUsed", { n: usedBy(c.id).length }) : t("condDelete"), run: () => deleteCondition(c.id) },
    ];
    openMenu(e, items);
  };

  return (
    <aside className="side investigate" aria-label={t("investigate")}>
      <div className="side-head"><h2>{t("investigate")}</h2></div>
      <div className="inv-body">
        {whatChanged && <WhatChanged key={`${whatChanged.a}|${whatChanged.b}`} />}
        <div className="cond-head">
          <h3>{t("conditions")}</h3>
          <button className="btn outline sm cond-new" onClick={() => useApp.setState({ condEdit: { id: "new" } })} disabled={!files.length}>
            <Icon.Plus /> {t("condNew")}
          </button>
        </div>
        {!files.length && <p className="hint">{t("condNoFiles")}</p>}
        {edit?.id === "new" && <CondEditor key="new" />}
        {!conds.length && edit?.id !== "new" && files.length > 0 && <p className="hint">{t("condEmpty")}</p>}
        <ul className="cond-list">
          {conds.map((c) => {
            const k = count(c.id);
            return (
              <li key={c.id} className={`cond-row${focus === c.id ? " focus" : ""}${c.visible ? "" : " hidden"}`}>
                <div className="cond-line">
                  <button className="iconbtn cond-eye" aria-pressed={c.visible} title={t(c.visible ? "condHide" : "condShow")}
                    onClick={() => updateCondition(c.id, { visible: !c.visible })}>{c.visible ? "◉" : "○"}</button>
                  <span className="cond-swatch" style={{ background: c.color }} />
                  <button className="linklike cond-name" title={t("condStepHint")}
                    onClick={() => stepOccurrence(c.id, 1)}>{c.name}</button>
                  <span className="cond-count" title={k.tip}>{k.missing ? "–" : fmtNum(k.n, lang, 6)}</span>
                  <button className="iconbtn cond-more" aria-label={t("condMenu")} onClick={(e) => rowMenu(e, c)}><Icon.More /></button>
                </div>
                {edit?.id === c.id ? <CondEditor key={c.id} cond={c} before={k.n} /> : (
                  <div className="cond-text">{c.combine ? c.combine.ids.map((id) => conds.find((x) => x.id === id)?.name ?? "?").join(c.combine.op === "and" ? " ∧ " : " ∨ ") : c.text}</div>
                )}
              </li>
            );
          })}
        </ul>
        {conds.length > 0 && <p className="hint">{t("condKeysHint")}</p>}
        {conds.length > 0 && <button className="btn outline sm cond-matrix" onClick={() => useApp.setState({ matrixOpen: true })}>{t("mxOpen", { n: files.length })}</button>}
        {focus && conds.some((c) => c.id === focus) && <OccSection key={focus} cond={conds.find((c) => c.id === focus)!} />}
      </div>
    </aside>
  );
}

/** The editor of one condition (or a new one): what it says, its options, and - while it is being
 *  written - how many stretches it finds, before anything is saved. */
function CondEditor({ cond, before }: { cond?: Condition; before?: number }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const draft = useApp((s) => s.condEdit?.draft);
  const [name, setName] = useState(cond?.name ?? draft?.name ?? "");
  const [text, setText] = useState(cond?.text ?? draft?.text ?? "");
  const [exit, setExit] = useState(cond?.exit ?? "");
  const [minDur, setMinDur] = useState(String(cond?.minDur ?? 0));
  const [gap, setGap] = useState(String(cond?.mergeGap ?? 0));
  const [more, setMore] = useState(!!(cond?.exit || cond?.minDur || cond?.mergeGap));
  const [preview, setPreview] = useState<{ n: number; err?: string; hint?: string } | null>(null);
  const signals: SigOption[] = useMemo(() => {
    const seen = new Set<string>();
    return runs.filter((r) => r.format !== "derived").flatMap((r) => r.signals).filter((s) => !seen.has(s.name) && seen.add(s.name))
      .map((s) => ({ label: s.name, sub: "", insert: /^[A-Za-z_][\w.]*$/.test(s.name) ? s.name : `{${s.name}}` }));
  }, [runs]);
  const opts = { text, exit, minDur: Number(minDur) || 0, mergeGap: Number(gap) || 0 };

  // the count while typing (a short pause first: one request per thought, not per key)
  useEffect(() => {
    if (!text.trim()) { setPreview(null); return; }
    const id = setTimeout(async () => {
      try {
        const r = await evaluateOne(opts);
        const vals: CondResult[] = Object.values(r);
        const err = vals.find((x) => x.error)?.error;
        const n = vals.reduce((s, x) => s + (x.count ?? 0), 0);
        const missingAll = vals.length > 0 && vals.every((x) => x.missing?.length);
        let hint: string | undefined;
        if (missingAll) hint = t("condMissing", { names: [...new Set(vals.flatMap((x) => x.missing ?? []))].join(", ") });
        else if (!n && !err) {
          // never: say the range of what it reads, so a wrong threshold shows at once
          const ranges = vals.flatMap((x) => Object.entries(x.ranges ?? {}));
          hint = ranges.length ? t("condNever", { ranges: ranges.slice(0, 3).map(([k, [a, b]]) => `${k} ${fmtNum(a, lang, 4)} … ${fmtNum(b, lang, 4)}`).join("; ") }) : undefined;
        }
        setPreview({ n, err, hint });
      } catch (e) { setPreview({ n: 0, err: String((e as Error).message) }); }
    }, 300);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, exit, minDur, gap]);

  const close = () => useApp.setState({ condEdit: null });
  const ok = !!name.trim() && !!text.trim() && !preview?.err;
  const save = () => {
    if (!ok) return;
    saveCondition({ ...(cond ? { id: cond.id } : {}), name: name.trim(), text: text.trim(), exit: exit.trim() || undefined,
      minDur: Number(minDur) || undefined, mergeGap: Number(gap) || undefined });
    close();
  };
  return (
    <div className="cond-editor" onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } }}>
      <label className="afield"><span>{t("condName")}</span>
        <input className="cond-name-in" value={name} onChange={(e) => setName(e.target.value)} placeholder={t("condNamePh")} autoFocus={!cond} /></label>
      <label className="afield"><span>{t("condWhen")}</span></label>
      <ExprInput value={text} onChange={setText} vars={[]} signals={signals} ariaLabel={t("condWhen")} placeholder='{Speed} > 12 and Mode == "AUTO"'
        invalid={!!preview?.err} onSubmit={save} />
      <button className="linklike cond-more-toggle" onClick={() => setMore(!more)}>{more ? "▾" : "▸"} {t("condMore")}</button>
      {more && <>
        <label className="afield"><span>{t("condExit")}</span></label>
        <ExprInput value={exit} onChange={setExit} vars={[]} signals={signals} ariaLabel={t("condExit")} placeholder="{RPM} < 1900" />
        <label className="afield"><span>{t("condMinDur")}</span>
          <input className="cond-min" type="number" min={0} step="any" value={minDur} onChange={(e) => setMinDur(e.target.value)} /></label>
        <label className="afield"><span>{t("condMergeGap")}</span>
          <input className="cond-gap" type="number" min={0} step="any" value={gap} onChange={(e) => setGap(e.target.value)} /></label>
      </>}
      <p className={`hint cond-preview${preview?.err ? " err" : ""}`}>
        {preview?.err ? preview.err
          : preview ? (cond && before !== undefined && before !== preview.n ? t("condCountChange", { a: before, b: preview.n }) : t("condCount", { n: preview.n }))
            + (preview.hint ? ` ${preview.hint}` : "")
          : t("condHint")}
      </p>
      <div className="cond-actions">
        <button className="btn outline sm" onClick={close}>{t("cancel")}</button>
        <button className="btn primary sm cond-save" disabled={!ok} onClick={save}>{t("save")}</button>
      </div>
    </div>
  );
}

/** Investigation step 3, for the condition in focus: its stretches as a table (one value of one
 *  signal per stretch, sortable, a click goes there), the overlay of them in a new tab, and which
 *  signals differ most inside them from outside. */
function OccSection({ cond }: { cond: Condition }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const results = useApp((s) => s.condResults[cond.id]);
  const names = useMemo(() => condSignals(cond.id), [results, cond.id]);   // eslint-disable-line react-hooks/exhaustive-deps
  const [sig, setSig] = useState("");
  const [stat, setStat] = useState<"max" | "min" | "mean">("max");
  const [sort, setSort] = useState<{ k: "a" | "d" | "v"; up: boolean }>({ k: "a", up: true });
  const [rows, setRows] = useState<{ rid: string; a: number; b: number; v: number | null }[]>([]);
  const [differ, setDiffer] = useState<Awaited<ReturnType<typeof api.occDiffer>>["items"] | null>(null);
  const [busy, setBusy] = useState(false);
  const name = sig || names[0] || "";
  const multi = new Set(rows.map((r) => r.rid)).size > 1;

  useEffect(() => {
    const iv = intervalsByRun(cond.id);
    if (!Object.keys(iv).length) { setRows([]); return; }
    let gone = false;
    api.occTable(iv, name ? [name] : []).then((r) => {
      if (!gone) setRows(r.rows.map((x) => ({ rid: x.rid, a: x.a, b: x.b, v: x.values[name]?.[stat] ?? null })));
    }).catch(() => { if (!gone) setRows([]); });
    return () => { gone = true; };
  }, [results, name, stat, cond.id]);
  useEffect(() => { setDiffer(null); }, [results]);

  const sorted = [...rows].sort((p, q) => {
    const f = (r: typeof p) => (sort.k === "a" ? r.a : sort.k === "d" ? r.b - r.a : r.v ?? -Infinity);
    return (f(p) - f(q)) * (sort.up ? 1 : -1);
  });
  const head = (k: "a" | "d" | "v", label: string) => (
    <th><button className="linklike" onClick={() => setSort({ k, up: sort.k === k ? !sort.up : k === "a" })}>
      {label}{sort.k === k ? (sort.up ? " ▴" : " ▾") : ""}</button></th>
  );
  const go = (r: { a: number; b: number }) => {
    const pad = Math.max((r.b - r.a) * 0.5, 0.5);
    actions.showSpan(r.a - pad, r.b + pad);
    useApp.setState({ condFocus: cond.id, cursor: { ...useApp.getState().cursor, on: true, dual: true, t1: r.a, t2: r.b, active: 1 } });
  };
  const copy = () => {
    const lines = [[...(multi ? ["file"] : []), "start_s", "duration_s", `${name}_${stat}`].join("\t"),
      ...sorted.map((r) => [...(multi ? [fileLabel(runs, r.rid)] : []), r.a, r.b - r.a, r.v ?? ""].join("\t"))];
    void navigator.clipboard.writeText(lines.join("\n")).then(() => useApp.getState().toast({ kind: "info", text: t("occCopied") }));
  };
  const findDiffer = async () => {
    setBusy(true);
    try { setDiffer((await api.occDiffer(intervalsByRun(cond.id))).items); }
    catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
    finally { setBusy(false); }
  };
  const addSignal = (n: string, files: string[]) => {
    const tb = activeTab(useApp.getState().ws);
    if (!tb.plots[tb.active]) return;
    actions.addSignals(files.map((rid) => `${rid}/${n}`).filter((id) => runs.some((r) => r.signals.some((s) => s.id === id))));
  };
  if (!rows.length) return null;
  return (
    <section className="occ-section">
      <h3>{t("occTitle", { name: cond.name })}</h3>
      <div className="occ-controls">
        <select className="occ-sig" value={name} onChange={(e) => setSig(e.target.value)} aria-label={t("occSignal")}>
          {names.map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
        <select className="occ-stat" value={stat} onChange={(e) => setStat(e.target.value as "max" | "min" | "mean")} aria-label={t("occStat")}>
          <option value="max">max</option><option value="min">min</option><option value="mean">{t("occMean")}</option>
        </select>
      </div>
      <div className="occ-table-wrap">
        <table className="occ-table">
          <thead><tr>{multi && <th>{t("occFile")}</th>}{head("a", t("occStartS"))}{head("d", t("occDurS"))}{head("v", `${stat}`)}</tr></thead>
          <tbody>
            {sorted.map((r, i) => (
              <tr key={i} onClick={() => go(r)} tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") go(r); }}>
                {multi && <td>{fileLabel(runs, r.rid)}</td>}
                <td>{fmtNum(r.a, lang, 5)}</td><td>{fmtNum(r.b - r.a, lang, 4)}</td><td>{r.v === null ? "–" : fmtNum(r.v, lang, 5)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="occ-actions">
        <button className="btn outline sm occ-overlay" disabled={!name} onClick={() => overlayInNewTab(cond.id, name)}>{t("occOverlay")}</button>
        <button className="btn outline sm occ-differ" disabled={busy} onClick={findDiffer}>{t("occDiffer")}</button>
        <button className="btn outline sm" onClick={copy}>{t("copyTable")}</button>
      </div>
      {differ && (
        <div className="occ-differ-list">
          <p className="hint">{t("occDifferHint")}</p>
          {!differ.length ? <p className="hint">{t("occDifferNone")}</p> : (
            <ol>
              {differ.map((d) => (
                <li key={d.name}>
                  <button className="linklike" title={t("occDifferAdd")} onClick={() => addSignal(d.name, d.files)}>{d.name}</button>
                  {" "}<span className={d.up ? "up" : "down"}>{d.up ? "↑" : "↓"}</span>
                  {" "}{t("occTimes", { x: fmtNum(d.effect, lang, 2) })}
                  <span className="muted"> · {fmtNum(d.meanOut, lang, 4)} → {fmtNum(d.meanIn, lang, 4)}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </section>
  );
}
