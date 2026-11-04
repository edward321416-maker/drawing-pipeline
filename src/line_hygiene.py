"""C-T13A 선 정리(Clean Line Pass) 기하 모듈 — 렌더러와 분리된 순수 함수.

원칙
- 구조선(벽·기둥·문·가구 윤곽)은 모양을 바꾸지 않는다. 실제로 원·원호인 꼭짓점 열만 SVG 호(A) 명령으로 정확히 바꾼다
  (원호 적합 최대 편차 ≤ ARC_TOL). 일괄 simplify() 는 하지 않는다.
- 장식선(조경 곡선·화단 윤곽)만 모서리를 지키며 가는 3차 베지어로 매끈하게 만든다 (표본 편차 ≤ SMOOTH_TOL).
- 모든 변환은 원래 꼭짓점과의 최대 편차를 log 에 남긴다.

모든 좌표는 SVG 좌표(이미 변환된 값)이며 길이 단위는 미터(도면 월드)다.
"""
from __future__ import annotations

import math

import numpy as np

ARC_TOL = 0.004          # 호 적합 허용 편차 (m). 1:500 종이 0.012 mm — 눈으로 구분 불가
SMOOTH_TOL = 0.05        # 장식선 평활 허용 편차 (m). 1:500 종이 0.1 mm
CORNER_DEG = 28.0        # 이 각도보다 크게 꺾이는 꼭짓점은 모서리로 보존
MIN_ARC_PTS = 6
MIN_ARC_DEG = 14.0
MAX_ARC_SCAN = 400       # 이보다 긴 꼭짓점 열은 호 탐색을 건너뛴다


