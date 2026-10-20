#!/usr/bin/env python3
"""matrix.json から KiCad 基板 (.kicad_pcb) を生成する。配線はしない（Freerouting で行う）。

KiCad 同梱の Python で実行する:
  scripts/kicad_python.sh scripts/gen_pcb.py build/option-c/matrix.json pcb/macjis.kicad_pcb

座標系: キー領域の左上を原点 (0, 0)、y は下向き、単位 mm。
キー領域の上に MCU 用の帯 (TOP_STRIP_MM) を設け、XIAO nRF52840 Plus と電池コネクタを置く。
"""
import json
import math
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
LOCAL_LIB = ROOT / "pcb/lib/keyboard.pretty"
STOCK_LIB = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")

TOP_STRIP_MM = 21.0
EDGE_MARGIN_MM = 1.0
CORNER_RADIUS_MM = 1.0
DIODE_OFFSET_MM = (3.0, 5.6)  # スイッチ中心からの位置（裏面）。穴とソケットパッドを避ける
# ケースへ留める M2 ネジ（低頭）。表はネジ頭 φ3.8、裏はケースの支柱 φ4 が部品に当たらない位置を探す
MOUNT_CLEAR_TOP_MM = 2.2  # 穴の部品の外形線 (r2.15) がスイッチの外形と重ならない
MOUNT_CLEAR_BOTTOM_MM = 2.0
# ネジを置きたいおおよその位置（キー領域の幅・高さに対する割合）。上帯は y < 0
MOUNT_TARGETS = [(0.03, 0.08), (0.36, 0.08), (0.64, 0.08), (0.97, 0.08),
                 (0.03, 0.92), (0.36, 0.92), (0.64, 0.92), (0.97, 0.92)]
# 上帯のネジは底から通し、基板と一緒に上帯の樹脂カバー（裏の柱 φ6）を留める。
# ケースの裏で、奥のゴム足 2 つ（ケース外形の左右の端から 20 mm、gen_assembly.py）の間に等間隔で 3 つ並べる
FOOT_FROM_CASE_EDGE_MM = 20.0
CASE_OUTSIDE_PCB_MM = 1.0 + 0.5 + 3.0  # 基板の外周 + 隙間 + 壁（gen_assembly.py の EDGE_MARGIN / CASE_GAP / CASE_WALL）
BAT_CONNECTOR_FROM_RIGHT_MM = 96.0  # 電池コネクタ（裏）。右のカバーのネジとネジ受けの間
COVER_CLEAR_TOP_MM = 3.2
# 中央は裏の部品が密でネジを通せないため、ケース底の柱（φ3、上にゴム足）で下から支えるだけにする
SUPPORT_CLEAR_BOTTOM_MM = 1.7
SUPPORT_TARGETS = [(0.18, 0.5), (0.5, 0.5), (0.82, 0.5)]
MOUNT_SEARCH_MM = 12

# XIAO nRF52840 Plus（基板に直接はんだ付け）。信号のパッド番号は matrix.json の "pad"。
# 電源スイッチは無く、電池は XIAO の VBAT パッドに直結（電源オフは ZMK の soft off）
XIAO_POWER = {"28": "BAT+", "29": "GND", "13": "GND"}
XIAO_LEN_MM = 21.0
XIAO_USB_MM = 12.6        # モジュール中心から USB-C の先端まで（基板の右辺の内側に収める）
XIAO_ANTENNA_MM = 7.0     # モジュール中心から USB と反対側へこの距離より先がアンテナ部


def mm(x, y):
    return pcbnew.VECTOR2I_MM(x, y)


def load(lib, name):
    fp = pcbnew.FootprintLoad(str(lib), name)
    if fp is None:
        raise SystemExit(f"footprint not found: {lib}/{name}")
    return fp


