#!/bin/bash
###########################################################################
# ai-entrypoint.sh
#   ai コンテナの起動スクリプト。イメージが管理する設定のうち、まだ無いものを
#   配り、デスクトップ（KasmVNC）と ssh サーバー（user コンテナの ai コマンドの接続先）を
#   起動してから、
#   ai / user 共通の entrypoint.sh に処理を渡す。
#
#   設定は --seed で「まだ無いものだけ」作る。既にあるファイルは書き換えない
#   （イメージ側の更新を取り込むタイミングは利用者が決める。
#     ai コンテナで sync-home-defaults --check / sync-home-defaults を実行する）。
#
#   .env の GIT_SIGNING_KEY があれば、git の署名を設定する（setup-git-signing）。
#   秘密鍵を AI エージェントのセッションの環境変数に残さないよう、設定したらすぐに消す
#   （start-sshd はこのスクリプトの環境変数を ssh のセッションへ引き継ぐ）。
#
#   設定の配布や署名の設定、デスクトップ・ssh サーバーの起動に失敗しても、AI エージェントは
#   使えるようにコンテナは起動させる
#   （デスクトップのログは ~/.vnc/ にある。直したら start-desktop で起動し直せる。
#     ssh サーバーのログは ~/.local/state/ai-sshd/ にある。start-sshd で起動し直せる）。
###########################################################################
set -uo pipefail

if ! /usr/local/bin/sync-home-defaults --seed; then
  echo "ai-entrypoint: イメージが管理する設定を配れませんでした（sync-home-defaults --check で確認できます）" >&2
fi

if ! /usr/local/bin/setup-git-signing; then
  echo "ai-entrypoint: git の署名を設定できませんでした（GIT_SIGNING_KEY を確認してください）" >&2
fi
unset GIT_SIGNING_KEY

if ! /usr/local/bin/start-desktop; then
  echo "ai-entrypoint: デスクトップ（KasmVNC）を起動できませんでした。ログ: ~/.vnc/" >&2
fi

if ! /usr/local/bin/start-sshd; then
  echo "ai-entrypoint: ssh サーバーを起動できませんでした。ログ: ~/.local/state/ai-sshd/" >&2
fi

exec /usr/local/bin/entrypoint.sh "$@"
