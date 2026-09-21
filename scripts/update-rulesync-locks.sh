#!/usr/bin/env bash
# docker-images 配下の rulesync 設定（ai の skills 取得）の rulesync.lock を作り直す。
#
# rulesync.jsonc の ref（Renovate が更新する）を変えると lock と不一致になり、
# イメージのビルドが `rulesync install --frozen` で失敗する。この乖離を解消する。
#
# 取得結果（.rulesync/skills/.curated/）はイメージのビルド時に取り直すため、
# リポジトリには lock だけを持たせる。そのため作業用のコピーで install を実行し、
# 生成された lock だけを書き戻す（作業ツリーに .rulesync/ を残さない）。
#
# 使い方（リポジトリ内のどこからでも可）:
#   bash scripts/update-rulesync-locks.sh
#
# rulesync はイメージと同じバージョンを使うこと（ai コンテナ内で実行するのが簡単）。
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

status=0
for config in docker-images/*/opt/*/rulesync.jsonc; do
    [ -f "$config" ] || continue

    project_dir="$(dirname "$config")"
    lock="$project_dir/rulesync.lock"

    echo "==> $config"

    # 作業用のコピーで実行する。既存の lock も持っていき、ref が変わっていない
    # ソースは解決済みのコミットをそのまま使わせる（無意味な差分を出さないため）。
    stage="$work_dir/$(basename "$project_dir")"
    mkdir -p "$stage"
    cp "$config" "$stage/rulesync.jsonc"
    [ -f "$lock" ] && cp "$lock" "$stage/rulesync.lock"

    if ! output="$(cd "$stage" && rulesync install 2>&1)"; then
        echo "$output" >&2
        echo "[lock] $config: rulesync install に失敗しました" >&2
        status=1
        continue
    fi
    echo "$output"

    if [ ! -f "$stage/rulesync.lock" ]; then
        echo "[lock] $config: rulesync.lock が生成されませんでした" >&2
        status=1
        continue
    fi

    # 生成した lock で --frozen が通ること（= イメージのビルドが通ること）を確かめる。
    if ! output="$(cd "$stage" && rulesync install --frozen 2>&1)"; then
        echo "$output" >&2
        echo "[lock] $config: 生成した lock で --frozen が通りません" >&2
        status=1
        continue
    fi

    cp "$stage/rulesync.lock" "$lock"
    # 他の設定ファイルと同じ 0644 に揃える
    chmod 0644 "$lock"
done

exit "$status"
