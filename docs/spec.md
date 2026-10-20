# 仕様書（ドラフト）

最終更新: 2026-10-19

## 1. 確定事項

| 項目 | 内容 |
|---|---|
| 配列 | **案 C**: MacBook 風 JIS（15u・81 キー、無線、一体型） |
| スイッチ | Kailh Ambients Silent Choc **V1** Nocturnal（静音リニア 20g、5 ピン）。遊舎工房で 35 個入り ¥5,390 |
| スイッチ固定 | ホットスワップソケット（Kailh Choc 用、V1/V2 共通ピン） |
| 長いキーの支え | スタビライザーは使わず、キーの下にスイッチを複数置いて並列に配線する（Space 3 個、左 Shift・Enter 2 個） |
| キーキャップ | 自作（build123d で設計し JLC3DP で造形）。Choc V1 軸、約 18 mm 角。黒（Black Resin）、刻印は彫り込みのみ（色は入れない）。刻印は MacBook の JIS 配列と同じでかなは無し（`scripts/legends.py`、一覧 `build/keycaps/set/legends.png`） |
| MCU | Seeed Studio XIAO nRF52840 Plus（遊舎工房で購入可。基板に直接はんだ付け）。ZMK のボード名は `seeeduino_xiao_ble` |
| ファームウェア | ZMK |
| 電源 | LiPo バッテリー 250 mAh（EEMB 502030。充電は XIAO 内蔵回路）。電源スイッチは無く、fn+esc 長押しで ZMK の soft off、キーを押すと復帰 |
| その他部品 | 電池の線は基板に直接はんだ付け（JST PH コネクタも付けられる）。リセットボタンと状態ランプ（3 色 LED）は XIAO 上のものを上帯カバーの穴から使う |
| 基板製造 | JLCPCB（2 層 FR-4、ソルダーレジスト黒、部品実装なし。手半田） |
| ケース | アルミ 6061 CNC（JLCCNC）、ビーズブラスト + クリアアルマイト（銀）。上帯は樹脂カバー（JLC3DP Black Resin、キーキャップと同じ。厚さ 2 mm。アンテナ窓を兼ねる） |

## 2. 配列案（C に決定）

キー寸法は K3 Pro JIS（Keychron 公式 VIA 定義 `layout/reference_k3pro_jis_via.json`）を基準にしている。
キーキャップを自作に切り替えたため、今はセットに無いサイズも作れる。

| 案 | 幅 | キー数 | 内容 | プレビュー |
|---|---|---|---|---|
| A | 16u（304.8 mm） | 87 | K3 Pro JIS そのまま。右端に del / pgup / pgdn / home / end の列あり | `build/option-a/layout.png` |
| C | 15u（285.8 mm） | 81 | 右端の列を削除した MacBook 風。下段は fn opt cmd 英数 space かな cmd ←↑↓→、caps 位置は ctrl | `build/option-c/layout.png` |
| C2 | 15u（285.8 mm） | 81 | C と同じ形で、全キーをセットの刻印どおりに使う。下段は ctrl opt cmd 英数 space かな cmd ←↑↓→、fn は 半角/全角 の位置 | `build/option-c2/layout.png` |

- MacBook のような「上下半分の高さの ↑↓」は不可。Choc のスイッチ本体が約 15 mm 角で、半分の高さ（9.5 mm）に 2 個縦に並ばないため。
- 矢印は 4 つ横一列に決定（逆 T 字は右 Shift を細くすれば作れるが採用しない）。
- 案 C の caps 位置は ctrl（刻印も control）。MacBook に無い 3 キーの刻印: 1 の左は「半角」、右上の 2 つは鍵（画面ロック）と Bluetooth（接続先の切り替え）
- 案 C は 16u の下段から fn を 1 つ減らしている。fn は左下に置く。

## 3. マトリクスとピン数

XIAO nRF52840 Plus の GPIO は縁の 11 本（D0〜D10）+ 追加パッド 9 本（D11〜D19）= 20 本。
D16 (P0.31) は電池電圧の測定につながっているので使わず、残り 19 本のうち 18 本で 9×9 を組む（D19 は予備）。

| 案 | キー数 | 物理どおり | 推奨の電気的マトリクス |
|---|---|---|---|
| A | 87 | 6×16 = 22 本（不足） | 8×11 = 88 → 19 本 |
| C | 81 | 6×15 = 21 本（余裕ゼロ） | 9×9 = 81 → 18 本 |

