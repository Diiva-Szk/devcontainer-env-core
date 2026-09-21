# /etc/profile が PATH を再設定した後、mise の shims を復元する。
# Codex の shell snapshot を含む、非対話のログインシェルでも読み込まれる。
# ツールを持たないユーザーには追加せず、再読み込み時の重複も避ける。
if [ -d "$HOME/.local/share/mise/shims" ]; then
    case ":$PATH:" in
        *":$HOME/.local/share/mise/shims:"*) ;;
        *) export PATH="$HOME/.local/share/mise/shims:$PATH" ;;
    esac
fi
