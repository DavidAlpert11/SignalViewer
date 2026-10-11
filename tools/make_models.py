"""
The 3D models of the map objects (aircraft, UAV, drone, missile, ship, vehicle), built from simple
shapes and written as binary glTF (.glb) to frontend/public/models/. Ours: no licence questions,
a few KB each, offline.

    python tools/make_models.py

Axes (glTF): +X forward (the nose), +Y up, +Z to the right side. Sizes in metres. Two materials:
"body" white (the app tints it with the object's colour) and "detail" grey (canopy, wheels...).
"""
import json
import math
import os
import struct

import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "public", "models")


class Mesh:
    def __init__(self):
        self.parts = {"body": ([], [], []), "detail": ([], [], [])}

    def quad(self, part, a, b, c, d):
        """A flat quad a-b-c-d (counter-clockwise seen from outside)."""
        P, N, I = self.parts[part]
        a, b, c, d = (np.asarray(v, dtype=np.float64) for v in (a, b, c, d))
        n = np.cross(b - a, d - a)
        L = np.linalg.norm(n)
        if L < 1e-12:
            n = np.cross(c - b, a - b)
            L = np.linalg.norm(n) or 1
        n = n / L
        k = len(P)
        P += [a, b, c, d]
        N += [n] * 4
        I += [k, k + 1, k + 2, k, k + 2, k + 3]

    def hexa(self, part, c):
        """Eight corners: bottom 0-3 then top 4-7, both counter-clockwise seen from above."""
        b0, b1, b2, b3, t0, t1, t2, t3 = c
        self.quad(part, b0, b3, b2, b1)                 # bottom (facing down)
        self.quad(part, t0, t1, t2, t3)                 # top
        self.quad(part, b0, b1, t1, t0)
        self.quad(part, b1, b2, t2, t1)
        self.quad(part, b2, b3, t3, t2)
        self.quad(part, b3, b0, t0, t3)

    def box(self, part, x0, x1, y0, y1, z0, z1):
        self.hexa(part, [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1),
                         (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)])

    def panel(self, part, outline, y0, y1):
        """A flat shape in the X-Z plane (outline counter-clockwise from above), from y0 to y1."""
        n = len(outline)
        for i in range(n):
            (xa, za), (xb, zb) = outline[i], outline[(i + 1) % n]
            self.quad(part, (xa, y0, za), (xb, y0, zb), (xb, y1, zb), (xa, y1, za))
        # caps as a fan (outlines here are convex)
        for i in range(1, n - 1):
            self.tri(part, (outline[0][0], y1, outline[0][1]), (outline[i][0], y1, outline[i][1]), (outline[i + 1][0], y1, outline[i + 1][1]))
            self.tri(part, (outline[0][0], y0, outline[0][1]), (outline[i + 1][0], y0, outline[i + 1][1]), (outline[i][0], y0, outline[i][1]))

    def tri(self, part, a, b, c):
        P, N, I = self.parts[part]
        a, b, c = (np.asarray(v, dtype=np.float64) for v in (a, b, c))
        n = np.cross(b - a, c - a)
        n = n / (np.linalg.norm(n) or 1)
        k = len(P)
        P += [a, b, c]
        N += [n] * 3
        I += [k, k + 1, k + 2]

    def body(self, part, stations, seg=12, axis_y=0.0, axis_z=0.0):
        """A round body along X: stations [(x, radius)], closed at both ends; its axis at (y, z)."""
        ang = [2 * math.pi * i / seg for i in range(seg)]
        ring = lambda x, r: [(x, axis_y + r * math.sin(a), axis_z + r * math.cos(a)) for a in ang]
        for (xa, ra), (xb, rb) in zip(stations, stations[1:]):
            A, B = ring(xa, ra), ring(xb, rb)
            for i in range(seg):
                j = (i + 1) % seg
                self.quad(part, A[i], A[j], B[j], B[i])
        for (x, r), sign in ((stations[0], -1), (stations[-1], 1)):
            if r > 0:
                R = ring(x, r)
                for i in range(seg):
                    j = (i + 1) % seg
                    (self.tri(part, (x, axis_y, axis_z), R[j], R[i]) if sign < 0 else self.tri(part, (x, axis_y, axis_z), R[i], R[j]))

    def disc(self, part, cx, cz, r, y0, y1, seg=16):
        self.panel(part, [(cx + r * math.cos(2 * math.pi * i / seg), cz + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)][::-1], y0, y1)


