/* W10: Save / Don't save / Cancel when the app's window closes with unsaved work (unsaved.ts). */
import { useEffect, useState } from "react";
import { useT } from "../i18n";
import { saveSession } from "../files";
import { closeAsk, closeNow, setCloseAsk } from "../unsaved";
import { useEscape } from "./Overlays";

export default function UnsavedDialog() {
  const t = useT();
  const [open, setOpen] = useState(closeAsk.open);
  useEffect(() => {
    const f = () => setOpen(closeAsk.open);
    closeAsk.listeners.add(f);
    return () => { closeAsk.listeners.delete(f); };
  }, []);
  useEscape(() => setCloseAsk(false), open);
  if (!open) return null;
  const save = async () => { if (await saveSession()) { setCloseAsk(false); void closeNow(); } };
  return (
    <div className="scrim" onMouseDown={() => setCloseAsk(false)}>
      <div className="dialog small unsaved-dialog" role="alertdialog" aria-label={t("unsavedTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("unsavedTitle")}</h2></div>
        <div className="dialog-pad"><p className="confirm-text">{t("unsavedText")}</p></div>
        <div className="dialog-foot unsaved-foot">
          <button className="btn outline discard" onClick={() => { setCloseAsk(false); void closeNow(); }}>{t("unsavedDiscard")}</button>
          <button className="btn outline" autoFocus onClick={() => setCloseAsk(false)}>{t("cancel")}</button>
          <button className="btn primary" onClick={save}>{t("unsavedSave")}</button>
        </div>
      </div>
    </div>
  );
}
