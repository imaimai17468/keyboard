#!/usr/bin/env python3
"""JLCCNC に付けるケースの 2D 図面（めねじの指定用）を A3・1:1 の PDF で書き出す。

JLCCNC はタップ（めねじ）を 3D データからは読まないので、穴の位置と仕様を図面で指定する。
書き方は note.com/copkbd/n/n7063aaa7e778 に倣う（第三角法、1:1、「M2x0.4 6H x 有効長/下穴深さ」）。

  python3 scripts/gen_drawing.py build/assembly/case_features.json build/assembly/case_drawing.pdf
"""
import json
import subprocess
import sys
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGE_W, PAGE_H = 420, 297  # A3 横（mm）


def main():
    f = json.loads(Path(sys.argv[1]).read_text())
    pdf = Path(sys.argv[2])
    W, H = f["size"]
    Z, ZF = f["height"], f["height_front"]
    tap, cb, usb = f["tap"], f["counterbore"], f["usb"]
    ox, oy = 35, 22  # 上面図の左上
    sx = lambda x: ox + x
    sy = lambda y: oy + (H - y)
    fy = oy + H + 22          # 正面図の上端（上面図の下）
    el = []
    line = lambda x1, y1, x2, y2, c="#000", w=0.35, d="": el.append(
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{c}" stroke-width="{w}"'
        + (f' stroke-dasharray="{d}"' if d else "") + "/>")
    text = lambda x, y, s, size=3.0, anchor="start", weight="400": el.append(
        f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}">{s}</text>')

    # 上面図: 外形・内側の開口（細線）・穴
    r = f["corner_r"]
    el.append(f'<rect x="{sx(0)}" y="{sy(H)}" width="{W}" height="{H}" rx="{r}" fill="none" stroke="#000" stroke-width="0.5"/>')
    ix0, iy0, ix1, iy1 = f["inner"]
    el.append(f'<rect x="{sx(ix0)}" y="{sy(iy1)}" width="{ix1 - ix0}" height="{iy1 - iy0}" rx="{f["inner_r"]}" '
              'fill="none" stroke="#000" stroke-width="0.25"/>')
    text(sx(W / 2), oy - 6, "TOP VIEW", 3.5, "middle", "700")
    for i, (x, y) in enumerate(f["tapped"], 1):
        cx, cy = sx(x), sy(y)
        el.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{tap["boss_d"] / 2}" fill="none" stroke="#000" stroke-width="0.2"/>')
        el.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{tap["drill_d"] / 2}" fill="none" stroke="#c00" stroke-width="0.35"/>')
        line(cx - 3, cy, cx + 3, cy, "#c00", 0.15)
        line(cx, cy - 3, cx, cy + 3, "#c00", 0.15)
        ty = cy - 4 if y > H / 2 else cy + 6.5
        text(cx + 2.5, ty, f"T{i}", 3.2, "start", "700")
    for i, (x, y) in enumerate(f["through"], 1):
        cx, cy = sx(x), sy(y)
        el.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{cb["hole_d"] / 2}" fill="none" stroke="#000" stroke-width="0.35"/>')
        el.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{cb["d"] / 2}" fill="none" stroke="#000" stroke-width="0.2" stroke-dasharray="1 0.8"/>')
        text(cx + 3.2, cy - 3, f"C{i}", 3.2, "start", "700")
    # 原点と全体寸法
    line(sx(0) - 4, sy(0), sx(0) + 6, sy(0), w=0.2)
    line(sx(0), sy(0) + 4, sx(0), sy(0) - 6, w=0.2)
    text(sx(0) - 1.5, sy(0) + 5, "DATUM (0,0)", 2.6, "end")
    line(sx(0), oy - 3, sx(W), oy - 3, w=0.2)
    text(sx(W) - 1, oy - 4, f"{W:.1f}", 2.8, "end")
    line(ox - 6, sy(H), ox - 6, sy(0), w=0.2)
    text(ox - 7, sy(H / 2), f"{H:.1f}", 2.8, "end")

    # 正面図（手前から）: 外形の高さ。奥の張り出しは隠れ線
    el.append(f'<rect x="{sx(0)}" y="{fy}" width="{W}" height="{Z}" fill="none" stroke="#000" stroke-width="0.5"/>')
    line(sx(0), fy + ZF, sx(W), fy + ZF, w=0.2, d="1.5 1")
    text(sx(W / 2), fy + Z + 7, "FRONT VIEW", 3.5, "middle", "700")
    text(sx(0) - 1.5, fy + Z / 2 + 1, f"{Z:.1f}", 2.8, "end")

    # 右側面図は A3 の 1:1 に入らないので省く（段付きの底・USB-C の開口は 3D データで指定）

    # 穴の表
    tx, ty = ox, fy + Z + 18
    text(tx, ty, "HOLE TABLE (from DATUM, mm)", 3.2, "start", "700")
    rows = [("ID", "X", "Y", "SPEC")]
    spec_t = (f'{tap["thread"]} x {tap["thread_len"]:g} / drill &#216;{tap["drill_d"]:g} x {tap["drill_depth"]:g} '
              "(blind, from top of internal boss)")
    spec_c = f'&#216;{cb["hole_d"]:g} THRU, counterbore &#216;{cb["d"]:g} x {cb["depth"]:g} from bottom face (NOT tapped)'
    rows += [(f"T{i}", f"{x:.2f}", f"{y:.2f}", spec_t) for i, (x, y) in enumerate(f["tapped"], 1)]
    rows += [(f"C{i}", f"{x:.2f}", f"{y:.2f}", spec_c) for i, (x, y) in enumerate(f["through"], 1)]
    for j, row in enumerate(rows):
        yy = ty + 5 + j * 4.2
        for x, s in zip((0, 12, 32, 52), row):
            text(tx + x, yy, s, 2.8, "start", "700" if j == 0 else "400")

    # 注記と表題欄
    nx, ny = ox + 205, fy + Z + 18
    notes = [
        "NOTES",
        "1. Material: Aluminum 6061-T6.",
        "2. Finish: bead blasting + anodizing, Natural, matte.",
        "3. General tolerance: ISO 2768-m. Dimensions in mm.",
        f'4. Tapped holes T1-T{len(f["tapped"])} ({len(f["tapped"])} places): {tap["thread"]}, thread depth {tap["thread_len"]:g},',
        f'   drill &#216;{tap["drill_d"]:g} depth {tap["drill_depth"]:g}. Blind holes, do NOT drill through the bottom.',
        f'5. Holes C1-C{len(f["through"])}: through, with counterbore from the bottom face. Not tapped.',
        "6. Break all sharp edges, C0.2 max. Burr-free.",
        "7. All other geometry (stepped bottom, USB-C opening R1) per 3D model case.step.",
        "8. Third angle projection. Scale 1:1 on A3.",
    ]
    for j, s in enumerate(notes):
        text(nx, ny + j * 4.4, s, 2.8, "start", "700" if j == 0 else "400")
    bx, by = PAGE_W - 120, PAGE_H - 22
    el.append(f'<rect x="{bx}" y="{by}" width="110" height="14" fill="none" stroke="#000" stroke-width="0.4"/>')
    text(bx + 3, by + 6, "macjis keyboard case", 3.6, "start", "700")
    text(bx + 3, by + 11.5, "Al 6061 / A3 1:1 / third angle / mm", 2.6)
    # 第三角法の記号は省略し注記で示す。外枠
    el.append(f'<rect x="8" y="8" width="{PAGE_W - 16}" height="{PAGE_H - 16}" fill="none" stroke="#000" stroke-width="0.5"/>')

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" '
           f'viewBox="0 0 {PAGE_W} {PAGE_H}" font-family="Helvetica, Arial, sans-serif">'
           + "".join(el) + "</svg>")
    html = pdf.with_suffix(".html")
    html.write_text('<!doctype html><meta charset="utf-8"><style>@page{size:420mm 297mm;margin:0}'
                    "html,body{margin:0}svg{display:block}</style>" + svg)
    pdf.with_suffix(".svg").write_text(svg)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf.resolve()}", f"file://{html.resolve()}"],
                   check=True, capture_output=True)
    print(pdf)


if __name__ == "__main__":
    main()
