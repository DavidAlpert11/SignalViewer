/* RE2: the Report screen's library of ready-made parts and ready reports (reportReady.ts) - by category, each part
   a click (or a drag) into the text where the cursor is; the reference object and the baseline file guessed and
   changeable; the user's own report templates kept and offered again. */
import { useEffect, useState } from "react";
import { api, type ReportScan } from "../api";
import { useApp } from "../store";
import { useT } from "../i18n";
import { prompt } from "./Overlays";
import { deleteMyReport, myReports, partCategories, readyReports, readyText, saveMyReport, type Choice, type MyReport } from "../reportReady";

export default function ReportParts({ block, ready, text }: { block: (s: string) => void; ready: (s: string) => void; text: string }) {
  const t = useT();
  const lang = useApp((s) => s.ws.report?.lang ?? s.lang);
  const version = useApp((s) => s.runs.map((r) => r.id + ":" + (r.version ?? "")).join(","));
  const notes = useApp((s) => (s.ws.notes ?? []).length > 0);
  const [scan, setScan] = useState<ReportScan | null>(null);
  const [choice, setChoice] = useState<Choice>({});
  const [mine, setMine] = useState<MyReport[]>(myReports);
  useEffect(() => {
    let gone = false;
    api.reportParts().then((r) => { if (!gone) setScan(r); }).catch(() => { if (!gone) setScan(null); });
    return () => { gone = true; };
  }, [version]);
  if (!scan) return null;
  const item = (label: string, insert: string, title?: string, run?: () => void) => (
    <button key={label + insert} className="rd-lib-item" title={title ?? insert} draggable
      onDragStart={(e) => { e.dataTransfer.setData("application/x-sv-report", insert); e.dataTransfer.setData("text/plain", insert); }}
      onClick={run ?? (() => block(insert))}>{label}</button>
  );
  const save = async () => {
    const name = await prompt(t("rpSaveMine"), t("rpSaveMineAsk"), "");
    if (!name?.trim()) return;
    setMine(saveMyReport(name.trim(), text));
    useApp.getState().toast({ kind: "info", text: t("rpSavedMine", { name: name.trim() }) });
  };
  const cats = partCategories(scan, lang, choice);
  return (
    <div className="rd-parts">
      <h3 className="eyebrow">{t("rpReady")}</h3>
      <div className="rd-lib-tab rd-ready">
        {readyReports(scan, lang).map((r) => item(r.label, readyText(r.id, scan, lang, choice, notes), r.hint,
          () => ready(readyText(r.id, scan, lang, choice, notes))))}
        {mine.map((m) => (
          <span key={m.name} className="rd-mine">
            {item("★ " + m.name, m.text, t("rpMineHint"), () => ready(m.text))}
            <button className="iconbtn rd-mine-del" title={t("rpMineDelete")} aria-label={t("rpMineDelete")} onClick={() => setMine(deleteMyReport(m.name))}>×</button>
          </span>
        ))}
        <button className="btn outline rd-save-mine" onClick={save}>{t("rpSaveMine")}</button>
      </div>
      <h3 className="eyebrow">{t("rpParts")}</h3>
      {cats.map((c) => (
        <details key={c.id} className={`rd-cat rd-cat-${c.id}`} open={!c.empty}>
          <summary><b>{c.title}</b>{c.found && <span className="hint"> · {c.found}</span>}</summary>
          {c.id === "navigation" && scan.objects.length >= 2 && (
            <label className="afield rd-choice"><span>{t("rpReference")}</span>
              <select value={choice.reference ?? scan.reference ?? ""} onChange={(e) => setChoice({ ...choice, reference: e.target.value })}>
                {scan.objects.map((o) => <option key={o.name} value={o.name}>{o.name} ({o.cls}){o.name === scan.reference ? ` - ${t("rpGuessed")}` : ""}</option>)}
              </select></label>
          )}
          {c.id === "compare" && scan.files.length >= 2 && (
            <label className="afield rd-choice"><span>{t("rpBaseline")}</span>
              <select value={choice.base ?? scan.base ?? scan.files[0].name} onChange={(e) => setChoice({ ...choice, base: e.target.value })}>
                {scan.files.map((f) => <option key={f.id} value={f.name}>{f.name}{f.name === scan.base ? ` - ${t("rpGuessed")}` : ""}</option>)}
              </select></label>
          )}
          {c.empty ? <p className="hint">{c.empty}</p> : <div className="rd-lib-tab">{c.parts.map((p) => item(p.label, p.insert, p.title))}</div>}
        </details>
      ))}
    </div>
  );
}
