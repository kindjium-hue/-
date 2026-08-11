#!/usr/bin/env python3
"""세 파일을 합쳐 아임웹 코드위젯에 한 번에 붙여넣는 파일을 만든다.

이 위젯은 게시판 목록을 읽어야 해서 `fetch`를 쓴다. Widget Studio 샌드박스는
외부·내부 통신을 모두 막으므로 **코드위젯(코드 에디터)에만** 넣을 수 있다.

    python3 onefile.py
"""

from __future__ import annotations

from pathlib import Path

from preview import body_of

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / "한번에붙여넣기.html"
OUT_TEXT = BASE_DIR / "아임웹-일정달력-복사용.txt"

HEAD = """<!--
  ┌──────────────────────────────────────────────────────────────┐
  │  청명 일정 달력 — 한 파일 버전 (아임웹 코드위젯용)           │
  └──────────────────────────────────────────────────────────────┘
  아임웹 관리자 → 페이지 편집 → 위젯 추가 → 「코드」 → 코드 에디터 열기 →
  이 파일 내용을 처음부터 끝까지 통째로 붙여넣으세요.

  고칠 곳은 바로 아래 <section ...> 한 줄입니다.
    · data-pin="8282"       접속 번호 (비우면 번호 없이 열립니다)
    · data-board="/board"   일정 게시판 목록 주소 ★ 꼭 사장님 게시판 주소로 바꾸세요
    · data-write=""         글쓰기 주소 (비우면 게시판 주소로 갑니다)
    · data-pages="3"        목록을 몇 페이지까지 읽을지
    · data-works="..."      작업항목 (쉼표로 구분, 색은 앞에서부터 6개까지)
    · data-owners="..."     담당자 (쉼표로 구분)

  게시판 글 제목 규칙 (위젯의 「일정 등록하기」가 자동으로 만들어 줍니다)
    2026-08-14 09:00 | 옥상방수, 누수탐지 | 카카오프렌즈 지곡점 | 송경훈 | 수원 권선구 | 예정

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
