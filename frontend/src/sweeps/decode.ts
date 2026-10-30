/* The answer's columns, from base64 Float32 to typed arrays. */
import type { Col } from "./model";

export interface WireCol {
  name: string; type: "num" | "cat"; data: string; labels?: string[];
  group?: Col["group"]; agg?: string; label?: string; part?: Col["part"]; condition?: number; constant?: boolean; flat?: boolean;
}

export function f32(b64: string): Float32Array {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Float32Array(bytes.buffer);
}

export function decodeCol(w: WireCol, group: Col["group"] = "run"): Col {
  return { name: w.name, kind: w.type, values: f32(w.data), labels: w.labels, group: w.group ?? group,
    agg: w.agg, label: w.label, part: w.part, condition: w.condition, constant: w.constant, flat: w.flat };
}
