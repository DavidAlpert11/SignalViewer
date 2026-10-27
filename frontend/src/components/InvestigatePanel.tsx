import { useEffect, useMemo, useState } from "react";
import { useApp, type Condition, type CondResult, type MenuItem } from "../store";
import { fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { openMenu } from "./Overlays";
import ExprInput, { type SigOption } from "./ExprInput";
import { combineConditions, deleteCondition, evaluateOne, saveCondition, stepOccurrence, updateCondition, usedBy } from "../conditions";

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
