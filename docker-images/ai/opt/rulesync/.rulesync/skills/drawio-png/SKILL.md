---
name: drawio-png
description: dip（drawio-png-cli）で `.drawio.png` に埋め込まれた draw.io 図面を読み取り・編集・新規作成する手順。VS Code の draw.io 拡張で保存したのと同じ見た目の PNG を作る。`.drawio.png` の中身（ノード・接続・ページ）を説明する、図形やラベルを追加・変更・削除する、アイコン（Simple Icons などの draw.io カスタムライブラリ）を図に入れる、XML から VS Code で開ける PNG を作る、図面を検証する、といった依頼では必ずこのスキルを使うこと。ユーザーが「dip」と言わなくても、`.drawio.png` や draw.io の PNG 図面を扱う依頼なら該当する。PNG のバイト列を自前のスクリプトで解析・書き換えしないこと。
---

# drawio-png

`.drawio.png`（PNG 画像と編集用の draw.io XML を 1 ファイルに持つ図面）を、CLI の `dip` で読み書きする。

## 最初に

このファイルは案内用で、使い方の本文ではない。`dip` のコマンドを実行する前に、本文を CLI から読み込む。

```sh
dip skill          # 基本の手順（VS Code 拡張と同じ見た目で描く vscode モード）。ここから始める
dip skill --full   # Desktop レンダラー、raw・desktop モード、フォント指定、--no-render などを含む全機能
```

本文はインストールされている dip に同梱されていて、常にその版のコマンドと一致する。
このファイルは版によって変わらないので、手順は書いていない。

## dip が無い場合

```sh
command -v dip && dip --version
```

dip が無ければ、[GitHub Releases](https://github.com/szk302/drawio-png-cli/releases) の OS 別アーカイブ
（展開して `dip` を PATH に置く）か、`cargo install --git https://github.com/szk302/drawio-png-cli --locked` で入れる。
`dip skill` が無い古い dip なら、更新する。どちらもできない場合は、その旨をユーザーに伝えて止まる。
PNG のバイト列を自前のスクリプトで解析・書き換えして代用しない。
