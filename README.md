# keyboard

自作キーボード macjis（MacBook 風 JIS 配列 81 キー、Kailh Choc V1、XIAO nRF52840 Plus、ZMK、無線）の制作用リポジトリ。

- 仕様と設計の判断: [docs/spec.md](docs/spec.md)
- 生成のスクリプト（配列 → 基板・ケース・キーキャップ・ZMK）: [scripts/](scripts/)
- 制作記の「制作」の節: [article/制作.md](article/制作.md)

## 自分のキーボードを作るためのスキル

このリポジトリの経験を、ほかの人が Claude Code と話しながら自分のキーボードを基板から作れるようにまとめたスキルが [skills/diy-keyboard/](skills/diy-keyboard/) にあります。配列は自由で、分割や別の部品にも使える指針です（分割はこのリポジトリでは作っていないため、確かめていない指針です）。

```bash
npx skills add imaimai17468/keyboard
```

入れたら、Claude Code に「自作キーボードを基板から作りたい」のように話しかけてください。
