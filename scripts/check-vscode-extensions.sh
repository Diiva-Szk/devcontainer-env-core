#!/usr/bin/env bash
# Feature で指定している VS Code 拡張機能のバージョンが Marketplace に存在することを確認する。
#
# Renovate は Marketplace のバージョンを参照できず、GitHub のリリースを代理指標にしている
# （renovate.json5 の customManagers 参照）。GitHub にはリリースがあっても Marketplace に
# 公開されていない版があり、それを指定すると拡張機能をインストールできなくなる。
# （例: janisdd.vscode-edit-csv の v0.11.10）
#
# Marketplace のバージョン一覧は extensionquery API（POST）でしか取得できないため、
# Renovate の customDatasources（GET のみ）ではなく、この検査で補う。
#
# 使い方:
#   bash scripts/check-vscode-extensions.sh [devcontainer-feature.json ...]
#   （省略時は devcontainer-features 配下の Feature すべて）
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

if [ "$#" -eq 0 ]; then
    set -- devcontainer-features/*/devcontainer-feature.json
fi

# 以下の2形式から "<拡張機能ID> <バージョン>" を取り出す。
#   customizations.vscode.extensions:  "publisher.extension@1.2.3"
#   settings["extensions.allowed"]:    "publisher.extension": ["1.2.3"]
# 注意: devcontainer-feature.json は jsonc（コメント付き）であり jq では扱えない。
extract_extensions() {
    sed -n -E \
        -e 's/^[[:space:]]*"([A-Za-z0-9-]+\.[A-Za-z0-9.-]+)@([^"]+)".*/\1 \2/p' \
        -e 's/^[[:space:]]*"([A-Za-z0-9-]+\.[A-Za-z0-9.-]+)"[[:space:]]*:[[:space:]]*\[[[:space:]]*"([^"]+)".*/\1 \2/p' \
        "$@"
}

# ID は大文字小文字を区別しないため、小文字にそろえて重複を除く
mapfile -t entries < <(extract_extensions "$@" | tr '[:upper:]' '[:lower:]' | sort -u)

if [ "${#entries[@]}" -eq 0 ]; then
    echo "[vscode-ext] 拡張機能の指定が見つかりませんでした" >&2
    exit 1
fi

status=0
for entry in "${entries[@]}"; do
    read -r id version <<<"$entry"

    body="$(jq -nc --arg id "$id" '{filters: [{criteria: [{filterType: 7, value: $id}]}], flags: 1}')"
    versions="$(curl --proto '=https' --tlsv1.2 -fsSL --retry 3 \
        -X POST 'https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery' \
        -H 'Content-Type: application/json' \
        -H 'Accept: application/json;api-version=3.0-preview.1' \
        -d "$body" |
        jq -r '.results[0].extensions[0].versions[]?.version')"

    if [ -z "$versions" ]; then
        echo "[vscode-ext] ${id}: Marketplace に存在しません" >&2
        status=1
    elif grep -qxF "$version" <<<"$versions"; then
        echo "[vscode-ext] ${id}@${version}: OK"
    else
        latest="$(sort -V <<<"$versions" | tail -n 1)"
        echo "[vscode-ext] ${id}@${version}: Marketplace に存在しません（最新は ${latest}）" >&2
        status=1
    fi
done

exit "$status"
