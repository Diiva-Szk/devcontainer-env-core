#!/usr/bin/env bash
# バージョンと両アーキテクチャの SHA256 を一緒に更新する。
# lmm は cwd に応じて環境を補うラッパーを使うため、mise の同名 shim は作らない。
set -euo pipefail
version=0.1.0
case "$(uname -m)" in
  x86_64) target=x86_64-unknown-linux-musl; checksum=9bcbd2374f404592f1d37485ee6ba5fa67882affda278abfd1db7f250d9a3dc0 ;;
  aarch64) target=aarch64-unknown-linux-musl; checksum=7cc464997daa4fcf241c0a9e39c4e561ff07899f2cf58eadd520d5965cf35f5f ;;
  *) echo "lmm: unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
archive="lmm-v${version}-${target}"
curl --fail --location --retry 3 \
  "https://github.com/szk302/local-markdown-mail/releases/download/v${version}/${archive}.tar.gz" \
  -o "${tmp}/${archive}.tar.gz"
printf '%s  %s\n' "${checksum}" "${tmp}/${archive}.tar.gz" | sha256sum --check -
tar -xzf "${tmp}/${archive}.tar.gz" -C "${tmp}"
# LICENSE・THIRD-PARTY-LICENSES.txt・MUSL-COPYRIGHT も本体と一緒に残す。
cp -a "${tmp}/${archive}/." /opt/lmm/
chmod -R u=rwX,go=rX /opt/lmm
ln -s /opt/lmm/lmm /usr/local/bin/lmm-native
lmm-native --version
