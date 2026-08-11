#!/usr/bin/env python3
"""세 파일을 합쳐 아임웹 「HTML 삽입」 블록에 한 번에 붙여넣는 파일을 만든다.

Widget Studio는 HTML/CSS/JS 탭이 따로라 한 번에 붙여넣을 수 없다. 대신 아임웹
페이지 편집기의 HTML 블록에는 <style>·<script>가 들어간 코드를 통째로 넣을 수
있으므로, 설정 패널 값(`{{변수}}`)은 annotation의 `@default`로 채워 넣고 도장
그림은 파일 안에 박아 한 덩어리로 만든다.

    python3 onefile.py
"""

from __future__ import annotations

import base64
from pathlib import Path

from preview import ANNOTATION, TOKEN, defaults

BASE_DIR = Path(__file__).resolve().parent
SEAL = BASE_DIR.parent / "notion-worklog" / "assets" / "seal.png"
OUT = BASE_DIR / "한번에붙여넣기.html"

HEAD = """<!--
  ┌──────────────────────────────────────────────────────────────┐
  │  청명 견적서 위젯 — 한 파일 버전                             │
  └──────────────────────────────────────────────────────────────┘
  아임웹 관리자 → 페이지 편집 → 위젯 추가 → 「HTML」(코드 삽입) 블록에
  이 파일 내용을 처음부터 끝까지 통째로 붙여넣으세요. PC·모바일 겸용입니다.

  고칠 곳은 바로 아래 <section ...> 한 줄뿐입니다.
    · data-pin="8282"          접속 번호 (비우면 번호 없이 열립니다)
    · data-form-url=""         웹 폼 주소를 넣으면 "웹 폼 열기" 링크가 보입니다
    · data-roof-*  data-wall-* 평당 단가와 1식 금액 (원, 숫자만)

  이 파일은 widget.html · widget.css · widget.js 를 합쳐 만든 것입니다.
  세 파일을 고친 뒤 `python3 onefile.py` 를 다시 실행하면 새로 만들어집니다.
-->
"""


def build() -> Path:
    html = (BASE_DIR / "widget.html").read_text(encoding="utf-8")
    css = (BASE_DIR / "widget.css").read_text(encoding="utf-8")
    js = (BASE_DIR / "widget.js").read_text(encoding="utf-8")

    values = defaults(html)
    if SEAL.exists():
        data = base64.b64encode(SEAL.read_bytes()).decode("ascii")
        values["image-seal"] = f"data:image/png;base64,{data}"

    body = ANNOTATION.sub("", html).strip()
    body = TOKEN.sub(lambda match: values.get(match.group(1), ""), body)

    # 아임웹 HTML 블록은 위젯 편집기와 달리 스크립트를 따로 감싸 주지 않는다.
    # 중괄호로 묶어 const 이름이 사이트의 다른 스크립트와 부딪히지 않게 한다.
    OUT.write_text(
        f"{HEAD}\n<style>\n{css.strip()}\n</style>\n\n{body}\n\n"
        f"<script>\n{{\n{js.strip()}\n}}\n</script>\n",
        encoding="utf-8",
    )
    return OUT


def main() -> int:
    path = build()
    print(f"만들었습니다: {path}")
    print(f"{len(path.read_text(encoding='utf-8')):,}자 — 이 파일 내용을 통째로 붙여넣으면 됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
