/* Groups of signals the user makes and names in the signal list (owner, 2026-11-03): any signals of
   any open file, and made signals. "/" in a name nests it: "Nav/IMU" is listed inside "Nav". Kept
   in the workspace (ws.sigGroups): undoable, saved with the session and the autosave. */
import { useApp } from "./store";
import type { SigGroupDef } from "./store/model";

export const cleanGroupName = (name: string) => name.split("/").map((p) => p.trim()).filter(Boolean).join("/");

const edit = (f: (gs: SigGroupDef[]) => SigGroupDef[]) =>
  useApp.getState().commit((ws) => { ws.sigGroups = f(structuredClone(ws.sigGroups ?? [])).filter((g) => g.sigs.length); return ws; });

export function addToGroup(name: string, ids: string[]) {
  const n = cleanGroupName(name);
  if (!n || !ids.length) return;
  edit((gs) => {
    const g = gs.find((x) => x.name === n);
    if (g) g.sigs = Array.from(new Set([...g.sigs, ...ids]));
    else gs.push({ name: n, sigs: Array.from(new Set(ids)) });
    return gs;
  });
}

export function removeFromGroup(name: string, ids: string[]) {
  edit((gs) => gs.map((g) => (g.name === name ? { ...g, sigs: g.sigs.filter((id) => !ids.includes(id)) } : g)));
}

/** A group and the groups inside it get the new name (the part of their names it was). */
export function renameGroup(from: string, to: string) {
  const n = cleanGroupName(to);
  if (!n || n === from) return;
  edit((gs) => {
    const out: SigGroupDef[] = [];
    for (const g of gs) {
      const name = g.name === from ? n : g.name.startsWith(from + "/") ? n + g.name.slice(from.length) : g.name;
      const same = out.find((x) => x.name === name);       // renamed onto an existing group: joined
      if (same) same.sigs = Array.from(new Set([...same.sigs, ...g.sigs])); else out.push({ name, sigs: g.sigs });
    }
    return out;
  });
}

/** The group and the groups inside it are gone; the signals stay where they are in their files. */
export function ungroup(path: string) {
  edit((gs) => gs.filter((g) => g.name !== path && !g.name.startsWith(path + "/")));
}

export interface GroupNode { path: string; label: string; depth: number; sigs: string[]; children: GroupNode[]; all: string[] }

/** The groups as a tree; `keep` decides which signals are listed (open ones, those a search finds).
 *  A node with nothing left under it is left out. */
export function groupTree(defs: SigGroupDef[], keep: (id: string) => boolean): GroupNode[] {
  const nodes = new Map<string, GroupNode>();
  const node = (path: string): GroupNode => {
    let n = nodes.get(path);
    if (!n) {
      const parts = path.split("/");
      n = { path, label: parts[parts.length - 1], depth: parts.length - 1, sigs: [], children: [], all: [] };
      nodes.set(path, n);
      if (parts.length > 1) node(parts.slice(0, -1).join("/")).children.push(n);
    }
    return n;
  };
  for (const g of defs) {
    const n = node(g.name);
    for (const id of g.sigs) if (keep(id) && !n.sigs.includes(id)) n.sigs.push(id);
  }
  const fill = (n: GroupNode): string[] => {
    n.children = n.children.filter((c) => fill(c).length);
    n.all = Array.from(new Set([...n.sigs, ...n.children.flatMap((c) => c.all)]));
    return n.all;
  };
  return [...nodes.values()].filter((n) => n.depth === 0 && fill(n).length);
}

export const groupNames = () => (useApp.getState().ws.sigGroups ?? []).map((g) => g.name);
