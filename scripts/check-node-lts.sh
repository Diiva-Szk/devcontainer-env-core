#!/usr/bin/env bash
# mise 設定で指定している Node が LTS のリリースであることを確認する。
#
# Renovate は現在の版が LTS であれば LTS 以外へ更新しないが、手作業で LTS 以外の版
# （奇数メジャーや、LTS 入り前の偶数メジャー）を指定するとその系列のまま更新が続く。
# LTS 限定の前提が崩れないよう、nodejs.org の index.json の lts 欄で検査する。
#
# 使い方:
#   bash scripts/check-node-lts.sh [mise の config.toml ...]
#   （省略時は docker-images 配下の mise 設定すべて）
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

if [ "$#" -eq 0 ]; then
    set -- docker-images/*/etc/mise/config.toml docker-images/*/opt/mise/config.toml
fi

index_json="$(curl --proto '=https' --tlsv1.2 -fsSL --retry 3 https://nodejs.org/dist/index.json)"

status=0
checked=0
for config in "$@"; do
    [ -f "$config" ] || continue

    # "core:node" = "24.14.1" または node = "24.14.1" 形式の行からバージョンを取り出す
    version="$(sed -n -E 's/^[[:space:]]*"?(core:)?node"?[[:space:]]*=[[:space:]]*"([^"]+)".*/\2/p' "$config" | head -n 1)"
    [ -n "$version" ] || continue
    checked=$((checked + 1))

    # 見つからなければ空、LTS でなければ false、LTS ならコードネームが返る
    lts="$(jq -r --arg v "v${version}" '.[] | select(.version == $v) | .lts' <<<"$index_json")"

    case "$lts" in
        "")
            echo "[node-lts] $config: Node ${version} は nodejs.org に存在しません" >&2
            status=1
            ;;
        false)
            echo "[node-lts] $config: Node ${version} は LTS ではありません" >&2
            status=1
            ;;
        *)
            echo "[node-lts] $config: Node ${version} は LTS (${lts}) です"
            ;;
    esac
done

if [ "$checked" -eq 0 ]; then
    echo "[node-lts] Node を指定している mise 設定が見つかりませんでした" >&2
    exit 1
fi

exit "$status"
