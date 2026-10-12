#!/usr/bin/env bash
# ai の find-docs スキル（Context7 CLI / ctx7 の SKILL.md。vendoring）を、mise 設定に
# 書かれた ctx7 と同じ版の公式リポジトリのタグ（ctx7@<版>）から作り直す。
#
# ctx7 の版は Renovate が mise 設定（docker-images/ai/opt/mise/config.toml）で上げるが、
# vendoring した SKILL.md と find-docs.version は連動しない。そのままではイメージの
# ビルドが版の照合（find-docs.version と ctx7 --version）で失敗するため、この乖離を解消する。
# PR 上では update-find-docs-skill ワークフローが実行するため、手元での実行は任意。
#
# 内容は毎回タグから作り直す（取得 + patch-find-docs.py の置換）。版が変わっていなければ
# 既存のファイルと同じ内容になり、差分は出ない。
#
# 上流の LICENSE が変わっていた場合は何も書き換えずに失敗する。ライセンスの種類や
# 著作権表示の変更は人が確認し、docs/MAINTAINING.md の記載も直す必要があるため。
#
# 使い方（リポジトリ内のどこからでも可）:
#   bash scripts/update-find-docs-skill.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

config="docker-images/ai/opt/mise/config.toml"
project_dir="docker-images/ai/opt/rulesync"
skill_dir="$project_dir/.rulesync/skills/find-docs"
version_file="$project_dir/find-docs.version"
repo_url="https://github.com/upstash/context7.git"

version="$(sed -n 's/^"npm:ctx7" = "\([^"]*\)"$/\1/p' "$config")"
if [ -z "$version" ]; then
    echo "[find-docs] $config から ctx7 のバージョンを特定できませんでした" >&2
    exit 1
fi
# タグ名に使うため、版の形式を確かめる
if ! [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$ ]]; then
    echo "[find-docs] ctx7 のバージョンの形式が想定外です: $version" >&2
    exit 1
fi
echo "==> ctx7@$version"

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

# 必要なのは2ファイルだけのため、blob を必要になった時点で取得する partial clone にし、
# チェックアウトもしない。ctx7@<版> は注釈付きタグだが、git clone --branch はタグが
# 指すコミットを取得するため、rulesync の git transport の問題（vendoring の理由）は起きない。
if ! git clone --quiet --depth 1 --filter=blob:none --no-checkout \
    --branch "ctx7@$version" "$repo_url" "$work_dir/context7"; then
    echo "[find-docs] $repo_url のタグ ctx7@$version を取得できませんでした" >&2
    exit 1
fi
git -C "$work_dir/context7" show HEAD:skills/find-docs/SKILL.md > "$work_dir/SKILL.md"
git -C "$work_dir/context7" show HEAD:LICENSE > "$work_dir/LICENSE"

if ! cmp -s "$work_dir/LICENSE" "$skill_dir/LICENSE"; then
    diff -u "$skill_dir/LICENSE" "$work_dir/LICENSE" >&2 || true
    echo "[find-docs] 上流（ctx7@$version）の LICENSE が変わっています。" >&2
    echo "  内容を確認して $skill_dir/LICENSE を置き換え、docs/MAINTAINING.md の記載も直してください。" >&2
    exit 1
fi

# 上流の文言が変わって置換できない場合はここで失敗する（patch-find-docs.py を直す）
python3 "$project_dir/patch-find-docs.py" "$work_dir/SKILL.md"

if cmp -s "$work_dir/SKILL.md" "$skill_dir/SKILL.md" \
    && [ "$(cat "$version_file")" = "$version" ]; then
    echo "  変更なし"
    exit 0
fi

# 書き込みは既存のファイルへの上書きにする（パーミッションを変えない）
cat "$work_dir/SKILL.md" > "$skill_dir/SKILL.md"
printf '%s\n' "$version" > "$version_file"
echo "  find-docs スキルを ctx7@$version から作り直しました"
