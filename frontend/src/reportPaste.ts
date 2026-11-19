/* RE2 (owner, 2026-11-19): what is pasted or dropped into the report from outside - a table from Word, a web page or
   Excel becomes a Markdown table (the text stays the one source: it diffs, travels in templates, opens in old
   versions as text); a picture is kept IN the session (ws.report.assets, downscaled and capped) and written
   ![name](asset:<id>), so it travels with the session and the template and needs no file beside them. No library:
   the browser's DOMParser and a canvas. */

/** A Markdown table cell: one line, the pipes escaped. */
const cell = (s: string) => s.replace(/\s*\n\s*/g, "<br>").replace(/\|/g, "\\|").replace(/\s+/g, " ").trim();

export function rowsToMarkdown(rows: string[][]): string {
  const n = Math.max(...rows.map((r) => r.length));
  const pad = (r: string[]) => [...r, ...Array(n - r.length).fill("")];
  const [head, ...body] = rows.map(pad);
  return ["| " + head.map(cell).join(" | ") + " |", "|" + "---|".repeat(n), ...body.map((r) => "| " + r.map(cell).join(" | ") + " |")].join("\n");
}

/** Inline formatting of a cell or a paragraph: bold, italic, links; everything else its text. */
function inline(el: Node): string {
  let out = "";
  el.childNodes.forEach((c) => {
    if (c.nodeType === 3) { out += (c.textContent ?? "").replace(/\s+/g, " "); return; }
    if (c.nodeType !== 1) return;
    const e = c as HTMLElement, tag = e.tagName.toLowerCase(), inner = inline(e);
    const style = (e.getAttribute("style") ?? "").toLowerCase();
    if (tag === "br") out += "\n";
    else if (!inner.trim()) out += inner;
    else if (tag === "b" || tag === "strong" || /font-weight:\s*(bold|[6-9]00)/.test(style)) out += `**${inner.trim()}** `;
    else if (tag === "i" || tag === "em" || /font-style:\s*italic/.test(style)) out += `*${inner.trim()}* `;
    else if (tag === "a" && /^https?:/.test(e.getAttribute("href") ?? "")) out += `[${inner.trim()}](${e.getAttribute("href")})`;
    else if (tag === "p" || tag === "div") out += inner + "\n";
    else out += inner;
  });
  return out.replace(/ +\n/g, "\n").replace(/\*\* +([.,;:)])/g, "**$1");
}

/** A <table> as rows of cell texts. A merged cell (rowspan / colspan) is repeated in the cells it covers - a
 *  Markdown table has no merged cells, and an empty cell would read as "nothing there". */
export function tableRows(t: HTMLTableElement): { rows: string[][]; merged: boolean } {
  const grid: string[][] = [];
  let merged = false;
  Array.from(t.rows).forEach((tr, r) => {
    grid[r] ??= [];
    let c = 0;
    Array.from(tr.cells).forEach((td) => {
      while (grid[r][c] !== undefined) c++;
      const text = inline(td).trim();
      const rs = Math.max(1, +(td.getAttribute("rowspan") ?? 1) || 1), cs = Math.max(1, +(td.getAttribute("colspan") ?? 1) || 1);
      if (rs > 1 || cs > 1) merged = true;
      for (let i = 0; i < rs; i++) for (let j = 0; j < cs; j++) { (grid[r + i] ??= [])[c + j] = text; }
      c += cs;
    });
  });
  return { rows: grid.map((r) => Array.from(r, (x) => x ?? "")).filter((r) => r.some((x) => x.trim())), merged };
}

/** HTML from the clipboard (Word, a web page, Excel) -> Markdown: tables, headings, lists, paragraphs, bold /
 *  italic / links. null when it has nothing a plain paste would not do as well (no table, no structure). */
