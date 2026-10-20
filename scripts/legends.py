"""キーキャップの刻印（MacBook の JIS 配列に合わせる。かなは入れない）。

legend(key, board_width) がキー上面に彫る形（build123d の Sketch、キー中心基準・y 上向き・mm）を返す。
- 英字: 中央に大きく。数字・記号: 上に shift 時の記号、下に通常の文字
- 修飾キー: 単語を下の隅に小さく。control / option / command は反対側の上の隅に記号
- F 列: 上にアイコン、下に F1〜F12。fn は左下に地球、右上に fn
彫りの線幅は JLC3DP で潰れないよう 0.4 mm 以上を目安にする（小さい文字は太いウェイト）。
"""
import math

from build123d import (Align, BuildLine, BuildSketch, CenterArc, Circle, EllipticalCenterArc, Line,
                       Locations, Mode, Polygon, Polyline, Rectangle, Sketch, Text, offset, trace)

FONT_DIR = "/System/Library/Fonts"
FONTS = {
    "big": f"{FONT_DIR}/ヒラギノ角ゴシック W6.ttc",    # 英字・数字（4 mm 前後）
    "small": f"{FONT_DIR}/ヒラギノ角ゴシック W8.ttc",  # 修飾キーの単語など（3 mm 以下）
    "sym": f"{FONT_DIR}/Apple Symbols.ttf",           # ⌃ ⌥（ヒラギノに無い）
}
CHAR = 4.2      # 英字
DUAL = 3.4      # 数字・記号の 2 段
WORD = 2.6      # 修飾キーの単語
MOD_SYM = 3.6   # ⌘（ヒラギノ）
MOD_SYM_APPLE = 6.0  # ⌃ ⌥（Apple Symbols は字面が小さいので大きめに指定）
FKEY = 2.6      # F1〜F12
ICON = 5.4      # F 列などのアイコンの高さ
STROKE = 0.5    # アイコンの線幅
INSET = 2.7     # キーの外形（隙間込み）から刻印までの余白
THICKEN = 0.06  # 文字の輪郭を外へ広げる量（線幅は 2 倍増える）

# label -> 刻印の種類。数字・記号は (shift 時, 通常)
DUALS = {"1": ("!", "1"), "2": ("\"", "2"), "3": ("#", "3"), "4": ("$", "4"), "5": ("%", "5"),
         "6": ("&", "6"), "7": ("'", "7"), "8": ("(", "8"), "9": (")", "9"), "0": ("", "0"),
         "-": ("=", "-"), "^": ("~", "^"), "¥": ("|", "¥"), "@": ("`", "@"), "[": ("{", "["),
         ";": ("+", ";"), ":": ("*", ":"), "]": ("}", "]"), ",": ("<", ","), ".": (">", "."),
         "/": ("?", "/"), "_": ("", "_")}
WORDS = {"esc": "esc", "tab": "tab", "bs": "delete", "enter": "return", "shift": "shift"}
MODS = {"ctrl": ("control", "⌃"), "opt": ("option", "⌥"), "cmd": ("command", "⌘")}
FKEYS = {"F1": "bri_down", "F2": "bri_up", "F3": "mission", "F4": "launchpad", "F5": None, "F6": None,
         "F7": "prev", "F8": "play", "F9": "next", "F10": "mute", "F11": "vol_down", "F12": "vol_up"}
ICONS = {"lock": "lock", "light": "bluetooth"}   # light は Bluetooth の接続先切り替え（ZMK の BT_NXT）
CENTER = {"英数": "英数", "かな": "かな", "半角": "半角"}
ARROWS = {"←": 180, "↑": 90, "↓": 270, "→": 0}


def _text(s, size, font, x, y, ax, ay, max_w=None):
    """文字の外形（グリフの実際の輪郭）の端を (x, y) に合わせる。Text の align は字送り幅基準で、
    記号だと実際の形がはみ出すため。細い線（_ など）が潰れないよう THICKEN だけ太らせる。"""
    with BuildSketch() as sk:
        Text(s, size, font_path=FONTS[font])
    if max_w and sk.sketch.bounding_box().size.X > max_w:   # 入りきらない単語は縮める（1u の command など）
        return _text(s, size * max_w / sk.sketch.bounding_box().size.X * 0.98, font, x, y, ax, ay)
    shape = None
    for face in sk.sketch.faces():   # 文字全体だと offset が失敗することがあるので 1 面ずつ
        if size >= CHAR:             # 大きい英字は十分太い（W の谷に棘が出るので太らせない）
            shape = face if shape is None else shape + face
            continue
        try:
            with BuildSketch() as one:
                offset(face, amount=THICKEN)
            face = one.sketch
        except RuntimeError:
            pass
        shape = face if shape is None else shape + face
    bb = shape.bounding_box()
    pick = {Align.MIN: lambda lo, hi: lo, Align.CENTER: lambda lo, hi: (lo + hi) / 2, Align.MAX: lambda lo, hi: hi}
    return shape.translate((x - pick[ax](bb.min.X, bb.max.X), y - pick[ay](bb.min.Y, bb.max.Y), 0))