def dedupe(pts, eps=1e-7):
    out = [pts[0]]
    for p in pts[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > eps:
            out.append(p)
    return out


def fit_circle(pts):
    """최소제곱 원 적합. (cx, cy, r, 최대편차) 또는 None."""
    P = np.asarray(pts, dtype=float)
    if len(P) < 4:
        return None
    x, y = P[:, 0], P[:, 1]
    A = np.column_stack([x, y, np.ones(len(P))])
    b = x * x + y * y
    try:
        sol = np.linalg.lstsq(A, b, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None
    cx, cy = sol[0] / 2, sol[1] / 2
    r2 = sol[2] + cx * cx + cy * cy
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    dev = float(np.max(np.abs(np.hypot(x - cx, y - cy) - r)))
    return cx, cy, r, dev


EDGE_SAGITTA_TOL = 0.007     # m: 꼭짓점 사이 변이 맞춘 원에서 이만큼 이상 벗어나면 원이 아니다 (둥근 네모 좌판처럼 모서리 꼭짓점만 원 위에 있는 경우를 거른다)


def is_regular_arc(pts, r):
    """호로 인정: ① 누적 꺾임이 10° 이상이고 절대 꺾임 합의 85% 이상이 같은 방향(공선·잡음 열 배제) ② 모든 변의 현이 원에서 EDGE_SAGITTA_TOL 안(꼭짓점 사이 직선이 원을 가로지르지 않음)."""
    if len(pts) < MIN_ARC_PTS or r < 0.08:
        return False
    ang = []
    for i in range(1, len(pts) - 1):
        a = (pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
        b = (pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        ang.append(math.degrees(math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1])))
    tot, ab = sum(ang), sum(abs(a) for a in ang)
    if not ang or abs(tot) < 10.0 or abs(tot) < 0.85 * ab:                      # 한 방향으로 일관되게 도는 열만(공선·지그재그 잡음 열 배제; 변 중간에 낀 꼭짓점의 반올림 잡음은 허용)
        return False
    for i in range(len(pts) - 1):
        c = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        if c / 2 > r or r - math.sqrt(max(r * r - c * c / 4, 0.0)) > EDGE_SAGITTA_TOL:
            return False
    return True


def arc_span(pts, cx, cy):
    """중심 기준 누적 각도(라디안, 부호 있음)."""
    tot = 0.0
    a_prev = math.atan2(pts[0][1] - cy, pts[0][0] - cx)
    for p in pts[1:]:
        a = math.atan2(p[1] - cy, p[0] - cx)
        d = (a - a_prev + math.pi) % (2 * math.pi) - math.pi
        tot += d
        a_prev = a
    return tot


def _fmt(v):
    return ("%.3f" % v).rstrip("0").rstrip(".") if abs(v) >= 0.0005 else "0"


def _pt(p):
    return "%s,%s" % (_fmt(p[0]), _fmt(p[1]))


def turn_angles(pts):
    out = []
    for i in range(1, len(pts) - 1):
        a = (pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
        b = (pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        la, lb = math.hypot(*a), math.hypot(*b)
        if la < 1e-9 or lb < 1e-9:
            out.append(0.0)
            continue
        c = max(-1.0, min(1.0, (a[0] * b[0] + a[1] * b[1]) / (la * lb)))
        out.append(math.degrees(math.acos(c)))
    return out


def rdp(pts, tol):
    if len(pts) < 3:
        return list(pts)
    a, b = np.asarray(pts[0], float), np.asarray(pts[-1], float)
    ab = b - a
    L = float(np.hypot(*ab))
    P = np.asarray(pts[1:-1], float)
    if L < 1e-12:
        d = np.hypot(*(P - a).T)
    else:
        d = np.abs(ab[0] * (P[:, 1] - a[1]) - ab[1] * (P[:, 0] - a[0])) / L
    i = int(np.argmax(d))
    if d[i] > tol:
        left = rdp(pts[: i + 2], tol)
        right = rdp(pts[i + 1:], tol)
        return left[:-1] + right
    return [pts[0], pts[-1]]


def _seg_dist(p, a, b):
    ab = (b[0] - a[0], b[1] - a[1])
    L2 = ab[0] * ab[0] + ab[1] * ab[1]
    if L2 < 1e-18:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / L2))
    return math.hypot(p[0] - (a[0] + t * ab[0]), p[1] - (a[1] + t * ab[1]))


def poly_distance(samples, pts):
    """표본점들에서 꺾은선 pts 까지의 최대 거리."""
    P = np.asarray(pts, float)
    A, B = P[:-1], P[1:]
    AB = B - A
    L2 = np.maximum(np.sum(AB * AB, axis=1), 1e-18)
    worst = 0.0
    for s in samples:
        t = np.clip(np.sum((np.asarray(s) - A) * AB, axis=1) / L2, 0, 1)
        proj = A + AB * t[:, None]
        worst = max(worst, float(np.min(np.hypot(*(proj - np.asarray(s)).T))))
    return worst


def bezier_samples(p0, c1, c2, p1, n=12):
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p1[0],
                    u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p1[1]))
    return out


def catmull_rom(run):
    """꼭짓점 열(≥2) → 3차 베지어 세그먼트 [(p0, c1, c2, p1)] (균일 Catmull-Rom, 양끝 복제)."""
    n = len(run)
    segs = []
    for i in range(n - 1):
        p0, p1 = run[i], run[i + 1]
        pm = run[i - 1] if i > 0 else p0
        pp = run[i + 2] if i + 2 < n else p1
        c1 = (p0[0] + (p1[0] - pm[0]) / 6.0, p0[1] + (p1[1] - pm[1]) / 6.0)
        c2 = (p1[0] - (pp[0] - p0[0]) / 6.0, p1[1] - (pp[1] - p0[1]) / 6.0)
        segs.append((p0, c1, c2, p1))
    return segs


def smooth_run(run, tol=SMOOTH_TOL):
    """곡선처럼 보이는 꼭짓점 열을 가는 베지어로. 반환 (cubic 세그먼트 목록, 편차) 또는 None(직선 유지)."""
    if len(run) < 7:
        return None
    for t in (0.04, 0.02, 0.01):
        s = rdp(run, t)
        if len(s) < 3 or len(s) > len(run) * 0.6:
            continue
        segs = catmull_rom(s)
        samples = []
        for sg in segs:
            samples += bezier_samples(*sg, n=10)
        dev = max(poly_distance(samples, run), poly_distance(run, [q for sg in segs for q in bezier_samples(*sg, n=10)]) if len(run) < 150 else 0.0)
        if dev <= tol:
            return segs, dev
    return None


