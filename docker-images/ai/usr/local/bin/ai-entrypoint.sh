#!/bin/bash
###########################################################################
# ai-entrypoint.sh
#   ai コンテナの起動スクリプト。デスクトップ（KasmVNC）を起動してから、
#   ai / user 共通の entrypoint.sh に処理を渡す。
#
#   デスクトップの起動に失敗しても、AI エージェントは使えるようにコンテナは起動させる
#   （ログは ~/.vnc/ にある。直したら start-desktop で起動し直せる）。
###########################################################################
set -uo pipefail

if ! /usr/local/bin/start-desktop; then
  echo "ai-entrypoint: デスクトップ（KasmVNC）を起動できませんでした。ログ: ~/.vnc/" >&2
fi

exec /usr/local/bin/entrypoint.sh "$@"