def _stroke(draw, x, y, s):
    """draw(s) が BuildLine の中で線を引き、STROKE の太さの面にする。線ごとに太らせてから足す
    （交差や閉じた線をまとめて trace すると OCCT の sweep が失敗するため）。"""
    with BuildLine() as ln:
        draw(s)
    shape = None
    for edge in ln.edges():
        with BuildSketch() as sk:
            trace(edge, line_width=STROKE)
        shape = sk.sketch if shape is None else shape + sk.sketch
    return shape.translate((x, y, 0))


def _filled(points, x, y):
    with BuildSketch() as sk:
        Polygon(*[(x + px, y + py) for px, py in points], align=None)
    return sk.sketch


def _triangle(angle, side, x=0.0, y=0.0):
    r = side / math.sqrt(3)
    pts = [(r * math.cos(math.radians(angle + a)), r * math.sin(math.radians(angle + a))) for a in (0, 120, 240)]
    return _filled(pts, x, y)


def _sun(s, big):
    core = s * (0.17 if not big else 0.2)
    r1, r2 = s * 0.31, s * (0.4 if not big else 0.5)
    with BuildSketch() as sk:
        Circle(core)
    parts = [sk.sketch]

    def rays(_):
        for i in range(8):
            a = math.radians(45 * i)
            Line((r1 * math.cos(a), r1 * math.sin(a)), (r2 * math.cos(a), r2 * math.sin(a)))
    parts.append(_stroke(rays, 0, 0, s))
    return parts


def _speaker(s, waves):
    body = [(-0.42, -0.13), (-0.2, -0.13), (0.02, -0.34), (0.02, 0.34), (-0.2, 0.13), (-0.42, 0.13)]
    dx = -0.1 * waves   # 波の数だけ左に寄せて全体を中央に
    parts = [_filled([((px + dx) * s, py * s) for px, py in body], 0, 0)]
    if waves:
        def arcs(_):
            for i in range(waves):
                CenterArc(((0.04 + dx) * s, 0), s * (0.2 + 0.15 * i), -40, 80)
        parts.append(_stroke(arcs, 0, 0, s))
    return parts


def _icon(name, s, x, y):
    if name in ("bri_down", "bri_up"):
        parts = _sun(s, name == "bri_up")
    elif name == "mission":       # 開いているウインドウを並べる（Mission Control）
        def frames(_):
            for cx, cy, w, h in ((-0.27, 0.22, 0.42, 0.3), (0.27, 0.22, 0.42, 0.3), (0, -0.2, 0.96, 0.36)):
                x0, x1, y0, y1 = (cx - w / 2) * s, (cx + w / 2) * s, (cy - h / 2) * s, (cy + h / 2) * s
                Polyline((x0, y0), (x1, y0), (x1, y1), (x0, y1), close=True)
        parts = [_stroke(frames, 0, 0, s)]
    elif name == "launchpad":     # アプリを並べる（Launchpad）
        with BuildSketch() as sk:
            with Locations(*[(cx * s * 0.32, cy * s * 0.32) for cx in (-1, 0, 1) for cy in (-0.6, 0.6)]):
                Rectangle(s * 0.2, s * 0.2)
        parts = [sk.sketch]
    elif name in ("prev", "next"):
        a, d = (180, -1) if name == "prev" else (0, 1)
        parts = [_triangle(a, s * 0.42, d * -s * 0.12), _triangle(a, s * 0.42, d * s * 0.18)]
    elif name == "play":
        with BuildSketch() as sk:
            with Locations((s * 0.16, 0), (s * 0.32, 0)):
                Rectangle(s * 0.08, s * 0.36)
        parts = [_triangle(0, s * 0.42, -s * 0.2), sk.sketch]
    elif name in ("mute", "vol_down", "vol_up"):
        parts = _speaker(s, {"mute": 0, "vol_down": 1, "vol_up": 3}[name])
    elif name == "lock":
        with BuildSketch() as sk:
            with Locations((0, -s * 0.15)):
                Rectangle(s * 0.6, s * 0.44)

        def shackle(_):
            r = s * 0.18
            Line((-r, s * 0.07), (-r, s * 0.18))
            CenterArc((0, s * 0.18), r, 0, 180)
            Line((r, s * 0.18), (r, s * 0.07))
        parts = [sk.sketch, _stroke(shackle, 0, 0, s)]
    elif name == "bluetooth":
        def rune(_):
            pts = [(px * s, py * s) for px, py in
                   ((-0.22, 0.22), (0.22, -0.2), (0, -0.45), (0, 0.45), (0.22, 0.2), (-0.22, -0.22))]
            for a, b in zip(pts, pts[1:]):   # 線が交差するので 1 本ずつ（Polyline だと trace が崩れる）
                Line(a, b)
        parts = [_stroke(rune, 0, 0, s)]
    elif name == "globe":
        def globe(_):
            r = s * 0.5
            CenterArc((0, 0), r, 0, 360)
            EllipticalCenterArc((0, 0), r * 0.45, r, arc_size=360)
            Line((-r, 0), (r, 0))
            Line((0, -r), (0, r))
        parts = [_stroke(globe, 0, 0, s)]
    else:
        raise ValueError(name)
    return [p.translate((x, y, 0)) for p in parts]


