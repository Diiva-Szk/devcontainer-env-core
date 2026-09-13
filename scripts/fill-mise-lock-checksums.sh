#!/usr/bin/env bash
# mise.lock のプラットフォームエントリのうち、checksum が無いものを補完する。
#
# mise lock は、配布元（aqua レジストリ等）がチェックサムを提供しない成果物について
# checksum を記録しない（例: aws-cli, docker/cli, google-cloud-sdk, claude-code）。
# mise は checksum が lock にあればインストール時に検証するが、無ければ検証しない。
# aqua の require_checksum と同等の保証を得るため、成果物を実際にダウンロードして
# sha256 を計算し、lock へ書き込む（aqua の update-checksum と同じ考え方）。
#
# --reuse で以前の lock を渡すと、同じ URL に記録済みの checksum を再利用し、
# ダウンロードを省略する（lock を作り直す運用で、変わっていない成果物を再取得しないため）。
#
# 使い方:
#   scripts/fill-mise-lock-checksums.sh [--reuse <旧mise.lock>] <mise.lock>...  # 補完する
#   scripts/fill-mise-lock-checksums.sh --check <mise.lock>...                 # 欠落があれば失敗する（CI用）
set -euo pipefail

usage() {
    echo "usage: $0 [--check | --reuse <old-mise.lock>] <mise.lock>..." >&2
    exit 2
}

check_only=false
reuse_lock=""
case "${1:-}" in
    --check)
        check_only=true
        shift
        ;;
    --reuse)
        [ "$#" -ge 2 ] || usage
        reuse_lock="$2"
        shift 2
        ;;
esac

if [ "$#" -eq 0 ]; then
    usage
fi

# checksum の無いプラットフォームエントリの url を列挙する。
# エントリは [tools."<tool>"."platforms.<os-arch>"] で始まり、次の [ で終わる。
missing_urls() {
    awk '
        function flush() {
            if (in_platform && !has_checksum && url != "") print url
        }
        /^\[/ {
            flush()
            in_platform = ($0 ~ /\."platforms\.[^"]+"\]$/)
            has_checksum = 0
            url = ""
            next
        }
        in_platform && /^checksum[[:space:]]*=/ { has_checksum = 1 }
        in_platform && /^url[[:space:]]*=/ {
            url = $0
            sub(/^url[[:space:]]*=[[:space:]]*"/, "", url)
            sub(/".*$/, "", url)
        }
        END { flush() }
    ' "$1"
}

# 指定 lock で、指定 URL のプラットフォームエントリに記録済みの checksum（"sha256:..."）を出力する。
recorded_checksum() {
    awk -v target="$2" '
        function flush() {
            if (in_platform && url == target && checksum != "") { print checksum; found = 1; exit }
        }
        /^\[/ {
            flush()
            in_platform = ($0 ~ /\."platforms\.[^"]+"\]$/)
            url = ""
            checksum = ""
            next
        }
        in_platform && /^checksum[[:space:]]*=/ {
            checksum = $0
            sub(/^checksum[[:space:]]*=[[:space:]]*"/, "", checksum)
            sub(/".*$/, "", checksum)
        }
        in_platform && /^url[[:space:]]*=/ {
            url = $0
            sub(/^url[[:space:]]*=[[:space:]]*"/, "", url)
            sub(/".*$/, "", url)
        }
        END { if (!found) flush() }
    ' "$1"
}

status=0
for lock in "$@"; do
    mapfile -t urls < <(missing_urls "$lock" | sort -u)

    if [ "${#urls[@]}" -eq 0 ]; then
        echo "[checksum] $lock: 欠落なし"
        continue
    fi

    if [ "$check_only" = true ]; then
        for url in "${urls[@]}"; do
            echo "[checksum] $lock: checksum がありません: $url" >&2
        done
        status=1
        continue
    fi

    for url in "${urls[@]}"; do
        case "$url" in
            https://*) ;;
            *)
                echo "[checksum] $lock: https 以外の URL は扱いません: $url" >&2
                exit 1
                ;;
        esac

        checksum=""
        if [ -n "$reuse_lock" ] && [ -f "$reuse_lock" ]; then
            checksum="$(recorded_checksum "$reuse_lock" "$url")"
        fi

        if [ -n "$checksum" ]; then
            echo "[checksum] $lock: 旧 lock から再利用: $url"
        else
            echo "[checksum] $lock: 計算中: $url"
            checksum="sha256:$(curl --proto '=https' --tlsv1.2 -fsSL --retry 3 "$url" | sha256sum | cut -d' ' -f1)"
        fi

        tmp="$(mktemp)"
        # 同じ URL を持ち checksum の無いエントリ（全プラットフォーム共通の成果物など）すべてに、
        # url 行の直前へ checksum 行を挿入する。
        awk -v target="$url" -v checksum="$checksum" '
            function flush(   i) {
                for (i = 1; i <= n; i++) {
                    if (in_platform && !has_checksum && i == url_line) {
                        print "checksum = \"" checksum "\""
                    }
                    print buf[i]
                }
                n = 0
            }
            /^\[/ {
                flush()
                in_platform = ($0 ~ /\."platforms\.[^"]+"\]$/)
                has_checksum = 0
                url_line = 0
            }
            {
                buf[++n] = $0
                if (in_platform && $0 ~ /^checksum[[:space:]]*=/) has_checksum = 1
                if (in_platform && $0 == "url = \"" target "\"") url_line = n
            }
            END { flush() }
        ' "$lock" >"$tmp"

        # リダイレクトではなく cat でコピーし、元ファイルのパーミッションを維持する
        cat "$tmp" >"$lock"
        rm -f "$tmp"
    done
done

exit "$status"
