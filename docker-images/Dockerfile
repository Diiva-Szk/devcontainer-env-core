# hadolint global ignore=DL3008,DL3013
###########################################################################
# Build args (共通)
###########################################################################
ARG ARG_BASE_IMAGE_REPOSITORY="debian"
ARG ARG_BASE_IMAGE_TAG="13.5-slim"
ARG ARG_BASE_IMAGE_DIGEST="sha256:28de0877c2189802884ccd20f15ee41c203573bd87bb6b883f5f46362d24c5c2"

###########################################################################
# mise:
#   mise 本体の取得元。公式イメージからバイナリだけを取り出す。
#   タグと digest は Renovate が更新する（digest 固定ですり替えを防ぐ）。
#   公式イメージは debian trixie ベースでビルドされているため、
#   base（debian 13）とは glibc が一致する。
###########################################################################
FROM jdxcode/mise:2026.9.1@sha256:df5adf538c92d86f9807e738c7c7a9b32a1ae06edf441ede141333e3fe6a2cd9 AS mise

###########################################################################
# base:
#   最小土台。
#   OS / ロケール / tzdata / ca-certificates / 非rootユーザのみ。
#   開発ツール(mise, git, build-essential等)や Python/Node は含めない。
###########################################################################
FROM ${ARG_BASE_IMAGE_REPOSITORY}:${ARG_BASE_IMAGE_TAG}@${ARG_BASE_IMAGE_DIGEST} AS base

ARG UID=1000
ARG GID=1000
ARG USER_NAME=dev
ARG TZ="Asia/Tokyo"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    USER_NAME="${USER_NAME}" \
    PATH="/home/${USER_NAME}/.local/bin:${PATH}"

# 必要最小限のシステムパッケージ
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        tzdata \
        locales && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 日本語ロケール / タイムゾーン
RUN ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime && \
    echo "${TZ}" > /etc/timezone && \
    sed -i -E 's/# (ja_JP.UTF-8)/\1/' /etc/locale.gen && \
    sed -i -E 's/# (en_US.UTF-8)/\1/' /etc/locale.gen && \
    locale-gen

ENV TZ="${TZ}" \
    LANG=ja_JP.UTF-8 \
    LANGUAGE=ja_JP:ja \
    LC_NUMERIC=en_US.UTF-8 \
    LC_TIME=en_US.UTF-8

# 非rootユーザ作成（素の作成のみ。sudo設定はここでは行わない）
RUN groupadd --gid "${GID}" "${USER_NAME}" && \
    useradd --uid "${UID}" --gid "${GID}" --shell /bin/bash --create-home "${USER_NAME}" && \
    mkdir -p "/home/${USER_NAME}/.config" && \
    chown -R "${USER_NAME}:${USER_NAME}" "/home/${USER_NAME}/.config"

WORKDIR "/home/${USER_NAME}"

###########################################################################
# dev-base:
#   開発共通の土台。base に開発ツール一式と mise、mise 経由の
#   uv/fnm と、それらによる Python/Node を追加する。ai / user 双方の親。
###########################################################################
FROM base AS dev-base

ARG USER_NAME=dev
ARG PYTHON_VERSION=3.14
ARG NODE_VERSION=24.14.1

ENV PYTHON_VERSION="${PYTHON_VERSION}" \
    NODE_VERSION="${NODE_VERSION}"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# 開発用システムパッケージ
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        build-essential \
        curl \
        wget \
        unzip \
        less \
        procps \
        openssh-client && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# -------------------------------------------------------------------
# mise 本体
# -------------------------------------------------------------------
# root 所有で配置し、ユーザ（特に ai）からは書き換えられないようにする。
COPY --from=mise --chown=root:root /usr/local/bin/mise /usr/local/bin/mise

# ベース共通のツール定義（system スコープ）。
# root 所有で配置し、ユーザは読み取りのみ。mise.lock も同梱し、
# settings.locked により lock に無いツールはインストールさせない。
# パーミッションはビルドコンテキスト側に依存させず明示する
# （mise lock は mise.lock を 0600 で書き出すため、そのままでは一般ユーザが読めない）。
# COPY --chmod はレガシービルダー（BuildKit 無効）で使えないため RUN で設定する。
COPY --chown=root:root dev-base/etc/mise /etc/mise

# entrypoint もユーザから書き換えられないよう root 所有・実行権限付きで配置する。
COPY --chown=root:root dev-base/usr/local/bin/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod -R u=rwX,go=rX /etc/mise && \
    chmod 0755 /usr/local/bin/mise /usr/local/bin/entrypoint.sh

# ツール本体はユーザの data dir（既定: ~/.local/share/mise）に入り、shims 経由で PATH に載る。
# ワークスペース側の mise.toml（実行時に足したツール）は mise が自動で読み込む。
#   → 実行中に足したツールは立て直しても消えない。
#     恒久化したくなったらイメージ側の config.toml へ昇格する。
ENV PATH="/home/${USER_NAME}/.local/share/mise/shims:${PATH}"

