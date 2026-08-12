#!/usr/bin/env python3
"""세 파일을 합쳐 아임웹 코드위젯에 한 번에 붙여넣는 파일을 만든다.

    python3 onefile.py
"""

from __future__ import annotations

from pathlib import Path

from preview import body_of

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / "한번에붙여넣기.html"
OUT_TEXT = BASE_DIR / "아임웹-작업현황폼-복사용.txt"

HEAD = """<!--
  ┌──────────────────────────────────────────────────────────────┐
  │  청명 작업현황 작성 폼 — 한 파일 버전 (아임웹 코드위젯용)    │
  └──────────────────────────────────────────────────────────────┘
  아임웹 관리자 → 페이지 편집 → 위젯 추가 → 「코드」 → 코드 에디터 열기 →
  이 파일 내용을 처음부터 끝까지 통째로 붙여넣으세요.

  쓰는 법
    1) 이 폼을 채운다
    2) ① 제목 복사 → 아임웹 일정의 «상세 일정» 제목 칸에 붙여넣기
    3) ② HTML 복사 → 본문 도구막대의 </> 를 누르고 붙여넣은 뒤 다시 </> 로 돌아오기
    4) BEFORE·AFTER 자리에 사진을 넣고 저장

  고칠 곳은 바로 아래 <section ...> 한 줄입니다.
    · data-works="..."     작업항목 (쉼표로 구분)
    · data-owners="..."    담당자 (쉼표로 구분)
    · data-states="..."    진행상태 (쉼표로 구분)
    · data-calendar=""     일정 달력 페이지 주소 (넣으면 «일정 달력 열기» 링크가 보입니다)

  widget.html · widget.css · widget.js 를 합쳐 만든 파일입니다.
  세 파일을 고친 뒤 `python3 onefile.py` 를 다시 실행하면 새로 만들어집니다.
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
