"""추가 설치 없이(파이썬 표준 라이브러리만으로) 노션을 쓰는 최소 도구.

`pip install` 없이도 데이터베이스를 만들 수 있어야 해서 이 파일만 표준 라이브러리로 두었다.
사진·견적서 업로드처럼 무거운 일은 `notion_api.py`(httpx)가 담당한다.

여기 있는 것:
- `request()`     노션 REST 호출 (urllib)
- `normalize_id()` 노션 URL에서 32자리 id 뽑기
- `SCHEMA`        현장 업무 데이터베이스 속성 정의 (app.py의 FIELD_* 와 맞아야 한다)
- `read_env()` / `write_env()`  아주 단순한 .env 읽기·쓰기
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

STATUS_OPTIONS = [
    {"name": "접수", "color": "default"},
    {"name": "견적", "color": "yellow"},
    {"name": "예정", "color": "blue"},
    {"name": "진행중", "color": "orange"},
    {"name": "완료", "color": "green"},
    {"name": "보류", "color": "red"},
]

WORK_TYPE_OPTIONS = [
    {"name": "누수탐지", "color": "purple"},
    {"name": "누수피해복구", "color": "pink"},
    {"name": "하수구막힘", "color": "brown"},
    {"name": "옥상방수", "color": "blue"},
    {"name": "외벽방수", "color": "green"},
    {"name": "기타", "color": "default"},
]

SCHEMA = {
    "현장명": {"title": {}},
    "작업항목": {"select": {"options": WORK_TYPE_OPTIONS}},
    "진행상태": {"select": {"options": STATUS_OPTIONS}},
    "작업일": {"date": {}},
    "담당자": {"select": {"options": []}},
    "주소": {"rich_text": {}},
    "연락처": {"phone_number": {}},
    "면적": {"number": {"format": "number"}},
    "견적서": {"files": {}},
    "BEFORE": {"files": {}},
    "AFTER": {"files": {}},
    "등록시각": {"created_time": {}},
}


class NotionHttpError(RuntimeError):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(message or f"노션 API 오류 (HTTP {status})")


def request(token: str, method: str, path: str, payload: dict | None = None) -> dict:
    """노션 REST 호출. 표준 라이브러리만 쓴다."""
    body = json.dumps(payload).encode() if payload is not None else None
    call = urllib.request.Request(
        f"{API_BASE}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(call, timeout=60) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            message = json.loads(raw).get("message", "")
        except (ValueError, AttributeError):
            message = raw[:300].decode(errors="replace")
        raise NotionHttpError(error.code, message) from None
    except urllib.error.URLError as error:
        raise NotionHttpError(0, f"노션에 연결하지 못했습니다 ({error.reason})") from None


def normalize_id(raw: str) -> str:
    """노션 URL이나 하이픈 있는 id에서 32자리 id를 뽑아낸다."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    if "notion.so" in raw or raw.startswith("http"):
        raw = raw.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
        raw = raw.rsplit("-", 1)[-1]
    return raw.replace("-", "")


def rich_text(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text}}] if text else []


def read_env(path: str | Path) -> dict[str, str]:
    path = Path(path)
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def write_env(path: str | Path, updates: dict[str, str]) -> None:
    """.env의 기존 줄·주석을 유지하면서 주어진 키만 바꾸거나 추가한다."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.partition("=")[0].strip()
        if key in remaining:
            lines[index] = f"{key}={remaining.pop(key)}"

    for key, value in remaining.items():
        lines.append(f"{key}={value}")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
