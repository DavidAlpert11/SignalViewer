/* Groups of sets (MF00): the automatic ones (all, holds, Pareto, fails, error, marked) and the
   user's - colour, name, count, the eye (hidden in every plot and the table), a click makes it the
   active group (what the tools read). The brush saves as a group (a live rule; Shift: the sets it
   has now, frozen). A group's menu: rename, freeze, ∪ ∩ ∖ with the active group, delete. */
import { useMemo, useState } from "react";
import { useT, type TKey } from "../../i18n";
import { category } from "../../sweeps/colors";
import { hasFilter } from "../../sweeps/filters";
import { autoMasks, combine, count, groupMask, maskOfKey, setIds, type AutoGroup, type GroupOp } from "../../sweeps/groups";
import { useSweeps, type Study } from "../../sweeps/state";
import { openMenu } from "../Overlays";

const AUTO_KEYS: Record<AutoGroup | "marked", TKey> = {
  all: "swGrpAll", holds: "swGrpHolds", pareto: "swGrpPareto", fails: "swGrpFails", error: "swGrpError", suggested: "swGrpSuggested", marked: "swGrpMarked",
};
const OP_KEYS: Record<GroupOp, TKey> = { union: "swGrpUnion", intersect: "swGrpIntersect", minus: "swGrpMinus" };

export default function GroupsPanel({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const a = study.answer!;
  const v = study.view;
  const groups = useMemo(() => v.groups ?? [], [v.groups]);
  const ids = useMemo(() => setIds(a), [a]);
  const auto = useMemo(() => autoMasks(a, [], ids), [a, ids]);
  const counts = useMemo(() => new Map(groups.map((g) => [g.id, count(groupMask(g, a, ids))])), [groups, a, ids]);
  const [editing, setEditing] = useState<string | null>(null);
  const active = v.activeGroup ?? "all";
  const brush = Object.values(v.filters).some(hasFilter);
  const nameOf = (key: string) => (key in AUTO_KEYS ? t(AUTO_KEYS[key as AutoGroup]) : groups.find((g) => g.id === key)?.name ?? key);
  const nextName = () => t("swGrpNew", { n: groups.length + 1 });

  const autoRows: (AutoGroup | "marked")[] = ["all", "holds",
    ...(a.sets.some((c) => c.name === "#pareto") ? ["pareto" as const] : []), "fails",
    ...(count(auto.error) ? ["error" as const] : []), ...(v.rerun.length ? ["marked" as const] : [])];

  const menu = (e: React.MouseEvent, id: string) => {
    const g = groups.find((x) => x.id === id)!;
    const other = active !== id ? maskOfKey(a, groups, active, v.rerun, [], ids) : null;
    openMenu(e, [
      { label: t("swGrpRename"), run: () => setEditing(id) },
      ...(!g.frozen ? [{ label: t("swGrpFreeze"), run: () => st.editGroup(id, { frozen: true }) }] : []),
      ...(other ? (["union", "intersect", "minus"] as GroupOp[]).map((op) => ({
        label: t(OP_KEYS[op], { a: g.name, b: nameOf(active) }),
        run: () => st.addFrozenGroup(`${g.name} ${op === "union" ? "∪" : op === "intersect" ? "∩" : "∖"} ${nameOf(active)}`, combine(op, groupMask(g, a, ids), other)),
      })) : []),
      { label: t("swGrpDelete"), run: () => st.removeGroup(id) },
    ]);
  };

  return (
    <div className="sw-groups" aria-label={t("swGroups")}>
      <div className="sw-groups-head">
        <b>{t("swGroups")}</b>
        <button className="btn outline" disabled={!brush} title={t("swGrpSaveHint")}
          onClick={(e) => st.saveGroup(e.shiftKey, nextName())}>{t("swGrpSave")}</button>
      </div>
      <ul className="sw-groups-list">
        {autoRows.map((k) => {
          const m = k === "marked" ? maskOfKey(a, groups, "marked", v.rerun, [], ids)! : auto[k];
          return (
            <li key={k} className={`sw-group auto${active === k ? " active" : ""}`} data-group={k}
              onClick={() => st.setView({ activeGroup: k === "all" ? undefined : k })}>
              <span className="sw-group-sw auto" />
              <span className="sw-group-name">{t(AUTO_KEYS[k])}</span>
              <span className="sw-group-n">{count(m).toLocaleString()}</span>
              {k === "marked" && <button className="iconbtn" title={t("swGrpFromMarked")} aria-label={t("swGrpFromMarked")}
                onClick={(e) => { e.stopPropagation(); st.addFrozenGroup(nextName(), m); }}>+</button>}
            </li>
          );
        })}
        {groups.map((g) => (
          <li key={g.id} className={`sw-group${active === g.id ? " active" : ""}${g.hidden ? " hidden" : ""}`} data-group={g.id}
            onClick={() => st.setView({ activeGroup: g.id })} onContextMenu={(e) => menu(e, g.id)}>
            <span className="sw-group-sw" style={{ background: category(g.color) }} />
            {editing === g.id
              ? <input className="sw-group-edit" autoFocus defaultValue={g.name} onClick={(e) => e.stopPropagation()}
                  onBlur={(e) => { const n = e.target.value.trim(); if (n) st.editGroup(g.id, { name: n }); setEditing(null); }}
                  onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); if (e.key === "Escape") setEditing(null); }} />
              : <span className="sw-group-name" onDoubleClick={() => setEditing(g.id)}
                  title={t(g.frozen ? "swGrpFrozen" : "swGrpLive")}>{g.frozen ? "❄ " : ""}{g.name}</span>}
            <span className="sw-group-n">{(counts.get(g.id) ?? 0).toLocaleString()}</span>
            <button className="iconbtn" aria-pressed={!g.hidden} title={t(g.hidden ? "swGrpShow" : "swGrpHide")} aria-label={t(g.hidden ? "swGrpShow" : "swGrpHide")}
              onClick={(e) => { e.stopPropagation(); st.editGroup(g.id, { hidden: !g.hidden }); }}>{g.hidden ? "◌" : "◉"}</button>
            <button className="iconbtn" aria-label={t("swGrpMenu")} onClick={(e) => menu(e, g.id)}>⋯</button>
          </li>
        ))}
      </ul>
      {!groups.length && <p className="hint">{t("swGrpEmptyHint")}</p>}
    </div>
  );
}
