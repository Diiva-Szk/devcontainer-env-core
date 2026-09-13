#!/usr/bin/env bash
# 本Featureは devcontainer-feature.json の customizations のみを提供するため、
# コンテナイメージへのインストール処理は行わない。
set -euo pipefail

echo "[vscode-common] VS Code の共通設定・拡張機能・許可リストを適用しました（インストール処理なし）"
