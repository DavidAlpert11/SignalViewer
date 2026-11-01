/* The Sweeps templates (S07): roles, scales, goals, robustness, what is shown (maps, table columns,
   next runs' choices) - without the table's runs - for the next table with the same columns. Save
   the study as one (asks before replacing one of the same name), apply one, export one to a file
   for a colleague, import one, delete one. Like the Recordings templates' library. */
import { useEffect, useState } from "react";
import { pickPath } from "../../store";
import { useT } from "../../i18n";
import { Icon } from "../../icons";
import { sweepApi } from "../../sweeps/api";
import { useSweeps, type Study } from "../../sweeps/state";
import { notify, notifyError } from "../../sweeps/notify";
import { confirmAsk, useEscape } from "../Overlays";

export default function TemplatesDialog({ study, onClose }: { study: Study; onClose: () => void }) {
  const t = useT();
  useEscape(onClose);
  const st = useSweeps.getState();
  const templates = useSweeps((s) => s.templates);
  const [sel, setSel] = useState<string | null>(null);
  const [name, setName] = useState(study.name.replace(/\.[^.]+$/, ""));
  useEffect(() => { st.loadTemplates(); }, [st]);
  const have = new Set(study.columns.map((c) => c.name));
  const fit = (cols: { name: string }[]) => cols.filter((c) => have.has(c.name)).length;
  const cur = templates.find((x) => x.name === sel) ?? null;

  const save = async () => {
    const n = name.trim();
    if (!n) return;
    if (templates.some((x) => x.name === n) && !(await confirmAsk(t("swTplReplace"), t("swTplReplaceAsk", { n })))) return;
    try { await st.saveTemplate(n); setSel(n); notify(t("swTemplateSaved", { n })); } catch (e) { notifyError(e); }
  };
  const apply = (n: string) => { st.applyTemplate(n); notify(t("swTplApplied", { n })); onClose(); };
  const exportTo = async () => {
    if (!cur) return;
    const p = await pickPath({ mode: "save", title: t("swTplExport"), exts: [".json"], defaultName: `${cur.name}.json` });
    if (!p) return;
    try { const r = await sweepApi.exportTemplate(cur.name, p); notify(t("swSaved", { path: r.path })); } catch (e) { notifyError(e); }
  };
  const importFrom = async () => {
    const p = await pickPath({ mode: "open", title: t("swTplImport"), exts: [".json"] });
    if (!p) return;
    try { const n = await st.importTemplate(p); setSel(n); notify(t("swTplImported", { n })); } catch (e) { notifyError(e); }
  };
  const remove = async () => {
    if (!cur || !(await confirmAsk(t("swTplDelete"), t("swTplDeleteAsk", { n: cur.name })))) return;
    try { await st.deleteTemplate(cur.name); notify(t("swTemplateDeleted", { n: cur.name })); setSel(null); } catch (e) { notifyError(e); }
  };
  const goals = (q: unknown) => ((q as { goals?: unknown[] })?.goals ?? []).length;

  return (
    <div className="scrim" onMouseDown={onClose}>
      <div className="dialog sw-tpl" role="dialog" aria-label={t("swTemplates")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("swTemplates")}</h2>
          <button className="iconbtn" onClick={onClose} aria-label={t("close")}><Icon.X /></button></div>
        <div className="dialog-body">
          <p className="hint">{t("swTplIntro")}</p>
          <div className="sw-row sw-tpl-save">
            <input aria-label={t("swTemplateName")} value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") save(); }} />
            <button className="btn primary" disabled={!name.trim()} onClick={save}>{t("swTplSaveThis")}</button>
            <button className="btn outline" onClick={importFrom}>{t("swTplImport")}</button>
          </div>
          {templates.length === 0 ? <p className="empty-note">{t("swTplNone")}</p> : (
            <div className="sw-tpl-list" role="listbox" aria-label={t("swTemplates")}>
              {templates.map((x) => {
                const f = fit(x.columns);
                return (
                  <button key={x.name} role="option" aria-selected={sel === x.name} className={`sw-tpl-item${sel === x.name ? " on" : ""}`}
                    onClick={() => setSel(x.name)} onDoubleClick={() => apply(x.name)}>
                    <b>{x.name}</b>
                    <span className="hint">{t("swTplFit", { n: f, of: x.columns.length })} · {t("swTplGoals", { n: goals(x.question) })}
                      {x.saved ? ` · ${x.saved}` : ""}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <div className="dialog-foot">
          <button className="btn outline sw-danger" disabled={!cur} onClick={remove}>{t("swTplDelete")}</button>
          <span style={{ flex: 1 }} />
          <button className="btn outline" disabled={!cur} onClick={exportTo}>{t("swTplExport")}</button>
          <button className="btn primary" disabled={!cur} onClick={() => cur && apply(cur.name)}>{t("swApply")}</button>
        </div>
      </div>
    </div>
  );
}
