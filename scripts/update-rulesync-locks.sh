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

# rulesync.lock は解決した時刻（resolvedAt）を持ち、実行のたびに変わる。
# これを無条件に書き戻すと、PR で lock を push するワークフローが毎回差分を作り、
# その push がワークフロー自身を再び起動して止まらなくなる。
# 時刻を除いた内容が同じなら「変更なし」と扱うため、比較用の正規形を作る。
canonical_lock() {
    python3 -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    data = json.load(f)
for source in data.get("sources", {}).values():
    if isinstance(source, dict):
        source.pop("resolvedAt", None)
json.dump(data, sys.stdout, sort_keys=True)
' "$1"
}

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

    # --update が要る。付けないと rulesync は lock にある解決済みコミットを再利用し、
    # rulesync.jsonc の ref を変えても lock が追従しない（このスクリプトの目的が果たせない）。
    # タグを指す限り、ref が変わっていなければ同じコミットに解決されるため、
    # 実際の差分は resolvedAt だけになり、後段の比較で握り潰される。
    if ! output="$(cd "$stage" && rulesync install --update 2>&1)"; then
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

    # resolvedAt だけが変わった場合は旧 lock を残す（無意味な差分を出さないため）
    if [ -f "$lock" ] && [ "$(canonical_lock "$lock")" = "$(canonical_lock "$stage/rulesync.lock")" ]; then
        echo "  変更なし"
        continue
    fi

    cp "$stage/rulesync.lock" "$lock"
    # 他の設定ファイルと同じ 0644 に揃える
    chmod 0644 "$lock"
done

exit "$status"