export function htmlToMarkdown(html: string): { text: string; merged: boolean } | null {
  const doc = new DOMParser().parseFromString(html, "text/html");
  doc.querySelectorAll("style, script, meta, title, xml, o\\:p").forEach((x) => x.remove());
  const hasTable = !!doc.querySelector("table");
  const structured = hasTable || !!doc.querySelector("h1, h2, h3, ul, ol, b, strong, i, em, [class^='MsoHeading'], [class^='MsoList']");
  if (!structured) return null;
  let merged = false;
  const out: string[] = [];
  const walk = (el: Element) => {
    for (const c of Array.from(el.children)) {
      const tag = c.tagName.toLowerCase(), cls = c.getAttribute("class") ?? "";
      if (tag === "table") {
        const r = tableRows(c as HTMLTableElement);
        merged ||= r.merged;
        if (r.rows.length) out.push(rowsToMarkdown(r.rows));
      } else if (/^h[1-6]$/.test(tag) || /^MsoHeading(\d)/.test(cls)) {
        const lvl = /^h(\d)$/.exec(tag)?.[1] ?? /^MsoHeading(\d)/.exec(cls)?.[1] ?? "2";
        const s = inline(c).trim();
        if (s) out.push(`${"#".repeat(Math.min(6, +lvl))} ${s.replace(/\n/g, " ")}`);
      } else if (tag === "ul" || tag === "ol") {
        out.push(Array.from(c.children).filter((li) => li.tagName.toLowerCase() === "li")
          .map((li, i) => `${tag === "ol" ? `${i + 1}.` : "-"} ${inline(li).trim().replace(/\n/g, " ")}`).join("\n"));
      } else if (/MsoList/.test(cls)) {                 // Word's list paragraphs are <p> with a bullet glyph
        out.push(`- ${inline(c).trim().replace(/^[·•o§\-–\d.)\s]+/, "").replace(/\n/g, " ")}`);
      } else if (tag === "p") {
        const s = inline(c).trim();
        if (s) out.push(s);
      } else walk(c);
    }
  };
  walk(doc.body);
  const text = out.join("\n\n").replace(/\n{3,}/g, "\n\n").trim();
  return text ? { text, merged } : null;
}

/** Tab-separated lines (Excel, LibreOffice, a table copied as text) -> a Markdown table; null otherwise. */
export function tsvToMarkdown(text: string): string | null {
  const lines = text.replace(/\r/g, "").replace(/\n+$/, "").split("\n");
  if (lines.length < 2 || !lines.every((l) => l.includes("\t"))) return null;
  const rows = lines.map((l) => l.split("\t"));
  return rowsToMarkdown(rows);
}

// ------------------------------------------------------------------------------------------------ pictures

export interface Asset { name: string; mime: string; data: string; w: number; h: number }
/** a picture is downscaled to this on its long side; above the caps the screen says so */
export const MAX_SIDE = 2000;
export const MAX_ONE = 5 * 1024 * 1024;
export const MAX_ALL = 20 * 1024 * 1024;

/** A short id from the bytes (the same picture pasted twice is kept once). */
export async function assetId(data: string): Promise<string> {
  const bytes = new TextEncoder().encode(data);
  if (globalThis.crypto?.subtle) {
    const h = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
    return Array.from(h.slice(0, 6), (b) => b.toString(16).padStart(2, "0")).join("");
  }
  let x = 2166136261;
  for (const b of bytes) x = Math.imul(x ^ b, 16777619) >>> 0;
  return x.toString(16).padStart(8, "0");
}

/** A picture file -> an asset: downscaled to MAX_SIDE, PNG for drawings / screenshots, JPEG for photos. */
export async function pictureAsset(file: Blob, name: string): Promise<Asset> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((ok, bad) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => bad(new Error("not a picture")); i.src = url; });
    const k = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
    const w = Math.max(1, Math.round(img.naturalWidth * k)), h = Math.max(1, Math.round(img.naturalHeight * k));
    const c = document.createElement("canvas");
    c.width = w; c.height = h;
    const g = c.getContext("2d")!;
    g.drawImage(img, 0, 0, w, h);
    const photo = file.type === "image/jpeg";
    const mime = photo ? "image/jpeg" : "image/png";
    const data = c.toDataURL(mime, 0.85).split(",", 2)[1];
    return { name: name.replace(/\.[^.]+$/, "") || "picture", mime, data, w, h };
  } finally { URL.revokeObjectURL(url); }
}

/** Bytes of an asset (base64 length -> bytes). */
export const assetBytes = (a: { data: string }) => Math.floor(a.data.length * 3 / 4);

/** The assets a text uses (only these are sent and kept). */
export function usedAssets(text: string, all: Record<string, Asset> | undefined): Record<string, Asset> {
  const out: Record<string, Asset> = {};
  for (const m of text.matchAll(/\(asset:([\w-]+)\)/g)) if (all?.[m[1]]) out[m[1]] = all[m[1]];
  return out;
}
