#!/usr/bin/env python3
"""draw.io のサイドバーの図形パレット（VS Code の draw.io 拡張の図形パレットと同じもの）を、
パレットごとに d-png-cli のライブラリにし、`d-png-cli library pack` で取得元（file:）に置く。

d-png-cli は v0.2.0 で組み込みのライブラリ（開発版の `drawio/aws4-compute` など）を廃止し、
図形はライブラリにして登録する方式になった。リポジトリにはライブラリを置かず、イメージの
ビルド時に、/opt/drawio-webapp（DRAWIO_WEBAPP_COMMIT。拡張 1.9.0 と同じ draw.io 26.0.2）の
サイドバーのコードをヘッドレスの Chrome で動かして作る。方法は d-png-cli の開発版にあった
生成スクリプト（scripts/shape_catalog.py。v0.2.0 で削除）と同じ。

- ライブラリ名はパレットの ID から作る（`aws4Compute` → `aws4-compute`）。版は draw.io の版。
- 開発版と違い、図に埋め込まれた画像（data:image。Google Cloud・SAP のアイコンなど）の
  エントリーも含める。拡張のパレットにあるものと同じにするため。
- Web 資材に無い画像（img/...）や、上流に定義の無いステンシルを使うエントリーは除く
  （拡張でも描けず、d-png-cli では ASSET_MISSING になるため）。

使い方（Dockerfile の ai ステージから呼ぶ）:
    python3 -I build-drawio-libraries.py --webapp /opt/drawio-webapp \\
        --chrome /opt/google/chrome/chrome --scope drawio --to /opt/d-png-libraries
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

# サイドバーが名前を出しているが、固定した版の draw.io に定義が無いステンシル。
UPSTREAM_MISSING = ("mxgraph.aws4.piop",)

# mxResources のキーのままになるパレットの表示名（resources/dia.txt の英語の値）。
# 生成ページは draw.io の文言の資材を読まないため、ここで補う。
RESOURCE_TITLES = {
    "advanced": "Advanced",
    "android": "Android",
    "archiMate21": "ArchiMate 2.1",
    "arrows": "Arrows",
    "azure": "Azure",
    "basic": "Basic",
    "bootstrap": "Bootstrap",
    "cabinets": "Cabinets",
    "entityRelation": "Entity Relation",
    "floorplans": "Floorplans",
    "flowchart": "Flowchart",
    "general": "General",
    "misc": "Misc",
    "uml": "UML",
}

# 生成できたことを確かめるライブラリ（サイドバーの作りが変わって空になったときに気づくため）。
REQUIRED = (
    "general", "arrows", "flowchart", "aws4-compute", "aws4-groups", "azure2-compute",
    "gcp2-compute", "kubernetes", "cisco-routers", "signs-safety", "rack-cisco", "pid-pumps",
)

NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def run_sidebar(webapp: Path, chrome: str, work: Path) -> dict:
    """サイドバーのパレットを作るページを Chrome で開き、書き出した JSON を返す。"""
    template = Path(__file__).with_name("drawio-sidebar.html").read_text(encoding="utf-8")
    base = '<base href="{}/">'.format(html.escape(webapp.resolve().as_uri(), quote=True))
    page = work / "drawio-sidebar.html"
    page.write_text(template.replace("<head>", "<head>\n" + base, 1), encoding="utf-8")
    proc = subprocess.run(
        [
            chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
            "--no-first-run", "--disable-background-networking", "--disable-component-update",
            "--disable-sync", "--disable-extensions",
            # ページはローカルの資材だけを読む。外部への名前解決はすべて失敗させる。
            "--host-resolver-rules=MAP * ~NOTFOUND",
            "--user-data-dir=" + str(work / "profile"),
            "--allow-file-access-from-files",
            "--dump-dom", page.as_uri(),
        ],
        # Chrome がホーム（~/.pki など）に書くものをイメージに残さない。
        env={**os.environ, "HOME": str(work)},
        capture_output=True, text=True, timeout=600,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(f"Chrome が失敗しました（終了コード {proc.returncode}）")
    match = re.search(r'<pre id="out">(.*?)</pre>', proc.stdout, re.DOTALL)
    if not match or not match.group(1):
        sys.exit("サイドバーのページが何も出力しませんでした")
    result = json.loads(html.unescape(match.group(1)))
    if result["errors"]:
        sys.exit("サイドバーのパレットを作れませんでした:\n" + "\n".join(result["errors"]))
    return result


def slug(palette_id: str) -> str:
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", palette_id)
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def title_of(entry: dict) -> str:
    """サイドバーのタイトル。無ければ最初のセルのラベル、それも無ければ図形・画像の名前。"""
    if text(entry["title"]):
        return text(entry["title"])
    label = re.match(r'<(?:mxCell|object|UserObject)\b[^>]*?\s(?:value|label)="([^"]*)"', entry["xml"])
    if label:
        plain = text(re.sub(r"<[^>]*>", " ", html.unescape(html.unescape(label.group(1)))))
        if plain:
            return plain if len(plain) <= 60 else plain[:59].rstrip() + "…"
    style = re.search(r'style="([^"]*)"', entry["xml"])
    name = re.search(r"(?:^|;)(?:image|shape)=([^;]+)", html.unescape(style.group(1))) if style else None
    if name and not name.group(1).startswith("data:"):
        last = re.split(r"[/.]", re.sub(r"(_\d+x\d+)?\.(png|svg|jpe?g|gif)$", "", name.group(1)))[-1]
        return text(last.replace("_", " "))
    return ""


def size(value) -> float:
    return value if isinstance(value, (int, float)) and value > 0 else 0


def missing_image(webapp: Path, xml: str) -> str | None:
    """セルの style が名前を出している Web 資材の画像（img/...）のうち、無いもの。"""
    for style in re.findall(r'style="([^"]*)"', xml):
        # draw.io と同じく、1 つの style では最後の image= が効く。
        found = re.findall(r"(?:^|;)image=([^;]*)", html.unescape(style))
        if found and found[-1].startswith("img/") and not (webapp / found[-1]).is_file():
            return found[-1]
    return None


def library_xml(title: str, entries: list[dict]) -> str:
    """d-png-cli の登録ファイルの書式（仕様 9.3）で書く。library pack が正規化し直す。"""
    lines = []
    for entry in entries:
        line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
        lines.append(line.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    return "<mxlibrary title={}>[\n{}\n]</mxlibrary>\n".format(quoteattr(title), ",\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--webapp", required=True, type=Path, help="draw.io の Web 資材（src/main/webapp）")
    parser.add_argument("--chrome", required=True, help="Chrome の実行ファイル（ラッパーではなく実体）")
    parser.add_argument("--scope", required=True, help="ライブラリのスコープ（例: drawio）")
    parser.add_argument("--to", required=True, type=Path, help="取得元のディレクトリ（library pack --to）")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        result = run_sidebar(args.webapp, args.chrome, work)
        version = result["version"]
        names: set[str] = set()
        total = skipped = 0
        for palette in result["palettes"]:
            # 引数を渡さずに作ったパレットは、style や大きさが壊れる。
            if any(re.search(r'undefined|="NaN"', e["xml"]) for e in palette["entries"]):
                sys.exit(f"{palette['id']}: パレットが引数なしで作られました")
            entries = []
            for e in palette["entries"]:
                image = missing_image(args.webapp, e["xml"])
                stencil = next((n for n in UPSTREAM_MISSING if n in e["xml"]), None)
                if image or stencil:
                    print(f"note: {palette['id']} の {e['title']!r} を除きました"
                          f"（上流に {image or stencil} がありません）", file=sys.stderr)
                    skipped += 1
                    continue
                # ページはセルだけを書き出すため、基盤セル（0・1）で包んで <mxGraphModel> にする。
                entries.append({
                    "title": title_of(e),
                    "w": size(e.get("w")),
                    "h": size(e.get("h")),
                    "xml": '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
                           + e["xml"] + "</root></mxGraphModel>",
                })
            if not entries:
                continue
            name = slug(palette["id"])
            if not NAME_PATTERN.match(name) or name in names:
                sys.exit(f"{palette['id']}: ライブラリ名 {name!r} が不正か重複しています")
            names.add(name)
            title = RESOURCE_TITLES.get(palette["title"], text(palette["title"])) or name
            source = work / f"{name}.xml"
            source.write_text(library_xml(title, entries), encoding="utf-8")
            subprocess.run(
                ["d-png-cli", "library", "pack", str(source), "--name", f"@{args.scope}/{name}",
                 "--version", version, "--to", str(args.to)],
                check=True, stdout=subprocess.DEVNULL,
            )
            total += len(entries)
        missing = [n for n in REQUIRED if n not in names]
        if missing:
            sys.exit("生成されなかったライブラリがあります: " + ", ".join(missing))
        print(f"@{args.scope}: draw.io {version} の {len(names)} パレット、{total} 図形"
              f"（除外 {skipped}）を {args.to} に置きました")


if __name__ == "__main__":
    main()