def aircraft():
    m = Mesh()
    m.body("body", [(7.5, 0), (6.5, 0.6), (4.5, 0.9), (-4, 0.85), (-7, 0.35), (-7.5, 0)])
    m.panel("body", [(1.5, 0.6), (-1.2, 0.6), (-2.6, 7.5), (-1.6, 7.5)][::-1], -0.12, 0.12)     # right wing
    m.panel("body", [(1.5, -0.6), (-1.6, -7.5), (-2.6, -7.5), (-1.2, -0.6)][::-1], -0.12, 0.12)
    m.panel("body", [(-5.4, 0.3), (-6.6, 0.3), (-7.2, 2.6), (-6.4, 2.6)][::-1], 0.1, 0.25)       # tailplane
    m.panel("body", [(-5.4, -0.3), (-6.4, -2.6), (-7.2, -2.6), (-6.6, -0.3)][::-1], 0.1, 0.25)
    m.hexa("body", [(-5.2, 0.4, -0.08), (-7.3, 0.3, -0.08), (-7.3, 0.3, 0.08), (-5.2, 0.4, 0.08),
                    (-6.4, 2.8, -0.06), (-7.4, 2.8, -0.06), (-7.4, 2.8, 0.06), (-6.4, 2.8, 0.06)])   # fin
    m.body("detail", [(5.6, 0), (5.2, 0.45), (3.6, 0.5), (3.0, 0)], seg=10, axis_y=0.65)          # canopy
    return m


def uav():
    m = Mesh()
    m.body("body", [(4.2, 0), (3.6, 0.35), (2.5, 0.45), (-1.2, 0.4), (-1.6, 0.2), (-1.8, 0)])
    m.panel("body", [(0.6, 0.4), (-0.3, 0.4), (-0.4, 8.5), (0.2, 8.5)][::-1], -0.06, 0.06)
    m.panel("body", [(0.6, -0.4), (0.2, -8.5), (-0.4, -8.5), (-0.3, -0.4)][::-1], -0.06, 0.06)
    for zc in (1.7, -1.7):                                                                           # tail booms
        m.body("body", [(0.3, 0), (0.2, 0.09), (-4.6, 0.09), (-4.8, 0)], seg=8, axis_z=zc)
        m.hexa("body", [(-3.9, 0.05, zc - 0.04), (-4.7, 0.05, zc - 0.04), (-4.7, 0.05, zc + 0.04), (-3.9, 0.05, zc + 0.04),
                        (-4.4, 1.0, zc - 0.03), (-4.8, 1.0, zc - 0.03), (-4.8, 1.0, zc + 0.03), (-4.4, 1.0, zc + 0.03)])   # fins
    m.panel("body", [(-4.0, 1.75), (-4.7, 1.75), (-4.7, -1.75), (-4.0, -1.75)][::-1], 0.0, 0.08)  # tailplane
    m.body("detail", [(-1.6, 0), (-1.7, 0.25), (-1.9, 0.25), (-2.0, 0)], seg=10)                  # pusher hub
    return m


def drone():
    m = Mesh()
    m.box("body", -0.18, 0.18, -0.06, 0.08, -0.18, 0.18)
    for sx, sz in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        x, z = 0.45 * sx, 0.45 * sz
        # arm from the body to the motor, as a thin hexahedron
        ux, uz = sx / math.sqrt(2) * 0.03, -sz / math.sqrt(2) * 0.03
        m.hexa("body", [(0.1 * sx - ux, -0.02, 0.1 * sz - uz), (x - ux, -0.02, z - uz), (x + ux, -0.02, z + uz), (0.1 * sx + ux, -0.02, 0.1 * sz + uz),
                        (0.1 * sx - ux, 0.02, 0.1 * sz - uz), (x - ux, 0.02, z - uz), (x + ux, 0.02, z + uz), (0.1 * sx + ux, 0.02, 0.1 * sz + uz)])
        m.disc("detail", x, z, 0.04, -0.02, 0.06, seg=10)                                            # motor
        m.disc("detail", x, z, 0.24, 0.07, 0.085, seg=20)                                            # rotor disc
    m.hexa("detail", [(0.18, 0.08, -0.06), (0.26, 0.08, 0), (0.26, 0.08, 0), (0.18, 0.08, 0.06),
                      (0.18, 0.1, -0.06), (0.26, 0.1, 0), (0.26, 0.1, 0), (0.18, 0.1, 0.06)])      # front mark
    return m


def missile():
    m = Mesh()
    m.body("body", [(2.5, 0), (2.0, 0.12), (1.4, 0.17), (-2.3, 0.17), (-2.5, 0.12)], seg=14)
    for a in (0, 90, 180, 270):
        r = math.radians(a)
        dy, dz = math.sin(r), math.cos(r)
        ty, tz = -dz * 0.012, dy * 0.012
        p = lambda x, rr: (x, rr * dy, rr * dz)
        q = [p(-1.6, 0.15), p(-2.45, 0.15), p(-2.5, 0.55), p(-2.2, 0.55)]
        m.hexa("body", [(v[0], v[1] - ty, v[2] - tz) for v in q] + [(v[0], v[1] + ty, v[2] + tz) for v in q])
    m.body("detail", [(2.5, 0), (2.05, 0.115), (1.95, 0.0)], seg=14)                               # seeker
    return m


