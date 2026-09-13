#!/usr/bin/env bash
# docker-images 配下の mise 設定（dev-base / ai / user）の mise.lock を作り直す。
#
# mise lock を既存の lock に対して実行すると、オプション変更前やバージョン更新前の
# 古いエントリが残ることがあるため、毎回ゼロから生成して「lock = 設定から決まる値」にする。
# チェックサムを提供しない配布元の成果物は fill-mise-lock-checksums.sh で補完する
# （変わっていない URL は旧 lock の値を再利用するため、再ダウンロードは発生しない）。
#
# 使い方（リポジトリ内のどこからでも可。mise はイメージと同じバージョンを使うこと）:
#   bash scripts/update-mise-locks.sh
#
# GitHub API を多用するため、GITHUB_TOKEN を設定して実行することを推奨する。
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# イメージは linux/amd64 と linux/arm64 の両方でビルドされ得るため、両方を記録する。
PLATFORMS="linux-x64,linux-arm64"

# リポジトリの設定だけを対象にするため、実行環境（user コンテナ等）の system / global 設定と
# ワークスペース側の設定を読み込ませない。safe モードで設定からのコード実行も禁止する。
empty_dir="$(mktemp -d)"
trap 'rm -rf "$empty_dir"' EXIT
export MISE_SYSTEM_CONFIG_DIR="$empty_dir"
export MISE_GLOBAL_CONFIG_FILE="$empty_dir/config.toml"
export MISE_SAFE=1
export MISE_YES=1

# lock を順序に依存しない形に正規化して出力する。
# [[tools...]] から次の [[ までを1エントリとし、エントリ単位で並べ替える。
canonical_lock() {
    awk '
        /^\[\[/ { if (entry != "") print entry; entry = "" }
        { entry = entry $0 "\x1f" }
        END { if (entry != "") print entry }
    ' "$1" | LC_ALL=C sort
}

status=0
for config in docker-images/*/etc/mise/config.toml docker-images/*/opt/mise/config.toml; do
    [ -f "$config" ] || continue

    mise_dir="$(dirname "$config")"   # .../mise
    root_dir="$(dirname "$mise_dir")" # mise/config.toml を持つ config root
    lock="$mise_dir/mise.lock"

    echo "==> $config"

    old_lock="$empty_dir/old.lock"
    rm -f "$old_lock"
    if [ -f "$lock" ]; then
        cp "$lock" "$old_lock"
        rm -f "$lock"
    fi

    # config root より上位のディレクトリにある mise.toml を拾わないようにする。
    # 失敗時は旧 lock に戻し、中途半端な lock を残さない。
    restore() {
        if [ -f "$old_lock" ]; then cp "$old_lock" "$lock"; else rm -f "$lock"; fi
        status=1
    }

    # config root より上位のディレクトリにある mise.toml を拾わないようにする。
    if ! output="$(cd "$root_dir" && MISE_CEILING_PATHS="$(dirname "$PWD")" mise lock --platform "$PLATFORMS" 2>&1)"; then
        echo "$output" >&2
        restore
        continue
    fi
    echo "$output" | grep -v '^mise lock  ' || true

    # 解決できなかったツールがあると "(N skipped)" になる。lock が不完全なまま
    # イメージをビルドすると locked モードで失敗するため、ここで検出して止める。
    if ! echo "$output" | grep -q '(0 skipped)'; then
        echo "[lock] $lock: 解決できなかったプラットフォームエントリがあります（上のログを確認）" >&2
        restore
        continue
    fi

    # テンプレートの展開ミス等で、arm64 のエントリに x86_64 向けの成果物が記録されていないか確認する。
    if awk '
            /^\[/ { arm = ($0 ~ /"platforms\.linux-arm64"\]$/) }
            arm && /^url[[:space:]]*=/ && /(x86_64|amd64|x64)/ { print; bad = 1 }
            END { exit !bad }
        ' "$lock" >&2; then
        echo "[lock] $lock: linux-arm64 のエントリに x86_64 向けと思われる URL があります（上記）" >&2
        restore
        continue
    fi

    if [ -f "$old_lock" ]; then
        bash scripts/fill-mise-lock-checksums.sh --reuse "$old_lock" "$lock"
    else
        bash scripts/fill-mise-lock-checksums.sh "$lock"
    fi

    # mise lock は同一ツールの複数エントリ（プラットフォーム別オプションを持つツール等）の
    # 並び順が実行ごとに変わる。内容が同じなら旧 lock を残し、無意味な差分を出さない。
    if [ -f "$old_lock" ] && [ "$(canonical_lock "$old_lock")" = "$(canonical_lock "$lock")" ]; then
        cp "$old_lock" "$lock"
    fi

    # mise lock は 0600 で書き出すため、他の設定ファイルと同じ 0644 に揃える
    # （Dockerfile 側でも明示しているが、作業ツリーの状態を不自然にしないため）。
    chmod 0644 "$lock"
done

exit "$status"
