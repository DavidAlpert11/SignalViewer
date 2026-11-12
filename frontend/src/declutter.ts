/* W9: labels that would overlap on screen - the higher priority kept (0 first: an object's name, then a mode,
   then the log's events), as the 2D timeline does with its texts. Greedy: each label in priority order is kept
   when its box touches no box kept before it. Pure (screen boxes in, kept flags out). */
export interface LabelBox { x: number; y: number; w: number; h: number; prio: number }

export function declutter(boxes: LabelBox[], gap = 2): boolean[] {
  const order = boxes.map((_, i) => i).sort((a, b) => boxes[a].prio - boxes[b].prio || a - b);
  const kept: LabelBox[] = [];
  const out = new Array<boolean>(boxes.length).fill(false);
  for (const i of order) {
    const b = boxes[i];
    if (!Number.isFinite(b.x) || !Number.isFinite(b.y)) continue;
    const hit = kept.some((k) => b.x < k.x + k.w + gap && k.x < b.x + b.w + gap && b.y < k.y + k.h + gap && k.y < b.y + b.h + gap);
    if (!hit) { kept.push(b); out[i] = true; }
  }
  return out;
}
