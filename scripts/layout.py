#!/usr/bin/env python3
"""KLE形式の配列JSONを読み、キー中心座標(mm)のJSONとプレビューSVGを出力する。

出力する keys.json が配列の単一の情報源で、KiCadへの部品配置・ZMKの物理レイアウト・
ケース外形はすべてここから生成する。

usage: python3 scripts/layout.py layout/option-c.kle.json build/option-c
"""
import json
import sys
from pathlib import Path

PITCH = 19.05  # mm / 1u
MULTI_MIN_U = 2.0  # 2u 以上のキーはスタビライザーの代わりにスイッチを複数並べて支える


def switch_offsets(w, h):
    """キー中心からのスイッチ位置 (mm)。長いキーは両端のスイッチを隣のキーから 1u の位置に置く。

    スイッチはすべて同じキーとして並列に配線する（どこを押しても入力される）。
    """
    if h >= MULTI_MIN_U:
        d = (h - 1) / 2
        return [[0.0, round(-d * PITCH, 3)], [0.0, round(d * PITCH, 3)]]
    if w < MULTI_MIN_U:
        return [[0.0, 0.0]]
    d = (w - 1) / 2
    xs = [-d, d] if w < 4 else [-d, 0.0, d]
    return [[round(x * PITCH, 3), 0.0] for x in xs]


def parse_kle(rows):
    keys = []
    meta = {}
    y = 0.0
    for row in rows:
        if isinstance(row, dict):
            meta.update(row)
            continue
        x = 0.0
        props = {}
        for item in row:
            if isinstance(item, dict):
                props.update(item)
                continue
            x += props.pop("x", 0.0)
            y += props.pop("y", 0.0)
            w = props.pop("w", 1.0)
            h = props.pop("h", 1.0)
            key = {"label": item, "x": x, "y": y, "w": w, "h": h}
            if "w2" in props or "h2" in props:
                key["secondary"] = {
                    "x": x + props.pop("x2", 0.0),
                    "y": y + props.pop("y2", 0.0),
                    "w": props.pop("w2", w),
                    "h": props.pop("h2", h),
                }
            keys.append(key)
            x += w
        y += 1.0
    return meta, keys


def to_mm(keys):
    out = []
    for i, k in enumerate(keys):
        # スイッチ中心は主矩形の中心 (ISO Enterも縦長部分の中心)
        cx = (k["x"] + k["w"] / 2) * PITCH
        cy = (k["y"] + k["h"] / 2) * PITCH
        out.append({
            "id": i,
            "label": k["label"],
            "x_mm": round(cx, 3),
            "y_mm": round(cy, 3),
            "w_u": k["w"],
            "h_u": k["h"],
            "switches": switch_offsets(k["w"], k["h"]),
            # キー外形の矩形 [左, 上, 幅, 高さ] (mm, キー中心基準)。ISO Enter は 2 つ
            "rects": [[round((r["x"] - k["x"] - k["w"] / 2) * PITCH, 3),
                       round((r["y"] - k["y"] - k["h"] / 2) * PITCH, 3),
                       round(r["w"] * PITCH, 3), round(r["h"] * PITCH, 3)]
                      for r in [k] + ([k["secondary"]] if "secondary" in k else [])],
        })
    return out


def bounds(keys):
    rects = []
    for k in keys:
        rects.append(k)
        if "secondary" in k:
            rects.append(k["secondary"])
    return (max(r["x"] + r["w"] for r in rects), max(r["y"] + r["h"] for r in rects))


def render_svg(meta, keys, keys_mm, size_u):
    s = 60  # px / 1u
    pad = 20
    gap = 3
    width = size_u[0] * s + pad * 2
    height = size_u[1] * s + pad * 2 + 40
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="Hiragino Sans, sans-serif">',
        f'<rect width="100%" height="100%" fill="#f4f4f4"/>',
        f'<text x="{pad}" y="{height - 15:.0f}" font-size="16" fill="#333">'
        f'{meta.get("name", "")} — {size_u[0] * PITCH:.1f} × {size_u[1] * PITCH:.1f} mm (キー領域)</text>',
    ]
    for k, m in zip(keys, keys_mm):
        multi = len(m["switches"]) > 1
        fill = "#d9a441" if multi else "#2b2b2b"
        for r in [k] + ([k["secondary"]] if "secondary" in k else []):
            parts.append(
                f'<rect x="{pad + r["x"] * s + gap:.1f}" y="{pad + r["y"] * s + gap:.1f}" '
                f'width="{r["w"] * s - gap * 2:.1f}" height="{r["h"] * s - gap * 2:.1f}" '
                f'rx="5" fill="{fill}"/>')
        cx = pad + m["x_mm"] / PITCH * s
        cy = pad + m["y_mm"] / PITCH * s
        for dx, dy in m["switches"]:
            parts.append(f'<circle cx="{cx + dx / PITCH * s:.1f}" cy="{cy + dy / PITCH * s:.1f}" '
                         f'r="2" fill="#e05050"/>')
        parts.append(
            f'<text x="{cx:.1f}" y="{cy - 8:.1f}" font-size="13" fill="#fff" '
            f'text-anchor="middle">{k["label"]}</text>')
        parts.append(
            f'<text x="{cx:.1f}" y="{cy + 18:.1f}" font-size="9" '
            f'fill="{"#5a3d00" if multi else "#999"}" '
            f'text-anchor="middle">{m["w_u"]:g}u</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def main():
    src, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    meta, keys = parse_kle(json.loads(src.read_text()))
    keys_mm = to_mm(keys)
    size_u = bounds(keys)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "keys.json").write_text(json.dumps({
        "name": meta.get("name"),
        "pitch_mm": PITCH,
        "size_mm": [round(size_u[0] * PITCH, 3), round(size_u[1] * PITCH, 3)],
        "key_count": len(keys_mm),
        "keys": keys_mm,
    }, ensure_ascii=False, indent=2))
    (out_dir / "layout.svg").write_text(render_svg(meta, keys, keys_mm, size_u))
    multi = {m["label"]: len(m["switches"]) for m in keys_mm if len(m["switches"]) > 1}
    total = sum(len(m["switches"]) for m in keys_mm)
    print(f"{meta.get('name')}: {len(keys_mm)} keys, {total} switches, "
          f"{size_u[0]:g}u x {size_u[1]:g}u, multi-switch keys: {multi}")


if __name__ == "__main__":
    main()
