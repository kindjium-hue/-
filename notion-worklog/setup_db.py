#!/usr/bin/env python3
"""노션에 '현장 업무' 데이터베이스를 만들어 준다.

파이썬 표준 라이브러리만 쓰므로 `pip install` 없이 바로 실행할 수 있다.
맥이면 `노션DB만들기.command`를 더블클릭하면 이 파일이 대화식으로 돌아간다.

    python3 setup_db.py                                    # 물어보면서 진행
    python3 setup_db.py --parent-page https://notion.so/…  # 새 DB 만들기
    python3 setup_db.py --database <DB URL 또는 ID>         # 기존 DB에 빠진 속성만 추가
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import notion_lite as nl

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

NEXT_STEPS = """
─────────────────────────────────────────────
노션 앱에서 아래 세 가지만 손으로 해 주세요. (뷰는 API로 만들 수 없습니다)

1. 보드 뷰   : 새 보기 → 보드 → 그룹 기준 `진행상태`
               → 접수 / 견적 / 예정 / 진행중 / 완료 칸반이 됩니다
               (그룹 기준을 `작업항목`으로 두면 누수탐지·옥상방수별로 나뉩니다)
2. 캘린더 뷰 : 새 보기 → 캘린더 → 날짜 기준 `작업일`
               → 이번 주 현장 일정이 한눈에 보입니다
3. 갤러리 뷰 : 새 보기 → 갤러리 → 카드 미리보기를 `BEFORE`로
               → 시공 전 사진이 카드 표지로 뜹니다
               (본문에 넣은 사진을 쓰려면 `페이지 콘텐츠`를 고르세요)

공유는 DB 페이지 우측 상단 `공유`에서 직원을 초대하면 됩니다.
거래처에는 `웹에 게시`로 열람 전용 링크를 보낼 수 있습니다.

사진과 견적서는 지금은 노션 앱에서 직접 올리시면 됩니다.
`BEFORE`·`AFTER` 칸에 시공 전후 사진을 나눠 올려 두면 비교하기 좋습니다.
휴대폰 웹 폼으로 자동 등록하려면 README.md의 5단계를 보세요.
─────────────────────────────────────────────"""


def main() -> int:
    parser = argparse.ArgumentParser(description="현장 업무 노션 DB 생성/보정")
    parser.add_argument("--parent-page", help="DB를 만들 상위 페이지 URL 또는 ID")
    parser.add_argument("--database", help="이미 있는 DB에 빠진 속성만 추가")
    parser.add_argument("--title", default="현장 업무", help="새로 만들 DB 제목")
    parser.add_argument("--token", help="노션 integration 토큰 (없으면 .env 또는 입력)")
    args = parser.parse_args()

    token = args.token or os.getenv("NOTION_TOKEN") or nl.read_env(ENV_PATH).get("NOTION_TOKEN", "")
    interactive = not (args.parent_page or args.database)

    if interactive:
        print("현장 업무 노션 데이터베이스를 만듭니다.\n")
        print("먼저 준비하실 것 두 가지 (자세한 절차는 README.md 1~2단계):")
        print("  1) notion.so/my-integrations 에서 만든 토큰 (ntn_ 로 시작)")
        print("  2) DB를 담을 노션 페이지 URL — 그 페이지 ··· → 연결 에서 integration을 추가해 두세요\n")

    if not token:
        token = getpass.getpass("노션 토큰 (입력해도 화면에 보이지 않습니다): ").strip()
    if not token:
        print("토큰이 없으면 진행할 수 없습니다.", file=sys.stderr)
        return 1

    parent = args.parent_page
    if not parent and not args.database:
        parent = input("노션 페이지 URL: ").strip()
    if not parent and not args.database:
        print("페이지 URL이 없으면 진행할 수 없습니다.", file=sys.stderr)
        return 1

    try:
        if args.database:
            return patch_database(token, nl.normalize_id(args.database))
        return create_database(token, nl.normalize_id(parent), args.title, offer_env=interactive)
    except nl.NotionHttpError as error:
        print(f"\n실패: {error}", file=sys.stderr)
        if error.status in (401, 403):
            print("토큰이 맞는지 확인해 주세요.", file=sys.stderr)
        elif error.status == 404:
            print(
                "그 페이지를 integration에 연결하지 않았을 수 있습니다.\n"
                "노션에서 페이지 우측 상단 ··· → 연결 → 만든 integration을 선택한 뒤 다시 실행하세요.",
                file=sys.stderr,
            )
        return 1


def create_database(token: str, parent_page_id: str, title: str, *, offer_env: bool) -> int:
    database = nl.request(
        token,
        "POST",
        "/databases",
        {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": nl.rich_text(title),
            "properties": nl.SCHEMA,
        },
    )
    database_id = database["id"].replace("-", "")

    print(f"\n데이터베이스를 만들었습니다: {database.get('url', '(URL 없음)')}")
    print("속성: " + ", ".join(nl.SCHEMA))

    saved = False
    if offer_env:
        answer = input("\n토큰과 DB ID를 .env에 저장할까요? (나중에 웹 폼에 필요합니다) [Y/n] ").strip()
        saved = answer.lower() not in ("n", "no")
    if saved:
        nl.write_env(ENV_PATH, {"NOTION_TOKEN": token, "NOTION_DATABASE_ID": database_id})
        print(f"저장했습니다: {ENV_PATH}")
    else:
        print("\n.env에 아래 줄을 넣어 두세요:\n")
        print(f"NOTION_DATABASE_ID={database_id}")

    print(NEXT_STEPS)
    return 0


def patch_database(token: str, database_id: str) -> int:
    existing = nl.request(token, "GET", f"/databases/{database_id}").get("properties") or {}
    missing = {}
    for name, definition in nl.SCHEMA.items():
        if name in existing:
            continue
        if "title" in definition or "created_time" in definition:
            # title은 DB마다 하나뿐이고, created_time은 이름만 다를 수 있어 건너뛴다.
            print(f"건너뜀: '{name}' — 기존 DB의 같은 역할 속성을 그대로 쓰세요.")
            continue
        missing[name] = definition

    if not missing:
        print("추가할 속성이 없습니다. 그대로 쓰면 됩니다.")
        return 0

    nl.request(token, "PATCH", f"/databases/{database_id}", {"properties": missing})
    print("추가한 속성: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