def build_path(pts, closed, smooth=False, log=None, layer="", arc_tol=ARC_TOL, smooth_tol=SMOOTH_TOL):
    """꼭짓점 열 → SVG path d (호는 A, 장식 곡선은 C, 나머지는 L). pts 는 SVG 좌표."""
    pts = dedupe(list(pts))
    if closed and len(pts) > 1 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-7:
        pts = pts[:-1]
    n = len(pts)
    if n < 2:
        return ""
    # ① 전체가 한 원 (기둥·튜브·스툴·테이블)
    if closed and n >= 8:
        fc = fit_circle(pts)
        if fc and fc[3] <= min(arc_tol, 0.01 * fc[2]) and abs(arc_span(pts + [pts[0]], fc[0], fc[1])) > 2 * math.pi * 0.98 and is_regular_arc(pts + pts[:2], fc[2]):
            cx, cy, r, dev = fc
            if log is not None:
                log.append({"kind": "circle", "layer": layer, "n_before": n, "n_after": 2, "max_dev_m": round(dev, 5), "r_m": round(r, 3)})
            return "M%s A%s,%s 0 1 1 %s A%s,%s 0 1 1 %s Z" % (_pt((cx + r, cy)), _fmt(r), _fmt(r), _pt((cx - r, cy)), _fmt(r), _fmt(r), _pt((cx + r, cy)))
    seq = pts + ([pts[0]] if closed else [])
    cmds = ["M" + _pt(seq[0])]
    i = 0
    m = len(seq)
    scan = m <= MAX_ARC_SCAN
    line_run = [seq[0]]

    def emit_line_run():
        nonlocal line_run
        if len(line_run) < 2:
            line_run = line_run[-1:]
            return
        done = False
        if smooth and len(line_run) >= 7:
            ang = turn_angles(line_run)
            # 모서리에서 나눠 각 구간을 평활
            cuts = [0] + [j + 1 for j, a in enumerate(ang) if a > CORNER_DEG] + [len(line_run) - 1]
            pieces = [line_run[cuts[k]: cuts[k + 1] + 1] for k in range(len(cuts) - 1)]
            out_cmds, n_after, devs, ok = [], 0, [], False
            for pc_ in pieces:
                sm = smooth_run(pc_, smooth_tol) if len(pc_) >= 7 else None
                if sm:
                    ok = True
                    for sg in sm[0]:
                        out_cmds.append("C%s %s %s" % (_pt(sg[1]), _pt(sg[2]), _pt(sg[3])))
                    n_after += len(sm[0])
                    devs.append(sm[1])
                else:
                    for q in pc_[1:]:
                        out_cmds.append("L" + _pt(q))
                    n_after += len(pc_) - 1
            if ok:
                cmds.extend(out_cmds)
                if log is not None:
                    log.append({"kind": "smooth", "layer": layer, "n_before": len(line_run), "n_after": n_after, "max_dev_m": round(max(devs), 5)})
                done = True
        if not done:
            for q in line_run[1:]:
                cmds.append("L" + _pt(q))
        line_run = line_run[-1:]

    while i < m - 1:
        best = None
        if scan and i + MIN_ARC_PTS - 1 < m:
            j = i + MIN_ARC_PTS - 1
            while j < m:
                fc = fit_circle(seq[i: j + 1])
                if fc and fc[3] <= min(arc_tol, 0.01 * fc[2]) and is_regular_arc(seq[i: j + 1], fc[2]):
                    best = (j, fc)
                    j += 1
                elif best is None and j < i + MIN_ARC_PTS + 3 and fc and fc[3] <= min(arc_tol, 0.01 * fc[2]):
                    j += 1                                                              # 아직 짧아 균등성 판정이 불안정할 때만 조금 더 본다
                else:
                    break
            if best:
                sp = abs(math.degrees(arc_span(seq[i: best[0] + 1], best[1][0], best[1][1])))
                if sp < MIN_ARC_DEG or best[1][2] > 400:
                    best = None
        if best:
            emit_line_run()
            j, (cx, cy, r, dev) = best
            tot = arc_span(seq[i: j + 1], cx, cy)
            if abs(tot) > math.pi * 0.9:                                                # 반원을 넘는 호는 둘로 나눈다(끝점이 시작점과 같아지는 퇴화 호 방지)
                mid = (i + j) // 2
                t1 = arc_span(seq[i: mid + 1], cx, cy)
                cmds.append("A%s,%s 0 0 %d %s" % (_fmt(r), _fmt(r), 1 if t1 > 0 else 0, _pt(seq[mid])))
                tot = arc_span(seq[mid: j + 1], cx, cy)
            cmds.append("A%s,%s 0 %d %d %s" % (_fmt(r), _fmt(r), 1 if abs(tot) > math.pi else 0, 1 if tot > 0 else 0, _pt(seq[j])))
            if log is not None:
                log.append({"kind": "arc", "layer": layer, "n_before": j - i + 1, "n_after": 1, "max_dev_m": round(dev, 5), "r_m": round(r, 3)})
            i = j
            line_run = [seq[j]]
        else:
            line_run.append(seq[i + 1])
            i += 1
    emit_line_run()
    return " ".join(cmds) + (" Z" if closed else "")