電気的な行列は物理的な行・列と一致しなくてよい。ダイオードは 1 キー 1 個（1N4148W / SOD-123）、col2row。

案 C の割り当て（`scripts/matrix.py`）:
- 各物理行の左から 9 キー → 行 R0〜R5 × 列 C0〜C8
- 各物理行の 10 キー目以降（27 キー）→ 読み順に R6〜R8 × C0〜C8
- 行ピン: D0〜D6, D11, D12
- 列ピン: D7〜D10, D13, D14, D15, D17, D18（D14/D15 は NFC ピンを GPIO として使用）
- ピンの対応は Seeed の Arduino variant（Seeed_XIAO_nRF52840_Plus/variant.cpp）と KiCad シンボルのピン番号から。
  公式 Wiki の図は D17 (P1.07) と D19 (P1.03) が入れ替わっているという報告があるため、実機で確かめる

## 4. 未解決事項（ブロッカー）

1. **キーキャップ軸の嵌合**: 3D プリントの Choc V1 軸が、抜けず割れずに挿さるか。材質（樹脂か MJF ナイロンか）と寸法の公差を試作で決める。
2. **複数スイッチで支える長いキーの感触**: 端を押したときに引っかからないか。バネ荷重はスイッチの数だけ足されるため、Space は約 60 g、左 Shift・Enter は約 40 g で、1u（20 g）より重くなる。

## 5. 購入リスト

- Kailh Ambients Silent Choc V1 Nocturnal 35 個入り ×3（105 個。必要数 85 + 予備）
- XIAO nRF52840 Plus ×1（遊舎工房）— 購入済み (2026-10-20)。予備は必要なら追加
- 本体部品（基板発注時に買う。取り付けは自分ではんだ付け）
  - ダイオード 1N4148W（SOD-123）×81 + 予備: 遊舎工房「ダイオード - SMDタイプ（100個入り）」
  - LiPo 電池: EEMB 502030 250 mAh（Amazon）。コネクタは切って線を基板に直接はんだ付け。毎日 8 時間使って 2 か月前後の見積もり（実機で測る）
  - ホットスワップソケット Kailh CPG135001S30 ×90: 遊舎工房「Kailh Switch Socket」の Choc（10 個入り × 9）
  - ネジ・組み立て部品（Amazon。商品とリンクは完成図の「購入リスト」）
    - M2 × 3 mm ナベ頭ネジ（黒）×7: 基板をケースに留める（めねじは M2×0.4 6H、下穴 2.5 mm・有効ねじ長 1.5 mm。ネジは基板 1.6 + 1.4 mm かかる。JIS のナベ頭は頭 φ3.5 × 1.3 mm で設計の逃げに収まる）
    - M2 × 10 mm ナベ頭ネジ ×3: 底からカバーを留める（頭は底のザグリに沈む。インサートに 2.4 mm かかる）
    - M2 インサート 外径 3 × 長さ 3 mm ×3: カバーの柱の穴 φ3.2 に 5 分硬化エポキシで接着（樹脂のカバーは熱圧入できない）
    - ゴム足: 手前 φ10 × 4 mm ×2、奥 3M CS-01（φ7.9 × 2.2 mm）×2。奥が 1.2 mm 高く手前に少し傾く
    - カプトンテープ（電池の下の絶縁、中央の支え柱の上）、強力両面テープ（電池の固定）

先に試作するもの:
- キーキャップ試作（JLC3DP）: 1u を軸の太さ違いで 3 種類、Space（軸 3 本）を 1 本
- 試作のためにスイッチ 1 袋とソケット数個があれば足りる

## 6. 基板ドラフト v0（2026-10-19）

`scripts/build_pcb.sh` で配列から製造データまで自動生成できる状態。

