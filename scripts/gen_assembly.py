#!/usr/bin/env python3
"""完成図用の 3D モデル（ケース・基板・スイッチ・キーキャップ）を部品の種類ごとに glTF (JSON) で書き出す。

  .venv/bin/python scripts/gen_assembly.py build/option-c/matrix.json pcb/macjis.kicad_pcb build/assembly/models

基板は KiCad の 3D 書き出し（配線・パッド・シルク・部品入り）をそのまま使う。ネジ位置は gen_pcb.py が書く
pcb/macjis.holes.json から読む。容量を減らすため gltf-transform（npx で取得）で頂点を量子化する。

完成図のビューア scripts/assembly_viewer.html を出力先の親フォルダに index.html として置く（models/*.json を読む。Artifact で GLB を配信できないため glTF の JSON にし、ビューア側で GLB に組み直す）。

ケースは仮の形（アルミ一体のトレイ + 上帯の樹脂カバー）。座標: x 右、y 上（keys.json の y を反転）、z 上、
基板の上面が z = 0、単位 mm。
"""
import base64
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from build123d import (Align, Axis, Box, BuildPart, BuildSketch, Compound, Cylinder, Location, Locations, Mode,
                       RectangleRounded, export_gltf, export_step, extrude, fillet)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_keycaps as kc  # noqa: E402
import legends as lg  # noqa: E402