class Builder:
    def __init__(self):
        self.board = pcbnew.BOARD()
        self.nets = {}
        ds = self.board.GetDesignSettings()
        ds.SetCopperLayerCount(2)
        ds.m_TrackMinWidth = pcbnew.FromMM(0.2)
        ds.m_MinClearance = pcbnew.FromMM(0.2)
        nc = ds.m_NetSettings.GetDefaultNetclass()
        nc.SetTrackWidth(pcbnew.FromMM(0.25))
        nc.SetClearance(pcbnew.FromMM(0.2))
        nc.SetViaDiameter(pcbnew.FromMM(0.6))
        nc.SetViaDrill(pcbnew.FromMM(0.3))

    def net(self, name):
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(n)
            self.nets[name] = n
        return self.nets[name]

    def place(self, fp, ref, x, y, rot=0.0, back=False, pads=None):
        fp.SetReference(ref)
        self.board.Add(fp)  # Flip はボードに追加した後でないと落ちる
        fp.SetPosition(mm(x, y))
        if back:
            fp.Flip(mm(x, y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            name = (pads or {}).get(pad.GetNumber())
            if name:
                pad.SetNet(self.net(name))
        return fp

    def keepout(self, rects, cu=(pcbnew.F_Cu, pcbnew.B_Cu), vias=True):
        """配線・ビア・ベタ禁止エリア（矩形 (x0, y0, x1, y1) のリスト）。既定は両面。"""
        layers = pcbnew.LSET()
        for layer in cu:
            layers.AddLayer(layer)
        for (ax, ay, bx, by) in rects:
            z = pcbnew.ZONE(self.board)
            z.SetIsRuleArea(True)
            z.SetDoNotAllowTracks(True)
            z.SetDoNotAllowVias(vias)
            z.SetDoNotAllowPads(False)
            z.SetDoNotAllowFootprints(False)
            z.SetDoNotAllowZoneFills(True)
            z.SetLayerSet(layers)
            o = z.Outline()
            o.NewOutline()
            for px, py in [(ax, ay), (bx, ay), (bx, by), (ax, by)]:
                o.Append(pcbnew.FromMM(px), pcbnew.FromMM(py))
            self.board.Add(z)

    def obstacles(self):
        """部品が占める矩形 (x0, y0, x1, y1) を表・裏に分けて返す。パッドと Fab / 外形線の範囲。"""
        top, bottom = [], []

        def rect(bb):
            return (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                    pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))

        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                if pad.IsOnLayer(pcbnew.F_Cu):
                    top.append(rect(pad.GetBoundingBox()))
                if pad.IsOnLayer(pcbnew.B_Cu):
                    bottom.append(rect(pad.GetBoundingBox()))
            # 外形は線の集まりなので、面ごとに線全体を囲む矩形にする（内側も部品が占める）
            for side, layers in ((top, (pcbnew.F_Fab, pcbnew.F_CrtYd)), (bottom, (pcbnew.B_Fab, pcbnew.B_CrtYd))):
                rs = [rect(g.GetBoundingBox()) for g in fp.GraphicalItems() if g.GetLayer() in layers]
                if rs:
                    side.append((min(r[0] for r in rs), min(r[1] for r in rs),
                                 max(r[2] for r in rs), max(r[3] for r in rs)))
        return top, bottom

    def edge_keepout(self, x0, y0, x1, y1, w):
        """基板端に沿った禁止帯。Freerouting は基板端クリアランスを知らないため。"""
        self.keepout([(x0, y0, x1, y0 + w), (x0, y1 - w, x1, y1),
                      (x0, y0, x0 + w, y1), (x1 - w, y0, x1, y1)])

    def outline(self, x0, y0, x1, y1, r):
        def seg(a, b):
            s = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(mm(*a))
            s.SetEnd(mm(*b))
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(pcbnew.FromMM(0.1))
            self.board.Add(s)

        def arc(c, start, angle):
            s = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_ARC)
            s.SetCenter(mm(*c))
            s.SetStart(mm(*start))
            s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T), True)
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(pcbnew.FromMM(0.1))
            self.board.Add(s)

        seg((x0 + r, y0), (x1 - r, y0))
        seg((x1, y0 + r), (x1, y1 - r))
        seg((x1 - r, y1), (x0 + r, y1))
        seg((x0, y1 - r), (x0, y0 + r))
        arc((x1 - r, y0 + r), (x1 - r, y0), 90)
        arc((x1 - r, y1 - r), (x1, y1 - r), 90)
        arc((x0 + r, y1 - r), (x0 + r, y1), 90)
        arc((x0 + r, y0 + r), (x0, y0 + r), 90)


def clearance(x, y, rects):
    return min(math.hypot(max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1)) for x0, y0, x1, y1 in rects)


