#!/usr/bin/env python3
"""위젯 세 파일을 합쳐 브라우저로 열어 볼 수 있는 한 장짜리 HTML을 만든다.

아임웹은 `{{변수}}`를 설정 패널 값으로 바꿔 렌더링한다. 여기서는 annotation의
`@default`를 그 자리에 넣어 같은 화면을 흉내 낸다.

    python3 preview.py            # widget-preview.html 생성
    python3 preview.py --열기      # 만들고 바로 열기
"""

from __future__ import annotations

import argparse
import re
import shutil
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SEAL_SOURCE = BASE_DIR.parent / "notion-worklog" / "assets" / "seal.png"
OUT = BASE_DIR / "widget-preview.html"

ANNOTATION = re.compile(r"\{\{!--(.*?)--\}\}", re.S)
TOKEN = re.compile(r"\{\{\s*([a-z][a-z0-9-]*)\s*\}\}")


def defaults(html: str) -> dict[str, str]:
    """annotation에서 변수 기본값을 뽑는다."""
    found: dict[str, str] = {}
    for block in ANNOTATION.findall(html):
        name = re.search(r"@name\s+([a-z0-9-]+)", block)
        value = re.search(r'@default\s+("([^"]*)"|\S+)', block)
        if not name:
            continue
        raw = ""
        if value:
            raw = value.group(2) if value.group(2) is not None else value.group(1)
        found[name.group(1)] = (raw or "").strip('"')
    return found


def build() -> Path:
    html = (BASE_DIR / "widget.html").read_text(encoding="utf-8")
    css = (BASE_DIR / "widget.css").read_text(encoding="utf-8")
    js = (BASE_DIR / "widget.js").read_text(encoding="utf-8")

    values = defaults(html)
    if SEAL_SOURCE.exists():
        shutil.copy(SEAL_SOURCE, BASE_DIR / "seal.png")
        values["image-seal"] = "seal.png"

    body = ANNOTATION.sub("", html)
    body = TOKEN.sub(lambda match: values.get(match.group(1), ""), body)

    OUT.write_text(
        "<!doctype html>\n"
        '<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>견적서 위젯 미리보기</title>\n"
        f"<style>\n{css}\n</style>\n</head>\n<body>\n{body}\n"
        f"<script>\n{js}\n</script>\n</body>\n</html>\n",
        encoding="utf-8",
    )
    return OUT


def main() -> int:
    parser = argparse.ArgumentParser(description="위젯 미리보기 파일 만들기")
    parser.add_argument("--열기", "--open", dest="open_it", action="store_true",
                        help="만들고 바로 브라우저로 열기")
    args = parser.parse_args()

    path = build()
    print(f"만들었습니다: {path}")
    print("아임웹에 올리기 전 이 파일을 브라우저로 열어 확인하세요.")
    if args.open_it:
        webbrowser.open(path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
