"""Model-derived axonometric renderer: orthographic, z-buffer, flat shading, image-space outlines, optional glass pass.

Everything drawn comes from the model-cache triangles (MODEL VERIFIED imagery). Colours, view, explode offsets and cut-aways are
presentation choices; geometry is never edited.

    img, proj = axon.render(model, groups, az=40, el=28, width_px=2400)
    px, py = proj.to_px(x, y, z)                 # place labels / leaders in model (drawing-frame) coordinates

`groups`: list of dict(objs=[model objects], color="#rrggbb", alpha=1.0, edge=True,
                       z0=None, z1=None,   keep only the part of the objects between these heights (triangles are clipped)
                       dz=0.0,             lift the group (exploded views)
                       bands=[(z0,z1,dz)], clip each object into height bands and lift every band by its own dz
                       clip=callable)      (n,3,3)->(m,3,3) triangle filter, e.g. axon.cut_quadrant(x0, y0)
alpha < 1 groups are drawn in a second, depth-tested but non-writing glass pass (not sorted per pixel: nearest glass wins).
"""
import math

import numpy as np
from PIL import Image

import t14i  # noqa: F401
import book_views as bv


def _hex(c):
    c = c.lstrip("#")
    return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], float)


class Proj:
    def __init__(self, az, el, scale_px_per_m, ox, oy):
        self.az, self.el, self.s, self.ox, self.oy = math.radians(az), math.radians(el), scale_px_per_m, ox, oy

    def uvd(self, P):
        """(n,3) drawing-frame points -> u right, v up, depth toward the viewer (larger = closer), all in metres."""
        P = np.asarray(P, float).reshape(-1, 3)
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        ca, sa = math.cos(self.az), math.sin(self.az)
        x1, y1 = x * ca - y * sa, x * sa + y * ca
        return x1, z * math.cos(self.el) + y1 * math.sin(self.el), -y1 * math.cos(self.el) + z * math.sin(self.el)

    def to_px(self, x, y, z):
        u, v, _ = self.uvd([[x, y, z]])
        return float(self.ox + u[0] * self.s), float(self.oy - v[0] * self.s)


def _clip_z(T, z0=None, z1=None):
    if z0 is not None and len(T):
        T = bv._clip_half(T, np.array([0.0, 0.0, 1.0]), z0)
    if z1 is not None and len(T):
        T = bv._clip_half(T, np.array([0.0, 0.0, -1.0]), -z1)
    return T


def cut_quadrant(x0, y0):
    """Cut-away: remove the quadrant x > x0 and y > y0 (drawing-frame metres); triangles are clipped on both planes."""
    def f(T):
        if len(T) == 0:
            return T
        a = bv._clip_half(T, np.array([-1.0, 0.0, 0.0]), -x0)                 # x <= x0 stays whole
        b = bv._clip_half(T, np.array([1.0, 0.0, 0.0]), x0)                   # x >= x0: only the y <= y0 part stays
        if len(b):
            b = bv._clip_half(b, np.array([0.0, -1.0, 0.0]), -y0)
        parts = [p for p in (a, b) if len(p)]
        return np.concatenate(parts) if parts else np.zeros((0, 3, 3))
    return f


def cut_halfspace(nx, ny, c):
    """Remove everything with nx*x + ny*y > c."""
    def f(T):
        return bv._clip_half(T, np.array([-nx, -ny, 0.0]), -c) if len(T) else T
    return f


def _normals(T):
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    return n / ln


def _gather(model, groups):
    solid, glass = [], []
    oid = 0
    for g in groups:
        bands = g.get("bands") or [(g.get("z0"), g.get("z1"), g.get("dz", 0.0))]
        for o in g["objs"]:
            T0 = model.tris(o)
            if len(T0) == 0:
                continue
            for z0, z1, dz in bands:
                T = _clip_z(T0, z0, z1)
                if len(T) and g.get("clip") is not None:
                    T = g["clip"](T)
                if len(T) == 0:
                    continue
                if dz:
                    T = T + np.array([0.0, 0.0, dz])
                oid += 1
                rec = (T, _hex(g.get("color", "#cccccc")), float(g.get("alpha", 1.0)), oid, bool(g.get("edge", True)))
                (glass if rec[2] < 0.999 else solid).append(rec)
    return solid, glass


