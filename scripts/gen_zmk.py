#!/usr/bin/env python3
"""matrix.json から ZMK のシールド定義（overlay / keymap など）を生成する。

キーの並びは物理的な読み順（phys_row, phys_idx）で、matrix-transform・physical-layout・
keymap の 3 つをこの順に揃えて出力する。

usage: python3 scripts/gen_zmk.py build/option-c/matrix.json firmware/boards/shields/macjis
"""
import json
import sys
from pathlib import Path

SHIELD = "macjis"
PITCH = 19.05

# 物理行ごとの (刻印, MAC_BASE, FN)。刻印は matrix.json と一致するか検査する。
# FN の "___" は &trans。MacBook と同じく F 列は通常メディアキー、fn+F 列で F1-F12。
KEYMAP = [
    [("esc", "&kp ESC", "&soft_off_hold"),  # fn+esc 長押しで電源オフ（どのキーでも復帰）
     ("F1", "&kp C_BRI_DN", "&kp F1"),
     ("F2", "&kp C_BRI_UP", "&kp F2"),
     ("F3", "&kp C_AC_DESKTOP_SHOW_ALL_WINDOWS", "&kp F3"),
     ("F4", "&kp C_AC_DESKTOP_SHOW_ALL_APPLICATIONS", "&kp F4"),
     ("F5", "&kp F5", "&kp F5"),
     ("F6", "&kp F6", "&kp F6"),
     ("F7", "&kp C_PREV", "&kp F7"),
     ("F8", "&kp C_PP", "&kp F8"),
     ("F9", "&kp C_NEXT", "&kp F9"),
     ("F10", "&kp C_MUTE", "&kp F10"),
     ("F11", "&kp C_VOL_DN", "&kp F11"),
     ("F12", "&kp C_VOL_UP", "&kp F12"),
     ("lock", "&kp LC(LG(Q))", "&bootloader"),  # 画面ロック / fn: 書き込みモード
     ("light", "&bt BT_NXT", "___")],
    [("半角", "&kp GRAVE", "___"),
     ("1", "&kp N1", "&bt BT_SEL 0"),
     ("2", "&kp N2", "&bt BT_SEL 1"),
     ("3", "&kp N3", "&bt BT_SEL 2"),
     ("4", "&kp N4", "&bt BT_CLR"),
     ("5", "&kp N5", "&out OUT_TOG"),
     ("6", "&kp N6", "___"),
     ("7", "&kp N7", "___"),
     ("8", "&kp N8", "___"),
     ("9", "&kp N9", "___"),
     ("0", "&kp N0", "___"),
     ("-", "&kp MINUS", "___"),
     ("^", "&kp EQUAL", "___"),
     ("¥", "&kp INT_YEN", "___"),
     ("bs", "&kp BSPC", "&kp DEL")],
    [("tab", "&kp TAB", "___"),
     ("Q", "&kp Q", "___"),
     ("W", "&kp W", "___"),
     ("E", "&kp E", "___"),
     ("R", "&kp R", "___"),
     ("T", "&kp T", "___"),
     ("Y", "&kp Y", "___"),
     ("U", "&kp U", "___"),
     ("I", "&kp I", "___"),
     ("O", "&kp O", "___"),
     ("P", "&kp P", "___"),
     ("@", "&kp LBKT", "___"),
     ("[", "&kp RBKT", "___"),
     ("enter", "&kp ENTER", "___")],
    [("ctrl", "&kp LCTRL", "___"),
     ("A", "&kp A", "___"),
     ("S", "&kp S", "___"),
     ("D", "&kp D", "___"),
     ("F", "&kp F", "___"),
     ("G", "&kp G", "___"),
     ("H", "&kp H", "___"),
     ("J", "&kp J", "___"),
     ("K", "&kp K", "___"),
     ("L", "&kp L", "___"),
     (";", "&kp SEMI", "___"),
     (":", "&kp SQT", "___"),
     ("]", "&kp NUHS", "___")],
    [("shift", "&kp LSHFT", "___"),
     ("Z", "&kp Z", "___"),
     ("X", "&kp X", "___"),
     ("C", "&kp C", "___"),
     ("V", "&kp V", "___"),
     ("B", "&kp B", "___"),
     ("N", "&kp N", "___"),
     ("M", "&kp M", "___"),
     (",", "&kp COMMA", "___"),
     (".", "&kp DOT", "___"),
     ("/", "&kp FSLH", "___"),
     ("_", "&kp INT_RO", "___"),
     ("shift", "&kp RSHFT", "___")],
    [("fn", "&mo FN", "___"),
     ("opt", "&kp LALT", "___"),
     ("cmd", "&kp LCMD", "___"),
     ("英数", "&kp LANG2", "___"),
     ("space", "&kp SPACE", "___"),
     ("かな", "&kp LANG1", "___"),
     ("cmd", "&kp RCMD", "___"),
     ("←", "&kp LEFT", "&kp HOME"),
     ("↑", "&kp UP", "&kp PG_UP"),
     ("↓", "&kp DOWN", "&kp PG_DN"),
     ("→", "&kp RIGHT", "&kp END")],
]


def load_keys(path):
    keys = json.loads(Path(path).read_text())["keys"]
    keys.sort(key=lambda k: (k["phys_row"], k["phys_idx"]))
    return keys


