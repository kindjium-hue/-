#!/usr/bin/env python3
"""노션에 '현장 업무' 데이터베이스를 만들어 준다.

먼저 노션에서 아무 페이지나 하나 만들고, 그 페이지를 integration에 공유한 다음
그 페이지 URL을 넘기면 된다. 자세한 절차는 README.md 참고.

    python setup_db.py --parent-page https://www.notion.so/...

이미 만든 DB에 빠진 속성만 채우고 싶으면:

    python setup_db.py --database <DB URL 또는 ID>
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

import notion_api as na

BASE_DIR = Path(__file__).resolve().parent

STATUS_OPTIONS = [
    {"name": "접수", "color": "default"},
    {"name": "견적", "color": "yellow"},
    {"name": "예정", "color": "blue"},
    {"name": "진행중", "color": "orange"},
    {"name": "완료", "color": "green"},
    {"name": "보류", "color": "red"},
]

# 폼이 쓰는 속성 이름은 app.py의 FIELD_* 상수와 맞아야 한다.
SCHEMA = {
    "현장명": {"title": {}},
    "진행상태": {"select": {"options": STATUS_OPTIONS}},
    "작업일": {"date": {}},
    "담당자": {"select": {"options": []}},
    "주소": {"rich_text": {}},
    "연락처": {"phone_number": {}},
    "면적": {"number": {"format": "number"}},
    "견적금액": {"number": {"format": "won"}},
    "견적서": {"files": {}},
    "등록시각": {"created_time": {}},
}


def main() -> int:
    load_dotenv(BASE_DIR / ".env")

    parser = argparse.ArgumentParser(description="현장 업무 노션 DB 생성/보정")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--parent-page", help="DB를 만들 상위 페이지 URL 또는 ID")
    group.add_argument("--database", help="이미 있는 DB에 빠진 속성만 추가")
    parser.add_argument("--title", default="현장 업무", help="새로 만들 DB 제목")
    args = parser.parse_args()

    token = os.getenv("NOTION_TOKEN", "").strip()
    if not token:
        print("NOTION_TOKEN이 없습니다. .env에 넣거나 환경변수로 지정하세요.", file=sys.stderr)
        return 1

    notion = na.Notion(token)
    try:
        if args.database:
            return patch_database(notion, na.normalize_id(args.database))
        return create_database(notion, na.normalize_id(args.parent_page), args.title)
    except na.NotionError as error:
        print(f"실패: {error}", file=sys.stderr)
        if error.status in (401, 404):
            print(
                "\n토큰이 틀렸거나, 해당 페이지/DB를 integration에 공유하지 않았을 수 있습니다.\n"
                "노션에서 페이지 우측 상단 ··· → 연결 → 만든 integration을 선택해 주세요.",
                file=sys.stderr,
            )
        return 1
    finally:
        notion.close()


def create_database(notion: na.Notion, parent_page_id: str, title: str) -> int:
    database = notion.create_database(parent_page_id, title, SCHEMA)
    database_id = database["id"].replace("-", "")
    print(f"DB를 만들었습니다: {database.get('url', '(URL 없음)')}")
    print("\n.env에 아래 줄을 넣으세요:\n")
    print(f"NOTION_DATABASE_ID={database_id}")
    return 0


def patch_database(notion: na.Notion, database_id: str) -> int:
    existing = notion.database(database_id).get("properties") or {}
    missing = {}
    for name, definition in SCHEMA.items():
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

    notion.update_database(database_id, missing)
    print("추가한 속성: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