USER "${USER_NAME}"

# ベース共通ツールをインストール（uv/fnm を含む）
RUN mise install && \
    mise --version

# -------------------------------------------------------------------
# Python (uv) / Node (fnm) をビルド時にインストール
# -------------------------------------------------------------------
RUN uv python install "${PYTHON_VERSION}" --default --preview && \
    uv pip install ipykernel pandas pyarrow --system --break-system-packages

RUN if ! grep -q "fnm env" "${HOME}/.bashrc"; then \
        echo "eval \"$(fnm env --shell bash)\"" >> "${HOME}/.bashrc"; \
    fi && \
    eval "$(fnm env --shell bash)" && \
    fnm install "v${NODE_VERSION}" && \
    fnm default "v${NODE_VERSION}"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

###########################################################################
# ai:
#   AIエージェント環境。Claude Code / Codex / Copilot / Kiro CLI / Antigravity CLI を持つ。
#   sudo なし / AWS認証情報なし / docker.sock なし（意図的に権限を絞る）。
###########################################################################
FROM dev-base AS ai

ARG USER_NAME=dev

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# ai 専用のツール定義（global スコープ）。dev-base の system 設定と合成される。
# root 所有・読み取り専用で配置する（パーミッションを明示する理由は dev-base と同じ）。
COPY --chown=root:root ai/opt/mise /opt/mise
ENV MISE_GLOBAL_CONFIG_FILE="/opt/mise/config.toml"

USER root
RUN chmod -R u=rwX,go=rX /opt/mise

USER "${USER_NAME}"

# ai 専用ツールをインストール（Kiro CLI / Antigravity CLI を含む）
RUN mise install

# -------------------------------------------------------------------
# 各 CLI の初期セットアップ
#   バイナリの取得・検証は mise が行う。ここではインストール後の初期化のみ実行する。
# -------------------------------------------------------------------
# Kiro CLI: シェル統合（~/.bashrc 等への追記）とローカルデータの初期化。
RUN kiro-cli setup --no-confirm && \
    kiro-cli --version

# Antigravity CLI: `agy install` はシェルのプロファイルへ ~/.local/bin の PATH を追記するだけで、
# PATH は base で設定済みのため実行しない（~/.local/bin に mise 管理外の agy を置かせないため）。
RUN agy --version

# ai 用の home 初期ファイル
COPY --chown=${USER_NAME}:${USER_NAME} ai/home-config "/home/${USER_NAME}"

CMD ["sleep", "infinity"]

###########################################################################
# user:
#   作業者(あなた)の環境。sudo(パスワード関門) と docker CLI を持ち、
#   docker.sock 経由で ai コンテナを操作する。AWS認証情報を扱う側。
###########################################################################
FROM dev-base AS user
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG USER_NAME=dev
ARG USER_PASS=dev
ARG DOCKER_GID=988

# sudo はこの user ステージにのみ導入（攻撃面を ai から排除）
USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        sudo && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# sudo（パスワードつき）
RUN echo "${USER_NAME}:${USER_PASS}" | /usr/sbin/chpasswd && \
    echo "${USER_NAME} ALL=(ALL:ALL) ALL" > "/etc/sudoers.d/${USER_NAME}" && \
    chmod 0440 "/etc/sudoers.d/${USER_NAME}" && \
    visudo -c -f "/etc/sudoers.d/${USER_NAME}"

# docker.sock アクセス用グループ（ホストの docker GID に合わせる）
RUN if getent group docker > /dev/null 2>&1; then \
        groupmod -g "${DOCKER_GID}" docker; \
    else \
        groupadd -g "${DOCKER_GID}" docker; \
    fi && \
    usermod -aG docker "${USER_NAME}"

# user 専用のツール定義（global スコープ）。dev-base の system 設定と合成される。
# root 所有・読み取り専用で配置する（パーミッションを明示する理由は dev-base と同じ）。
# （このステージはここまで USER root のまま）
COPY --chown=root:root user/opt/mise /opt/mise
ENV MISE_GLOBAL_CONFIG_FILE="/opt/mise/config.toml"
RUN chmod -R u=rwX,go=rX /opt/mise

USER "${USER_NAME}"

# user 専用ツール（docker CLI 等）
RUN mise install

# -------------------------------------------------------------------
# renovate (ローカル確認用。本番運用は GitHub Actions 側)
# -------------------------------------------------------------------
RUN eval "$(fnm env --shell bash)" && \
    npm install -g renovate

# user 用の home 初期ファイル
COPY --chown=${USER_NAME}:${USER_NAME} user/home-config/ "/home/${USER_NAME}"
