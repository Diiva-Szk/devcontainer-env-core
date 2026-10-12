# /etc/bash.bashrc から読み込む。Worktrunk の公式シェル統合で wt switch 後に cd する。
case $- in
    *i*) ;;
    *) return ;;
esac

# ログイン時は /etc/profile.d より先に /etc/bash.bashrc が読まれる。
. /etc/profile.d/mise.sh
# user の paranoid モードでも、プロジェクトの trust 前に worktree を操作できるようにする。
# / でイメージ側の設定から実体を解決し、関数の呼び出し時も shim を経由しない。
# 利用者が明示した WORKTRUNK_BIN は Worktrunk 本来の指定として尊重する。
if [ -z "${WORKTRUNK_BIN:-}" ]; then
    WORKTRUNK_BIN="$(cd / && mise which wt 2>/dev/null)" || unset WORKTRUNK_BIN
fi
if [ -x "${WORKTRUNK_BIN:-}" ]; then
    export WORKTRUNK_BIN
    eval "$("${WORKTRUNK_BIN}" config shell init bash)"
fi
