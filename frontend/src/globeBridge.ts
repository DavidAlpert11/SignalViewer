/* 26.U3: what a 3D view can do from its plot's ⋯ menu - the picture of the view is drawn by Cesium
   inside Globe3D (a lazy-loaded part), so it registers its own "save image" here by plot id. */
export const globeImage = new Map<string, (scale: number) => void>();
