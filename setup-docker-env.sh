#!/usr/bin/env bash
# setup-docker-env.sh

DOCKER_SOCK_PATH="/var/run/docker.sock"
# docker compose は compose.yml と同じディレクトリの .env を読むため、スクリプト自身の場所を基準にする
# （配置先のディレクトリ名や実行時のカレントディレクトリに依存させない）
DOT_ENV_FILE_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"

echo "==> Configuring universal Docker environments (Mac / WSL2)..."

# 1. Dockerが起動しているかチェック
if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "Error: Docker is not running or not installed."
  exit 1
fi


echo "Detected Docker socket path: ${DOCKER_SOCK_PATH}"

# 2. 汎用的なGID取得（コンテナ内からマウントされたソケットを調べる）
DOCKER_GID=$(docker run --rm -v "${DOCKER_SOCK_PATH}:/tmp/docker.sock" alpine stat -c %g /tmp/docker.sock 2>/dev/null)

if [ -z "$DOCKER_GID" ]; then
  # compose.yml の DOCKER_GID デフォルト値と揃えること（食い違うと検出失敗時のみ挙動がずれる）
  echo "Warning: Failed to detect DOCKER_GID dynamically. Falling back to default (988)."
  DOCKER_GID=988
fi

echo "Detected Docker GID: ${DOCKER_GID}"

# 4. .env ファイルを安全に更新 (既存の変数を保持して追記/上書き)
touch "${DOT_ENV_FILE_PATH}"

update_env_var() {
  local key=$1
  local value=$2
  local target_file="${DOT_ENV_FILE_PATH}"

  if grep -q "^${key}=" "$target_file"; then
    grep -v "^${key}=" "$target_file" > "${target_file}.tmp"
    echo "${key}=${value}" >> "${target_file}.tmp"
    mv "${target_file}.tmp" "$target_file"
  else
    echo "${key}=${value}" >> "$target_file"
  fi
}

update_env_var "DOCKER_GID" "${DOCKER_GID}"
update_env_var "DOCKER_SOCK_PATH" "${DOCKER_SOCK_PATH}"

echo "==> .env file generated successfully!"
