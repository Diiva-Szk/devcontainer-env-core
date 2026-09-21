#!/bin/bash
###########################################################################
# entrypoint.sh
#   ai / user 共通のコンテナ起動スクリプト。
#   重い導入処理はビルド時(Dockerfile)に済ませてあるため、
#   ここは「起動時にしか効かせられない軽い初期化」+ exec "$@" のみ。
#
#   将来、起動時にしか決まらない初期化(マウント後の処理、環境変数に応じた
#   挙動切り替え等)が必要になったら、exec の前に追記する。
#
#   Python / Node を含むツールは Dockerfile の ENV で mise の shims を PATH に載せる。
#   ログインシェルでは /etc/profile が PATH を上書きするため、
#   /etc/profile.d/mise.sh で shims を戻す。
#   ワークスペース側の mise.toml（実行中に足したツール）は mise 自身が
#   カレントディレクトリから探索して読み込むため、ここでの設定は不要。
###########################################################################
set -euo pipefail

# command が渡らなかった場合の安全弁。
#   compose.yml の command 省略や devcontainer.json の overrideCommand 設定次第で
#   引数が空になり得る。その状態で exec "$@" に落ちると何も起動せずスクリプトが
#   正常終了し、コンテナが即停止してしまう（原因が分かりにくい）。
if [[ "$#" -eq 0 ]]; then
  exec sleep infinity
fi

exec "$@"
