#!/bin/sh
# layout/*.kle.json から build/<name>/{keys.json,layout.svg,layout.png} を生成する
set -eu
cd "$(dirname "$0")/.."
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

for src in layout/*.kle.json; do
  name=$(basename "$src" .kle.json)
  out="build/$name"
  python3 -I scripts/layout.py "$src" "$out"
  svg="$out/layout.svg"
  w=$(sed -nE '1s/.*width="([0-9]+)".*/\1/p' "$svg")
  h=$(sed -nE '1s/.*height="([0-9]+)".*/\1/p' "$svg")
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size="$w,$h" \
    --screenshot="$PWD/$out/layout.png" "file://$PWD/$svg" >/dev/null 2>&1
done