# ── 독립 검증용: SVG path d 를 꺾은선으로 표본화 (M L C A Z) ───────────────────────────────────
def sample_path(d, n_arc=24, n_bez=12):
    import re
    tok = re.findall(r"[MLCAZHhVv]|-?\d+\.?\d*(?:e-?\d+)?", d)
    out, subs = [], []
    i = 0
    cur = start = (0.0, 0.0)
    cmd = None
    while i < len(tok):
        t = tok[i]
        if t in "MLCAZHhVv":
            cmd = t
            i += 1
            if t == "Z":
                if out:
                    out.append(start)
                    subs.append(out)
                    out = []
                cur = start
                continue
        if cmd == "M":
            if out:
                subs.append(out)
            cur = start = (float(tok[i]), float(tok[i + 1]))
            out = [cur]
            i += 2
            cmd = "L"
        elif cmd == "L":
            cur = (float(tok[i]), float(tok[i + 1]))
            out.append(cur)
            i += 2
        elif cmd in ("h", "H", "v", "V"):
            v = float(tok[i])
            cur = ((cur[0] + v if cmd == "h" else v if cmd == "H" else cur[0]), (cur[1] + v if cmd == "v" else v if cmd == "V" else cur[1]))
            out.append(cur)
            i += 1
        elif cmd == "C":
            c1, c2, p1 = [(float(tok[i + k]), float(tok[i + k + 1])) for k in (0, 2, 4)]
            out += bezier_samples(cur, c1, c2, p1, n_bez)[1:]
            cur = p1
            i += 6
        elif cmd == "A":
            rx, ry, rot, large, sweep, x, y = [float(v) for v in tok[i:i + 7]]
            out += _arc_samples(cur, rx, int(large), int(sweep), (x, y), n_arc)
            cur = (x, y)
            i += 7
        else:
            i += 1
    if out:
        subs.append(out)
    return subs


def _arc_samples(p0, r, large, sweep, p1, n):
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = (x0 - x1) / 2, (y0 - y1) / 2
    d2 = dx * dx + dy * dy
    if d2 < 1e-18:
        return [p1]
    r = max(r, math.sqrt(d2))
    sq = max(0.0, (r * r - d2) / d2)
    coef = math.sqrt(sq) * (-1 if large == sweep else 1)
    cxp, cyp = coef * dy, -coef * dx
    cx, cy = cxp + (x0 + x1) / 2, cyp + (y0 + y1) / 2
    a0 = math.atan2(y0 - cy, x0 - cx)
    a1 = math.atan2(y1 - cy, x1 - cx)
    da = a1 - a0
    if sweep and da < 0:
        da += 2 * math.pi
    if not sweep and da > 0:
        da -= 2 * math.pi
    return [(cx + r * math.cos(a0 + da * k / n), cy + r * math.sin(a0 + da * k / n)) for k in range(1, n + 1)]
