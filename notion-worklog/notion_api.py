"""Notion REST API 얇은 래퍼.

이 프로젝트에 필요한 것만 담았다.
- 파일 업로드(단일/멀티파트) → 사진·견적서를 노션에 직접 올린다
- 데이터베이스 조회·질의, 페이지 생성·수정, 블록 추가
- 데이터베이스 생성(setup_db.py에서 사용)

Notion 파일 업로드는 3단계다.
1. POST /file_uploads          업로드 자리를 만든다 (id 발급)
2. POST /file_uploads/{id}/send  실제 바이트를 보낸다 (멀티파트면 여러 번)
3. 발급받은 id를 파일 속성이나 이미지/파일 블록에 붙인다
"""

from __future__ import annotations

import math
import mimetypes
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import httpx

from notion_lite import API_BASE, NOTION_VERSION, normalize_id  # noqa: F401 (재수출)

# 20MB까지는 한 번에, 그보다 크면 멀티파트로 쪼개 올린다.
SINGLE_PART_LIMIT = 20 * 1024 * 1024
PART_SIZE = 10 * 1024 * 1024

# 노션 rich_text 한 조각의 글자 수 상한
TEXT_CHUNK = 1900

# 블록 추가는 한 번에 100개까지
BLOCK_BATCH = 100


class NotionError(RuntimeError):
    """노션이 4xx/5xx를 돌려줬을 때."""

    def __init__(self, status: int, payload: Any):
        self.status = status
        self.payload = payload
        message = payload.get("message") if isinstance(payload, dict) else None
        super().__init__(message or f"노션 API 오류 (HTTP {status})")


@dataclass(frozen=True)
class Upload:
    """업로드가 끝난 파일. id를 속성/블록에 붙여 쓴다."""

    id: str
    name: str


class Notion:
    def __init__(self, token: str, *, timeout: float = 180.0):
        if not token:
            raise ValueError("NOTION_TOKEN이 비어 있습니다.")
        self._http = httpx.Client(
            base_url=API_BASE,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
            },
        )

    def close(self) -> None:
        self._http.close()

    def _call(self, method: str, path: str, **kwargs: Any) -> dict:
        response = self._http.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = {"message": response.text[:500]}
            raise NotionError(response.status_code, payload)
        return response.json()

    # ------------------------------------------------------------------ 파일

    def upload(self, filename: str, data: bytes, content_type: str | None = None) -> Upload:
        """바이트를 노션에 올리고 첨부에 쓸 수 있는 업로드 id를 돌려준다."""
        content_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

        if len(data) <= SINGLE_PART_LIMIT:
            created = self._call(
                "POST",
                "/file_uploads",
                json={"filename": filename, "content_type": content_type},
            )
            self._send_part(created["id"], filename, content_type, data)
        else:
            parts = math.ceil(len(data) / PART_SIZE)
            created = self._call(
                "POST",
                "/file_uploads",
                json={
                    "filename": filename,
                    "content_type": content_type,
                    "mode": "multi_part",
                    "number_of_parts": parts,
                },
            )
            for index in range(parts):
                chunk = data[index * PART_SIZE : (index + 1) * PART_SIZE]
                self._send_part(created["id"], filename, content_type, chunk, part_number=index + 1)
            self._call("POST", f"/file_uploads/{created['id']}/complete")

        return Upload(id=created["id"], name=filename)

    def _send_part(
        self,
        upload_id: str,
        filename: str,
        content_type: str,
        chunk: bytes,
        part_number: int | None = None,
    ) -> None:
        self._call(
            "POST",
            f"/file_uploads/{upload_id}/send",
            files={"file": (filename, chunk, content_type)},
            data={"part_number": str(part_number)} if part_number else None,
        )

    # -------------------------------------------------------------- 데이터베이스

    def database(self, database_id: str) -> dict:
        return self._call("GET", f"/databases/{database_id}")

    def create_database(self, parent_page_id: str, title: str, properties: dict) -> dict:
        return self._call(
            "POST",
            "/databases",
            json={
                "parent": {"type": "page_id", "page_id": parent_page_id},
                "title": rich_text(title),
                "properties": properties,
            },
        )

    def update_database(self, database_id: str, properties: dict) -> dict:
        return self._call("PATCH", f"/databases/{database_id}", json={"properties": properties})

    def query(self, database_id: str, **body: Any) -> dict:
        return self._call("POST", f"/databases/{database_id}/query", json=body)

    # ------------------------------------------------------------------ 페이지

    def create_page(
        self,
        database_id: str,
        properties: dict,
        children: Sequence[dict] | None = None,
    ) -> dict:
        children = list(children or [])
        page = self._call(
            "POST",
            "/pages",
            json={
                "parent": {"database_id": database_id},
                "properties": properties,
                "children": children[:BLOCK_BATCH],
            },
        )
        if len(children) > BLOCK_BATCH:
            self.append_blocks(page["id"], children[BLOCK_BATCH:])
        return page

    def page(self, page_id: str) -> dict:
        return self._call("GET", f"/pages/{page_id}")

    def update_page(self, page_id: str, properties: dict) -> dict:
        return self._call("PATCH", f"/pages/{page_id}", json={"properties": properties})

    def append_blocks(self, page_id: str, children: Sequence[dict]) -> None:
        for start in range(0, len(children), BLOCK_BATCH):
            self._call(
                "PATCH",
                f"/blocks/{page_id}/children",
                json={"children": list(children[start : start + BLOCK_BATCH])},
            )


