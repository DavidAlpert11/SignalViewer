import { useEffect, useState } from "react";
import { api, type PyOp, type PyOpsInfo } from "../api";
import { pickPath, useApp } from "../store";
import { useT } from "../i18n";

/** T31: the chosen Python operation and its arguments (AnalysisPanel turns it into op "py"). */
export interface PyChoice { op: PyOp; args: Record<string, number | string | boolean> }

/** The "Python" kind of Create signals: the user's own operations from their operations folder
 *  (only that folder runs; a session keeps only the operation's name). Lists the operations with
 *  their description and parameters, the files that did not load, and the folder's buttons. */
export default function PyOpsSection({ choice, onChange }: { choice: PyChoice | null; onChange: (c: PyChoice | null) => void }) {
  const t = useT();
  const [info, setInfo] = useState<PyOpsInfo | null>(null);
  const [busy, setBusy] = useState(false);

  const apply = (r: PyOpsInfo) => {
    setInfo(r);
    const same = choice && r.ops.find((o) => o.id === choice.op.id);
    if (same) onChange({ op: same, args: { ...same.params, ...pick(choice.args, same.params) } });
    else onChange(r.ops[0] ? { op: r.ops[0], args: { ...r.ops[0].params } } : null);
  };
  const run = async (f: () => Promise<PyOpsInfo>) => {
    setBusy(true);
    try {
      apply(await f());
      // F34: a reload / another folder recomputes the signals made with Python operations: the
      // run list carries their new versions, and the plots showing them fetch them again
      if (f !== api.pyops) useApp.setState({ runs: await api.listRuns() });
    }
    catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
    finally { setBusy(false); }
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { run(api.pyops); }, []);

  const changeFolder = async () => {
    const path = await pickPath({ mode: "folder", title: t("pyChooseFolder") });
    if (path) run(() => api.pyopsFolder(path));
  };
  const reveal = async () => {
    try { await api.pyopsReveal(); }
    catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
  };

  const saveClient = async () => {
    const path = await pickPath({ mode: "folder", title: t("pushSaveClientTitle") });
    if (!path) return;
    try {
      const r = await api.pushSaveClient(path);
      useApp.getState().toast({ kind: "info", text: t("pushClientSaved", { path: r.path }) });
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
  };

  if (!info) return <p className="hint">{t("loading")}</p>;
  const op = choice?.op;
  return (
    <div className="pyops">
      <p className="hint">{t("pyIntro")}</p>
      {info.ops.length > 0 && op && <>
        <label className="afield"><span>{t("operation")}</span>
          <select value={op.id} onChange={(e) => {
            const o = info.ops.find((x) => x.id === e.target.value);
            if (o) onChange({ op: o, args: { ...o.params } });
          }}>
            {info.ops.map((o) => <option key={o.id} value={o.id} title={o.id}>{o.name}</option>)}
          </select>
        </label>
        {op.doc && <p className="hint pyops-doc" dir="auto">{op.doc}</p>}
        {Object.entries(op.params).map(([k, d]) => (
          <label key={k} className="afield"><span>{k}</span>
            {typeof d === "boolean"
              ? <input type="checkbox" checked={!!choice!.args[k]} onChange={(e) => onChange({ op, args: { ...choice!.args, [k]: e.target.checked } })} />
              : <input type={typeof d === "number" ? "number" : "text"} step="any" value={String(choice!.args[k] ?? d)}
                  onChange={(e) => onChange({ op, args: { ...choice!.args, [k]: e.target.value } })} />}
          </label>
        ))}
      </>}
      {!info.ops.length && <p className="empty-note">{t("pyNone")}</p>}
      {info.errors.length > 0 && (
        <div className="pyops-errors" role="alert">
          <b>{t("pyErrors")}</b>
          {info.errors.map((e, i) => <div key={i} dir="ltr"><code>{e.file}</code> {e.error}</div>)}
        </div>
      )}
      <div className="pyops-push">
        <b>{t("pushTitle")}</b>
        <p className="hint">{t("pushHint")}</p>
        <pre dir="ltr">{"from signalviewer_push import show\nshow(t, {\"altitude\": alt}, name=\"sim 3\")"}</pre>
        <button className="btn sm" onClick={saveClient}>{t("pushSaveClient")}</button>
      </div>
      <div className="pyops-folder">
        <span className="pyops-path">{t("pyFolder")}: <bdi dir="ltr" title={info.folder}>{info.folder}</bdi></span>
        <div className="pyops-btns">
          <button className="btn sm" disabled={busy} onClick={() => run(api.pyopsReload)}>{t("pyReload")}</button>
          <button className="btn sm" disabled={busy} onClick={reveal}>{t("pyOpenFolder")}</button>
          {!info.ops.length && <button className="btn sm" disabled={busy} onClick={() => run(api.pyopsExample)}>{t("pyExample")}</button>}
          <button className="btn sm" disabled={busy} onClick={changeFolder}>{t("pyChangeFolder")}</button>
          {!info.default && <button className="btn sm" disabled={busy} onClick={() => run(() => api.pyopsFolder(null))}>{t("pyDefaultFolder")}</button>}
        </div>
      </div>
    </div>
  );
}

/** Keep the user's values for parameters the operation still has (after Reload). */
function pick(args: Record<string, number | string | boolean>, params: Record<string, unknown>) {
  return Object.fromEntries(Object.entries(args).filter(([k]) => k in params));
}
