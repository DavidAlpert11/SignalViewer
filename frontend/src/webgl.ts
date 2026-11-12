/** Can this browser make a WebGL context at all? (No: an old / blocked graphics driver, a virtual
 *  machine or remote desktop - and Chrome / Edge 139+ no longer fall back to software WebGL.) P4: when it
 *  cannot, the Map is drawn flat (GeoChart) - this module is tiny so the check does not load CesiumJS. */
let known: boolean | null = null;
export function hasWebGL(): boolean {
  if (known !== null) return known;
  try {
    const c = document.createElement("canvas");
    const gl = (c.getContext("webgl2") || c.getContext("webgl")) as WebGLRenderingContext | null;
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    known = !!gl;
  } catch { known = false; }
  return known;
}
