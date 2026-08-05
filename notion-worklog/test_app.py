"""노션 API를 대신하는 가짜 서버로 폼 흐름을 점검한다.

    python3 -m unittest test_app -v
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import unittest.mock
from datetime import date
from pathlib import Path

os.environ.setdefault("NOTION_TOKEN", "test-token")
os.environ.setdefault("NOTION_DATABASE_ID", "d" * 32)
os.environ.setdefault("WORKLOG_ACCESS_CODE", "")

import fitz
import httpx
from fastapi.testclient import TestClient
from PIL import Image

import app as worklog
import notion_api as na
import notion_lite
import quote
import setup_db

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
        "면적": {"type": "number", "number": {"format": "number"}},
        "견적서": {"type": "files", "files": {}},
        "BEFORE": {"type": "files", "files": {}},
        "AFTER": {"type": "files", "files": {}},
        "작업항목": {
            "type": "select",
            "select": {"options": [{"name": "외벽방수"}, {"name": "누수탐지"}, {"name": "기타"}]},
        },
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
        self.page = json.loads(json.dumps(PAGE))  # 테스트에서 바꿔 쓸 수 있게 복사
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
            return httpx.Response(200, json=self.page)
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


class SetupDbTest(unittest.TestCase):
    """노션 DB 생성 스크립트 (표준 라이브러리만 쓰는 경로)."""

    def setUp(self):
        self.calls: list[tuple[str, str, dict | None]] = []

        def fake_request(token, method, path, payload=None):
            self.calls.append((method, path, payload))
            if method == "POST" and path == "/databases":
                return {"id": "d" * 32, "url": "https://www.notion.so/" + "d" * 32}
            if method == "GET":
                return {"properties": {"현장명": {"type": "title"}, "주소": {"type": "rich_text"}}}
            return {}

        patcher = unittest.mock.patch.object(setup_db.nl, "request", fake_request)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_schema_covers_every_field_the_form_writes(self):
        for name in (
            worklog.FIELD_TITLE, worklog.FIELD_WORK, worklog.FIELD_STATUS, worklog.FIELD_DATE,
            worklog.FIELD_OWNER, worklog.FIELD_ADDRESS, worklog.FIELD_PHONE, worklog.FIELD_AREA,
            worklog.FIELD_QUOTE, worklog.FIELD_BEFORE, worklog.FIELD_AFTER,
        ):
            self.assertIn(name, notion_lite.SCHEMA, name)
        self.assertEqual(notion_lite.SCHEMA[worklog.FIELD_TITLE], {"title": {}})
        statuses = [o["name"] for o in notion_lite.SCHEMA["진행상태"]["select"]["options"]]
        self.assertEqual(statuses, ["접수", "견적", "예정", "진행중", "완료", "보류"])
        works = [o["name"] for o in notion_lite.SCHEMA["작업항목"]["select"]["options"]]
        self.assertEqual(
            works,
            ["누수탐지", "누수피해복구", "하수구막힘", "옥상방수", "외벽방수", "기타"],
        )
        self.assertNotIn("견적금액", notion_lite.SCHEMA)  # 작업항목으로 대체했다

    def test_create_sends_schema_and_saves_env(self):
        with tempfile.TemporaryDirectory() as folder:
            env = Path(folder) / ".env"
            env.write_text("# 설정\nNOTION_TOKEN=이전값\nWORKLOG_ACCESS_CODE=8282\n", encoding="utf-8")
            with unittest.mock.patch.object(setup_db, "ENV_PATH", env), \
                 unittest.mock.patch("builtins.input", return_value=""):
                code = setup_db.create_database("ntn_test", "p" * 32, "현장 업무", offer_env=True)
            self.assertEqual(code, 0)

            saved = notion_lite.read_env(env)
            self.assertEqual(saved["NOTION_TOKEN"], "ntn_test")
            self.assertEqual(saved["NOTION_DATABASE_ID"], "d" * 32)
            # 기존 줄과 주석은 그대로 남는다
            self.assertEqual(saved["WORKLOG_ACCESS_CODE"], "8282")
            self.assertIn("# 설정", env.read_text(encoding="utf-8"))

        method, path, payload = self.calls[0]
        self.assertEqual((method, path), ("POST", "/databases"))
        self.assertEqual(payload["parent"], {"type": "page_id", "page_id": "p" * 32})
        self.assertEqual(payload["properties"], notion_lite.SCHEMA)

    def test_patch_only_adds_missing_properties(self):
        self.assertEqual(setup_db.patch_database("ntn_test", "d" * 32), 0)
        patched = [payload for method, path, payload in self.calls if method == "PATCH"]
        added = patched[0]["properties"]
        self.assertIn("진행상태", added)
        self.assertIn("면적", added)
        self.assertNotIn("주소", added)  # 이미 있음
        self.assertNotIn("현장명", added)  # title은 건드리지 않는다

    def test_normalize_id(self):
        url = "https://www.notion.so/team/현장-업무-1234567890abcdef1234567890abcdef?v=1&pvs=4"
        self.assertEqual(notion_lite.normalize_id(url), "1234567890abcdef1234567890abcdef")
        self.assertEqual(notion_lite.normalize_id(""), "")

    def test_http_error_message_is_readable(self):
        error = notion_lite.NotionHttpError(404, "Could not find page")
        self.assertEqual(str(error), "Could not find page")
        self.assertEqual(str(notion_lite.NotionHttpError(500, "")), "노션 API 오류 (HTTP 500)")


class QuoteTest(unittest.TestCase):
    """견적서 자동 생성 (고객명 + 면적)."""

    def setUp(self):
        self.config = quote.load_config()

    def test_korean_amount(self):
        cases = {
            1_200_000: "일백이십만",
            1_650_000: "일백육십오만",
            3_260_000: "삼백이십육만",
            10_000: "일만",
            1_235_000: "일백이십삼만오천",
            120: "일백이십",
        }
        for value, expected in cases.items():
            self.assertEqual(quote.korean_amount(value), expected, value)

    def test_items_follow_area(self):
        items = quote.build_items(10, self.config)
        by_name = {item.name: item for item in items}
        self.assertEqual(by_name["크랙보수"].quantity, 10)
        self.assertEqual(by_name["크랙보수"].amount, 250_000)
        self.assertEqual(by_name["표면 방수제 도포"].amount, 300_000)
        self.assertEqual(by_name["스카이 차량"].quantity, 1)  # 고정 항목

        built = quote.build_quote("탑동 881~8", 10, config=self.config)
        self.assertEqual(built.subtotal, 1_650_000)
        self.assertEqual(built.total, 1_650_000)  # 네고 금액 없으면 합계 그대로

        doubled = quote.build_quote("탑동 881~8", 20, config=self.config)
        self.assertEqual(doubled.subtotal, 1_650_000 + 550_000)

    def test_work_type_picks_its_own_price_table(self):
        built = quote.build_quote("탑동 881~8", 10, work_type="외벽방수", config=self.config)
        self.assertEqual(built.project, "외벽방수")
        self.assertEqual(built.subtotal, 1_650_000)

        # 단가를 아직 안 넣은 항목은 견적서를 만들지 않고 안내한다
        with self.assertRaises(quote.QuoteError) as caught:
            quote.build_quote("매탄동 상가", 5, work_type="누수탐지", config=self.config)
        self.assertIn("누수탐지", str(caught.exception))
        self.assertIn("단가", str(caught.exception))

        # 없는 항목 이름이면 쓸 수 있는 목록을 알려 준다
        with self.assertRaises(quote.QuoteError) as caught:
            quote.build_quote("테스트", 5, work_type="배관교체", config=self.config)
        self.assertIn("외벽방수", str(caught.exception))

    def test_work_type_list_and_price_availability(self):
        self.assertEqual(
            quote.work_type_names(self.config),
            ["누수탐지", "누수피해복구", "하수구막힘", "옥상방수", "외벽방수", "기타"],
        )
        self.assertTrue(quote.has_prices(self.config, "외벽방수"))
        self.assertFalse(quote.has_prices(self.config, "누수탐지"))
        self.assertFalse(quote.has_prices(self.config, "없는항목"))

    def test_notes_come_from_work_type_then_fall_back(self):
        outer = quote.build_notes(self.config, "외벽방수")
        self.assertIn("* 공사명: 외벽 방수 공사", outer)
        common = quote.build_notes(self.config, "누수탐지")
        self.assertEqual(common, self.config["특이사항"])
        self.assertNotIn("* 공사명: 외벽 방수 공사", common)

    def test_final_amount_overrides_total(self):
        built = quote.build_quote("탑동 881~8", 10, final_amount=1_400_000, config=self.config)
        self.assertEqual(built.subtotal, 1_650_000)
        self.assertEqual(built.total, 1_400_000)

    def test_pdf_contains_form_text(self):
        built = quote.build_quote(
            "탑동 881~8", 10, final_amount=1_400_000,
            quote_date=date(2026, 7, 21), config=self.config,
        )
        pdf = quote.render_bytes(built)
        self.assertTrue(pdf.startswith(b"%PDF"))
        # 폰트를 잘라내지 않으면 3MB가 넘어 노션 무료 플랜에 부담이 된다.
        self.assertLess(len(pdf), 500_000, f"PDF가 너무 큽니다: {len(pdf):,} bytes")

        with fitz.open(stream=pdf, filetype="pdf") as document:
            self.assertEqual(document.page_count, 1)
            text = document[0].get_text()

        for expected in (
            "견 적 서", "2026 년 7 월 21일", "탑동 881~8 귀중", "아래와 같이 견적합니다.",
            "청명종합설비", "윤병동", "552-08-01511", "방수미장 공사업",
            "일금 일백사십만원정", "1,400,000", "외벽방수", "크랙보수", "표면 방수제 도포",
            "1,650,000", "특", "송경훈", "착수금50%,잔금50%",
        ):
            self.assertIn(expected, text, expected)

    def test_filename(self):
        built = quote.build_quote("탑동 881~8", 10, quote_date=date(2026, 8, 3), config=self.config)
        self.assertEqual(quote.suggest_filename(built), "견적서_청명종합설비_탑동881~8_20260803.pdf")

    def test_area_must_be_positive(self):
        with self.assertRaises(quote.QuoteError):
            quote.build_quote("탑동", 0, config=self.config)
        with self.assertRaises(quote.QuoteError):
            quote.build_quote("  ", 10, config=self.config)

    def test_cli_writes_pdf(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "견적서.pdf"
            code = quote.main(["--고객", "탑동 881~8", "--면적", "10", "-o", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue(out.exists() and out.stat().st_size > 5000)

    def test_cli_discount_rounds_down(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "q.pdf"
            self.assertEqual(
                quote.main(["--고객", "탑동", "--면적", "10", "--할인", "15", "-o", str(out)]), 0
            )
            with fitz.open(out) as document:
                # 1,650,000의 15% 할인 → 1,402,500 → 만원 단위 내림
                self.assertIn("1,400,000", document[0].get_text())


class QuoteWebTest(unittest.TestCase):
    """웹 폼과 견적서 생성이 이어지는지."""

    def setUp(self):
        self.fake = FakeNotion()
        worklog._notion = self.fake.client
        worklog._schema_cache["value"] = None
        self.client = TestClient(worklog.app)

    def test_quote_page_lists_work_types_and_prices(self):
        response = self.client.get("/quote")
        self.assertEqual(response.status_code, 200)
        self.assertIn("견적서 만들기", response.text)
        self.assertIn("크랙보수", response.text)
        self.assertIn("25,000원", response.text)
        for name in ("누수탐지", "누수피해복구", "하수구막힘", "옥상방수", "외벽방수", "기타"):
            self.assertIn(name, response.text)
        self.assertIn("단가 미등록", response.text)

    def test_entry_form_lists_work_types(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("작업항목", response.text)
        self.assertIn("누수탐지", response.text)
        self.assertIn("BEFORE", response.text)
        self.assertIn("AFTER", response.text)

    def test_quote_api_returns_pdf(self):
        response = self.client.post(
            "/api/quote", data={"customer": "탑동 881~8", "area": "10 ㎡"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertIn("UTF-8''", response.headers["content-disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
        with fitz.open(stream=response.content, filetype="pdf") as document:
            self.assertIn("탑동 881~8 귀중", document[0].get_text())

    def test_quote_api_rejects_bad_area(self):
        response = self.client.post("/api/quote", data={"customer": "탑동", "area": "넓음"})
        self.assertEqual(response.status_code, 400)

    def test_entry_attaches_generated_quote(self):
        response = self.client.post(
            "/api/entries",
            data={"title": "탑동 881~8", "status": "예정", "area": "10"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["warning"], "")

        properties = self.fake.created_page()["properties"]
        self.assertEqual(properties["면적"]["number"], 10)
        self.assertEqual(len(properties["견적서"]["files"]), 1)
        self.assertTrue(properties["견적서"]["files"][0]["name"].endswith(".pdf"))

        uploaded = [body for method, path, body in self.fake.calls if path == "/v1/file_uploads"]
        self.assertEqual(uploaded[0]["content_type"], "application/pdf")

    def test_manual_amount_goes_into_the_pdf(self):
        response = self.client.post(
            "/api/entries",
            data={"title": "탑동 881~8", "area": "10", "amount": "1,400,000"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.fake.created_page()["properties"]["견적서"]["files"]), 1)

    def test_entry_saves_work_type_and_before_after(self):
        response = self.client.post(
            "/api/entries",
            data={"title": "옥상 누수", "work_type": "누수탐지", "status": "접수"},
            files=[
                ("before_photos", ("전.jpg", photo_bytes((1600, 1200)), "image/jpeg")),
                ("after_photos", ("후.jpg", photo_bytes((1600, 1200)), "image/jpeg")),
            ],
        )
        self.assertEqual(response.status_code, 200, response.text)

        properties = self.fake.created_page()["properties"]
        self.assertEqual(properties["작업항목"]["select"]["name"], "누수탐지")
        self.assertEqual(len(properties["BEFORE"]["files"]), 1)
        self.assertEqual(len(properties["AFTER"]["files"]), 1)
        self.assertEqual(properties["BEFORE"]["files"][0]["type"], "file_upload")
        # 서로 다른 업로드로 올라가야 한다 (노션은 업로드 하나를 한 곳에만 붙일 수 있다)
        self.assertNotEqual(
            properties["BEFORE"]["files"][0]["file_upload"]["id"],
            properties["AFTER"]["files"][0]["file_upload"]["id"],
        )

    def test_unpriced_work_type_warns_but_still_registers(self):
        response = self.client.post(
            "/api/entries",
            data={"title": "매탄동 상가 누수", "work_type": "누수탐지", "area": "5"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("누수탐지", response.json()["warning"])

        properties = self.fake.created_page()["properties"]
        self.assertEqual(properties["면적"]["number"], 5)
        self.assertNotIn("견적서", properties)  # 견적서는 못 만들었지만 등록은 됐다

    def test_work_type_becomes_the_project_on_the_pdf(self):
        response = self.client.post(
            "/api/entries",
            data={"title": "탑동 881~8", "work_type": "외벽방수", "area": "10"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["warning"], "")
        name = self.fake.created_page()["properties"]["견적서"]["files"][0]["name"]
        self.assertTrue(name.endswith(".pdf"))

    def test_progress_fills_after_when_empty(self):
        response = self.client.post(
            f"/api/entries/{'p' * 32}/progress",
            data={"status": "완료"},
            files=[("after_photos", ("완료.jpg", photo_bytes((1200, 900)), "image/jpeg"))],
        )
        self.assertEqual(response.status_code, 200, response.text)

        patched = [body for method, path, body in self.fake.calls
                   if method == "PATCH" and path.startswith("/v1/pages/")]
        self.assertEqual(len(patched[0]["properties"]["AFTER"]["files"]), 1)
        self.assertNotIn("AFTER", [
            "".join(part["text"]["content"] for part in block["heading_3"]["rich_text"])
            for block in self.fake.appended_blocks() if block["type"] == "heading_3"
        ][1:])  # 속성에 넣었으니 본문에 AFTER 제목을 또 만들지 않는다

    def test_progress_keeps_existing_after_photos(self):
        self.fake.page["properties"]["AFTER"] = {
            "type": "files",
            "files": [{"type": "file", "name": "먼저.jpg", "file": {"url": "https://x/1.jpg"}}],
        }
        response = self.client.post(
            f"/api/entries/{'p' * 32}/progress",
            data={"memo": "추가 사진"},
            files=[("after_photos", ("추가.jpg", photo_bytes((1200, 900)), "image/jpeg"))],
        )
        self.assertEqual(response.status_code, 200, response.text)

        patched = [body for method, path, body in self.fake.calls
                   if method == "PATCH" and path.startswith("/v1/pages/")]
        self.assertEqual(patched, [])  # 기존 사진을 덮어쓰지 않는다
        headings = [
            "".join(part["text"]["content"] for part in block["heading_3"]["rich_text"])
            for block in self.fake.appended_blocks() if block["type"] == "heading_3"
        ]
        self.assertIn("AFTER", headings)  # 대신 본문에 붙는다

    def test_entry_without_area_generates_nothing(self):
        self.client.post("/api/entries", data={"title": "면적 없음"})
        properties = self.fake.created_page()["properties"]
        self.assertNotIn("견적서", properties)
        self.assertNotIn("면적", properties)


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
