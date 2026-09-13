#!/usr/bin/env bash
# Renovate の postUpgradeTasks から呼ばれ、更新された Feature の version を patch 上げする。
#
# Feature は devcontainer-feature.json の "version" が既存の publish 済みタグと同じ場合、
# release ワークフローで何も publish されない。拡張機能のバージョンが更新されたら
# Feature 自身の version も上げる必要があるため、その1点だけを機械的に行う。
#
# 注意: devcontainer-feature.json は jsonc（コメント付き）であり jq では扱えない。
#       そのため "version" 行のみを対象にしたテキスト置換で更新する。
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Renovate は postUpgradeTasks をコミット前に実行するため、変更は作業ツリーに存在する。
# ステージ済み・未ステージのどちらも拾うため HEAD と比較する。
mapfile -t changed < <(git diff --name-only HEAD -- 'devcontainer-features/*/devcontainer-feature.json')

if [ "${#changed[@]}" -eq 0 ]; then
    echo "[bump] 変更された Feature はありません"
    exit 0
fi

extract_version() {
    sed -n 's/^[[:space:]]*"version"[[:space:]]*:[[:space:]]*"\([0-9][^"]*\)".*/\1/p' | head -n 1
}

for f in "${changed[@]}"; do
    # 基準は作業ツリーではなく HEAD の値にする。
    # こうしないと同一ブランチで再実行された際に version が二重に上がる。
    if ! base="$(git show "HEAD:$f" 2>/dev/null | extract_version)" || [ -z "$base" ]; then
        echo "[bump] $f: HEAD に存在しない新規 Feature のため bump しません"
        continue
    fi

    current="$(extract_version <"$f")"

    major="${base%%.*}"
    rest="${base#*.}"
    minor="${rest%%.*}"
    patch="${rest#*.}"

    # x.y.z 以外（プレリリース付きなど）は自動判断せず落とす
    if ! [[ "$major" =~ ^[0-9]+$ && "$minor" =~ ^[0-9]+$ && "$patch" =~ ^[0-9]+$ ]]; then
        echo "[bump] $f: version '$base' が x.y.z 形式ではないため自動更新できません" >&2
        exit 1
    fi

    new="${major}.${minor}.$((patch + 1))"

    if [ "$current" = "$new" ]; then
        echo "[bump] $f: 既に $new のため変更なし"
        continue
    fi

    tmp="$(mktemp)"
    # 最初に現れる version 行のみ置換する（拡張機能のバージョン文字列には触れない）
    awk -v new="$new" '
        !bumped && /^[[:space:]]*"version"[[:space:]]*:/ {
            sub(/"version"[[:space:]]*:[[:space:]]*"[^"]*"/, "\"version\": \"" new "\"")
            bumped = 1
        }
        { print }
    ' "$f" >"$tmp"

    # リダイレクトではなく cat でコピーし、元ファイルのパーミッションを維持する
    cat "$tmp" >"$f"
    rm -f "$tmp"

    echo "[bump] $f: $current -> $new"
done
