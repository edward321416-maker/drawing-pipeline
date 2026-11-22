"""Geometric walking network: a raster graph over a walkable polygon, shortest routes, connected components.

The walkable polygon already excludes wall setbacks, column clearance zones (column face + 0.6 m, i.e. a 1.2 m clear band
at a column), door swings, voids and solid cores, so every route cell is an actual place a visitor can stand.
"""
from __future__ import annotations

import numpy as np
import shapely
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point


class WalkNet:
    def __init__(self, region, step: float = 0.3):
        self.region, self.step = region, step
        if region is None or region.is_empty:
            self.n = 0
            return
        minx, miny, maxx, maxy = region.bounds
        self.x0, self.y0 = minx - step, miny - step
        nx, ny = int((maxx - minx) / step) + 3, int((maxy - miny) / step) + 3
        X, Y = np.meshgrid(self.x0 + np.arange(nx) * step, self.y0 + np.arange(ny) * step)
        mask = shapely.contains_xy(region, X, Y)
        self.shape, self.mask = mask.shape, mask
        self.n = int(mask.sum())
        if not self.n:
            return
        edt = ndimage.distance_transform_edt(mask) * step
        idx = -np.ones(mask.shape, dtype=np.int64)
        idx[mask] = np.arange(self.n)
        self.idx = idx
        self.xy = np.column_stack([X[mask], Y[mask]])
        self.tree = cKDTree(self.xy)
        rows, cols, wts = [], [], []
        for dj, di, ln in ((0, 1, 1.0), (1, 0, 1.0), (1, 1, 1.4142), (1, -1, 1.4142)):
            j0, j1 = 0, ny - dj
            i0, i1 = (0, nx - di) if di >= 0 else (-di, nx)
            A = idx[j0:j1, i0:i1]
            B = idx[j0 + dj: j1 + dj, i0 + di: i1 + di]
            ok = (A >= 0) & (B >= 0)
            ea = edt[j0:j1, i0:i1][ok]
            eb = edt[j0 + dj: j1 + dj, i0 + di: i1 + di][ok]
            near = 0.5 * (ea + eb)
            w = ln * step * (1.0 + 2.0 * np.clip(1.4 - near, 0.0, None) / 1.4)      # keep routes off walls / columns
            rows.append(A[ok])
            cols.append(B[ok])
            wts.append(w)
        r, c, w = np.concatenate(rows), np.concatenate(cols), np.concatenate(wts)
        self.graph = coo_matrix((w, (r, c)), shape=(self.n, self.n)).tocsr()
        self.ncomp, self.comp = connected_components(self.graph, directed=False)

    def nearest(self, pt, maxd: float = 1.0):
        """(cell index, distance) of the closest walkable cell to a point, or (None, distance) when farther than maxd."""
        if not self.n:
            return None, float("inf")
        d, i = self.tree.query([pt[0], pt[1]])
        return (int(i), float(d)) if d <= maxd else (None, float(d))

    def dist_from(self, sources):
        """Cost field from one cell or the nearest of several cells (scipy multi-source Dijkstra)."""
        src = [sources] if isinstance(sources, (int, np.integer)) else list(sources)
        d, pred, _ = dijkstra(self.graph, directed=False, indices=src, return_predecessors=True, min_only=True)
        return d, pred

    def path(self, pred, cell: int):
        out = [cell]
        while pred[cell] >= 0:
            cell = int(pred[cell])
            out.append(cell)
        return [tuple(self.xy[i]) for i in reversed(out)]          # from the source toward `cell`

    def route(self, a_cell: int, b_cell: int):
        d, pred = self.dist_from(a_cell)
        if not np.isfinite(d[b_cell]):
            return None
        pts = self.path(pred, b_cell)
        return pts, float(d[b_cell])

    def smooth(self, pts, tol: float = 0.3):
        """Simplified polyline, accepted only if it stays inside the walkable region."""
        if len(pts) < 3:
            return LineString(pts) if len(pts) == 2 else None
        ls = LineString(pts)
        for t in (tol, tol / 2, 0.1):
            s = ls.simplify(t)
            if s.within(self.region.buffer(0.02)):
                return s
        return ls


def route_length(ls) -> float:
    return float(ls.length)
