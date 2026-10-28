---
name: d-png
description: d-png-cli で `.drawio.png` に埋め込まれた draw.io 図面を読み取り・編集・新規作成する手順。VS Code の draw.io 拡張で保存したのと同じ見た目の PNG を作る。`.drawio.png` の中身（ノード・接続・ページ）を説明する、図形やラベルを追加・変更・削除する、アイコンや AWS などの図形をライブラリの参照で図に入れる、XML から VS Code で開ける PNG を作る、図面を検証する、といった依頼では必ずこのスキルを使うこと。ユーザーが CLI の名前を言わなくても、`.drawio.png` や draw.io の PNG 図面を扱う依頼なら該当する。PNG のバイト列を自前のスクリプトで解析・書き換えしないこと。
---

# d-png

`.drawio.png`（PNG 画像と編集用の draw.io XML を 1 ファイルに持つ図面）を、CLI の `d-png-cli` で読み書きする。

## 最初に

このファイルは案内用で、使い方の本文ではない。`d-png-cli` のコマンドを実行する前に、本文を CLI から読み込む。

```sh
d-png-cli skill   # XML を書いて write に渡す手順、ライブラリの参照、既存の PNG の read → 編集 → write
```

本文はインストールされている d-png-cli に同梱されていて、常にその版のコマンドと一致する。
このファイルは版によって変わらないので、手順は書いていない。

## d-png-cli が無い場合

```sh
command -v d-png-cli && d-png-cli --version
```

d-png-cli が無ければ、[GitHub Releases](https://github.com/szk302/d-png-cli/releases) の OS 別アーカイブ
（展開して `d-png-cli` を PATH に置く）か、`cargo install --git https://github.com/szk302/d-png-cli --locked` で入れる。
入れられない場合は、その旨をユーザーに伝えて止まる。
PNG のバイト列を自前のスクリプトで解析・書き換えして代用しない。