def find_spots(b, keys, targets, clear_top, clear_bottom, avoid, width, height):
    """各目標の近く（±MOUNT_SEARCH_MM）で、表・裏の部品から clear_top / clear_bottom 以上離れた位置のうち
    目標に最も近い点を選ぶ。clear_top が None なら表は見ない。
    候補は 0.5 mm 刻みの格子と、キーの角（4 つのキーの間は隙間が広い）。"""
    top, bottom = b.obstacles()
    corners = {(k["x_mm"] + left + w * fx, k["y_mm"] + up + h * fy)
               for k in keys for left, up, w, h in k["rects"] for fx in (0, 1) for fy in (0, 1)}
    lo_x, hi_x = -EDGE_MARGIN_MM + 3, width + EDGE_MARGIN_MM - 3
    lo_y, hi_y = -TOP_STRIP_MM + 3, height + EDGE_MARGIN_MM - 3
    chosen = []
    for tx, ty in targets:
        near = lambda rs: [r for r in rs if r[0] - 20 < tx + MOUNT_SEARCH_MM and r[2] + 20 > tx - MOUNT_SEARCH_MM
                           and r[1] - 20 < ty + MOUNT_SEARCH_MM and r[3] + 20 > ty - MOUNT_SEARCH_MM]
        t, bt = near(top), near(bottom)
        steps = range(-2 * MOUNT_SEARCH_MM, 2 * MOUNT_SEARCH_MM + 1)
        grid = [(tx + i / 2, ty + j / 2) for i in steps for j in steps]
        local = [c for c in corners if abs(c[0] - tx) <= MOUNT_SEARCH_MM and abs(c[1] - ty) <= MOUNT_SEARCH_MM]
        for x, y in sorted(grid + local, key=lambda c: math.hypot(c[0] - tx, c[1] - ty)):
            if not (lo_x <= x <= hi_x and lo_y <= y <= hi_y):
                continue
            if any(x0 - 3 <= x <= x1 + 3 and y0 - 3 <= y <= y1 + 3 for x0, y0, x1, y1 in avoid):
                continue
            if clear_top and t and clearance(x, y, t) < clear_top:
                continue
            if bt and clearance(x, y, bt) < clear_bottom:
                continue
            chosen.append((round(x, 3), round(y, 3)))
            break
        else:
            print(f"no spot near ({tx:.0f}, {ty:.0f})")
    return chosen


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    data = json.loads(src.read_text())
    b = Builder()
    signals = {str(p["pad"]): p["net"] for p in data["matrix"]["row_pins"] + data["matrix"]["col_pins"]}

    for i, k in enumerate(data["keys"], start=1):
        sw_net = f"SW{i}_D"
        # 長いキーはスイッチを複数並列につなぐ。ダイオードは 1 キー 1 個で、先頭のスイッチの横に置く
        for j, (dx, dy) in enumerate(k["switches"]):
            b.place(load(LOCAL_LIB, "SW_Hotswap_Kailh_Choc_V1V2"),
                    f"SW{i}" if j == 0 else f"SW{i}_{j + 1}", k["x_mm"] + dx, k["y_mm"] + dy,
                    pads={"1": f"COL{k['col']}", "2": sw_net})
        x, y = k["x_mm"] + k["switches"][0][0], k["y_mm"] + k["switches"][0][1]
        d = load(STOCK_LIB / "Diode_SMD.pretty", "D_SOD-123")
        dx, dy = DIODE_OFFSET_MM
        # col2row: スイッチ → アノード(2) → カソード(1) → 行
        d = b.place(d, f"D{i}", x + dx, y + dy, back=True,
                    pads={"1": f"ROW{k['row']}", "2": sw_net})
        p1, p2 = (next(p for p in d.Pads() if p.GetNumber() == n) for n in ("1", "2"))
        if p2.GetPosition().x < p1.GetPosition().x:  # アノードをソケット側（右）に向ける
            d.SetOrientationDegrees(d.GetOrientationDegrees() + 180)

    width = data["size_mm"][0]
    height = data["size_mm"][1]
    strip_y = -TOP_STRIP_MM / 2

    # XIAO: 上帯の右端、USB-C を右向き（基板の右辺）に。アンテナ側は内側
    mcu_x = width + EDGE_MARGIN_MM - XIAO_USB_MM
    b.place(load(LOCAL_LIB, "XIAO-nRF52840-Plus-SMD"), "U1", mcu_x, strip_y, pads={**signals, **XIAO_POWER})
    # アンテナ部の直下（端子列の間）と、モジュールの端から先 7 mm の帯全高を両面とも配線禁止にする
    end = mcu_x - XIAO_LEN_MM / 2
    b.keepout([(end, strip_y - 6.3, mcu_x - XIAO_ANTENNA_MM, strip_y + 6.3),
               (end - 7.0, -TOP_STRIP_MM, end, 0.0)])
    # モジュールの裏には露出したパッド（中央付近）があるので、その下の表面には配線を通さない。
    # 端子列のすぐ内側は空けておき、端子から短く引いてビアで裏面へ逃がせるようにする
    b.keepout([(end, strip_y - 5.0, mcu_x + XIAO_LEN_MM / 2, strip_y + 5.0)], cu=(pcbnew.F_Cu,), vias=False)
    # リセットボタンは XIAO 上のものを、上帯カバーの穴から押す

    # 電池は上帯の下に置くので、背の低い横向きのコネクタ（高さ 約 4.8 mm）を裏面に
    b.place(load(STOCK_LIB / "Connector_JST.pretty", "JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal"), "J_BAT",
            width - BAT_CONNECTOR_FROM_RIGHT_MM, strip_y - 3.0, back=True, pads={"1": "BAT+", "2": "GND"})

    antenna = (end - 7.0, -TOP_STRIP_MM, mcu_x - XIAO_ANTENNA_MM, 0.0)
    targets = [(width * fx, height * fy) for fx, fy in MOUNT_TARGETS]
    holes = find_spots(b, data["keys"], targets, MOUNT_CLEAR_TOP_MM, MOUNT_CLEAR_BOTTOM_MM, [antenna], width, height)
    foot_l = FOOT_FROM_CASE_EDGE_MM - CASE_OUTSIDE_PCB_MM
    foot_r = width + CASE_OUTSIDE_PCB_MM - FOOT_FROM_CASE_EDGE_MM
    cover_xs = [foot_l + (foot_r - foot_l) * k / 4 for k in (1, 2, 3)]
    covers = find_spots(b, data["keys"], [(x, strip_y) for x in cover_xs],
                        COVER_CLEAR_TOP_MM, MOUNT_CLEAR_BOTTOM_MM, [antenna], width, height)
    supports = find_spots(b, data["keys"], [(width * fx, height * fy) for fx, fy in SUPPORT_TARGETS],
                          None, SUPPORT_CLEAR_BOTTOM_MM, [antenna], width, height)
    for n, (x, y) in enumerate(holes + covers, start=1):
        b.place(load(STOCK_LIB / "MountingHole.pretty", "MountingHole_2.2mm_M2_ISO14580"), f"H{n}", x, y)
    # ネジ頭・ケースの支柱・カバーの柱が当たる所に配線を通さない
    r, rc = MOUNT_CLEAR_BOTTOM_MM, COVER_CLEAR_TOP_MM - 0.2
    b.keepout([(x - r, y - r, x + r, y + r) for x, y in holes]
              + [(x - rc, y - rc, x + rc, y + rc) for x, y in covers])

    edges = (-EDGE_MARGIN_MM, -TOP_STRIP_MM, width + EDGE_MARGIN_MM, height + EDGE_MARGIN_MM)
    b.outline(*edges, CORNER_RADIUS_MM)
    b.edge_keepout(*edges, 0.8)

    dst.parent.mkdir(parents=True, exist_ok=True)
    b.board.Save(str(dst))
    # DRC は .kicad_pro の設計ルールを使うため、ここで書き出す（無いと既定値のプロジェクトが作られる）
    ds = b.board.GetDesignSettings()
    dst.with_suffix(".kicad_pro").write_text(json.dumps({
        "meta": {"filename": dst.with_suffix(".kicad_pro").name, "version": 1},
        "board": {"design_settings": {"rules": {
            "min_track_width": pcbnew.ToMM(ds.m_TrackMinWidth),
            "min_clearance": pcbnew.ToMM(ds.m_MinClearance),
            "min_copper_edge_clearance": 0.5,
        }}},
    }, indent=2))
    # ケースの支柱の位置として gen_assembly.py が読む
    dst.with_suffix(".holes.json").write_text(json.dumps(
        [{"x_mm": x, "y_mm": y, "type": "screw"} for x, y in holes]
        + [{"x_mm": x, "y_mm": y, "type": "cover"} for x, y in covers]
        + [{"x_mm": x, "y_mm": y, "type": "support"} for x, y in supports], indent=2))
    print(f"mount: {len(holes)} screws, {len(covers)} cover screws, {len(supports)} supports")
    print(f"wrote {dst}: {len(data['keys'])} keys, {sum(len(k['switches']) for k in data['keys'])} switches, {len(b.nets)} nets")


if __name__ == "__main__":
    main()
