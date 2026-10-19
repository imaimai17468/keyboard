#!/bin/sh
# 配列 → マトリクス → 基板生成 → 自動配線 → DRC → JLCPCB 用ガーバー zip → 完成図・ケースを一括で行う
set -eu
cd "$(dirname "$0")/.."
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
NAME=option-c
PCB=pcb/macjis.kicad_pcb
OUT=build/pcb

python3 -I scripts/layout.py "layout/$NAME.kle.json" "build/$NAME"
python3 -I scripts/matrix.py "build/$NAME/keys.json" "build/$NAME/matrix.json" >/dev/null
scripts/kicad_python.sh scripts/gen_pcb.py "build/$NAME/matrix.json" "$PCB" 2>&1 | grep -v stdpbase
scripts/kicad_python.sh scripts/route.py "$PCB" > "$OUT/route.log" 2>&1 || { tail -20 "$OUT/route.log"; exit 1; }
grep -E '^routed' "$OUT/route.log"

mkdir -p "$OUT/gerber"
$K pcb drc --format json --severity-error -o "$OUT/drc.json" "$PCB" | tail -2
rm -f "$OUT"/gerber/*
$K pcb export gerbers --layers F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
  --subtract-soldermask --no-x2 -o "$OUT/gerber" "$PCB" >/dev/null
$K pcb export drill --format excellon --excellon-separate-th --generate-map --map-format gerberx2 \
  -o "$OUT/gerber/" "$PCB" >/dev/null
(cd "$OUT/gerber" && zip -q -r ../macjis-gerber.zip .)
echo "gerber: $OUT/macjis-gerber.zip"

# 完成図とケース（基板のネジ位置を使う）
.venv/bin/python scripts/gen_assembly.py "build/$NAME/matrix.json" "$PCB" build/assembly/models \
  2>&1 | grep -E '^(mount|case):'
