/* 26.U3: what a 3D view can do from its plot's ⋯ menu - the picture of the view is drawn by Cesium
   inside Globe3D (a lazy-loaded part), so it registers its own "save image" here by plot id. */
export const globeImage = new Map<string, (scale: number) => void>();
/** L11: a map's current view as [south, west, north, east] (registered by GeoChart by plot id) - for
 *  *Save image (PNG)…* of what is shown; absent or null: the image fits every track. */
export const geoViewBounds = new Map<string, () => [number, number, number, number] | null>();

/** P7: what a Map can do for the Places panel, registered by the drawing on screen (Globe3D or GeoChart) by
 *  plot id - fly the camera to a place or a saved view, the camera as it is now (Save this view), an object's
 *  position at the cursor (Mark this spot). */
export interface FlyTarget { lat: number; lon: number; alt?: number; heading?: number; pitch?: number; range?: number }
export const mapFly = new Map<string, (to: FlyTarget) => void>();
export const mapCameraNow = new Map<string, () => FlyTarget | null>();
export const mapObjectAt = new Map<string, (objectId: string) => { lat: number; lon: number; alt: number | null } | null>();
