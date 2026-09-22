#!/bin/bash
###########################################################################
# ai-entrypoint.sh
#   ai コンテナの起動スクリプト。イメージが管理する設定のうち、まだ無いものを
#   配り、デスクトップ（KasmVNC）を起動してから、
#   ai / user 共通の entrypoint.sh に処理を渡す。
#
#   設定は --seed で「まだ無いものだけ」作る。既にあるファイルは書き換えない
#   （イメージ側の更新を取り込むタイミングは利用者が決める。
#     ai コンテナで sync-home-defaults --check / sync-home-defaults を実行する）。
#
#   設定の配布やデスクトップの起動に失敗しても、AI エージェントは
#   使えるようにコンテナは起動させる
#   （デスクトップのログは ~/.vnc/ にある。直したら start-desktop で起動し直せる）。
###########################################################################
set -uo pipefail

if ! /usr/local/bin/sync-home-defaults --seed; then
  echo "ai-entrypoint: イメージが管理する設定を配れませんでした（sync-home-defaults --check で確認できます）" >&2
fi

if ! /usr/local/bin/start-desktop; then
  echo "ai-entrypoint: デスクトップ（KasmVNC）を起動できませんでした。ログ: ~/.vnc/" >&2
fi

exec /usr/local/bin/entrypoint.sh "$@"
