/* The re-run list (owner's spec 2026-11-02): the sets chosen to run again, in the Next runs tab - its
   one home (the button in the top row is gone). Each set with ×, Export (every combination of them,
   or only what is missing or failed), Clear. Its count is in the tab's name. */
import { pickPath } from "../../store";
import { useT } from "../../i18n";
import { Icon } from "../../icons";
import { setIds } from "../../sweeps/groups";
import { say } from "../../sweeps/notify";
import { useSweeps, type Study } from "../../sweeps/state";
import { openMenu } from "../Overlays";

export default function RerunList({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const list = study.view.rerun;
  const forValue = study.view.rerunSplit ?? [];
  const n = list.length + forValue.length;
  const ids = study.answer ? setIds(study.answer) : [];
  const exportRerun = async (onlyMissing: boolean) => {
    st.setView({ onlyMissing });
    const p = await pickPath({ mode: "save", title: t("swExportRerun"), exts: [".csv"], defaultName: "rerun.csv" });
    if (!p) return;
    say(useSweeps.getState().exportRerun(p).then((r) => { useSweeps.getState().journal("export", { path: r.path, n: r.rows }); return t("swExported", { n: r.rows, path: r.path }); }));
  };
  const menu = (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    openMenu({ clientX: r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent, [
      { label: t("swRerunAll"), run: () => exportRerun(false) },
      { label: t("swOnlyMissing"), run: () => exportRerun(true) },
    ]);
  };
  return (
    <section className="sw-rerun" aria-label={t("swRerunList")}>
      <h3>{t("swRerunList")} <span className="hint">({n})</span></h3>
      {!n ? <p className="hint">{t("swRerunEmpty")}</p> : (
        <>
          <ul className="sw-rerun-list">
            {list.map((i) => (
              <li key={i}><span className="sw-ellipsis mono" title={ids[i]}>#{i + 1} {ids[i]?.replace(/\|/g, ", ")}</span>
                <button className="iconbtn sm" aria-label={t("swRemoveFromRerun")} title={t("swRemoveFromRerun")}
                  onClick={() => st.setView({ rerun: list.filter((x) => x !== i) })}><Icon.X width={12} height={12} /></button></li>
            ))}
            {forValue.map((r, j) => (
              <li key={`${r.value}|${r.id}`}><span className="sw-ellipsis mono" title={`${r.id} · ${r.column} = ${r.value}`}>
                {r.id.replace(/\|/g, ", ")} <span className="hint">· {t("swRerunFor", { c: r.column, v: String(r.value) })}</span></span>
                <button className="iconbtn sm" aria-label={t("swRemoveFromRerun")} title={t("swRemoveFromRerun")}
                  onClick={() => st.setView({ rerunSplit: forValue.filter((_, k) => k !== j) })}><Icon.X width={12} height={12} /></button></li>
            ))}
          </ul>
          {forValue.length > 0 && <p className="hint">{t("swRerunForHint")}</p>}
          <div className="sw-row">
            <button className="btn primary" onClick={menu}>{t("swExportRerunN", { n })} ▾</button>
            <button className="btn" onClick={() => st.setView({ rerun: [], rerunSplit: [] })}>{t("swBulkClear")}</button>
          </div>
        </>
      )}
    </section>
  );
}
