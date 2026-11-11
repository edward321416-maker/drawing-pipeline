"""V2 도면집 공통 치수·기호 도구: 치수선(건축식 사선 눈금), 치수 체인, 축선 기호, 단면·입면·상세 호출 기호, 미니 키플랜.

모든 좌표는 시트 밀리미터. 치수 문자는 mm 정수(예: 9000), 글자 6 pt(2.1 mm), 치수선 0.15 mm, 눈금 사선 0.3 mm.
문자는 선 위에 겹치지 않게 선 바깥쪽(위/왼쪽)에 둔다(§3.3).
"""
import math

from t14d_sheet import Sheet  # noqa: F401

TICK = 1.0          # 사선 눈금 반길이(mm)
EXT_GAP = 1.2       # 대상물과 치수보조선 사이 간격
EXT_OVER = 1.5      # 치수선 너머로 나가는 보조선 길이


def fmt_mm(meters):
    """미터 → 건축 치수 문자(mm 정수, 천 단위 구분 없음)."""
    return "%d" % (round(meters * 100.0) * 10)          # 모델값을 10 mm 단위로 반올림(모델의 0.6 mm 수준 노이즈를 치수에 싣지 않음)


def dim_h(sh, x0, x1, y, text, from_y=None, above=True, pt=6.0, color="#222"):
    """수평 치수선. from_y가 있으면 대상물 위치(from_y)에서 치수선(y)까지 보조선을 그린다."""
    if from_y is not None:
        for x in (x0, x1):
            sgn = 1 if y > from_y else -1
            sh.line(x, from_y + sgn * EXT_GAP, x, y + sgn * EXT_OVER, 0.1, color)
    sh.line(x0, y, x1, y, 0.15, color)
    for x in (x0, x1):
        sh.line(x - TICK, y + TICK, x + TICK, y - TICK, 0.3, color)
    ty = y - 0.9 if above else y + 2.6
    sh.text((x0 + x1) / 2, ty, text, pt, "normal", color, "middle")


def dim_v(sh, y0, y1, x, text, from_x=None, left=True, pt=6.0, color="#222"):
    """수직 치수선(문자는 선을 따라 회전)."""
    if from_x is not None:
        for y in (y0, y1):
            sgn = 1 if x > from_x else -1
            sh.line(from_x + sgn * EXT_GAP, y, x + sgn * EXT_OVER, y, 0.1, color)
    sh.line(x, y0, x, y1, 0.15, color)
    for y in (y0, y1):
        sh.line(x - TICK, y + TICK, x + TICK, y - TICK, 0.3, color)
    tx = x - 0.9 if left else x + 2.6
    sh.text(tx, (y0 + y1) / 2, text, pt, "normal", color, "middle", rotate=-90)


def chain_h(sh, xs, y, labels, from_y=None, pt=6.0, color="#222"):
    """xs: 증가하는 경계 x(mm) 목록, labels: 각 구간 문자. 하나의 치수선에 눈금을 모두 찍는다."""
    if from_y is not None:
        for x in xs:
            sgn = 1 if y > from_y else -1
            sh.line(x, from_y + sgn * EXT_GAP, x, y + sgn * EXT_OVER, 0.1, color)
    sh.line(xs[0], y, xs[-1], y, 0.15, color)
    for x in xs:
        sh.line(x - TICK, y + TICK, x + TICK, y - TICK, 0.3, color)
    for a, b, t in zip(xs, xs[1:], labels):
        if b - a >= 6.5:
            sh.text((a + b) / 2, y - 0.9, t, pt, "normal", color, "middle")
        else:                                                                         # 좁은 칸은 문자를 줄여 위로 올린다
            sh.text((a + b) / 2, y - 3.2, t, pt - 1.0, "normal", color, "middle")


def chain_v(sh, ys, x, labels, from_x=None, pt=6.0, color="#222", left=True):
    """ys: 화면 y(mm) 목록(증가/감소 무관)."""
    if from_x is not None:
        for y in ys:
            sgn = 1 if x > from_x else -1
            sh.line(from_x + sgn * EXT_GAP, y, x + sgn * EXT_OVER, y, 0.1, color)
    sh.line(x, min(ys), x, max(ys), 0.15, color)
    for y in ys:
        sh.line(x - TICK, y + TICK, x + TICK, y - TICK, 0.3, color)
    for a, b, t in zip(ys, ys[1:], labels):
        lo, hi = min(a, b), max(a, b)
        tx = (x - 0.9) if left else (x + 2.6)
        if hi - lo < 6.5:
            tx += -2.6 if left else 2.6
        sh.text(tx, (lo + hi) / 2, t, pt if hi - lo >= 6.5 else pt - 1.0, "normal", color, "middle", rotate=-90)


