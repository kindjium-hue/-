#!/usr/bin/env python3
"""세 파일을 합쳐 아임웹 코드위젯에 한 번에 붙여넣는 파일을 만든다.

    python3 onefile.py
"""

from __future__ import annotations

from pathlib import Path

from preview import body_of

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / "한번에붙여넣기.html"
OUT_TEXT = BASE_DIR / "아임웹-조사도구-복사용.txt"

HEAD = """<!--
  ┌──────────────────────────────────────────────────────────────┐
  │  아임웹 캘린더 조사 도구 — 잠시만 올려 두는 위젯             │
  └──────────────────────────────────────────────────────────────┘
  캘린더가 있는 페이지에 코드위젯으로 올려 두고, 캘린더에서 시험용 일정을
  «추가»하고 «수정»해 보세요. 그 사이 오간 통신과 화면 구조를 정리해 보여 줍니다.
  「결과 복사」를 눌러 그대로 알려 주시면 정리 위젯을 정확히 만들 수 있습니다.

  확인이 끝나면 이 위젯은 지우세요.

  쿠키·비밀번호·토큰은 수집하지 않습니다. 주소와 항목 이름, 값의 길이만 적습니다.
-->
"""


def build() -> Path:
    html = (BASE_DIR / "widget.html").read_text(encoding="utf-8")
    css = (BASE_DIR / "widget.css").read_text(encoding="utf-8")
    js = (BASE_DIR / "widget.js").read_text(encoding="utf-8")

    # 코드위젯은 위젯 편집기와 달리 스크립트를 따로 감싸 주지 않는다.
    # 중괄호로 묶어 const 이름이 사이트의 다른 스크립트와 부딪히지 않게 한다.
    code = (
        f"{HEAD}\n<style>\n{css.strip()}\n</style>\n\n{body_of(html)}\n\n"
        f"<script>\n{{\n{js.strip()}\n}}\n</script>\n"
    )
    OUT.write_text(code, encoding="utf-8")
    OUT_TEXT.write_text(code, encoding="utf-8")
    return OUT


def main() -> int:
    path = build()
    print(f"만들었습니다: {path}")
    print(f"복사용 텍스트: {OUT_TEXT}")
    print(f"{len(path.read_text(encoding='utf-8')):,}자 — 이 내용을 통째로 붙여넣으면 됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
