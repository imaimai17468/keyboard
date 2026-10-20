#!/usr/bin/env python3
"""Choc V1 用キーキャップを build123d で生成する（STEP / STL）。

- test_*: 嵌合試作用。1u を軸の太さ違いで 3 種類と、軸 3 本の Space
- set/: 全 81 キー（刻印は scripts/legends.py）と、刻印を並べた確認用の set/legends.svg

  .venv/bin/python scripts/gen_keycaps.py build/option-c/matrix.json build/keycaps

座標: 軸の先端を z = 0 とし、上向きが +z。x, y はキー中心基準で y は上向き
（keys.json の y 下向きとは逆なので、読み込み時に反転する）。
軸はスイッチ中心から x 方向に ±2.85 mm。
軸の寸法は braindefender/KLP-Lame-Keycaps (CC-BY-SA 4.0) の STEP を実測した値。
"""
import json
import re
import sys
from pathlib import Path

from build123d import (Align, Axis, Box, BuildPart, BuildSketch, ExportSVG, Location, Locations, Mode,
                       Plane, Rectangle, Text, Unit, export_step, export_stl, extrude, fillet, insert, offset)

sys.path.insert(0, str(Path(__file__).parent))
import legends  # noqa: E402

PITCH = 19.05
GAP = 1.05               # 隣のキーとの隙間。1u の上面は 18.0 mm 角
STEM_PITCH = 5.7         # 軸 2 本の中心間
STEM_W = 1.15            # 軸の太さ（x）。嵌合試作で 1.05 / 1.15 / 1.25 を比べる
STEM_L = 2.95            # 軸の長さ（y）
STEM_ROOT = (1.6, 3.4, 0.6)  # 軸の付け根の補強 (x, y, 高さ)
UNDERSIDE_Z = 3.8        # 天板の下面（軸の先端から）
SKIRT_Z = 1.9            # 側壁の下端
TOP_T = 2.0              # 天板の厚み（刻印 0.4 mm を彫っても 1.6 mm 残る）
TOP_Z = UNDERSIDE_Z + TOP_T
WALL_T = 1.2             # JLC3DP の推奨最小肉厚
CORNER_R = 1.5
LEGEND_DEPTH = 0.4
FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"


def outline(rects, inset):
    """keys.json の rects（[左, 上, 幅, 高さ]、y 下向き）を合わせた外形を、inset だけ内側に寄せた面。"""
    with BuildSketch() as sk:
        for left, top, w, h in rects:
            with Locations((left + w / 2, -(top + h / 2))):
                Rectangle(w, h)
        offset(amount=-inset, mode=Mode.REPLACE)
    return sk.sketch


def keycap(rects, stems, legend="", legend_size=4.0, stem_w=STEM_W, engrave=True, under=""):
    """rects の外形のキーキャップ。stems はキー中心からのスイッチ位置 (mm, y 下向き) のリスト。
    legend は文字列（中央に legend_size で彫る）か、legends.legend() の面。

    engrave=False のときは彫らずに (本体, 刻印部分の立体) を返す。完成図で刻印の色を切り替えるため。
    under は天板の裏に彫る小さな文字（試作の見分け用。下から読めるよう左右反転）。
    """
    with BuildPart() as p:
        with BuildSketch(Location((0, 0, SKIRT_Z))):
            insert(outline(rects, GAP / 2))
        extrude(amount=TOP_Z - SKIRT_Z)
        fillet(p.edges().filter_by(Axis.Z), CORNER_R)
        fillet(p.edges().group_by(Axis.Z)[-1], 0.6)
        with BuildSketch(Location((0, 0, SKIRT_Z))):
            insert(outline(rects, GAP / 2 + WALL_T))
        extrude(amount=UNDERSIDE_Z - SKIRT_Z, mode=Mode.SUBTRACT)
        for sx, sy in stems:
            for dx in (-STEM_PITCH / 2, STEM_PITCH / 2):
                with Locations((sx + dx, -sy, 0)):
                    Box(stem_w, STEM_L, UNDERSIDE_Z + 0.1, align=(Align.CENTER, Align.CENTER, Align.MIN))
                with Locations((sx + dx, -sy, UNDERSIDE_Z - STEM_ROOT[2])):
                    Box(*STEM_ROOT, align=(Align.CENTER, Align.CENTER, Align.MIN))
        if under:
            with BuildSketch(Plane.XY.offset(UNDERSIDE_Z).rotated((180, 0, 0)).moved(Location((0, -4.8, 0)))):
                Text(under, 2.2, font_path=FONT)
            extrude(amount=-0.3, mode=Mode.SUBTRACT)
    cap = p.part
    if not legend:
        return cap if engrave else (cap, None)
    with BuildPart() as m:
        with BuildSketch(Location((0, 0, TOP_Z))):
            if isinstance(legend, str):
                Text(legend, legend_size, font_path=FONT)
            else:
                insert(legend)
        extrude(amount=-LEGEND_DEPTH)
    if engrave:
        return cap - m.part
    return cap, m.part


def export(part, path):
    export_step(part, str(path.with_suffix(".step")))
    export_stl(part, str(path.with_suffix(".stl")))
    bb = part.bounding_box()
    print(f"{path.name}: {bb.size.X:.2f} × {bb.size.Y:.2f} × {bb.size.Z:.2f} mm, {part.volume:.0f} mm³")


def preview(keys, width, path):
    """キーの外形と刻印を配列どおりに並べた SVG（上から見た図）。"""
    svg = ExportSVG(unit=Unit.MM, line_weight=0.15)
    svg.add_layer("outline", line_color=(150, 150, 150))
    svg.add_layer("legend", fill_color=(20, 20, 20), line_color=(20, 20, 20), line_weight=0.05)
    for k in keys:
        loc = Location((k["x_mm"], -k["y_mm"]))
        svg.add_shape(outline(k["rects"], GAP / 2).moved(loc).edges(), layer="outline")
        sk = legends.legend(k, width)
        if sk is not None:
            svg.add_shape(sk.moved(loc), layer="legend")
    svg.write(str(path))


def main():
    data = json.loads(Path(sys.argv[1]).read_text())
    keys, width = data["keys"], data["size_mm"][0]
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    one_u = [[-PITCH / 2, -PITCH / 2, PITCH, PITCH]]
    # 1u: 軸の太さ違い（材質の誤差 ±0.2〜0.3 mm に負けないよう 0.1 mm 刻み）。
    # 上面は刻印の読みやすさを見る文字、裏に軸の太さ（1/100 mm）を彫って見分ける
    for legend, sw in (("A", 1.05), ("あ", 1.15), ("F1", 1.25)):
        export(keycap(one_u, [(0, 0)], legend, 4.2, sw, under=str(round(sw * 100))),
               out / f"test_1u_stem{round(sw * 100)}")
    space = next(k for k in keys if k["label"] == "space")
    export(keycap(space["rects"], space["switches"]), out / "test_space")

    # 全キー。ファイル名は「番号_キー名」（記号や日本語のキーは番号のみ）
    full = out / "set"
    full.mkdir(exist_ok=True)
    preview(keys, width, full / "legends.svg")
    for k in keys:
        name = re.sub(r"[^A-Za-z0-9]", "", k["label"])
        export(keycap(k["rects"], k["switches"], legends.legend(k, width)),
               full / (f"{k['id']:02d}_{name}" if name else f"{k['id']:02d}"))


if __name__ == "__main__":
    main()
