#!/usr/bin/env python3
"""세 파일을 합쳐 아임웹 코드위젯에 한 번에 붙여넣는 파일을 만든다.

    python3 onefile.py
"""

from __future__ import annotations

from pathlib import Path

from preview import body_of

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / "한번에붙여넣기.html"
OUT_TEXT = BASE_DIR / "아임웹-일정정리달력-복사용.txt"

HEAD = """<!--
  ┌──────────────────────────────────────────────────────────────┐
  │  청명 일정 달력 (아임웹 캘린더 형식) — 한 파일 버전          │
  └──────────────────────────────────────────────────────────────┘
  아임웹 기본 캘린더가 쓰는 일정 자료를 그대로 읽어, 같은 모양의 달력과
  기간별 정리 표로 보여 줍니다. 아임웹 캘린더와 «같은 페이지»에 두세요.

  아임웹 관리자 → 페이지 편집 → 위젯 추가 → 「코드」 → 코드 에디터 열기 →
  이 파일 내용을 처음부터 끝까지 통째로 붙여넣으세요.

  고칠 곳은 바로 아래 <section ...> 한 줄입니다.
    · data-works="..."       작업항목. 일정 제목에서 찾아 배지로 보여 주고 골라 볼 수 있게 합니다
    · data-calendar=""       아임웹 캘린더 페이지 주소 (비우면 이 페이지)
    · data-board-code=""     비워 두면 스스로 찾습니다. 못 찾을 때만 넣으세요

  일정을 고치는 것은 아임웹 캘린더에서 합니다(줄 끝의 «열기»).
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
