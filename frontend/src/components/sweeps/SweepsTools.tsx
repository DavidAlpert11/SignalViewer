/* CC1 / CC2: the Sweeps area's tools in the top row - File ▾ (open, the study kept, its file, Clear) and its undo /
   redo. Loaded with the area (lazy in TopBar), so the Sweeps code stays out of the main bundle. */
import { useT } from "../../i18n";
import { Icon } from "../../icons";
import { openMenu } from "../Overlays";
import { SweepsUndo } from "./SweepsArea";
import { sweepsFileItems } from "../../sweeps/fileMenu";

export default function SweepsTools() {
  const t = useT();
  const at = (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const rtl = document.documentElement.dir === "rtl";
    return { clientX: rtl ? Math.max(8, r.right - 300) : r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent;
  };
  return (
    <span className="area-tools" role="toolbar" aria-label={t("areaSweeps")}>
      <button className="btn file-menu-btn" aria-haspopup="menu" aria-label={t("topFile")} title={t("swFileHint")}
        onClick={(e) => openMenu(at(e), sweepsFileItems(t))}>
        <Icon.Folder /><span className="hide-compact">{t("topFile")}</span> <Icon.Chevron width={12} height={12} />
      </button>
      <span className="sep" />
      <SweepsUndo />
    </span>
  );
}
