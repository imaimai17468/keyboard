#!/usr/bin/env python3
"""keys.json に電気的マトリクス（行・列）と XIAO nRF52840 Plus のピン割り当てを付与し matrix.json を出力する。

案 C（81 キー）を XIAO nRF52840 Plus の 18 本の GPIO で読むため 9×9 にする。
- 物理行 r の左から 9 キー (idx 0-8) → 行 R{r}, 列 C{idx}
- 各物理行の 10 キー目以降 (計 27 キー) → 読み順に R6/R7/R8 × C0-C8
ダイオードは col2row（スイッチ → ダイオード → 行）。

usage: python3 scripts/matrix.py build/option-c/keys.json build/option-c/matrix.json
"""
import json
import sys
from pathlib import Path

LEFT_COLS = 9
N = 9

# XIAO nRF52840 Plus の端子: 名前 → (nRF52840 のピン, フットプリントのパッド番号)。
# Seeed の Arduino variant (Seeed_XIAO_nRF52840_Plus/variant.cpp) とシンボルのピン番号から。
# D16 (P0.31) は電池電圧の測定につながっているので使わない
XIAO = {"D0": ("P0.02", 1), "D1": ("P0.03", 2), "D2": ("P0.28", 3), "D3": ("P0.29", 4),
        "D4": ("P0.04", 5), "D5": ("P0.05", 6), "D6": ("P1.11", 7), "D7": ("P1.12", 8),
        "D8": ("P1.13", 9), "D9": ("P1.14", 10), "D10": ("P1.15", 11),
        "D11": ("P0.15", 15), "D12": ("P0.19", 16), "D13": ("P1.01", 17), "D14": ("P0.09", 18),
        "D15": ("P0.10", 19), "D17": ("P1.07", 21), "D18": ("P1.05", 22), "D19": ("P1.03", 23)}
ROW_PINS = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D11", "D12"]   # 片側の縁と追加パッド
COL_PINS = ["D7", "D8", "D9", "D10", "D13", "D14", "D15", "D17", "D18"]  # もう片側の縁と追加パッド
# D19 は予備。D17 と D19 は公式の図で取り違えの報告があるので、実機で確かめる


def physical_rows(keys):
    """y 座標で物理行に分け、各行を x 順に並べる（ISO Enter は上の行に属する）。"""
    rows = {}
    for k in keys:
        top = k["y_mm"] - k["h_u"] * 19.05 / 2
        rows.setdefault(round(top / 19.05), []).append(k)
    return [sorted(rows[r], key=lambda k: k["x_mm"]) for r in sorted(rows)]


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    data = json.loads(src.read_text())
    rows = physical_rows(data["keys"])
    extra = []
    for r, row in enumerate(rows):
        for idx, k in enumerate(row):
            k["phys_row"], k["phys_idx"] = r, idx
            if idx < LEFT_COLS:
                k["row"], k["col"] = r, idx
            else:
                extra.append(k)
    first_extra_row = len(rows)
    for i, k in enumerate(extra):
        k["row"], k["col"] = first_extra_row + i // N, i % N

    used = {(k["row"], k["col"]) for k in data["keys"]}
    assert len(used) == len(data["keys"]), "マトリクス位置が重複している"
    assert max(k["row"] for k in data["keys"]) < N and max(k["col"] for k in data["keys"]) < N

    data["matrix"] = {
        "rows": N, "cols": N, "diode_direction": "col2row",
        "row_pins": [{"net": f"ROW{i}", "pin": p, "nrf": XIAO[p][0], "pad": XIAO[p][1]} for i, p in enumerate(ROW_PINS)],
        "col_pins": [{"net": f"COL{i}", "pin": p, "nrf": XIAO[p][0], "pad": XIAO[p][1]} for i, p in enumerate(COL_PINS)],
    }
    dst.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    grid = [["・"] * N for _ in range(N)]
    for k in data["keys"]:
        grid[k["row"]][k["col"]] = k["label"]
    for i, g in enumerate(grid):
        print(f"R{i}: " + " | ".join(f"{x:>4}" for x in g))


if __name__ == "__main__":
    main()
