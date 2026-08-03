"""노션 API를 대신하는 가짜 서버로 폼 흐름을 점검한다.

    python3 -m unittest test_app -v
"""

from __future__ import annotations

import io
import json
import os
import unittest

os.environ.setdefault("NOTION_TOKEN", "test-token")
os.environ.setdefault("NOTION_DATABASE_ID", "d" * 32)
os.environ.setdefault("WORKLOG_ACCESS_CODE", "")

import httpx
from fastapi.testclient import TestClient
from PIL import Image

import app as worklog
import notion_api as na

DB_SCHEMA = {
    "id": "d" * 32,
    "url": "https://www.notion.so/" + "d" * 32,
    "properties": {
        "현장명": {"type": "title", "title": {}},
        "진행상태": {
            "type": "select",
            "select": {"options": [{"name": "예정"}, {"name": "진행중"}, {"name": "완료"}]},
        },
        "작업일": {"type": "date", "date": {}},
        "담당자": {"type": "select", "select": {"options": [{"name": "김기사"}]}},
        "주소": {"type": "rich_text", "rich_text": {}},
        "연락처": {"type": "phone_number", "phone_number": {}},
        "견적금액": {"type": "number", "number": {"format": "won"}},
        "견적서": {"type": "files", "files": {}},
    },
}

PAGE = {
    "id": "p" * 32,
    "url": "https://www.notion.so/" + "p" * 32,
    "properties": {
        "현장명": {"type": "title", "title": [{"plain_text": "죽전 카페 간판"}]},
        "진행상태": {"type": "select", "select": {"name": "진행중"}},
        "작업일": {"type": "date", "date": {"start": "2026-08-05"}},
        "담당자": {"type": "select", "select": {"name": "김기사"}},
        "주소": {"type": "rich_text", "rich_text": [{"plain_text": "용인시 수지구"}]},
    },
}