- 外形: 287.75 × 136.3 mm（キー領域 + 外周 1 mm、上に 21 mm の帯）
- 上帯の右端に XIAO nRF52840 Plus（USB-C は右辺向き、アンテナ側は内側）、その左に電池コネクタ（裏面）。電源スイッチ・リセットスイッチは無し
- XIAO は基板に直接はんだ付け。縁のパッド（2.54 mm ピッチ）は横からはんだごてが当たる。追加パッド D11〜D18（縁のパッドの間、1.27 mm ずれ・パッド間 0.32 mm）は横からだとブリッジしやすいので、使う 7 本に φ0.5 の穴（銅の残り 0.225 mm）を開けて基板の裏からはんだを流す。モジュールの下に隠れる電池パッド (VBAT / GND) にも φ0.7 の穴。使わない D16・D19 は穴なし（裏の配線を通すため）
- アンテナ: XIAO の USB と反対側の端（チップアンテナ）。モジュール中心から 7 mm より先の直下と、端から先 7 mm の帯全高を配線・ビア禁止。モジュールの下の表面は配線禁止（モジュール裏の露出パッドと触れないため）
- スイッチ 85（81 キー。Space に 3 個、左 Shift・Enter に 2 個）、ダイオード 81（裏面）、2 層、Freerouting で全配線済み（所要 約 7〜12 分）
- 配線幅 0.2 mm 以上・間隔 0.2 mm。Freerouting は混んだ箇所で配線を細らせるため、配線時だけ間隔を 0.25 mm にし、読み込み後に 0.2 mm へ戻している
- DRC: エラー 0、未配線 0
- 出力: `pcb/macjis.kicad_pcb`、`build/pcb/macjis-gerber.zip`、配線図 `build/pcb/routed.png`

- ケース固定: M2 低頭ネジ 7 本（キー領域の上端・下端）＋上帯 3 本（底から通し、カバーの柱のインサートに締める）。位置は `gen_pcb.py` が表のネジ頭 φ3.8・裏のネジ受け φ4 が
  部品に当たらない隙間から自動で選び、`pcb/macjis.holes.json` に書き出す。中央は裏の部品が密でネジを通せないため、
  ケース底の柱 φ3（上にカプトンテープ）3 本で下から支える

**このままでは発注しない。** 未対応:
- 1:1 印刷で実物合わせ

## 6.5 ケース案 v0（仮、2026-10-19）

`scripts/gen_assembly.py` で完成図（ケース・基板・スイッチ・キーキャップ）を生成し、`build/assembly/index.html` で 3D 表示する。

- アルミ 6061 一体のトレイ。3 軸 CNC で上からだけ削れる形にする（参考: https://note.com/copkbd/n/n7063aaa7e778）
- 外形 294.8 × 143.3 mm。高さはキー側 15.1 mm（キートップまで 16.1 mm）、上帯側 18.1 mm。壁 3 mm、底 2 mm、内側の角 R2.5
- 底は 2 段: キーの下はソケットが入るだけ（基板の裏から 2.5 mm）、上帯の下だけ 5.5 mm 張り出して電池を入れる。裏面も削るので加工は 2 工程
- ゴム足: 手前 φ10 × 4 mm、奥 φ7.9 × 2.2 mm（3M CS-01）。奥が 1.2 mm 高く、手前に少し傾く
- 上帯（MCU の上）は樹脂のカバーで覆い、アンテナ窓を兼ねる。リセット用の穴あり
- 側面の穴: USB-C（右、11 × 6 mm）だけ。ここだけ横からの加工になる
- 上帯カバー: ケース内壁の段 (1 mm) に載せ、裏の柱 φ6（M2 インサートを接着）3 本を底からのネジで留める。上から見えるネジは無い。XIAO のリセットボタン用の穴 φ2 と状態ランプの穴 φ1.5 あり（位置は Seeed の基板データから。実物で確認する）
- 底からネジ受けの柱（φ4）10 本: 基板用 7 本は M2×0.4 6H めねじ（下穴 2.5 mm・有効 1.5 mm、底面まで 2 mm 残す）、カバー用 3 本は貫通 + 底面にザグリ。支え柱（φ3）3 本
- 奥の面の中央にレーザー刻印: アイコンの線画（assets/icon_frog.png の黒い線を potrace で輪郭にしたもの）と @imaimai17468、約 50.7 × 11.5 mm（`scripts/marking.py`）。形は変えないので STEP には入れず、図面 `build/assembly/case_marking_drawing.pdf` と原寸の線画 `case_marking.svg` で指定する。銀のアルマイトでは刻印は薄い灰色で控えめに出る
- 出力: `build/assembly/case.step`（アルミ）、`build/assembly/cover.step`（樹脂カバー）、`build/assembly/case_drawing.pdf`（JLCCNC に付ける図面。めねじ T1〜T7 と貫通穴 C1〜C3 の位置・仕様、A3・1:1・第三角法。`scripts/gen_drawing.py`）
- JLCCNC の注意（note.com/copkbd/n/n7063aaa7e778）: めねじは 3D データから読まれないので図面で指定する（形状にねじ山は作らない）。止まり穴の底から外側の面まで 2 mm 以上。内側の角は R ≥ 深さ/10 + 0.5（深さ 16.1 mm → R2.11 以上、R2.5 にしている）。バリ取りは図面に C0.2 と書く。刃物（φ3.2 程度）が通らない 3 mm 未満の隙間や、柱が壁に半分めり込んだ尖った隅を作らない（底の段は上帯のネジ受けから 3.4 mm 離す。柱と壁の最小隙間 5.6 mm、柱どうし 8.7 mm）。アルマイトの銀は廃止され Natural を選ぶ
- 電池: 上帯の下、ネジ受けの柱の間。厚さ 5 × 幅 20 × 長さ 64 mm 以内の LiPo。EEMB 502030（5 × 20 × 30 mm、250 mAh）を使う。電池の線は基板の電池コネクタ用の穴に直接はんだ付けする（赤 = 1 番ピン +）。コネクタ (S2B-PH-K) を付ければ取り外し式にもできる
- 表面の仕上げ: ビーズブラスト + クリア（銀）アルマイト。JLCCNC ではアルマイトを選ぶと標準で 120 メッシュのビーズブラストが付く（参考: https://jlccnc.com/help/article/appearance-standard-guidelines ）