def ship():
    m = Mesh()
    deck = [(30, 0), (22, 4.5), (-26, 5), (-30, 4), (-30, -4), (-26, -5), (22, -4.5)]
    m.panel("body", deck[::-1], -3.0, 2.0)
    m.box("detail", -18, -4, 2.0, 7.0, -3.5, 3.5)                                                  # superstructure
    m.box("detail", -12, -9, 7.0, 13.0, -0.8, 0.8)                                                 # mast
    m.box("body", 8, 16, 2.0, 3.2, -1.6, 1.6)
    return m


def vehicle():
    m = Mesh()
    m.box("body", -2.25, 2.25, 0.35, 1.15, -0.9, 0.9)
    m.hexa("detail", [(1.1, 1.15, -0.8), (-1.3, 1.15, -0.8), (-1.3, 1.15, 0.8), (1.1, 1.15, 0.8),
                      (0.6, 1.65, -0.75), (-1.2, 1.65, -0.75), (-1.2, 1.65, 0.75), (0.6, 1.65, 0.75)])
    for x in (1.45, -1.45):
        for z in (0.95, -0.95):
            # a wheel: a short cylinder across Z
            seg = 12
            pts = [(x + 0.34 * math.cos(2 * math.pi * i / seg), 0.34 + 0.34 * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
            for i in range(seg):
                (xa, ya), (xb, yb) = pts[i], pts[(i + 1) % seg]
                m.quad("detail", (xa, ya, z - 0.13), (xb, yb, z - 0.13), (xb, yb, z + 0.13), (xa, ya, z + 0.13))
            for zz, rev in ((z + 0.13, False), (z - 0.13, True)):
                for i in range(1, seg - 1):
                    a, b, c = (pts[0][0], pts[0][1], zz), (pts[i][0], pts[i][1], zz), (pts[i + 1][0], pts[i + 1][1], zz)
                    m.tri("detail", *((a, c, b) if rev else (a, b, c)))
    return m


def write_glb(mesh: Mesh, path: str):
    buf = bytearray()
    views, accessors, prims = [], [], []
    materials = [{"name": "body", "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1], "metallicFactor": 0.1, "roughnessFactor": 0.6}},
                 {"name": "detail", "pbrMetallicRoughness": {"baseColorFactor": [0.3, 0.32, 0.36, 1], "metallicFactor": 0.2, "roughnessFactor": 0.5}}]

    def add(arr, target, comp, typ, minmax=False):
        while len(buf) % 4:
            buf.append(0)
        off = len(buf)
        buf.extend(arr.tobytes())
        views.append({"buffer": 0, "byteOffset": off, "byteLength": arr.nbytes, "target": target})
        acc = {"bufferView": len(views) - 1, "componentType": comp, "count": len(arr) if arr.ndim == 1 else arr.shape[0], "type": typ}
        if minmax:
            acc["min"], acc["max"] = arr.min(axis=0).tolist(), arr.max(axis=0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    for mi, part in enumerate(("body", "detail")):
        P, N, I = mesh.parts[part]
        if not I:
            continue
        p = np.asarray(P, dtype=np.float32)
        n = np.asarray(N, dtype=np.float32)
        i = np.asarray(I, dtype=np.uint16 if len(P) < 65536 else np.uint32)
        prims.append({"attributes": {"POSITION": add(p, 34962, 5126, "VEC3", True), "NORMAL": add(n, 34962, 5126, "VEC3")},
                      "indices": add(i, 34963, 5123 if i.dtype == np.uint16 else 5125, "SCALAR"), "material": mi})
    gltf = {"asset": {"version": "2.0", "generator": "Signal Viewer tools/make_models.py"}, "scene": 0, "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0}], "meshes": [{"primitives": prims}], "materials": materials, "accessors": accessors,
            "bufferViews": views, "buffers": [{"byteLength": len(buf)}]}
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    while len(buf) % 4:
        buf.append(0)
    total = 12 + 8 + len(js) + 8 + len(buf)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(buf), 0x004E4942) + bytes(buf))


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("aircraft", aircraft), ("uav", uav), ("drone", drone), ("missile", missile), ("ship", ship), ("vehicle", vehicle)):
        path = os.path.join(OUT, f"{name}.glb")
        write_glb(fn(), path)
        print(f"{name}: {os.path.getsize(path) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