class FakeNotion:
    """실제 HTTP 대신 MockTransport를 물린 Notion 클라이언트."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []
        self.client = na.Notion("test-token")
        self.client._http = httpx.Client(
            base_url=na.API_BASE,
            transport=httpx.MockTransport(self._handle),
            headers={"Authorization": "Bearer test-token", "Notion-Version": na.NOTION_VERSION},
        )

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        body: dict = {}
        if request.headers.get("content-type", "").startswith("application/json") and request.content:
            body = json.loads(request.content)
        self.calls.append((request.method, path, body))

        if request.method == "GET" and path.startswith("/v1/databases/"):
            return httpx.Response(200, json=DB_SCHEMA)
        if request.method == "POST" and path.endswith("/query"):
            return httpx.Response(200, json={"results": [PAGE], "has_more": False})
        if path == "/v1/file_uploads":
            return httpx.Response(200, json={"id": f"upload-{len(self.calls)}", "status": "pending"})
        if path.endswith("/send") or path.endswith("/complete"):
            return httpx.Response(200, json={"id": "upload", "status": "uploaded"})
        if request.method == "POST" and path == "/v1/pages":
            return httpx.Response(200, json={**PAGE, "properties": body.get("properties", {})})
        if path.startswith("/v1/pages/"):
            return httpx.Response(200, json=PAGE)
        if path.startswith("/v1/blocks/"):
            return httpx.Response(200, json={"results": []})
        return httpx.Response(404, json={"message": f"경로 없음: {path}"})

    def created_page(self) -> dict:
        for method, path, body in self.calls:
            if method == "POST" and path == "/v1/pages":
                return body
        raise AssertionError("페이지 생성 요청이 없습니다.")

    def appended_blocks(self) -> list[dict]:
        blocks: list[dict] = []
        for method, path, body in self.calls:
            if method == "PATCH" and path.startswith("/v1/blocks/"):
                blocks.extend(body.get("children", []))
        return blocks


def photo_bytes(size: tuple[int, int] = (3200, 2400)) -> bytes:
    image = Image.new("RGB", size, (90, 140, 200))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=95)
    return buffer.getvalue()


class WorklogTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeNotion()
        worklog._notion = self.fake.client
        worklog._schema_cache["value"] = None
        self.client = TestClient(worklog.app)

    def test_form_shows_status_options(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("새 업무 등록", response.text)
        self.assertIn("진행중", response.text)
        self.assertIn("김기사", response.text)  # 담당자 datalist

    def test_create_entry_with_photo_and_quote(self):
        response = self.client.post(
            "/api/entries",
            data={
                "title": "죽전 카페 간판 설치",
                "status": "예정",
                "start_date": "2026-08-05",
                "end_date": "2026-08-06",
                "owner": "박사장",
                "address": "용인시 수지구 죽전동 1",
                "phone": "010-1234-5678",
                "amount": "1,200,000",
                "memo": "간판 철거 후 신규 설치\n전기 인입 확인 필요",
            },
            files=[
                ("photos", ("현장.jpg", photo_bytes(), "image/jpeg")),
                ("quotes", ("견적서.pdf", b"%PDF-1.4 fake", "application/pdf")),
            ],
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["url"].startswith("https://www.notion.so/"))

        properties = self.fake.created_page()["properties"]
        self.assertEqual(properties["현장명"]["title"][0]["text"]["content"], "죽전 카페 간판 설치")
        self.assertEqual(properties["진행상태"]["select"]["name"], "예정")
        self.assertEqual(properties["작업일"]["date"], {"start": "2026-08-05", "end": "2026-08-06"})
        self.assertEqual(properties["담당자"]["select"]["name"], "박사장")
        self.assertEqual(properties["연락처"]["phone_number"], "010-1234-5678")
        self.assertEqual(properties["견적금액"]["number"], 1200000)
        self.assertEqual(properties["견적서"]["files"][0]["type"], "file_upload")

        children = self.fake.created_page()["children"]
        kinds = [block["type"] for block in children]
        self.assertEqual(kinds.count("image"), 1)
        self.assertEqual(kinds.count("paragraph"), 2)  # 메모 두 줄
        self.assertIn("heading_3", kinds)

    def test_photo_is_downscaled_before_upload(self):
        original = photo_bytes((4000, 3000))
        self.client.post(
            "/api/entries",
            data={"title": "사진 축소 확인"},
            files=[("photos", ("big.jpg", original, "image/jpeg"))],
        )
        sent = [
            (method, path)
            for method, path, _ in self.fake.calls
            if path.endswith("/send")
        ]
        self.assertEqual(len(sent), 1)

        filename, data, content_type = worklog.optimize_image("big.jpg", original, "image/jpeg")
        self.assertLess(len(data), len(original))
        with Image.open(io.BytesIO(data)) as image:
            self.assertLessEqual(max(image.size), worklog.MAX_IMAGE_PX)
        self.assertEqual(content_type, "image/jpeg")
        self.assertEqual(filename, "big.jpg")

    def test_small_photo_is_left_alone(self):
        small = photo_bytes((800, 600))
        filename, data, content_type = worklog.optimize_image("small.jpg", small, "image/jpeg")
        self.assertEqual(data, small)
        self.assertEqual(filename, "small.jpg")
        self.assertEqual(content_type, "image/jpeg")

    def test_title_is_required(self):
        response = self.client.post("/api/entries", data={"title": "   "})
        self.assertEqual(response.status_code, 400)

    def test_oversized_file_is_rejected(self):
        response = self.client.post(
            "/api/entries",
            data={"title": "큰 파일"},
            files=[("quotes", ("big.zip", b"x" * (worklog.MAX_UPLOAD_BYTES + 1), "application/zip"))],
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("너무 큽니다", response.json()["detail"])

    def test_entry_list_page(self):
        response = self.client.get("/entries")
        self.assertEqual(response.status_code, 200)
        self.assertIn("죽전 카페 간판", response.text)
        self.assertIn("용인시 수지구", response.text)

    def test_progress_update_appends_blocks(self):
        page_id = "p" * 32
        response = self.client.post(
            f"/api/entries/{page_id}/progress",
            data={"status": "완료", "owner": "김기사", "memo": "마감 청소까지 완료"},
            files=[("photos", ("완료.jpg", photo_bytes((1600, 1200)), "image/jpeg"))],
        )
        self.assertEqual(response.status_code, 200, response.text)

        patched = [body for method, path, body in self.fake.calls
                   if method == "PATCH" and path == f"/v1/pages/{page_id}"]
        self.assertEqual(patched[0]["properties"]["진행상태"]["select"]["name"], "완료")

        kinds = [block["type"] for block in self.fake.appended_blocks()]
        self.assertEqual(kinds[:2], ["divider", "heading_3"])
        self.assertIn("image", kinds)

    def test_progress_update_needs_content(self):
        response = self.client.post(f"/api/entries/{'p' * 32}/progress", data={})
        self.assertEqual(response.status_code, 400)

    def test_multipart_upload_splits_large_file(self):
        data = b"y" * (na.SINGLE_PART_LIMIT + 1024)
        upload = self.fake.client.upload("large.zip", data, "application/zip")
        self.assertTrue(upload.id)
        create = [body for method, path, body in self.fake.calls if path == "/v1/file_uploads"][0]
        self.assertEqual(create["mode"], "multi_part")
        self.assertEqual(create["number_of_parts"], 3)
        sends = [path for _, path, _ in self.fake.calls if path.endswith("/send")]
        self.assertEqual(len(sends), 3)
        self.assertTrue(any(path.endswith("/complete") for _, path, _ in self.fake.calls))

    def test_normalize_id_from_url(self):
        url = "https://www.notion.so/workspace/My-Page-1234567890abcdef1234567890abcdef?pvs=4"
        self.assertEqual(na.normalize_id(url), "1234567890abcdef1234567890abcdef")
        self.assertEqual(na.normalize_id("1234-5678"), "12345678")


class AccessCodeTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeNotion()
        worklog._notion = self.fake.client
        worklog._schema_cache["value"] = None
        worklog.ACCESS_CODE = "1234"
        self.client = TestClient(worklog.app)

    def tearDown(self):
        worklog.ACCESS_CODE = ""

    def test_form_redirects_to_gate(self):
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn("/gate", response.headers["location"])

    def test_api_rejects_without_cookie(self):
        response = self.client.post("/api/entries", data={"title": "무단 등록"})
        self.assertEqual(response.status_code, 401)

    def test_gate_sets_cookie_and_allows_form(self):
        response = self.client.post(
            "/gate", data={"code": "1234", "next": "/"}, follow_redirects=False
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.client.get("/").status_code, 200)


if __name__ == "__main__":
    unittest.main()
