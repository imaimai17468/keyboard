"""ケースの奥の面にレーザー刻印するアイコンと文字。

アイコンの画像（assets/icon_frog.png）の黒い線を potrace で輪郭にし、文字（@imaimai17468）と並べる。
座標は刻印を正面から見たときの mm（u 右向き、v 上向き）。原点は刻印全体の中心。
"""
import math
from pathlib import Path

import numpy as np
import potrace
from build123d import Align, BuildSketch, Locations, Mode, Polygon, Text
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "assets" / "icon_frog.png"
HANDLE = "@imaimai17468"
FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc"
ICON_H = 14.0      # アイコンの画像の高さ。線のある範囲は約 11.4 mm（奥の面は高さ 18.1 mm）
TEXT_H = 4.2       # 文字の大きさ（Text のフォントサイズ）
GAP = 3.0          # アイコンと文字のあいだ
DARK = 110         # R・G・B がすべてこれより暗い画素を線とみなす（0〜255）


def _xy(p):
    return (p.x, p.y)


def _sample(seg_start, seg, n=8):
    """potrace の 1 区間を折れ線の点にする（始点は含めない）。"""
    if seg.is_corner:
        return [_xy(seg.c), _xy(seg.end_point)]
    p0, p1, p2, p3 = seg_start, _xy(seg.c1), _xy(seg.c2), _xy(seg.end_point)
    pts = []
    for i in range(1, n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def icon_loops(height=ICON_H):
    """アイコンの線の輪郭を [(外側か, [(u, v), ...]), ...] で返す。左下が原点、高さ height mm。"""
    img = np.asarray(Image.open(ICON).convert("RGB"))
    mask = img.max(axis=2) < DARK  # 黒い線だけ（赤い舌や紫のカタツムリは線にしない）
    h, w = mask.shape
    scale = height / h
    paths = potrace.Bitmap(~mask).trace(  # potracer は False の画素を図形として扱う
       turdsize=4, alphamax=1.0, opticurve=True, opttolerance=0.2)
    loops = []
    for curve in paths:
        pts = [_xy(curve.start_point)]
        for seg in curve.segments:
            pts += _sample(pts[-1], seg)
        pts = pts[:-1]  # 終点は始点と同じ
        uv = [(x * scale, (h - y) * scale) for x, y in pts]
        loops.append(uv)
    loops = [uv for uv in loops if abs(_area(uv)) > 0.01]
    # 入れ子の深さで塗りを決める（偶数の深さが線、奇数が線に囲まれた白い所）。向きは当てにしない
    depth = [sum(_inside(uv[0], other) for j, other in enumerate(loops) if j != i) for i, uv in enumerate(loops)]
    order = sorted(range(len(loops)), key=lambda i: depth[i])
    return [(depth[i] % 2 == 0, loops[i]) for i in order], w * scale


def _area(uv):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(uv, uv[1:] + uv[:1])) / 2


def _inside(p, poly):
    x, y = p
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def marking_sketch():
    """アイコンと文字を並べた刻印の形（build123d の面）。全体の中心が原点。"""
    loops, icon_w = icon_loops()
    with BuildSketch() as text_sk:
        Text(HANDLE, TEXT_H, font_path=FONT, align=(Align.MIN, Align.CENTER))
    text_w = text_sk.sketch.bounding_box().size.X
    total = icon_w + GAP + text_w
    u0 = -total / 2
    with BuildSketch() as sk:
        # 浅い順に、線（偶数の深さ）は足し、線に囲まれた所（奇数）は引く
        for outer, uv in loops:
            Polygon(*[(u0 + u, v - ICON_H / 2) for u, v in uv], align=None,
                    mode=Mode.ADD if outer else Mode.SUBTRACT)
        with Locations((u0 + icon_w + GAP, 0)):
            Text(HANDLE, TEXT_H, font_path=FONT, align=(Align.MIN, Align.CENTER))
    shape = sk.sketch
    c = shape.bounding_box().center()   # 線のある範囲の中心を原点にそろえる（画像の余白で上下にずれないよう）
    shape = shape.translate((-c.X, -c.Y, 0))
    size = shape.bounding_box().size
    return shape, (size.X, size.Y)


if __name__ == "__main__":
    sk, size = marking_sketch()
    bb = sk.bounding_box()
    print(f"marking {bb.size.X:.1f} x {bb.size.Y:.1f} mm, faces {len(sk.faces())}, area {sk.area:.1f} mm2")
