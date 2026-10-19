#!/usr/bin/env python3
"""Freerouting で自動配線する。DSN 書き出し → Freerouting → SES 読み込み → 保存。

usage: scripts/kicad_python.sh scripts/route.py pcb/macjis.kicad_pcb [passes]
"""
import subprocess
import sys
from pathlib import Path

import pcbnew

JAVA = "/opt/homebrew/opt/openjdk/bin/java"
FREEROUTING = Path.home() / ".local/share/freerouting/freerouting-2.5.0.jar"
ROUTE_MARGIN_MM = 0.05  # 細った配線 (最小 0.1 mm) を 0.2 mm に戻しても間隔を守れる余裕


def main():
    pcb = Path(sys.argv[1]).resolve()
    passes = sys.argv[2] if len(sys.argv) > 2 else "100"
    work = pcb.parent.parent / "build/pcb"
    work.mkdir(parents=True, exist_ok=True)
    dsn, ses = work / f"{pcb.stem}.dsn", work / f"{pcb.stem}.ses"

    board = pcbnew.LoadBoard(str(pcb))
    if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
        raise SystemExit("DSN export failed")
    # Freerouting は混んだ箇所で配線を細らせる。後で最小幅に戻せるよう、配線時だけ間隔に余裕を持たせる
    rule = pcbnew.ToMM(board.GetDesignSettings().m_MinClearance)
    text = dsn.read_text()
    old_rule = f"(clearance {round(rule * 1000)})"
    if old_rule not in text:
        raise SystemExit(f"{old_rule} not found in DSN")
    dsn.write_text(text.replace(old_rule, f"(clearance {round((rule + ROUTE_MARGIN_MM) * 1000)})"))
    ses.unlink(missing_ok=True)
    subprocess.run([JAVA, "-jar", str(FREEROUTING), "-de", str(dsn), "-do", str(ses),
                    "-mp", passes, "--gui.enabled=false"], check=True)
    if not ses.exists():
        raise SystemExit("Freerouting did not produce a session file")
    if not pcbnew.ImportSpecctraSES(board, str(ses)):
        raise SystemExit("SES import failed")
    min_width = board.GetDesignSettings().m_TrackMinWidth
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < min_width:
            t.SetWidth(min_width)
    board.Save(str(pcb))
    print(f"routed {pcb}")


if __name__ == "__main__":
    main()