## 7. 参照する設計データ

- スイッチフットプリント: perigoso/keyswitch-kicad-library の `SW_Hotswap_Kailh_Choc_V1V2`（MIT / CC-BY-SA 4.0）→ `pcb/lib/keyboard.pretty`
- XIAO nRF52840 Plus: Seeed-Studio/OPL_Kicad_Library の `XIAO-nRF52840-Plus-SMD`（CC-BY-SA 4.0）を、電池パッドと追加パッド（D11〜D15・D17・D18）に穴を開けて改変 → `pcb/lib/keyboard.pretty`
- XIAO のアンテナ・LED・リセットボタンの位置: 同ライブラリの `Seeed Studio XIAO nRF52840 v1.3` 基板データ
- ダイオード・スイッチ類・JST コネクタ: KiCad 標準ライブラリ
- Choc V1 キーキャップ軸の寸法: braindefender/KLP-Lame-Keycaps（CC-BY-SA 4.0）の STEP を実測。
  軸は 2 本、断面 約 1.15 × 2.95 mm、中心間 5.7 mm、長さ 約 3 mm。キーキャップ外形 17.5 × 16.5 mm

## 8. ツールチェーン

| 工程 | ツール |
|---|---|
| 配列 | KLE 形式 JSON（`layout/*.kle.json`）→ `scripts/build_layouts.sh` → `build/<案>/keys.json`（mm 座標）・プレビュー PNG |
| 基板 | KiCad 10（`brew install --cask kicad`）+ Freerouting 2.5（`~/.local/share/freerouting/`、要 `brew install openjdk`）。`scripts/build_pcb.sh` |
| ケース・キーキャップ | build123d（Python、`uv venv .venv` に導入）で STEP / STL 出力 → JLCCNC・JLC3DP |
| ファーム | ZMK v0.3.0 + zmk-rgbled-widget v0.3（ボード `seeeduino_xiao_ble`、シールド `macjis rgbled_adapter`。`firmware/`、`scripts/gen_zmk.py` で overlay / keymap を生成、`.github/workflows/zmk.yml` でビルド）。soft off・状態ランプ込みでローカルビルド確認済み、実機未確認 |

`build/<案>/keys.json` を配列の単一の情報源とし、KiCad の部品配置・ZMK の物理レイアウト・ケース外形はここから生成する。

## 9. 進め方

1. ~~配列案の決定~~（C）
2. キーキャップ試作（JLC3DP）とスイッチ購入 → 軸の公差と長いキーの感触を確認 ← いまここ
3. 基板（KiCad）: ~~自動生成・自動配線・DRC のパイプライン~~ → ネジ穴追加 → 1:1 印刷で実物合わせ → JLCPCB 発注
4. ケース（アンテナ窓・バッテリー・USB-C 開口・電源スイッチ）→ JLCCNC 見積もり・発注
5. ~~ZMK ファーム作成~~（ローカルビルド済み。GitHub Actions・実機は未確認）
6. 組み立て・動作確認