def _raster(items, proj, W, H, zb, cb, ib, sb, light, test=None, write_z=True, alpha=None):
    """Rasterise triangles into colour/depth/id/shade buffers (optionally alpha-blended against the colour buffer)."""
    for T, col, a, oid, edge in items:
        n = _normals(T)
        shade = 0.58 + 0.42 * np.clip(np.abs(n @ light), 0, 1)
        u, v, d = proj.uvd(T.reshape(-1, 3))
        px = (proj.ox + u * proj.s).reshape(-1, 3)
        py = (proj.oy - v * proj.s).reshape(-1, 3)
        d = d.reshape(-1, 3)
        for i in range(len(T)):
            x0, x1, x2 = px[i]
            y0, y1, y2 = py[i]
            xa, xb = max(int(math.floor(min(x0, x1, x2))), 0), min(int(math.ceil(max(x0, x1, x2))), W - 1)
            ya, yb = max(int(math.floor(min(y0, y1, y2))), 0), min(int(math.ceil(max(y0, y1, y2))), H - 1)
            if xb < xa or yb < ya:
                continue
            det = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(det) < 1e-9:
                continue
            gx = np.arange(xa, xb + 1)[None, :] + 0.5
            gy = np.arange(ya, yb + 1)[:, None] + 0.5
            l0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) / det
            l1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) / det
            l2 = 1.0 - l0 - l1
            m = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4)
            if not m.any():
                continue
            dd = l0 * d[i, 0] + l1 * d[i, 1] + l2 * d[i, 2]
            sz = zb[ya:yb + 1, xa:xb + 1]
            vis = m & (dd > sz + 1e-6)
            if test is not None:
                vis &= dd > test[ya:yb + 1, xa:xb + 1] - 1e-6
            if not vis.any():
                continue
            c = col * shade[i]
            if alpha is None:
                cb[ya:yb + 1, xa:xb + 1][vis] = c
            else:
                cb[ya:yb + 1, xa:xb + 1][vis] = cb[ya:yb + 1, xa:xb + 1][vis] * (1 - a) + c * a
            ib[ya:yb + 1, xa:xb + 1][vis] = oid if edge else -oid
            sb[ya:yb + 1, xa:xb + 1][vis] = shade[i]
            if write_z:
                sz[vis] = dd[vis]


def _edges(ib, zb, sb, zthr, sthr=0.10):
    e = np.zeros(ib.shape, bool)
    dx = (ib[:, 1:] != ib[:, :-1]) | (np.abs(zb[:, 1:] - zb[:, :-1]) > zthr) | (np.abs(sb[:, 1:] - sb[:, :-1]) > sthr)
    dy = (ib[1:, :] != ib[:-1, :]) | (np.abs(zb[1:, :] - zb[:-1, :]) > zthr) | (np.abs(sb[1:, :] - sb[:-1, :]) > sthr)
    e[:, 1:] |= dx
    e[1:, :] |= dy
    return e