def legend(key, board_width):
    """key は keys.json の 1 キー。刻印が無ければ None。"""
    label = key["label"]
    xs = [v for left, top, w, h in key["rects"] for v in (left, left + w)]
    ys = [-v for left, top, w, h in key["rects"] for v in (top, top + h)]
    left, right, bottom, top = min(xs) + INSET, max(xs) - INSET, min(ys) + INSET, max(ys) - INSET
    if label == "enter":          # 縦長の Enter は上の段（y > 0）の中に収める
        bottom = INSET
    right_side = key["x_mm"] > board_width / 2
    parts = []
    if len(label) == 1 and label.isalpha() and label.isascii():
        parts.append(_text(label, CHAR, "big", 0, 0, Align.CENTER, Align.CENTER))
    elif label in DUALS:
        upper, lower = DUALS[label]
        if upper:
            parts.append(_text(upper, DUAL, "big", 0, 2.6, Align.CENTER, Align.CENTER))
        parts.append(_text(lower, DUAL, "big", 0, -2.6, Align.CENTER, Align.CENTER))
    elif label in WORDS:
        ax, x = (Align.MAX, right) if right_side else (Align.MIN, left)
        parts.append(_text(WORDS[label], WORD, "small", x, bottom, ax, Align.MIN, right - left))
    elif label in MODS:
        word, sym = MODS[label]
        (ax, x), (sx, sax) = ((Align.MAX, right), (left, Align.MIN)) if right_side else \
            ((Align.MIN, left), (right, Align.MAX))
        parts.append(_text(word, WORD, "small", x, bottom, ax, Align.MIN, right - left))
        if sym == "⌘":
            parts.append(_text(sym, MOD_SYM, "big", sx, top, sax, Align.MAX))
        else:
            parts.append(_text(sym, MOD_SYM_APPLE, "sym", sx, top, sax, Align.MAX))
    elif label == "fn":
        parts.append(_text("fn", WORD, "small", right, top, Align.MAX, Align.MAX))
        parts += _icon("globe", ICON * 0.8, left + ICON * 0.4 + STROKE / 2, bottom + ICON * 0.4 + STROKE / 2)
    elif label in FKEYS:
        parts.append(_text(label, FKEY, "small", 0, bottom, Align.CENTER, Align.MIN))
        if FKEYS[label]:
            parts += _icon(FKEYS[label], ICON, 0, 2.0)
    elif label in ICONS:
        parts += _icon(ICONS[label], ICON, 0, 0)
    elif label in CENTER:
        parts.append(_text(CENTER[label], DUAL, "big", 0, 0, Align.CENTER, Align.CENTER))
    elif label in ARROWS:
        parts.append(_triangle(ARROWS[label], 3.0))
    elif label == "space":
        return None
    else:
        raise ValueError(f"刻印が未定義: {label}")
    sk = parts[0]
    for p in parts[1:]:
        sk = sk + p
    return sk