TOP_STRIP_MM = 21.0       # gen_pcb.py と同じ
EDGE_MARGIN_MM = 1.0
PCB_T = 1.6
# Choc V1 の簡略形状（基板上面から）
SW_BASE = (15.0, 15.0, 2.2)
SW_TOP = (13.8, 13.8, 2.8)
SW_STEM = (10.0, 4.5, 3.0)
CAP_Z = 8.0 - kc.UNDERSIDE_Z  # キーキャップの軸先端の高さ（スイッチの軸上面 8.0 にキャップ下面が載る）
# ケース
CASE_GAP = 0.5            # 基板とケース内壁の隙間
CASE_WALL = 3.0
CASE_R = 4.0
DECK_Z = 9.0              # ケース上面（キートップは CAP_Z + kc.TOP_Z = 10.0）
COVER_T = 2.0             # 上帯（MCU の上）を覆う樹脂カバーの厚み。細長いので反りにくいよう 2 mm（XIAO の USB-C の上に約 2.6 mm 残る）
INNER_R = 2.5             # 内側の角の丸み（刃物の半径。参考記事では 2.25〜2.5 mm）
# 底は 2 段。キーの下はソケット (1.8 mm) が入るだけの空間にして薄くし、電池は上帯の下の深い所に入れる
FLOOR_T = 2.0
FRONT_GAP = 2.5           # キーの下: 基板の裏から底板まで
BACK_GAP = 5.5            # 上帯の下: 電池 (厚さ 5 mm) と電池コネクタ (高さ 約 4.8 mm)
FLOOR_FRONT = -PCB_T - FRONT_GAP - FLOOR_T  # 底面の高さ（キー側）
FLOOR_BACK = -PCB_T - BACK_GAP - FLOOR_T    # 底面の高さ（上帯側）
# 段の位置（上帯の手前の端からキー側へ 4.5 mm、y 上向き）。上帯の手前の端にある基板のネジ受け（φ4、中心 y ≈ 1）を
# 深い側に丸ごと入れ、段の壁との間に刃物（深さ 16 mm なら φ3.2 程度）が通る 3.4 mm を空ける。
# 段の壁にネジ受けが半分めり込むと、刃物の届かない尖った隅ができる
STEP_Y = -4.5
FOOT_FRONT, FOOT_BACK = 4.0, 2.2  # ゴム足の高さ。手前 φ10 × 4 mm、奥 3M CS-01 (φ7.9 × 2.2 mm)。奥が 1.2 mm 高く、手前に少し傾く
SCREW_BOSS_D = 4.0        # ネジ受けの柱（M2 のめねじ、下穴 φ1.6）。gen_pcb.py の MOUNT_CLEAR_BOTTOM_MM と合わせる
# 基板用のめねじ M2×0.4 6H: 下穴 φ1.6 × 深さ 2.5、有効ねじ長 1.5（参考記事と同じ指定）。
# 止まり穴の底から外側の底面まで 2 mm 以上残すよう JLC から指示がある（キー側の底は 6.1 - 1.6 - 2.5 = 2.0 mm）
TAP_D, TAP_DEPTH, THREAD_LEN = 1.6, 2.5, 1.5
SUPPORT_D = 3.0           # 中央の支え柱。上にカプトンテープを貼って基板を下から支える
RUBBER_T = 0.1            # 支え柱の上に貼るカプトンテープ（基板の裏を傷つけない）
HEAD_D, HEAD_T = 3.8, 1.3  # M2 低頭ネジの頭
COUNTERBORE_D = 4.2       # カバー用ネジ（底から入れる）の頭の逃げ
COVER_POST_D = 6.0        # カバー裏の柱。M2 の熱圧入インサート (φ3.2 × 3 mm) を埋める
INSERT_D, INSERT_DEPTH = 3.2, 4.0
COVER_LEDGE = 1.0         # カバーを載せるケース内壁の段の幅
LED_HOLE_D = 1.5
# XIAO 中心から 3 色 LED とリセットボタンまで（y 上向き）。Seeed の XIAO nRF52840 v1.3 の基板データから
LED_OFFSET = (7.68, -5.71)
RESET_OFFSET = (8.57, 5.72)
USB_OPENING = (11.0, 6.0)  # 右側面の USB-C の穴（幅・高さ）。ケーブルのプラグ外形が通る大きさ
USB_OPENING_R = 1.0        # 穴の角の丸み（横から削る刃物の半径）
KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
GLTF_TRANSFORM = ["npx", "--yes", "@gltf-transform/cli@4.1.1"]
# マイコン（XIAO nRF52840 Plus、基板に直接はんだ付け）と電池の簡略形状
MCU_SIZE = (21.0, 17.8, 1.2)
MCU_Z = 0.0
XIAO_USB_MM = 12.6        # gen_pcb.py と同じ（モジュール中心から USB-C の先端まで）
BATTERY = (30.0, 20.0, 5.0)  # EEMB 502030（厚さ 5 × 幅 20 × 長さ 30 mm、250 mAh）。ネジ受けの柱の間なので長さ 64 mm まで入る
BATTERY_X = 163.0         # 中心の x（カバーのネジ受けの間で、電池コネクタに近い側。アンテナからは離す）
def glb_to_json(glb, dst):
    """GLB をバイナリ埋め込みの glTF (JSON) に変換する。Artifact で .glb を配信できないため。"""
    data = glb.read_bytes()
    n = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + n])
    bin_len = struct.unpack_from("<I", data, 20 + n)[0]
    payload = data[28 + n:28 + n + bin_len]
    gltf["buffers"][0]["uri"] = "data:application/octet-stream;base64," + base64.b64encode(payload).decode()
    dst.write_text(json.dumps(gltf, separators=(",", ":")))


def optimize(glb):
    """重複をまとめ、頂点を量子化して GLB を小さくする（three.js の GLTFLoader がそのまま読める形式）。"""
    tmp = glb.with_name(glb.stem + ".opt.glb")
    subprocess.run(GLTF_TRANSFORM + ["optimize", str(glb), str(tmp), "--compress", "quantize", "--instance", "false",
                                     "--simplify", "false", "--texture-compress", "false",
                                     "--palette", "false"],  # 材質を残す（ビューアで色を変えるため）
                   check=True, capture_output=True)
    tmp.replace(glb)


