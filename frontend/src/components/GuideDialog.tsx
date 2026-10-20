import { useEffect, useState, type ReactNode } from "react";
import { useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { useEscape } from "./Overlays";

/* T55: the user guide (docs/GUIDE.md, docs/GUIDE.he.md) inside the app - Help > User guide, F1.
   Loaded only when opened. A small Markdown reader for what the guide uses: headings, paragraphs,
   lists, tables, `code`, **bold**, *italic*. Built as React elements (no HTML from text). */

function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m: RegExpExecArray | null, k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const s = m[0];
    if (s.startsWith("`")) out.push(<code key={k++}>{s.slice(1, -1)}</code>);
    else if (s.startsWith("**")) out.push(<b key={k++}>{s.slice(2, -2)}</b>);
    else out.push(<i key={k++}>{s.slice(1, -1)}</i>);
    last = m.index + s.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function renderGuide(md: string): ReactNode[] {
  const lines = md.replace(/\r/g, "").split("\n");
  const out: ReactNode[] = [];
  let i = 0, k = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (!l.trim()) { i++; continue; }
    const h = /^(#{1,3})\s+(.*)$/.exec(l);
    if (h) {
      const n = h[1].length;
      out.push(n === 1 ? <h2 key={k++}>{inline(h[2])}</h2> : n === 2 ? <h3 key={k++}>{inline(h[2])}</h3> : <h4 key={k++}>{inline(h[2])}</h4>);
      i++; continue;
    }
    if (l.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        const cells = lines[i].trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        if (!cells.every((c) => /^:?-+:?$/.test(c))) rows.push(cells);
        i++;
      }
      const [head, ...body] = rows;
      out.push(<table key={k++} className="guide-table"><thead><tr>{head.map((c, j) => <th key={j}>{inline(c)}</th>)}</tr></thead>
        <tbody>{body.map((r, a) => <tr key={a}>{r.map((c, j) => <td key={j}>{inline(c)}</td>)}</tr>)}</tbody></table>);
      continue;
    }
    if (/^- /.test(l)) {
      const items: string[] = [];
      while (i < lines.length && (/^- /.test(lines[i]) || (/^ {2}\S/.test(lines[i]) && items.length))) {
        if (/^- /.test(lines[i])) items.push(lines[i].slice(2)); else items[items.length - 1] += " " + lines[i].trim();
        i++;
      }
      out.push(<ul key={k++}>{items.map((x, j) => <li key={j}>{inline(x)}</li>)}</ul>);
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#|\||- )/.test(lines[i])) { para.push(lines[i].trim()); i++; }
    out.push(<p key={k++}>{inline(para.join(" "))}</p>);
  }
  return out;
}

export default function GuideDialog() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const [md, setMd] = useState<string | null>(null);
  const close = () => useApp.setState({ guideOpen: false });
  useEscape(close, true);
  useEffect(() => {
    let off = false;
    (lang === "he" ? import("../../../docs/GUIDE.he.md?raw") : import("../../../docs/GUIDE.md?raw"))
      .then((m) => { if (!off) setMd(m.default); }).catch(() => { if (!off) setMd(""); });
    return () => { off = true; };
  }, [lang]);
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog guide" role="dialog" aria-label={t("menuGuide")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("menuGuide")}</h2>
          <button className="iconbtn" autoFocus onClick={close} aria-label={t("close")}><Icon.X /></button></div>
        <div className="dialog-body guide-body">{md === null ? null : renderGuide(md)}</div>
      </div>
    </div>
  );
}