def check_keymap(keys):
    flat = [entry for row in KEYMAP for entry in row]
    assert len(flat) == len(keys), f"keymap {len(flat)} 個 / matrix {len(keys)} 個"
    for k, (label, _, _) in zip(keys, flat):
        assert k["label"] == label, f"{k['label']} != {label} (row {k['phys_row']})"
    return flat


def physical_attrs(k):
    # centi-keyunit、x/y はキー左上
    w, h = round(k["w_u"] * 100), round(k["h_u"] * 100)
    x = round(k["x_mm"] / PITCH * 100 - w / 2)
    y = round(k["y_mm"] / PITCH * 100 - h / 2)
    return f"<&key_physical_attrs {w:>3} {h:>3} {x:>4} {y:>3} 0 0 0>"


def by_rows(keys, fmt, sep=" "):
    lines = []
    for r in sorted({k["phys_row"] for k in keys}):
        lines.append(sep.join(fmt(k) for k in keys if k["phys_row"] == r))
    return lines


def overlay(keys, matrix):
    def gpio(p):  # "P1.07" → "&gpio1 7"（追加パッドの D11〜D19 は xiao_d に無いので nRF のピンで書く）
        port, pin = p["nrf"][1:].split(".")
        return f"&gpio{port} {int(pin)}"

    rows = "\n            , ".join(
        f"<{gpio(p)} (GPIO_ACTIVE_HIGH | GPIO_PULL_DOWN)>  /* {p['net']} = {p['pin']} */"
        for p in matrix["row_pins"])
    cols = "\n            , ".join(
        f"<{gpio(p)} GPIO_ACTIVE_HIGH>  /* {p['net']} = {p['pin']} */"
        for p in matrix["col_pins"])
    rc = "\n".join(by_rows(keys, lambda k: f"RC({k['row']},{k['col']})"))
    attrs = "\n            , ".join(physical_attrs(k) + f"  /* {k['label']} */" for k in keys)
    return f"""/* scripts/gen_zmk.py で生成。直接編集しない */

#include <dt-bindings/zmk/matrix_transform.h>
#include <physical_layouts.dtsi>

/ {{
    chosen {{
        zmk,kscan = &kscan0;
        zmk,physical-layout = &{SHIELD}_layout;
    }};

    kscan0: kscan {{
        compatible = "zmk,kscan-gpio-matrix";
        wakeup-source;
        diode-direction = "{matrix['diode_direction']}";

        row-gpios
            = {rows}
            ;
        col-gpios
            = {cols}
            ;
    }};

    default_transform: keymap_transform_0 {{
        compatible = "zmk,matrix-transform";
        rows = <{matrix['rows']}>;
        columns = <{matrix['cols']}>;
        map = <
{rc}
        >;
    }};

    {SHIELD}_layout: {SHIELD}_layout {{
        compatible = "zmk,physical-layout";
        display-name = "MacBook JIS 75%";
        transform = <&default_transform>;

        keys  //                     w   h    x   y  rot rx ry
            = {attrs}
            ;
    }};
}};

/ {{
    /* 電源スイッチは無い。&soft_off で切り、キーを押すと復帰する（kscan を復帰元にする） */
    soft_off_wakers {{
        compatible = "zmk,soft-off-wakeup-sources";
        wakeup-sources = <&kscan0>;
    }};

}};

/* 状態ランプは XIAO の 3 色 LED。zmk-rgbled-widget の rgbled_adapter シールドが割り当てる
   （build.yaml で shield に一緒に指定する） */

/* D14 (P0.09) / D15 (P0.10) は NFC 端子なので GPIO として使う設定にする */
&uicr {{
    nfct-pins-as-gpios;
}};
"""


def keymap(keys, flat):
    def layer(name, idx):
        rows, i = [], 0
        for r in sorted({k["phys_row"] for k in keys}):
            n = sum(1 for k in keys if k["phys_row"] == r)
            cells = [flat[j][idx] for j in range(i, i + n)]
            rows.append("  ".join("&trans" if c == "___" else c for c in cells))
            i += n
        body = "\n".join(f"                {line}" for line in rows)
        return f"""        {name.lower()}_layer {{
            display-name = "{name}";
            bindings = <
{body}
            >;
        }};"""

    return f"""/* scripts/gen_zmk.py で生成。直接編集しない */

#include <behaviors.dtsi>
#include <dt-bindings/zmk/keys.h>
#include <dt-bindings/zmk/bt.h>
#include <dt-bindings/zmk/outputs.h>

#define FN 1

/ {{
    behaviors {{
        soft_off_hold: soft_off_hold {{
            compatible = "zmk,behavior-soft-off";
            #binding-cells = <0>;
            hold-time-ms = <1000>;  /* 誤って切らないよう 1 秒押し続けたときだけ */
        }};
    }};

    keymap {{
        compatible = "zmk,keymap";

{layer("MAC_BASE", 1)}

{layer("FN", 2)}
    }};
}};
"""


def main():
    src, out = sys.argv[1], Path(sys.argv[2])
    keys = load_keys(src)
    matrix = json.loads(Path(src).read_text())["matrix"]
    flat = check_keymap(keys)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{SHIELD}.overlay").write_text(overlay(keys, matrix))
    (out / f"{SHIELD}.keymap").write_text(keymap(keys, flat))
    print(f"{out}: {len(keys)} keys, {matrix['rows']}x{matrix['cols']} matrix")


if __name__ == "__main__":
    main()