def render(model, groups, az=40.0, el=28.0, width_px=2400, pad_px=50, bg="#ffffff", light=(-0.40, -0.55, 0.73), ssaa=2,
           extent_m=None, min_height_px=200, outline="#2b2b2b", zthr_m=0.9):
    """Render. Returns (PIL.Image RGB, Proj at output resolution). extent_m=(umin,umax,vmin,vmax) fixes the framing."""
    solid, glass = _gather(model, groups)
    if not solid and not glass:
        raise ValueError("nothing to render")
    allP = np.concatenate([r[0].reshape(-1, 3) for r in solid + glass])
    u, v, _ = Proj(az, el, 1.0, 0, 0).uvd(allP)
    umin, umax, vmin, vmax = extent_m if extent_m else (float(u.min()), float(u.max()), float(v.min()), float(v.max()))
    S = ssaa
    W = width_px * S
    s = (W - 2 * pad_px * S) / max(umax - umin, 1e-6)
    H = max(int((vmax - vmin) * s + 2 * pad_px * S), min_height_px * S)
    proj = Proj(az, el, s, pad_px * S - umin * s, H - pad_px * S + vmin * s)
    L = np.array(light, float)
    L /= np.linalg.norm(L)
    cb = np.zeros((H, W, 3), float)
    cb[:] = _hex(bg)
    zb = np.full((H, W), -1e9)
    ib = np.zeros((H, W), np.int32)
    sb = np.zeros((H, W))
    _raster(solid, proj, W, H, zb, cb, ib, sb, L)
    e_solid = _edges(ib, np.where(zb < -1e8, -1e3, zb), sb, zthr_m) & (ib != 0)
    e_hit = e_solid.copy()
    # neighbours that are background count as silhouette edges
    bgm = (ib == 0)
    e_hit[:, 1:] |= bgm[:, 1:] != bgm[:, :-1]
    e_hit[1:, :] |= bgm[1:, :] != bgm[:-1, :]
    e_hit &= (ib != 0)
    # glass pass
    if glass:
        gz = np.full((H, W), -1e9)
        gi = np.zeros((H, W), np.int32)
        gs = np.zeros((H, W))
        for rec in sorted(glass, key=lambda r: float(proj.uvd(r[0].reshape(-1, 3))[2].mean())):
            _raster([rec], proj, W, H, gz, cb, gi, gs, L, test=zb, write_z=True, alpha=rec[2])
        ge = _edges(gi, np.where(gz < -1e8, -1e3, gz), gs, zthr_m, 9.0) & (gi > 0)
        ge[:, 1:] |= (gi[:, 1:] != 0) != (gi[:, :-1] != 0)
        ge &= (gi > 0)
    else:
        ge = None
    oc = _hex(outline)
    cb[e_hit] = oc
    if ge is not None:
        cb[ge & ~e_hit] = cb[ge & ~e_hit] * 0.45 + oc * 0.55
    img = Image.fromarray(np.clip(cb, 0, 255).astype(np.uint8), "RGB").resize((width_px, H // S), Image.LANCZOS)
    return img, Proj(az, el, s / S, proj.ox / S, proj.oy / S)


def floor_bands(model, gap, lo="B2", hi="15F", top_extra=7.0):
    """[(z0, z1, dz)] one band per floor, slab at the bottom of its band, each band lifted by index*gap (exploded axonometric)."""
    F = sorted(((n, z) for n, z in model.floors.items()), key=lambda t: t[1])
    names = [n for n, _ in F]
    i0, i1 = names.index(lo), names.index(hi)
    out = []
    for k, i in enumerate(range(i0, i1 + 1)):
        z0 = F[i][1] - 0.55
        z1 = (F[i + 1][1] - 0.55) if i < i1 else F[i][1] + top_extra
        out.append((z0, z1, k * gap))
    return out


KIND_COLORS = {"slab": "#d8d1c4", "column": "#707070", "core_wall": "#8a8a8a", "tube_wall": "#8fbfd6", "shaft": "#b0b0b0", "stair": "#e08a2e",
               "ramp": "#d1562a", "facade": "#aecfdc", "roof": "#c8c8c8", "zone": "#cccccc"}
PROGRAM_COLORS = {"판매": "#f2a65a", "F&B": "#e4604f", "문화·엔터": "#7a6fc8", "garden": "#6bb36b", "서비스": "#a8a8a8", "anchor": "#a89be0"}


def render_cached(path, model, groups, **kw):
    """render() with an on-disk PNG cache (path) + JSON sidecar holding the projection. Delete the PNG to refresh. Returns (img, proj)."""
    import json
    import os
    side = path + ".json"
    if os.path.exists(path) and os.path.exists(side) and not os.environ.get("T14_AXON_REFRESH"):
        d = json.load(open(side))
        return Image.open(path).convert("RGB"), Proj(d["az_deg"], d["el_deg"], d["s"], d["ox"], d["oy"])
    img, pr = render(model, groups, **kw)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, optimize=True)
    json.dump({"az_deg": math.degrees(pr.az), "el_deg": math.degrees(pr.el), "s": pr.s, "ox": pr.ox, "oy": pr.oy, "size": list(img.size)}, open(side, "w"))
    return img, pr
