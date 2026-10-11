import { useApp } from "../store";
import { useEscape } from "./Overlays";
import { useT, type TKey } from "../i18n";
import { Icon } from "../icons";

const ROWS: [string, TKey][] = [
  ["Ctrl K", "hCommands"], ["Ctrl O", "openFiles"], ["Ctrl S", "saveSession"], ["Ctrl ⇧ O", "openSession"],
  ["Ctrl Z", "undo"], ["Ctrl Y", "redo"], ["Space", "hCursor"], ["D", "dualCursor"], ["← →", "hMoveCursor"],
  ["⇧ ← →", "hMoveCursorFast"], ["1 – 9", "hSelectPlot"], ["R", "resetZoom"], ["Z", "hZoomMode"], ["Backspace", "zoomBack"], ["F5", "refreshAll"], ["P", "hPlay"], ["Delete", "hRemoveSignal"],
  ["Ctrl +  /  Ctrl −", "hTextSize"], ["Ctrl 0", "hTextReset"], ["?", "shortcuts"], ["Esc", "hEscape"],
];
const MOUSE: [TKey, TKey][] = [
  ["hDrag", "hDragDo"], ["hWheel", "hWheelDo"], ["hDouble", "hDoubleDo"], ["hClick", "hClickDo"],
  ["hShiftClick", "hShiftClickDo"], ["hDragSignal", "hDragSignalDo"], ["hPan", "hPanDo"],
  ["hWheelAxis", "hWheelAxisDo"], ["hCtrlWheel", "hCtrlWheelDo"],
  ["hRight", "hRightDo"], ["hDragChip", "hDragChipDo"], ["hCtrlClick", "hCtrlClickDo"], ["hListSel", "hListSelDo"], ["hAltClick", "hAltClickDo"], ["hGutter", "hGutterDo"],
];

export default function Help() {
  const t = useT();
  const open = useApp((s) => s.helpOpen);
  useEscape(() => useApp.setState({ helpOpen: false }), open);
  if (!open) return null;
  const close = () => useApp.setState({ helpOpen: false });
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog help" role="dialog" aria-label={t("shortcuts")} onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={(e) => { if (e.key === "Escape") close(); }}>
        <div className="dialog-head"><h2>{t("shortcuts")}</h2>
          <button className="iconbtn" autoFocus onClick={close} aria-label={t("close")}><Icon.X /></button></div>
        <div className="dialog-body help-body">
          <table className="keys"><tbody>
            {ROWS.map(([k, l]) => <tr key={k}><td><span className="kbd">{k}</span></td><td>{t(l)}</td></tr>)}
          </tbody></table>
          <table className="keys"><tbody>
            {MOUSE.map(([a, b]) => <tr key={a}><td className="mouse">{t(a)}</td><td>{t(b)}</td></tr>)}
          </tbody></table>
        </div>
      </div>
    </div>
  );
}
