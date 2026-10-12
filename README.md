# devcontainer-env-core

プロジェクトに組み込んで使う、Dev Container の開発環境一式です。

- **2つのコンテナで権限を分離:** 作業者用の `user` コンテナと、AI エージェント用の `ai` コンテナを分け、AI エージェントには sudo・Docker ソケット・クラウドの認証情報を渡しません。どちらのコンテナにも Docker ソケットは渡さず、`user` から `ai` へは ssh で入ります。
- **検証済みのツールだけを導入:** CLI ツールや言語ランタイムは [mise](https://mise.jdx.dev/) の lockfile でバージョンとチェックサムを固定してインストールします。
- **VS Code の拡張機能を許可リストで管理:** Dev Container Feature として、共通設定と拡張機能の許可リスト（`extensions.allowed`）を提供します。

## 目次

- [構成](#構成)
- [同梱ツール](#同梱ツール)
- [必要なもの](#必要なもの)
- [使い方](#使い方)
- [VS Code の Feature](#vs-code-の-feature)
- [Worktrunk で worktree を操作する](#worktrunk-で-worktree-を操作する)
- [ツールの追加・バージョンの上書き](#ツールの追加バージョンの上書き)
- [設定項目](#設定項目)
- [AI ツールの状態の保存](#ai-ツールの状態の保存)
- [ビルドキャッシュ](#ビルドキャッシュ)
- [注意事項](#注意事項)
- [ライセンス](#ライセンス)

## 構成

プロジェクトの `.devcontainer/devcontainer-env-core` に配置すると、プロジェクトルートが両方のコンテナの `/home/dev/work` にマウントされます。

```mermaid
flowchart LR
    vscode["VS Code"] -->|アタッチ| user
    subgraph host["ホスト（Docker）"]
        user["user コンテナ<br/>作業者用"]
        ai["ai コンテナ<br/>AI エージェント用"]
        ws[("プロジェクトルート<br/>/home/dev/work")]
    end
    user -->|"ssh（ai コマンド）"| ai
    user --- ws
    ai --- ws
```

| | `user` コンテナ | `ai` コンテナ |
| --- | --- | --- |
| 用途 | 作業者が使う。VS Code がアタッチする | AI エージェント（Claude Code / Codex など）を動かす |
| ワークスペース（プロジェクトルート） | 読み書き可 | 読み書き可 |
| sudo | あり（パスワード必須） | なし |
| Docker ソケット | なし（コンテナの操作はホストで行う） | なし |
| 入り方 | VS Code がアタッチする | `user` から ssh（`ai` コマンド） |
| ワークスペースの `mise.toml` | `mise trust` するまで読み込まない | そのまま読み込む |

## 同梱ツール

バージョンは各設定ファイルで固定され、定期的に更新されます。

**共通（`user` / `ai`）** — [docker-images/dev-base/etc/mise/config.toml](docker-images/dev-base/etc/mise/config.toml)

| 分類 | ツール |
| --- | --- |
| 言語 | Python、Node.js（LTS のバージョンのみ） |
| Python パッケージ | uv、ipykernel、pandas、pyarrow |
| 汎用 | git、curl、wget、jq、yq、GitHub CLI（gh）、tmux、build-essential |
| ローカルメール | Local Markdown Mail（lmm。作業ディレクトリから送信者を自動設定） |
| Lint | hadolint、secretlint |
| Terraform | tfenv、tflint、terraform-docs |
| クラウド | AWS CLI、Google Cloud CLI |

**`ai` コンテナ** — [docker-images/ai/opt/mise/config.toml](docker-images/ai/opt/mise/config.toml)

Claude Code、OpenAI Codex CLI、GitHub Copilot CLI、GitHub Copilot Language Server、Amazon Kiro CLI、Google Antigravity CLI、rulesync、Dagu（`dagu`。agent-wt の DAG を動かす）、Playwright CLI・agent-browser（ブラウザは Google Chrome を使う）、Context7 CLI（ctx7）、drawio-png-cli（dip。`.drawio.png` の図面の抽出・検証・更新。描画には Google Chrome を使う）

dip のライブラリ（`dip library` / `dip insert` で図に入れる図形・アイコン）として、[Simple Icons の draw.io ライブラリ](https://github.com/mondeja/simple-icons-drawio)（`simple-icons`）を `/opt/drawio-libraries` に入れ、`DIP_LIBRARY_PATH` で指しています。ブランドのロゴの利用は、各ブランドの商標の条件に従ってください。

AWS・Google Cloud・Azure などの draw.io 標準の図形（`shape=mxgraph.aws4.*` や `image=img/lib/azure2/...` など）も描画できるよう、draw.io の Web 資材を `/opt/drawio-webapp` に入れ、`DIP_DRAWIO_WEB_PATH` で指しています。dip の既定の描画方式（`vscode` モード）用の資材のため、`--chromium-mode raw` / `desktop` ではこれらの図形は描けません。

VS Code の draw.io 拡張（`hediet.vscode-drawio`）で編集した `.drawio.png` を `ai` コンテナの AI エージェントに修正してもらう使い方を想定しています。資材は拡張（1.9.0）に入っている draw.io と同じ版で、拡張の図形パレットの図形は `ai` 側の dip でも描画できます。ただし次の点に注意してください。

- Web フォント（Google Fonts など）を指定した文字や、URL で参照している画像を含む図は、dip が外部への通信を既定で止めているため描画に失敗します（`--allow-network` が必要というエラーになります）。`dip embed` に `--allow-network` を付けると描画できます。拡張で挿入した画像（貼り付け・ファイルから）や Simple Icons は図に埋め込まれるため、そのまま描画できます。
- 拡張の画像はホスト側の VS Code が描くため、ホストとコンテナのフォントの違いによる細かな画素の差は残ります。

デスクトップ: KasmVNC、Openbox、Google Chrome、st（ターミナル）、fcitx5-mozc（日本語入力）

Playwright CLI・agent-browser の使い方スキル、Context7 CLI（ctx7）のドキュメント検索スキル（find-docs）、dip の `.drawio.png` 編集スキル（drawio-png）は、各 CLI・公式リポジトリが配布しているものをビルド時に取得し、rulesync で Claude Code・Codex・Copilot・Kiro・Antigravity のグローバル設定へ展開しています。

**`user` コンテナ** — [docker-images/user/opt/mise/config.toml](docker-images/user/opt/mise/config.toml)

Renovate CLI、sudo、`ai` コンテナに ssh で入る `ai`、`ai` コンテナのデスクトップを開く `ai-desktop`（`aid`）、Google Chrome（デスクトップなし。VS Code の拡張機能がヘッドレスで使う）

## 必要なもの

- Docker（Docker Desktop for Mac、または WSL2 上の Docker）
- [VS Code](https://code.visualstudio.com/) と [Dev Containers 拡張機能](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

## 使い方

### 1. プロジェクトに配置する

プロジェクトの `.devcontainer/devcontainer-env-core` に配置します。Git のサブモジュールとして追加すると、使うバージョン（コミット）を固定できます。

```sh
git submodule add https://github.com/Diiva-Szk/devcontainer-env-core.git .devcontainer/devcontainer-env-core
```

### 2. `.env` を作成する

`compose.yml` と同じディレクトリに `.env` を作成し、設定を書きます（[設定項目](#設定項目)）。省略すると既定値で動きますが、`user` コンテナの `sudo` のパスワード（`USER_PASS`、既定: `dev`）は変更してください。既定値のままでは、`user` コンテナで動いた悪意あるスクリプトが、既知のパスワードで root になれます。

```sh
# .devcontainer/devcontainer-env-core/.env
USER_PASS=<任意のパスワード>
```

### 3. `devcontainer.json` を作成する

`.devcontainer/devcontainer.json` を作成します。

```jsonc
{
  "name": "my-project",
  "dockerComposeFile": "devcontainer-env-core/compose.yml",
  "service": "user",
  "runServices": ["user", "ai"],
  "workspaceFolder": "/home/dev/work",
  "remoteUser": "dev",
  "features": {
    // 共通設定と拡張機能の許可リスト（他の vscode-* Feature を使う場合も必須）
    "ghcr.io/diiva-szk/devcontainer-env-core/vscode-common:1": {},
    // 必要に応じて追加
    "ghcr.io/diiva-szk/devcontainer-env-core/vscode-python:1": {},
    "ghcr.io/diiva-szk/devcontainer-env-core/vscode-terraform:1": {}
  }
}
```

プロジェクトのディレクトリ構成は次のようになります。

```text
my-project/
├── .devcontainer/
│   ├── devcontainer.json
│   └── devcontainer-env-core/   # このリポジトリ
│       ├── compose.yml
│       └── .env                 # 手順 2 で作成
└── ...
```

### 4. コンテナを開く

VS Code でプロジェクトを開き、コマンドパレットから **Dev Containers: Reopen in Container** を実行します。

初回はイメージをビルドします。このリポジトリの CI が `main` のビルドキャッシュを公開しているため、内容が同じ層はダウンロードで済み、変更のあった層だけがローカルでビルドされます（[ビルドキャッシュ](#ビルドキャッシュ)）。

### 5. AI エージェントを使う

`user` コンテナのターミナルで `ai` コマンドを実行すると、このプロジェクトの `ai` コンテナに ssh で入れます。どのディレクトリからでも実行でき、**`ai` コンテナでも同じディレクトリで起動します**（例: `~/work/src` で実行すると、`ai` コンテナの `~/work/src` で起動します）。

```sh
ai               # ai コンテナで bash を起動する
ai claude        # ai コンテナで直接 Claude Code を起動する（引数はそのまま渡る）

# ai コンテナ内で
claude     # Claude Code
codex      # OpenAI Codex CLI
copilot    # GitHub Copilot CLI
kiro-cli   # Amazon Kiro CLI
agy        # Google Antigravity CLI
rulesync   # AI エージェント向けのルール・設定の生成
sync-home-defaults  # イメージが管理する設定をイメージ側の内容に合わせる
playwright-cli  # ブラウザ操作（Playwright CLI）
agent-browser   # ブラウザ操作（agent-browser）
ctx7            # ライブラリの最新ドキュメントを引く（Context7 CLI）
dip             # .drawio.png の図面の抽出・検証・更新（drawio-png-cli）
dagu            # YAML で定義したワークフロー（DAG）の実行（agent-wt で使う）
```

- 各ツールのログイン（認証）は、初回に `ai` コンテナ内で行ってください。**ログイン情報と会話履歴は、コンテナを作り直しても残ります**（[AI ツールの状態の保存](#ai-ツールの状態の保存)）。
- `ctx7` は認証なしでも使えますが、レート制限が厳しくなります。`ctx7 login`（OAuth）か `CONTEXT7_API_KEY` 環境変数で認証してください（`ctx7 setup` は実行しないでください。各ツールのグローバル設定はこのイメージが管理しているため）。
- `ai` コンテナと共有していないディレクトリ（`~` など）で実行した場合は、`ai` コンテナの `~/work` で起動します。
- `ai` コマンドは、`ai` コンテナの ssh サーバー（`ai:2222`、ホストには公開していません）へ公開鍵で接続します。鍵は初回に `user` コンテナの `~/.ssh/ai_ed25519` に作られ、公開鍵とホスト鍵は volume で受け渡されます。手作業の設定は要りません。
- 接続できない場合は、`ai` コンテナの ssh サーバーが止まっている可能性があります。ホストから `ai` コンテナに入って `start-sshd` を実行すると起動し直せます（ログは `ai` コンテナの `~/.local/state/ai-sshd/`）。ホストから入る方法は [Docker の操作はホストで行う](#docker-の操作はホストで行う)を参照してください。
- mise のタスクとしても実行できます（`mise run ai`、`mise run ai claude`）。ただし、trust していない `mise.toml` があるディレクトリでは mise がエラーになるため、`ai` コマンドを直接実行してください（[`mise trust` が必要](#user-コンテナでは-mise-trust-が必要)）。

#### role・profile ごとの worktree（agent-wt）

`ai` コンテナには、git worktree を作り、指定した role（coder・reviewer・designer など）と profile（Claude Code の Opus 5.5、Codex など）の AI エージェントの設定を rulesync で配置する Dagu の DAG が入っています。同時に [Local Markdown Mail（lmm）](https://github.com/szk302/local-markdown-mail) のメールボックスと設定を用意し、プロジェクトルートと worktree の間で送受信できるようにします。role・profile ごとの設定はプロジェクトの `.agent-wt/` に置きます。

**対象の Git プロジェクトのルート**で実行します。上の導入手順では `~/work` 自体がプロジェクトルートです。`~/work` を作業用ディレクトリとして、その配下に別のリポジトリを clone する構成にも対応しています。たとえば `~/work/GitHub/org_name/other-project` で実行すれば、そのプロジェクトが対象になります。階層の深さに制限はなく、`~/work` 自体が Git リポジトリである必要もありません。イメージを更新したら、`user` / `ai` コンテナをリビルドしてください。

```sh
# ai コンテナ内で（user コンテナでは対象プロジェクトへ cd してから ai で入る）
cd ~/work/GitHub/org_name/other-project
# ~/work 自体が対象プロジェクトの場合は、代わりに cd ~/work
dagu start agent-wt-init                            # .agent-wt/ の雛形と root のメール環境を作る
# .agent-wt/worktrees.yaml の role・profile・branch・base を編集する
dagu start agent-wt-create -- NAME=login-coder       # worktree・AI設定・メール環境をまとめて作る

dagu start agent-wt-remove -- NAME=login-coder       # worktree を削除する（メール原本は残る）
dagu start agent-wt-remove -- NAME=login-coder DELETE_BRANCH=true  # ブランチも削除する
dagu start agent-wt-remove -- NAME=login-coder DISCARD_DRAFTS=true # 下書きの破棄を許可する（Git の検査は続ける）
```

```text
.agent-wt/
├── worktrees.yaml          # worktree ごとの role・profile・branch・base（NAME がキー）
├── common/                 # 全 role 共通の rulesync のソース（任意）
├── roles/<role>/           # role ごとの rulesync のソース（rules/ skills/ subagents/ など）
└── profiles/<profile>/
    ├── rulesync.jsonc      # 生成するツール（targets）と機能（features）
    ├── permissions.jsonc   # 権限など（任意。claudecode.model で Claude Code のモデルを指定できる）
    └── seed/               # rulesync の前に worktree へそのままコピーするファイル（任意）
```

```yaml
# .agent-wt/worktrees.yaml
worktrees:
  login-coder:
    role: coder
    profile: claude-opus5.5
    branch: feat/login   # 省略時は agent/<NAME>。ローカルに無ければ origin のブランチ、それも無ければ base から作る
    base: HEAD          # 現在のコミットから作る。main などのブランチ名も指定できる
```

- rulesync は `common` → `role` → `profile` の順にソースを重ねて生成します（同じ相対パスのファイルは後ろが勝ちます。中身はマージされません）。
- `ROLE=` `PROFILE=` `BRANCH=` `BASE=` を渡すと `worktrees.yaml` の値より優先します（`worktrees.yaml` に無い NAME でも作れます）。
- `BASE=origin/main` のようにリモート追跡ブランチから新しいブランチを作っても、upstream は自動設定しません。同名の `origin/<BRANCH>` が既にある場合は、それを追跡します。
- `NAME` はメールアドレスとしても使います。小文字の `a-z`・`0-9`・`.`・`_`・`-`、先頭は英数字、最大64文字です。`root` と `lmm` は予約済みです。
- 実行したディレクトリのプロジェクトが対象です。別の場所から実行する場合や Dagu の Web UI から起動する場合は、`REPO=/home/dev/work/GitHub/org_name/other-project` のようにプロジェクトの絶対パスを指定します。作成済み worktree 内からの初期化・作成・削除は受け付けません。
- `agent-wt-init` を再実行しても既存の `.agent-wt/` は上書きしません。設定の雛形を更新する場合は、`/opt/agent-wt/template/` と比較して必要な変更を取り込んでください。
- rulesync は Codex のモデル（`model`）を管理しないため、Codex の profile では `seed/.codex/config.toml` に書きます。rulesync はこのファイルの中身を残したまま権限などをマージします。Codex がプロジェクトの `.codex/config.toml` を読むのは、そのディレクトリを信頼したときだけです。
- 生成したファイルは worktree の `git status` に出ないようにします（追跡済みのファイルは `git update-index --skip-worktree`、未追跡のファイルは `.git/info/exclude` に worktree ごとのブロックで追記。`.worktrees/` 自体も `.git/info/exclude` で無視します）。git は worktree ごとの `info/exclude` を読まないため、同じパスは本体の作業ツリーでも無視されます。ブロックは削除時に消えます。
- worktree の作成・削除には [Worktrunk](#worktrunk-で-worktree-を操作する) の `wt switch` / `wt remove` を使います。DAG は配置先を `.worktrees/<NAME>` に固定し、Worktrunk の hooks を実行せず、AI 設定とメールの準備を行います。既に別の worktree で使われているブランチは受け付けません。削除は完了まで待ち、ブランチ削除を指定したときは事前に未マージのコミットを検査します。
- Git が検出する未コミットの変更や、`.lmm-drafts/` 内の下書きが残っていると、削除は失敗して何も消しません。`DELETE_BRANCH=true` のときは、ブランチが未マージの場合も何も消さずに止まります。下書きを破棄してよい場合は `DISCARD_DRAFTS=true` を渡してください。Git の検査は続けるため、未コミットの変更や、削除対象のブランチに未マージのコミットがあれば、下書きも含めて何も消しません。`FORCE=true` は未コミットの変更・下書きも強制削除し、`DELETE_BRANCH=true` と併用すると未マージのブランチも削除します。作成の途中で失敗した場合は、その実行で作った worktree とブランチを削除します。
- 実行のログは `dagu status <DAG 名>` や `~/.local/share/dagu/logs/` で確認できます。

作成後は `.worktrees/login-coder` に移動して、profile に対応する `claude` や `codex` を起動します。DAG は準備までを行い、エージェントの起動や常駐は行いません。

##### プロジェクトルートと worktree の間のメール

`lmm` は `user` / `ai` 両方で使えます。送信者はプロジェクトルートでは `root`、worktree では `NAME` です。コマンドを実行するディレクトリから毎回決めるため、`cd` のたびに `export` や `source` を実行する必要はありません。worktree のサブディレクトリからも使えます。

```sh
# プロジェクトルート → worktree
cd ~/work/GitHub/org_name/other-project  # ~/work 自体が対象なら cd ~/work
draft=$(lmm draft -s "ログイン機能の実装")
printf '\nログイン機能を実装してください。\n' >> "$draft/index.md"
lmm post -t login-coder "$draft" && rm -r -- "$draft"  # 送信成功時だけ下書きを片付ける

# worktree で受信し、プロジェクトルートへ報告する（宛先は省略できる）
cd .worktrees/login-coder
lmm receive                      # 出力されたディレクトリの index.md を読む
draft=$(lmm draft -s "実装結果")
printf '\n実装とテストが完了しました。\n' >> "$draft/index.md"
# .lmm.local.yml の post.reply_to により root へ送る
lmm post "$draft" && rm -r -- "$draft"

# プロジェクトルートで報告を受信する
cd ../..
lmm receive
```

- スレッドを保って返信する場合は、`lmm post --reply <受信ディレクトリ> <下書きディレクトリ>` を使います。`lmm wait --in-reply-to <送信時のID> --timeout 60` で返信を待てます。
- メールボックスと原本・送信控えは `<Git共通管理ディレクトリ>/agent-wt/lmm/`（通常は `.git/agent-wt/lmm/`）に置きます。プロジェクトごとに分離されるため、別プロジェクトでも同じ `NAME` を使えます。共有された work ディレクトリにあるので、`user` / `ai` 間で送受信でき、コンテナを作り直しても残ります。
- ルートと worktree に `.lmm.local.yml` を配置します。受信の展開先は各作業ツリーの `.lmm-inbox/<自分のアドレス>/`、下書きは `.lmm-drafts/<自分のアドレス>/` です。たとえばルートが受信したメールは、送信者にかかわらず `.lmm-inbox/root/` に展開されます。ルートに既存の `.lmm.local.yml` がある場合はその設定を保ちます。これらのローカルファイルは Git の管理対象から除外します。
- `lmm post` は送信後も下書きを残します。上の例では `&& rm -r -- "$draft"` により、送信が成功したときだけ下書きを削除しています。送信に失敗した下書きは残して修正・再送してください。
- worktree を削除してもメールボックスは残り、同じ `NAME` で再作成すると引き継ぎます。受信の展開コピーは worktree と一緒に消えますが、原本は残ります。`.lmm-drafts/` に下書きがある場合は、送信済みのものも含めて削除を止めます。必要な下書きを退避・整理するか、破棄してよい場合に限り `DISCARD_DRAFTS=true` を指定してください。未コミットの変更・未マージのコミットの検査は引き続き行います。メールボックスと履歴も不要になったら、ルートで `lmm box remove <NAME>` を実行します。
- 明示した `LMM_NAME` / `LMM_HOME` は自動設定より優先します。通常は設定せずに使ってください。agent-wt 未登録のリポジトリでは通常の lmm と同じ動作です。
- フック通知は自動では登録しません。必要に応じて lmm のドキュメントに従って設定します。同じアドレスで `wait` と `hook` を併用すると受信が競合するため、どちらかに揃えてください。

### 6. `ai` コンテナのデスクトップを見る

`ai` コンテナではデスクトップ（KasmVNC）が起動しており、AI エージェントが操作するブラウザ（Google Chrome）の画面をホストのブラウザで見られます。`user` コンテナのターミナル（VS Code）で `ai-desktop`（短縮形: `aid`）を実行すると、ホストのブラウザでデスクトップが開きます。

```sh
ai-desktop            # ポートの転送を開始して、ホストのブラウザで開く
ai-desktop status     # 転送の状態を表示する
ai-desktop stop       # 転送を止める
ai-desktop -p 18444   # user コンテナで待ち受けるポートを変える（既定: 8444）
```

```mermaid
flowchart LR
    browser["ホストのブラウザ<br/>https://localhost:8444"] -->|"VS Code のポート転送"| user
    subgraph host["ホスト（Docker）"]
        user["user コンテナ<br/>localhost:8444（ai-desktop）"]
        ai["ai コンテナ<br/>KasmVNC :8444"]
    end
    user -->|"Compose のネットワーク"| ai
```

- `ai` コンテナのポートはホストに公開していません。`ai-desktop` が `user` コンテナの `localhost:8444` を `ai` コンテナへ転送し、VS Code がそれをホストへ転送します。転送はバックグラウンドで続き、ターミナルを閉じても止まりません。
- ログインのユーザー名は `dev`、パスワードは `.env` の `KASMVNC_PASSWORD`（既定: `dev`）です（[設定項目](#設定項目)）。
- 証明書は `ai` コンテナの起動時に作る自己署名証明書のため、初回はブラウザに警告が表示されます。
- ブラウザが自動で開かない場合（VS Code 以外のターミナルなど）は、VS Code の「ポート」タブで 8444 が転送されていることを確認し、表示された URL を開いてください。
- mise のタスクとしても実行できます（`mise run ai-desktop`、短縮形 `mise run aid`、`mise run aid stop`）。ただし、trust していない `mise.toml` があるディレクトリでは mise がエラーになるため、`ai-desktop` コマンドを直接実行してください（[`mise trust` が必要](#user-コンテナでは-mise-trust-が必要)）。
- デスクトップが起動していない場合は、`ai` コンテナで `start-desktop` を実行すると起動し直せます（ログは `ai` コンテナの `~/.vnc/`）。
- `ai` コンテナのシェルから起動した GUI アプリ（`google-chrome` など）も、このデスクトップに表示されます。Chrome は DevTools Protocol（`127.0.0.1:9222`、`ai` コンテナ内のみ）で AI エージェントから操作できます。

## VS Code の Feature

| Feature | 内容 |
| --- | --- |
| `ghcr.io/diiva-szk/devcontainer-env-core/vscode-common` | 共通の VS Code 設定と拡張機能（日本語化、Git、Markdown、CSV、OpenAPI など）、および全 Feature の拡張機能の許可リスト（`extensions.allowed`） |
| `ghcr.io/diiva-szk/devcontainer-env-core/vscode-python` | Python 開発用の拡張機能（Python、Jupyter、Data Wrangler など） |
| `ghcr.io/diiva-szk/devcontainer-env-core/vscode-terraform` | Terraform 開発用の拡張機能 |

- 許可リストにない拡張機能は VS Code にインストールできません。`vscode-python` / `vscode-terraform` を使う場合も、許可リストを提供する `vscode-common` を必ず併用してください。
- `vscode-common` は Markdown Preview Enhanced の `chromePath` に `user` コンテナの Google Chrome（`/usr/local/bin/google-chrome`）を設定します。PDF・PNG などのエクスポートで使われます。
- `:1` と指定すると、メジャーバージョン 1 の最新版が使われます。

## Worktrunk で worktree を操作する

`user` / `ai` の両方のコンテナで [Worktrunk](https://worktrunk.dev/) の `wt` を使えます。対話 Bash にはシェル統合を設定してあるため、`wt switch` で worktree を作成・選択すると、そのディレクトリへ移動します。

```sh
wt switch --create feat/foo                # 新しいブランチと .worktrees/feat-foo を作り、移動する
wt switch --create feat/bar --base dev     # 分岐元を指定する
wt switch feat/foo                        # 既存のブランチへ移動する（worktree がなければ作る）
wt switch -                               # 前の worktree に戻る
wt list                                   # worktree と変更状況の一覧
wt remove --foreground --no-delete-branch feat/foo  # worktree を削除し、ブランチを残す
wt remove --foreground feat/bar            # worktree を削除し、統合済みならブランチも削除する
```

配置先の既定値は `.worktrees/{{ branch | sanitize }}` です。`feat/foo` は `.worktrees/feat-foo` となり、worktree 同士が入れ子になりません。設定は `/etc/xdg/worktrunk/config.toml` にあり、`~/.config/worktrunk/config.toml` で上書きできます。既存の `.worktrees/feat/foo` や、Dagu で作った `.worktrees/login-coder` も Git の登録情報から見つけるため、そのまま切り替えられます。既存の worktree を自動で移動することはありません。

- 新しいブランチは `--create` で作ります。分岐元を省略すると、Worktrunk が判定したデフォルトブランチを使います。既存のリモートブランチへ切り替えるときは、先に `git fetch` してください。
- プロジェクトの `.config/wt.toml` にある hooks は、内容を確認してから承認してください。hooks を実行しない場合は `wt switch --no-hooks ...` / `wt remove --no-hooks ...` を使います。
- `wt remove` は未コミットの変更があると止まります。未マージのブランチは残しますが、worktree 自体は削除します。`--force` は未コミットの変更の破棄、`-D` は未マージのブランチの削除を許可します。既定では削除をバックグラウンドで行うため、完了を待つときは `--foreground` を付けます。詳しくは [Worktrunk の削除仕様](https://worktrunk.dev/remove/)を参照してください。
- **agent-wt で作った worktree の削除は `dagu start agent-wt-remove -- NAME=...` を使ってください。** 下書きの保護、ブランチ削除前のマージ確認、生成設定の除外ルールの片付けも行います。`wt remove` を直接使うと、これらの agent-wt 固有の処理は行われません。
- `.worktrees/` は Git の管理対象外にしてください。`agent-wt-create` は `.git/info/exclude` に追加します。Worktrunk だけで使う場合は、プロジェクトの `.gitignore` などに追加してください。
- worktree はコンテナ内の絶対パス（`/home/dev/work/...`）で記録されるため、ホストの Git からは使えません。
- 対話 Bash の `wt` は、プロジェクトの `mise.toml` の trust に関係なく、イメージに入っている Worktrunk を使います。スクリプト内の `wt` や `git wt` は mise の shim を経由するため、`user` コンテナではプロジェクトや worktree の `mise.toml` の内容を確認して `mise trust` してください（[`mise trust` が必要](#user-コンテナでは-mise-trust-が必要)）。Bash 以外のシェルでは、[Worktrunk のシェル統合](https://worktrunk.dev/shell-integration/)を設定してください。

mise タスクからも操作できます。タスク名の後の引数・オプションは Worktrunk に渡します。

```sh
mise run wt:add feat/foo --base dev --no-hooks     # 新しいブランチと worktree を作る
mise run wt:switch feat/foo --no-hooks             # 既存ブランチの worktree を用意・選択する
mise run wt:list                                  # 一覧を表示する
mise run wt:rm feat/foo --no-delete-branch --no-hooks # worktree を削除し、ブランチを残す
```

`wt:add` は `wt switch --create --no-cd`、`wt:switch` は `wt switch --no-cd`、`wt:rm` は `wt remove --foreground` を実行します。**mise タスクは親シェルのディレクトリを変更できません。** 移動するときは対話 Bash の `wt switch` を使ってください。`user` コンテナで mise タスクを使う場合は、先に対象の `mise.toml` を `mise trust` する必要があります。agent-wt で作った worktree の削除には引き続き Dagu を使ってください。

独自の `git-wt` スクリプトは Worktrunk に置き換えました。Worktrunk が提供する `git-wt` も `wt` と同じ CLI です。以前の mise タスクと異なり、既存のブランチには `wt:switch` を使い、`wt:rm -f` は未コミットの変更だけを破棄します。未マージのブランチも削除する場合は、Worktrunk の `-D` を明示します。

## ツールの追加・バージョンの上書き

プロジェクトルートに `mise.toml` を置くと、イメージに入っているツールより優先されます。イメージに無いツールの追加もできます。

例: プロジェクトでは Node.js 22 を使う場合

```toml
# <プロジェクトルート>/mise.toml
[tools]
node = "22"
```

| カレントディレクトリ | 使われる Node.js |
| --- | --- |
| プロジェクトルート（`~/work`）とその配下 | 22（プロジェクトの `mise.toml`） |
| プロジェクト外（`~` など） | イメージのバージョン |

- **ファイル名は `mise.toml`** にしてください。`.mise.toml`、`.config/mise.toml`、`mise/config.toml` も使えますが、プロジェクト直下の `config.toml` は認識されません。
- イメージに入っていないバージョンは、初めてコマンドを実行したときに自動でインストールされます（明示的に入れる場合は `mise install`）。
- チェックサムを固定したい場合は、プロジェクトで `mise lock` を実行し、`mise.lock` もコミットしてください。

### `user` コンテナでは `mise trust` が必要

`user` コンテナは、ワークスペースの `mise.toml` を **`mise trust` するまで読み込みません**。trust するまでは、その配下で mise のツール（`node`、`python` など）が使えません。

ワークスペースは `ai` コンテナと共有しているため、AI エージェントが `mise.toml` を書き換える可能性があります。sudo と AWS の認証情報を持つ `user` コンテナで、確認していない設定が黙って読み込まれないようにしています。

```sh
mise trust --show     # 内容を確認する
mise trust mise.toml  # 確認してから trust する
```

- trust はファイルの内容に紐づくため、`mise.toml` を編集すると再度 trust が必要です。
- trust の記録はコンテナ内にあるため、コンテナを作り直すと再度 trust が必要です。
- `ai` コンテナでは trust は不要です。

### 別の Node.js を指定したときの注意

プロジェクトで別の Node.js を指定したディレクトリでは、次のコマンドがそのままでは使えなくなります。

イメージの Node.js のバージョンは [docker-images/dev-base/etc/mise/config.toml](docker-images/dev-base/etc/mise/config.toml) の `core:node` で確認できます（以下では `<イメージの版>` と表記します）。

- **イメージの Node.js に `npm install -g` したコマンド:** `No version is set for shim` エラーになります。イメージと同じバージョンも併せて指定すると使えます（先頭のバージョンが優先されます）。

  ```toml
  [tools]
  node = ["22", "<イメージの版>"]
  ```

- **`user` コンテナの `renovate`:** Renovate CLI はイメージの Node.js を前提にしています。そのディレクトリで有効な Node.js（上の例では先頭の 22）で起動すると失敗するため、イメージの Node.js を明示して実行してください。

  ```sh
  mise exec node@<イメージの版> -- renovate --version
  ```

## 設定項目

`.devcontainer/devcontainer-env-core/.env` に書くと、イメージのビルドとコンテナの起動に反映されます。変更後はコンテナをリビルドしてください（**Dev Containers: Rebuild Container**）。

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `USER_PASS` | `dev` | `user` コンテナの `sudo` のパスワード。**変更を推奨します**（イメージの最後の層で設定するため、変更してもビルドキャッシュは使われます） |
| `AWS_REGION` | `ap-northeast-1` | `user` コンテナの AWS リージョン |
| `KASMVNC_PASSWORD` | `dev` | `ai` コンテナのデスクトップ（KasmVNC）のログインパスワード。コンテナの起動時に反映する |
| `GIT_SIGNING_KEY` | （空） | `ai` コンテナの git の署名に使う SSH の秘密鍵の中身。空なら署名しない。コンテナの起動時に反映する（[git の署名](#git-の署名)） |
| `UID` / `GID` | `1000` | コンテナ内ユーザーの UID / GID。**通常は変更しないでください**（下記） |
| `USER_NAME` | `dev` | コンテナ内のユーザー名。**通常は変更しないでください**（下記） |

- **`UID` / `GID` / `USER_NAME` を変更すると、ビルドキャッシュがほぼ使われず、すべてをローカルでビルドします。** Linux ホストでは、Dev Containers がコンテナの作成時にユーザーの UID / GID をホストのユーザーに合わせるため（`updateRemoteUserUID`、既定で有効）、ファイルの所有者を合わせる目的で変更する必要はありません。
- `USER_NAME` を変更した場合は、`devcontainer.json` の `workspaceFolder`（`/home/<USER_NAME>/work`）と `remoteUser` も合わせて変更してください。

### git の署名

`user` コンテナの署名は、VS Code がホストの git の設定を転送するかどうかに任せており、このリポジトリでは対応していません（GnuPG は入っていないため GPG 署名は使えません。SSH 署名は `user.signingkey` を `key::` 形式で書き、ssh-agent を転送している場合などに限り動きます）。`ai` コンテナでは、`.env` の `GIT_SIGNING_KEY` に SSH の秘密鍵を書いたときだけ、コミットとタグに SSH 署名を付けます（書かなければ署名しません）。

1. 署名専用の鍵を作ります（パスフレーズは付けないでください。付けると起動時に読めず、署名は無効のままになります）。

   ```sh
   # ホストで実行する
   ssh-keygen -t ed25519 -N '' -C 'git signing (devcontainer ai)' -f ~/.ssh/id_ed25519_git_signing
   ```

2. 公開鍵（`~/.ssh/id_ed25519_git_signing.pub`）を GitHub の **Settings → SSH and GPG keys → New SSH key** で、Key type を **Signing Key** にして登録します。
3. 秘密鍵の中身を `.env` に書きます。改行を含むため、ダブルクォートで囲みます。

   ```sh
   # .devcontainer/devcontainer-env-core/.env
   GIT_SIGNING_KEY="-----BEGIN OPENSSH PRIVATE KEY-----
   ...
   -----END OPENSSH PRIVATE KEY-----"
   ```

4. コンテナを作り直します（**Dev Containers: Rebuild Container**）。起動時に `setup-git-signing` が鍵を `~/.ssh/git_signing_key` に書き出し、`~/.gitconfig` に `gpg.format=ssh`・`user.signingkey`・`commit.gpgsign=true`・`tag.gpgsign=true` を設定します。

- GitHub で Verified と表示されるには、コミットのメールアドレス（`user.email`）が鍵を登録したアカウントのものである必要があります。
- **`ai` コンテナの AI エージェントは書き出された秘密鍵を読めます**（`docker exec` で入ったシェルからは環境変数 `GIT_SIGNING_KEY` も見えます。`ai` コマンドの ssh のセッションには引き継ぎません）。普段の認証用の鍵や他の署名鍵を使い回さず、署名専用の鍵にしてください。漏れた疑いがあれば GitHub から鍵を削除します。

## AI ツールの状態の保存

`ai` コンテナの AI ツールの設定ディレクトリは Docker の volume にしてあり、**ログイン情報と会話履歴はコンテナを作り直しても残ります**。volume はプロジェクトごとに分かれるため、別のプロジェクトとは混ざりません（実際の名前は `<プロジェクト名>_devcontainer_ai-claude` のようになります）。

| ツール | volume にしているパス |
| --- | --- |
| Claude Code | `~/.claude` |
| Codex CLI | `~/.codex` |
| Copilot CLI | `~/.copilot` |
| Kiro CLI | `~/.kiro` と `~/.local/share/kiro-cli`（認証情報は後者の `data.sqlite3`） |
| Antigravity CLI | `~/.gemini` |
| Context7 CLI（ctx7） | `~/.config/context7`（認証情報は `credentials.json`） |

- Claude Code のアカウント情報を持つ `.claude.json` は、既定ではホーム直下に置かれて volume に入らないため、`CLAUDE_CONFIG_DIR` で `~/.claude/.claude.json` に移しています。

### イメージが管理する設定の更新

設定の一部はイメージが持ち主です（下表）。これらも volume に残るため、**イメージを更新しても古いままになります**。反映するタイミングは利用者が決められるよう、`ai` コンテナの `sync-home-defaults` で明示的に実行する形にしています。

```sh
# ai コンテナ内で
sync-home-defaults --check   # イメージ側と違うところを一覧する（何も変更しない）
sync-home-defaults           # 反映する
```

| | 対象 |
| --- | --- |
| `sync-home-defaults` で入れ替わる | `~/.claude/settings.json`、`~/.codex/config.toml`、`~/.kiro/settings/cli.json`、`~/.gemini/antigravity-cli/settings.json`、rulesync が生成した各ツールの `skills/` |
| 触られない | ログイン情報、会話履歴・セッション、上記と同じディレクトリにある実行時の状態（`~/.kiro/settings/feed_state.json` など） |

- **コンテナの起動時に勝手に上書きされることはありません。** 起動時に配られるのは「まだ無いファイル」だけです（イメージ側に増えた設定やスキルは自動で配られ、既にあるファイルは利用者が書き換えたものも含めてそのまま残ります）。
- 恒久的に変えたいときは、コンテナ内ではなくイメージ側（`docker-images/ai/home-config/` など）を変更してください。

### 状態を消す

ログインし直したい・状態をまっさらにしたいときは、コンテナを止めてから volume を削除します。

```sh
# ホストで実行する
docker volume ls | grep '_ai-'                     # 名前を確認する
docker volume rm <プロジェクト名>_devcontainer_ai-claude
```

ログイン情報は volume の中に平文で置かれます（コンテナ内と同じ扱いです）。

## ビルドキャッシュ

このリポジトリの CI は、`main` のイメージ定義からビルドした各層のキャッシュを GHCR（`ghcr.io/diiva-szk/devcontainer-env-core/build-cache`）に公開しています（amd64 / arm64）。`compose.yml` がこれを参照するため、ビルド時にキャッシュがある層はダウンロードされ、無い層だけがローカルでビルドされます。

- 使うテンプレートのコミットが `main` の最新でなくても動作します。`main` と内容が同じ層はダウンロードされ、異なる層以降だけがビルドされます。
- **キャッシュが使われるのは、Docker の containerd image store が有効な場合です。** 無効な場合はキャッシュが無視され、すべてをローカルでビルドします（動作に問題はありません）。Docker Desktop 4.34 以降と、Docker Engine 29 以降の新規インストールでは既定で有効です。次のコマンドで確認できます。

  ```sh
  docker info -f '{{ .DriverStatus }}'
  # [[driver-type io.containerd.snapshotter.v1]] と表示されれば有効
  ```

  無効な場合に有効にする方法:
  - **Docker Desktop:** Settings → General → **Use containerd for pulling and storing images** を有効にする
  - **Docker Engine（WSL2 など）:** `/etc/docker/daemon.json` に次を追加し、Docker を再起動する（`sudo systemctl restart docker`）

    ```json
    {
      "features": {
        "containerd-snapshotter": true
      }
    }
    ```

  > 切り替えると、それまでの保存方式で作ったイメージとコンテナは表示されなくなります（ディスク上には残り、元に戻すと再び表示されます）。

## 注意事項

### Docker の操作はホストで行う

`user` コンテナにも `ai` コンテナにも Docker ソケットを渡していないため、コンテナの中から Docker は使えません。`user` コンテナで動いたスクリプト（ビルドや依存パッケージのインストールなど）に、ホストの Docker を操作させないためです（Docker ソケットを使えると、ホストの root と同じことができてしまいます）。

コンテナの操作（イメージのビルド、プロジェクトのアプリの `docker compose up` など）は、ホストのターミナルで行ってください。`ai` コマンドが使えないときは、ホストから `ai` コンテナに直接入れます。

```sh
# ホストで実行する
docker ps --filter label=com.docker.compose.service=ai   # ai コンテナの名前を調べる
docker exec -it <ai コンテナの名前> bash
```

### その他

- **AI エージェントは確認なしで動作します。** `ai` コンテナの Claude Code・Codex などは、コマンド実行やファイル編集の確認プロンプトを出さない設定です。sudo・Docker ソケット・クラウドの認証情報を持たないことを前提にしているため、この設定を `user` コンテナやホストへ持ち出さないでください。
- **ワークスペースの内容は AI エージェントから読み書きできます。** API キーなどの秘密情報を、プロジェクトルート配下に置かないでください。
- **AI ツールのログイン情報は volume に平文で残ります。** コンテナを作り直しても消えないため、共有マシンで使う場合は [AI ツールの状態の保存](#ai-ツールの状態の保存)の手順で volume を削除してください。
- `ai` コンテナはネットワークに接続できます（外部 API の利用やパッケージの取得のため）。

## ライセンス

[MIT License](LICENSE)

このリポジトリの保守・開発に関する情報は [docs/MAINTAINING.md](docs/MAINTAINING.md) を参照してください。