def kicad_board(pcb, glb):
    """KiCad から基板の 3D モデル（配線・パッド・シルク・ソルダーレジスト・部品）を書き出す。
    原点は KiCad の座標原点で、glTF の座標はこのスクリプトの部品と一致する（基板の下面が 0 なので、ビューアで基板の
    厚みぶん下げる）。"""
    subprocess.run([KICAD_CLI, "pcb", "export", "glb", "-f", "--include-tracks", "--include-pads",
                    "--include-silkscreen", "--include-soldermask", "--user-origin", "0x0mm",
                    "-o", str(glb), str(pcb)], check=True, capture_output=True)


def main():
    data = json.loads(Path(sys.argv[1]).read_text())
    pcb_path = Path(sys.argv[2])
    mounts = json.loads(pcb_path.with_suffix(".holes.json").read_text())
    out = Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    width, height = data["size_mm"]
    x0, x1 = -EDGE_MARGIN_MM, width + EDGE_MARGIN_MM
    y0, y1 = -(height + EDGE_MARGIN_MM), TOP_STRIP_MM   # y 上向き
    mcu_x, strip_y = width + EDGE_MARGIN_MM - XIAO_USB_MM, TOP_STRIP_MM / 2

    screws = [(m["x_mm"], -m["y_mm"]) for m in mounts if m["type"] == "screw"]
    covers = [(m["x_mm"], -m["y_mm"]) for m in mounts if m["type"] == "cover"]
    supports = [(m["x_mm"], -m["y_mm"]) for m in mounts if m["type"] == "support"]
    # 基板のネジは上から、カバーのネジは底から（頭は底面のザグリに収まる）
    heads = [Cylinder(HEAD_D / 2, HEAD_T, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(Location((x, y, 0)))
             for x, y in screws]
    heads += [Cylinder(HEAD_D / 2, HEAD_T, align=(Align.CENTER, Align.CENTER, Align.MIN))
              .moved(Location((x, y, FLOOR_BACK + 0.2))) for x, y in covers]
    # マイコン: 基板に直接載せる。USB-C は右（基板の右辺）向き、その上に無線部のシールド缶
    mcu = [Box(*MCU_SIZE, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(Location((mcu_x, strip_y, MCU_Z))),
           Box(9.0, 9.0, 1.4, align=(Align.CENTER, Align.CENTER, Align.MIN))
           .moved(Location((mcu_x - 2.2, strip_y - 0.6, MCU_Z + MCU_SIZE[2])))]
    usb = [Box(7.4, 9.0, 3.2, align=(Align.MAX, Align.CENTER, Align.MIN))
           .moved(Location((mcu_x + XIAO_USB_MM - 0.5, strip_y, MCU_Z + MCU_SIZE[2])))]
    battery_y = (STEP_Y + TOP_STRIP_MM + CASE_GAP) / 2  # 深い所（段から内壁まで）の中央
    battery = Box(*BATTERY, align=(Align.CENTER, Align.CENTER, Align.MIN)).moved(
        Location((BATTERY_X, battery_y, FLOOR_BACK + FLOOR_T + 0.3)))

    switches, caps, legends = [], [], []
    for k in data["keys"]:
        kx, ky = k["x_mm"], -k["y_mm"]
        for dx, dy in k["switches"]:
            sx, sy = kx + dx, ky - dy
            for (w, h, t), z in ((SW_BASE, 0.0), (SW_TOP, SW_BASE[2]), (SW_STEM, SW_BASE[2] + SW_TOP[2])):
                switches.append(Box(w, h, t, align=(Align.CENTER, Align.CENTER, Align.MIN))
                                .moved(Location((sx, sy, z))))
        cap, mark = kc.keycap(k["rects"], k["switches"], lg.legend(k, width), engrave=False)
        caps.append(cap.moved(Location((kx, ky, CAP_Z))))
        if mark is not None:
            legends.append(mark.moved(Location((kx, ky, CAP_Z + 0.02))))  # 上面と重ならないよう少し浮かせる

    # ケース: 3 軸 CNC で上からだけ削れる一体トレイ（参考: note.com/copkbd/n/n7063aaa7e778）。
    # 上帯は樹脂のカバーで覆い、そのままアンテナ窓にする。側面の穴は右の USB-C だけ（横から加工）
    ox0, ox1 = x0 - CASE_GAP - CASE_WALL, x1 + CASE_GAP + CASE_WALL
    oy0, oy1 = y0 - CASE_GAP - CASE_WALL, y1 + CASE_GAP + CASE_WALL
    ix0, ix1, iy0, iy1 = x0 - CASE_GAP, x1 + CASE_GAP, y0 - CASE_GAP, y1 + CASE_GAP
    cover_y0 = 0.3  # カバーの手前の端（最上段のキーキャップとの隙間 約 0.8 mm）
    with BuildPart() as case:
        # 外形: 全体をキー側の厚さで作り、上帯の下だけ下に張り出させる（裏面も削るので 2 工程）
        with BuildSketch(Location(((ox0 + ox1) / 2, (oy0 + oy1) / 2, FLOOR_FRONT))):
            RectangleRounded(ox1 - ox0, oy1 - oy0, CASE_R)
        extrude(amount=DECK_Z - FLOOR_FRONT)
        by0 = STEP_Y - CASE_WALL
        with BuildSketch(Location(((ox0 + ox1) / 2, (by0 + oy1) / 2, FLOOR_BACK))):
            RectangleRounded(ox1 - ox0, oy1 - by0, CASE_R)
        extrude(amount=FLOOR_FRONT - FLOOR_BACK)  # 本体と重ねると角の丸みの境で細い破片ができる
        with BuildSketch(Location(((ix0 + ix1) / 2, (iy0 + iy1) / 2, FLOOR_FRONT + FLOOR_T))):
            RectangleRounded(ix1 - ix0, iy1 - iy0, INNER_R)
        extrude(amount=DECK_Z - FLOOR_FRONT, mode=Mode.SUBTRACT)
        with BuildSketch(Location(((ix0 + ix1) / 2, (STEP_Y + iy1) / 2, FLOOR_BACK + FLOOR_T))):
            RectangleRounded(ix1 - ix0, iy1 - STEP_Y, INNER_R)
        extrude(amount=FLOOR_FRONT - FLOOR_BACK + 1, mode=Mode.SUBTRACT)
        # 底からの柱: ネジ受け（めねじ付き、基板の裏まで）と中央の支え（ゴム足の分だけ低い）
        floor_top = lambda y: (FLOOR_BACK if y > STEP_Y - SCREW_BOSS_D else FLOOR_FRONT) + FLOOR_T
        # カバーを載せる段（上帯の範囲だけ内壁を COVER_LEDGE 広げる）
        with BuildSketch(Location(((ix0 + ix1) / 2, (cover_y0 + iy1 + COVER_LEDGE) / 2, DECK_Z - COVER_T))):
            RectangleRounded(ix1 - ix0 + 2 * COVER_LEDGE, iy1 + COVER_LEDGE - cover_y0, INNER_R)
        extrude(amount=COVER_T + 1, mode=Mode.SUBTRACT)
        for (x, y), d, top in ([(c, SCREW_BOSS_D, -PCB_T) for c in screws + covers]
                               + [(c, SUPPORT_D, -PCB_T - RUBBER_T) for c in supports]):
            with Locations((x, y, floor_top(y))):
                Cylinder(d / 2, top - floor_top(y), align=(Align.CENTER, Align.CENTER, Align.MIN))
        for x, y in screws:
            with Locations((x, y, -PCB_T - TAP_DEPTH)):
                Cylinder(TAP_D / 2, TAP_DEPTH, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        for x, y in covers:  # 底から貫通（頭はザグリに沈める）
            with Locations((x, y, FLOOR_BACK - 1)):
                Cylinder(1.2, 20, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
                Cylinder(COUNTERBORE_D / 2, 1 + HEAD_T + 0.2, align=(Align.CENTER, Align.CENTER, Align.MIN),
                         mode=Mode.SUBTRACT)
        usb_z = MCU_Z + MCU_SIZE[2] + 1.6
        with Locations((ix1 + CASE_WALL / 2, strip_y, usb_z)):
            Box(CASE_WALL + 1, *USB_OPENING, mode=Mode.SUBTRACT)
        usb_edges = case.edges().filter_by(Axis.X).filter_by(
            lambda e: abs(e.center().X - (ix1 + CASE_WALL / 2)) < CASE_WALL / 2 + 0.01
            and abs(e.center().Y - strip_y) <= USB_OPENING[0] / 2 + 0.01
            and abs(e.center().Z - usb_z) <= USB_OPENING[1] / 2 + 0.01)
        fillet(usb_edges, USB_OPENING_R)
    cover_z = DECK_Z - COVER_T
    led = (mcu_x + LED_OFFSET[0], strip_y + LED_OFFSET[1])
    reset = (mcu_x + RESET_OFFSET[0], strip_y + RESET_OFFSET[1])
    with BuildPart() as cover:
        with BuildSketch(Location(((ix0 + ix1) / 2, (cover_y0 + iy1 + COVER_LEDGE) / 2, cover_z))):
            RectangleRounded(ix1 - ix0 + 2 * COVER_LEDGE - 0.2, iy1 + COVER_LEDGE - cover_y0 - 0.1, INNER_R)
        extrude(amount=COVER_T)
        for x, y in covers:  # 裏の柱（基板の上面まで）とインサートの穴
            with Locations((x, y, 0)):
                Cylinder(COVER_POST_D / 2, cover_z, align=(Align.CENTER, Align.CENTER, Align.MIN))
            with Locations((x, y, 0)):
                Cylinder(INSERT_D / 2, INSERT_DEPTH, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        with Locations((*reset, cover_z)):  # XIAO のリセットボタンを細い棒で押す穴
            Cylinder(1.0, COVER_T * 3, mode=Mode.SUBTRACT)
        with Locations((*led, cover_z)):  # 状態ランプの光が見える穴
            Cylinder(LED_HOLE_D / 2, COVER_T * 3, mode=Mode.SUBTRACT)

    # ゴム足: 手前 2 つ（φ10）はキー側の底に、奥 2 つ（φ7.9）は上帯の張り出しの底に
    feet = [Cylinder(r, h, align=(Align.CENTER, Align.CENTER, Align.MAX)).moved(Location((x, y, z)))
            for x in (ox0 + 20, ox1 - 20)
            for y, z, h, r in ((oy0 + 12, FLOOR_FRONT, FOOT_FRONT, 5.0), (oy1 - 10, FLOOR_BACK, FOOT_BACK, 3.95))]
    groups = {"feet": feet, "case": [case.part], "cover": [cover.part], "mcu": mcu, "usb": usb, "battery": [battery],
              "switches": switches, "keycaps": caps, "legends": legends, "screws": heads}
    # JLCCNC / JLC3DP に出すケースとカバー
    export_step(case.part, str(out.parent / "case.step"))
    export_step(cover.part, str(out.parent / "cover.step"))
    # JLCCNC に付ける図面用（scripts/gen_drawing.py）。原点はケース外形の左下、y 上向き
    (out.parent / "case_features.json").write_text(json.dumps({
        "size": [ox1 - ox0, oy1 - oy0], "corner_r": CASE_R,
        "height": DECK_Z - FLOOR_BACK, "height_front": DECK_Z - FLOOR_FRONT,
        "inner": [ix0 - ox0, iy0 - oy0, ix1 - ox0, iy1 - oy0], "inner_r": INNER_R,
        "step_y": STEP_Y - CASE_WALL - oy0, "floor_t": FLOOR_T,
        "tapped": [[x - ox0, y - oy0] for x, y in screws],
        "tap": {"thread": "M2x0.4-6H", "thread_len": THREAD_LEN, "drill_d": TAP_D, "drill_depth": TAP_DEPTH,
                "boss_d": SCREW_BOSS_D, "boss_top_from_deck": DECK_Z + PCB_T},
        "through": [[x - ox0, y - oy0] for x, y in covers],
        "counterbore": {"d": COUNTERBORE_D, "depth": HEAD_T + 0.2, "hole_d": 2.4},
        "usb": {"w": USB_OPENING[0], "h": USB_OPENING[1], "r": USB_OPENING_R, "y": strip_y - oy0,
                "z_from_bottom": MCU_Z + MCU_SIZE[2] + 1.6 - FLOOR_BACK},
    }, indent=1))
    for name in ["board", *groups]:
        glb = out / f"{name}.glb"
        if name == "board":
            kicad_board(pcb_path, glb)
        else:
            export_gltf(Compound(groups[name]), str(glb), binary=True, linear_deflection=0.08, angular_deflection=0.4)
        optimize(glb)
        glb_to_json(glb, glb.with_suffix(".json"))
        glb.unlink()
        print(f"{name}: {glb.with_suffix('.json').stat().st_size // 1024} KB")
    # ビューアのラベル。位置は glTF の座標（m、y 上向き、z = keys.json の y）で、所属する部品と一緒に動く
    space = next(k for k in data["keys"] if k["label"] == "space")
    sx, sy = screws[0]
    labels = [
        ("mcu", "XIAO nRF52840 Plus（無線マイコン）", mcu_x - 2.2, strip_y, MCU_Z + MCU_SIZE[2] + 1.4),
        ("usb", "USB-C（充電・書き込み）", mcu_x + XIAO_USB_MM - 2.0, strip_y, MCU_Z + 4.4),
        ("board", "アンテナ部（配線禁止）", mcu_x - MCU_SIZE[0] / 2 - 3.0, strip_y, 0.0),
        ("cover", "状態ランプ（電源・接続・電池）", led[0], led[1], DECK_Z),
        ("screws", f"カバーを留めるネジ ×{len(covers)}（底から）", covers[-1][0], covers[-1][1], FLOOR_BACK),
        ("cover", "リセット（穴から押す）", reset[0], reset[1], DECK_Z),
        ("board", "電池コネクタ（裏）", width - 96.0, strip_y, -PCB_T),  # gen_pcb.py の BAT_CONNECTOR_FROM_RIGHT_MM
        ("battery", "LiPo 電池（上帯の下）", BATTERY_X, battery_y, FLOOR_BACK + FLOOR_T + BATTERY[2]),
        ("screws", f"M2 ネジ ×{len(screws)}", sx, sy, HEAD_T),
        ("case", f"中央の支え ×{len(supports)}", supports[0][0], supports[0][1], -PCB_T - RUBBER_T),
        ("switches", "Space はスイッチ 3 個", space["x_mm"], -space["y_mm"], 8.0),
    ]
    (out / "labels.json").write_text(json.dumps(
        [{"group": g, "text": t, "pos": [x / 1000, z / 1000, -y / 1000]} for g, t, x, y, z in labels],
        ensure_ascii=False, indent=1))
    shutil.copy(Path(__file__).with_name("assembly_viewer.html"), out.parent / "index.html")
    print(f"mount: {len(screws)} screws, {len(covers)} cover screws, {len(supports)} supports")
    print(f"case: {ox1 - ox0:.1f} × {oy1 - oy0:.1f} mm, 高さ キー側 {DECK_Z - FLOOR_FRONT:.1f} / "
          f"上帯側 {DECK_Z - FLOOR_BACK:.1f} mm (キートップまで {CAP_Z + kc.TOP_Z - FLOOR_FRONT:.1f} mm)")


if __name__ == "__main__":
    main()
