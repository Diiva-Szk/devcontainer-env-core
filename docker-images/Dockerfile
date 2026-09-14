# hadolint global ignore=DL3008,DL3013
###########################################################################
# Build args (共通)
###########################################################################
ARG ARG_BASE_IMAGE_REPOSITORY="debian"
ARG ARG_BASE_IMAGE_TAG="13.6-slim"
ARG ARG_BASE_IMAGE_DIGEST="sha256:d7e12182ce18b85b93007c1dedf31f2d29e01ccf3182cc4017c709b6259bc132"

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
#   Python / Node / uv 等を追加する。ai / user 双方の親。
#   Python / Node のバージョンは dev-base/etc/mise/config.toml で管理する。
###########################################################################
FROM base AS dev-base

ARG USER_NAME=dev

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

# Python パッケージの定義（ハッシュ付き requirements.txt）。root 所有・読み取り専用。
COPY --chown=root:root dev-base/opt/python /opt/python

RUN chmod -R u=rwX,go=rX /etc/mise /opt/python && \
    chmod 0755 /usr/local/bin/mise /usr/local/bin/entrypoint.sh

# ツール本体はユーザの data dir（既定: ~/.local/share/mise）に入り、shims 経由で PATH に載る。
# ワークスペース側の mise.toml（実行時に足したツール）は mise が自動で読み込む。
#   → 実行中に足したツールは立て直しても消えない。
#     恒久化したくなったらイメージ側の config.toml へ昇格する。
ENV PATH="/home/${USER_NAME}/.local/share/mise/shims:${PATH}"

USER ${USER_NAME}

# ベース共通ツールをインストール（Python / Node / uv を含む）
RUN mise install && \
    mise --version && \
    python --version && \
    node --version

# -------------------------------------------------------------------
# Python パッケージ
#   requirements.txt は推移的依存まで含めてバージョンとハッシュを固定している
#   （dev-base/opt/python/requirements.in から uv pip compile --generate-hashes で生成）。
#   --require-hashes により、ハッシュの無いパッケージや不一致のパッケージは拒否される。
#   --system は PATH 上の python（mise の Python）へ入れる。
#   mise の Python（python-build-standalone）は EXTERNALLY-MANAGED ではないため
#   --break-system-packages は不要。
# -------------------------------------------------------------------
RUN uv pip install --system --require-hashes -r /opt/python/requirements.txt

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

USER ${USER_NAME}

# ai 専用ツールをインストール（Kiro CLI / Antigravity CLI を含む）
#   バイナリの取得・検証は mise が行う。各 CLI の付属のセットアップコマンドは実行しない。
#
# Kiro CLI: `kiro-cli setup` は実行しない（シェル統合を入れない）。
#   シェル統合は ~/.bashrc から kiro-cli-term を `exec -a "bash (kiro-cli-term)"` で起動する。
#   PATH 上の kiro-cli-term は mise の shim で、shim は argv[0] で起動するツールを判別するため、
#   "bash (kiro-cli-term)" is not a valid shim で対話シェル自体が起動できなくなる。
#   kiro-cli chat などはシェル統合なしで使える。
#
# Antigravity CLI: `agy install` はシェルのプロファイルへ ~/.local/bin の PATH を追記するだけで、
#   PATH は base で設定済みのため実行しない（~/.local/bin に mise 管理外の agy を置かせないため）。
RUN mise install && \
    kiro-cli --version && \
    agy --version

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

# 【ビルドキャッシュのための順序】
#   利用者ごとに値が変わり得るビルド引数（USER_PASS）は、ステージの最後で宣言・使用する。
#   ARG は宣言以降のすべての RUN のキャッシュキーに含まれるため、途中で宣言すると
#   値を変えた利用者は以降の層（mise install / npm ci など）を CI のキャッシュから取得できない。
#   Docker ソケットのグループはビルドせず、compose.yml の group_add で起動時に付与する。
ARG USER_NAME=dev

# sudo はこの user ステージにのみ導入（攻撃面を ai から排除）
USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        sudo && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# sudo はパスワード必須（パスワード自体はステージの最後で設定する）
RUN echo "${USER_NAME} ALL=(ALL:ALL) ALL" > "/etc/sudoers.d/${USER_NAME}" && \
    chmod 0440 "/etc/sudoers.d/${USER_NAME}" && \
    visudo -c -f "/etc/sudoers.d/${USER_NAME}"

# user 専用のツール定義（global スコープ）。dev-base の system 設定と合成される。
# root 所有・読み取り専用で配置する（パーミッションを明示する理由は dev-base と同じ）。
COPY --chown=root:root user/opt/mise /opt/mise
ENV MISE_GLOBAL_CONFIG_FILE="/opt/mise/config.toml"

# Renovate CLI の定義（package.json / package-lock.json）。
# npm ci はユーザの Node（mise）で実行するため、インストール中だけユーザに書き込ませ、
# 完了後に root 所有・読み取り専用へ戻す。
COPY --chown=root:root user/opt/renovate /opt/renovate

RUN chmod -R u=rwX,go=rX /opt/mise /opt/renovate && \
    chown "${USER_NAME}" /opt/renovate

USER ${USER_NAME}

# -------------------------------------------------------------------
# user 専用ツール（docker CLI 等）と renovate (ローカル確認用。本番運用は GitHub Actions 側)
#   renovate は package-lock.json の integrity で依存を含めて固定し、npm ci で導入する。
#   インストールスクリプトは実行しない（re2 のネイティブ拡張は入らず、Renovate は
#   標準の RegExp にフォールバックする）。
# -------------------------------------------------------------------
RUN mise install && \
    npm ci --prefix /opt/renovate --ignore-scripts --no-audit --no-fund

USER root

# ai コンテナに入るコマンド（ai）。どのディレクトリからでも実行でき、
# カレントディレクトリに対応する ai コンテナ側のディレクトリで起動する。
COPY --chown=root:root user/usr/local/bin/ai /usr/local/bin/ai

RUN chown -R root:root /opt/renovate && \
    chmod -R u=rwX,go=rX /opt/renovate && \
    chmod 0755 /usr/local/bin/ai && \
    ln -s /opt/renovate/node_modules/.bin/renovate /usr/local/bin/renovate

# user 用の home 初期ファイル
COPY --chown=${USER_NAME}:${USER_NAME} user/home-config/ "/home/${USER_NAME}"

# -------------------------------------------------------------------
# sudo のパスワード（利用者ごとに変わるため最後の層で設定する）
# -------------------------------------------------------------------
ARG USER_PASS=dev
RUN echo "${USER_NAME}:${USER_PASS}" | /usr/sbin/chpasswd

# USER の値は引用符で囲まない。Dev Containers CLI は Feature を適用する際、
# 最後の USER からユーザー名を引用符ごと取り出すため、"dev" という存在しない
# ユーザーで起動しようとして失敗する（unable to find user "dev"）。
USER ${USER_NAME}
RUN renovate --version