# --------------------------------------------------------------- 블록·속성 헬퍼


def rich_text(text: str) -> list[dict]:
    """긴 글은 노션 글자 수 제한에 맞춰 여러 조각으로 나눈다."""
    text = text or ""
    if not text:
        return []
    return [
        {"type": "text", "text": {"content": text[i : i + TEXT_CHUNK]}}
        for i in range(0, len(text), TEXT_CHUNK)
    ]


def paragraphs(text: str) -> list[dict]:
    """줄바꿈 기준으로 문단 블록 목록을 만든다. 빈 줄은 건너뛴다."""
    blocks: list[dict] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": rich_text(line)},
            }
        )
    return blocks


def heading(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {"rich_text": rich_text(text)},
    }


def divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def image_block(upload: Upload, caption: str = "") -> dict:
    return {
        "object": "block",
        "type": "image",
        "image": {
            "type": "file_upload",
            "file_upload": {"id": upload.id},
            "caption": rich_text(caption),
        },
    }


def file_block(upload: Upload) -> dict:
    return {
        "object": "block",
        "type": "file",
        "file": {
            "type": "file_upload",
            "file_upload": {"id": upload.id},
            "name": upload.name,
        },
    }


def files_property(uploads: Iterable[Upload]) -> dict:
    return {
        "files": [
            {"type": "file_upload", "file_upload": {"id": u.id}, "name": u.name}
            for u in uploads
        ]
    }


# ------------------------------------------------------------------ 값 꺼내기


def plain(prop: dict | None) -> str:
    """속성 하나에서 사람이 읽을 문자열을 뽑아낸다."""
    if not prop:
        return ""
    kind = prop.get("type")
    if kind in ("title", "rich_text"):
        return "".join(part.get("plain_text", "") for part in prop.get(kind) or [])
    if kind == "select":
        return (prop.get("select") or {}).get("name", "")
    if kind == "multi_select":
        return ", ".join(option.get("name", "") for option in prop.get("multi_select") or [])
    if kind == "status":
        return (prop.get("status") or {}).get("name", "")
    if kind == "phone_number":
        return prop.get("phone_number") or ""
    if kind == "number":
        value = prop.get("number")
        return "" if value is None else f"{value:,.0f}"
    if kind == "date":
        date = prop.get("date") or {}
        start, end = date.get("start", ""), date.get("end")
        return f"{start} ~ {end}" if end else start
    if kind == "files":
        return ", ".join(item.get("name", "") for item in prop.get("files") or [])
    if kind in ("created_time", "last_edited_time"):
        return (prop.get(kind) or "")[:10]
    return ""


def select_options(schema: dict, name: str) -> list[str]:
    """DB 스키마에서 select 속성의 선택지 이름 목록을 꺼낸다."""
    prop = (schema.get("properties") or {}).get(name) or {}
    if prop.get("type") == "select":
        return [option["name"] for option in (prop.get("select") or {}).get("options", [])]
    if prop.get("type") == "status":
        return [option["name"] for option in (prop.get("status") or {}).get("options", [])]
    return []