def bubble(sh, x, y, label, r=3.0, pt=6.5, color="#222", fill="#fff"):
    import math as _m
    sh.path([[(x + r * _m.cos(t / 24 * 2 * _m.pi), y + r * _m.sin(t / 24 * 2 * _m.pi)) for t in range(25)]], fill=fill, stroke=color, w=0.2, closed=True)
    sh.text(x, y + pt * 0.3528 * 0.35, label, pt, "bold", color, "middle")


def axis_labels(xs, ys):
    """x 축선(왼→오른쪽) 알파벳 A,B,…, y 축선(위→아래) 숫자 1,2,… (평면·입면·단면이 같은 규약)."""
    xl = {round(x, 2): chr(ord("A") + i) for i, x in enumerate(sorted(xs))}
    yl = {round(y, 2): str(i + 1) for i, y in enumerate(sorted(ys, reverse=True))}
    return xl, yl


def section_tag(sh, x, y, letter, sheet_ref, arrow=(0, -1), r=3.2):
    """절단선 끝 기호: 원 + 문자 + 보는 방향 화살표 + 참조 시트."""
    bubble(sh, x, y, letter, r=r, pt=7.5, color="#c00")
    ax, ay = arrow
    tip = (x + ax * (r + 4.0), y + ay * (r + 4.0))
    sh.path([[(x + ax * r, y + ay * r), tip]], stroke="#c00", w=0.35, closed=False)
    px, py = -ay, ax
    sh.path([[tip, (tip[0] - ax * 1.6 + px * 1.0, tip[1] - ay * 1.6 + py * 1.0), (tip[0] - ax * 1.6 - px * 1.0, tip[1] - ay * 1.6 - py * 1.0)]], fill="#c00", stroke="#c00", w=0.1, closed=True)
    sh.text(x, y + r + 3.4 if ay >= 0 else y - r - 1.4, sheet_ref, 4.8, "normal", "#c00", "middle", bg=True)


def elevation_tag(sh, x, y, sheet_ref, direction, r=3.4):
    """입면 기호: 원 + 입면 번호 + 바깥을 가리키는 삼각 화살표. direction = 건물 바깥 방향 단위벡터(화면 좌표)."""
    bubble(sh, x, y, sheet_ref.split("-")[1], r=r, pt=6.0, color="#06a")
    dx, dy = direction
    tip = (x + dx * (r + 4.0), y + dy * (r + 4.0))
    px, py = -dy, dx
    sh.path([[tip, (tip[0] - dx * 3.0 + px * 1.6, tip[1] - dy * 3.0 + py * 1.6), (tip[0] - dx * 3.0 - px * 1.6, tip[1] - dy * 3.0 - py * 1.6)]], fill="#06a", stroke="#06a", w=0.1, closed=True)
    sh.text(x, y + r + 3.2, sheet_ref, 4.6, "normal", "#06a", "middle", bg=True)


def detail_tag(sh, x, y, sid, scale=None, r=3.4, dashed_r=None):
    """상세 호출: (선택) 대상 둘레 점선 원 + 기호(상세 번호 / 축척).

    축척 문자는 시트 레지스트리(tools/t14g/registry.py)에서 읽는다. 호출한 쪽이 scale을 넘기면 레지스트리와 같아야 하고,
    레지스트리에 없는 상세 번호를 호출하면 UnknownSheetError로 빌드가 멈춘다(감사 F-01).
    """
    from t14g import registry
    label = registry.callout_label(sid, scale)
    scale = registry.detail_scale(sid)
    if dashed_r:
        sh.path([[(x + dashed_r * math.cos(t / 28 * 2 * math.pi), y + dashed_r * math.sin(t / 28 * 2 * math.pi)) for t in range(29)]], stroke="#a60", w=0.25, dash="1.6,1.0", closed=True)
    bx, by = x + (dashed_r or 0) * 0.72 + r, y - (dashed_r or 0) * 0.72 - r
    if dashed_r:
        sh.line(x + dashed_r * 0.72, y - dashed_r * 0.72, bx, by, 0.2, "#a60")
    bubble(sh, bx, by, sid.split("-")[1], r=r, pt=6.0, color="#a60")
    sh.text(bx, by + r + 3.0, label, 4.6, "normal", "#a60", "middle", bg=True)
