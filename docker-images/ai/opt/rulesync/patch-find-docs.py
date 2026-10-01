#!/usr/bin/env python3
"""Context7 公式の find-docs スキル（SKILL.md）を、イメージに mise で固定した
`ctx7` コマンドを使う内容へ書き換える。

上流のスキルは、すべてのコマンドを `npx ctx7@latest ...` で実行させる前提で
書かれている。これをそのまま配ると、mise で固定した版ではなく実行時に npm から
最新版の ctx7 を取得して実行することになり、バージョン固定と lock の意味がなくなる。

想定した文字列が見つからない場合は失敗する（上流の文言が変わったとき、
黙って npx ctx7@latest が残ることを防ぐため）。ctx7 を更新する Renovate の PR で
これが起きた場合、ビルドが落ちるので、docs/MAINTAINING.md の手順に沿って
この置換を直すこと。

使い方:
    python3 patch-find-docs.py <SKILL.md のパス>
"""

from __future__ import annotations

import re
import sys

INSTALL_SECTION_PATTERN = re.compile(
    r"Run commands with `npx ctx7@latest` so setup always uses the latest CLI "
    r"without a global install:\n"
    r"\n"
    r"```bash\n"
    r".*?\n"
    r"```\n"
    r"\n"
    r"Optionally install globally if you prefer a bare `ctx7` command:\n"
    r"\n"
    r"```bash\n"
    r".*?\n"
    r"```\n",
    re.DOTALL,
)

INSTALL_SECTION_REPLACEMENT = (
    "`ctx7` is already installed in this environment (pinned via mise); "
    "run it directly without `npx`.\n"
)


def patch(text: str) -> str:
    new_text, count = INSTALL_SECTION_PATTERN.subn(INSTALL_SECTION_REPLACEMENT, text)
    if count != 1:
        raise ValueError(
            "想定したインストール手順の段落が見つかりませんでした"
            f"（置換 {count} 件、期待値 1 件）。上流の文言が変わった可能性があります。"
        )

    new_text, count = re.subn(r"npx ctx7@latest", "ctx7", new_text)
    if count == 0:
        raise ValueError(
            "`npx ctx7@latest` の置換対象が見つかりませんでした。"
            "上流の文言が変わった可能性があります。"
        )

    for leftover in ("npx ctx7", "ctx7@latest", "npm install -g"):
        if leftover in new_text:
            raise ValueError(
                f"置換後も `{leftover}` が残っています。置換ロジックを見直してください。"
            )

    return new_text


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <SKILL.md のパス>", file=sys.stderr)
        return 2

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        original = f.read()

    try:
        patched = patch(original)
    except ValueError as e:
        print(f"[patch-find-docs] {e}", file=sys.stderr)
        return 1

    with open(path, "w", encoding="utf-8") as f:
        f.write(patched)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
