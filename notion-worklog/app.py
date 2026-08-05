"""현장 업무 일정·진행상태를 노션에 올리는 모바일 웹 폼.

    uvicorn app:app --host 0.0.0.0 --port 8000

- GET  /                        새 업무 등록 폼
- GET  /entries                 최근 업무 목록 (노션 계정 없어도 볼 수 있다)
- GET  /entries/{page_id}       진행상태 업데이트 폼
- GET  /quote                   견적서만 만들어 내려받는 화면
- POST /api/entries             등록 처리 (사진·견적서 업로드, 견적서 자동 생성)
- POST /api/entries/{id}/progress   상태 변경 + 진행 메모/사진 추가
- POST /api/quote               고객명·면적으로 견적서 PDF 생성
"""

from __future__ import annotations

import hmac
import io
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote as urlquote

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import notion_api as na
import notion_lite as nl
import quote as quotelib

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger("worklog")

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "").strip()
DATABASE_ID = na.normalize_id(os.getenv("NOTION_DATABASE_ID", ""))
ACCESS_CODE = os.getenv("WORKLOG_ACCESS_CODE", "").strip()
MAX_IMAGE_PX = int(os.getenv("WORKLOG_MAX_IMAGE_PX", "2000"))
MAX_UPLOAD_MB = float(os.getenv("WORKLOG_MAX_UPLOAD_MB", "40"))

# 이 크기 아래의 사진은 굳이 다시 인코딩하지 않는다.
SOFT_IMAGE_BYTES = 1_200_000
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024)
COOKIE_NAME = "worklog_pass"
SCHEMA_TTL_SECONDS = 300

# setup_db.py가 만드는 속성 이름
FIELD_TITLE = "현장명"
FIELD_STATUS = "진행상태"
FIELD_DATE = "작업일"
FIELD_OWNER = "담당자"
FIELD_ADDRESS = "주소"
FIELD_PHONE = "연락처"
FIELD_AMOUNT = "견적금액"  # DB에 있으면 채우고, 없으면 건너뛴다
FIELD_QUOTE = "견적서"
FIELD_AREA = "면적"
FIELD_WORK = "작업항목"
FIELD_BEFORE = "BEFORE"
FIELD_AFTER = "AFTER"

FALLBACK_STATUSES = ["접수", "견적", "예정", "진행중", "완료", "보류"]
FALLBACK_WORK_TYPES = [option["name"] for option in nl.WORK_TYPE_OPTIONS]

app = FastAPI(title="현장 업무 기록")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

_notion: na.Notion | None = None
_schema_cache: dict[str, Any] = {"at": 0.0, "value": None}

try:  # 화면 머리말에 쓰는 회사 이름
    templates.env.globals["company_name"] = (
        quotelib.load_config().get("회사", {}).get("상호명") or "현장 업무 기록"
    )
except quotelib.QuoteError:
    templates.env.globals["company_name"] = "현장 업무 기록"


# ------------------------------------------------------------------ 기반 유틸


def notion() -> na.Notion:
    global _notion
    if _notion is None:
        _notion = na.Notion(NOTION_TOKEN)
    return _notion


def configured() -> bool:
    return bool(NOTION_TOKEN and DATABASE_ID)


def schema(refresh: bool = False) -> dict:
    """DB 스키마를 5분 캐시. 선택지(진행상태·담당자)를 폼에 뿌리는 데 쓴다."""
    import time

    now = time.monotonic()
    if refresh or _schema_cache["value"] is None or now - _schema_cache["at"] > SCHEMA_TTL_SECONDS:
        _schema_cache["value"] = notion().database(DATABASE_ID)
        _schema_cache["at"] = now
    return _schema_cache["value"]


def authorized(request: Request) -> bool:
    if not ACCESS_CODE:
        return True
    return hmac.compare_digest(request.cookies.get(COOKIE_NAME, ""), ACCESS_CODE)


def has_property(db_schema: dict, name: str, *types: str) -> bool:
    prop = (db_schema.get("properties") or {}).get(name)
    return bool(prop) and (not types or prop.get("type") in types)


def optimize_image(filename: str, data: bytes, content_type: str) -> tuple[str, bytes, str]:
    """휴대폰 사진을 긴 변 기준으로 줄여 다시 저장한다. 못 읽는 형식은 원본 그대로."""
    if not content_type.startswith("image/") or content_type in ("image/gif", "image/svg+xml"):
        return filename, data, content_type
    try:
        from PIL import Image, ImageOps
    except ModuleNotFoundError:
        return filename, data, content_type

    try:
        with Image.open(io.BytesIO(data)) as opened:
            image = ImageOps.exif_transpose(opened)
            oversized = max(image.size) > MAX_IMAGE_PX
            if not oversized and len(data) <= SOFT_IMAGE_BYTES:
                return filename, data, content_type
            if oversized:
                image.thumbnail((MAX_IMAGE_PX, MAX_IMAGE_PX))
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, "JPEG", quality=85, optimize=True)
    except Exception:  # HEIC 등 Pillow가 다루지 못하는 형식
        logger.info("이미지 최적화 건너뜀: %s", filename)
        return filename, data, content_type

    reduced = buffer.getvalue()
    if len(reduced) >= len(data):
        return filename, data, content_type
    return Path(filename).stem + ".jpg", reduced, "image/jpeg"


async def collect_uploads(files: list[UploadFile], *, as_image: bool) -> list[na.Upload]:
    """업로드된 파일을 노션에 올리고 업로드 id 목록을 돌려준다."""
    uploads: list[na.Upload] = []
    for item in files:
        if not item or not item.filename:
            continue
        data = await item.read()
        if not data:
            continue
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                413,
                f"'{item.filename}'이 너무 큽니다 ({len(data) / 1024 / 1024:.1f}MB). "
                f"{MAX_UPLOAD_MB:.0f}MB 이하로 올려 주세요.",
            )
        filename = Path(item.filename).name
        content_type = item.content_type or ""
        if as_image:
            filename, data, content_type = optimize_image(filename, data, content_type)
        uploads.append(notion().upload(filename, data, content_type or None))
    return uploads


def parse_amount(raw: str) -> float | None:
    cleaned = (raw or "").replace(",", "").replace("원", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_area(raw: str) -> float | None:
    cleaned = (raw or "").replace(",", "").replace("㎡", "").replace("m2", "").strip()
    if not cleaned:
        return None
    try:
        area = float(cleaned)
    except ValueError:
        return None
    return area if area > 0 else None


def build_pdf(
    customer: str,
    area: float,
    *,
    work_type: str | None = None,
    final_amount: int | None = None,
    quote_date: date | None = None,
    project: str | None = None,
) -> tuple[str, bytes, quotelib.Quote]:
    """견적서 PDF를 만들어 (파일명, 내용, 견적 내역)을 돌려준다."""
    built = quotelib.build_quote(
        customer,
        area,
        work_type=work_type,
        final_amount=final_amount,
        quote_date=quote_date,
        project=project,
        config=quotelib.load_config(),  # 단가를 고치면 서버 재시작 없이 반영된다
    )
    return quotelib.suggest_filename(built), quotelib.render_bytes(built), built


def work_type_choices(db_schema: dict, config: dict) -> list[dict]:
    """작업항목 목록. 단가가 등록된 항목만 견적서를 자동 생성할 수 있다."""
    names = na.select_options(db_schema, FIELD_WORK) or FALLBACK_WORK_TYPES
    return [{"name": name, "priced": quotelib.has_prices(config, name)} for name in names]


def notion_error_message(error: na.NotionError) -> str:
    text = str(error)
    if error.status in (401, 404):
        return "노션 연결이 끊겼습니다. DB가 integration에 공유되어 있는지 확인해 주세요."
    if "size" in text.lower() or "too large" in text.lower():
        return (
            "노션이 파일 크기를 거부했습니다. 무료 플랜은 파일 하나당 5MB까지만 올라갑니다. "
            "사진 장수를 줄이거나 유료 플랜에서 올려 주세요."
        )
    return f"노션 오류: {text}"


# ------------------------------------------------------------------ 화면 라우트


@app.get("/gate", response_class=HTMLResponse)
def gate(request: Request, next: str = "/", error: str = ""):
    if not ACCESS_CODE:
        return RedirectResponse(next or "/", status_code=303)
    return templates.TemplateResponse(
        request, "gate.html", {"next": next or "/", "error": error}
    )


@app.post("/gate")
def gate_submit(code: str = Form(""), next: str = Form("/")):
    if not hmac.compare_digest(code.strip(), ACCESS_CODE):
        return RedirectResponse(f"/gate?next={next}&error=1", status_code=303)
    response = RedirectResponse(next or "/", status_code=303)
    response.set_cookie(
        COOKIE_NAME, ACCESS_CODE, max_age=60 * 60 * 24 * 30, httponly=True, samesite="lax"
    )
    return response


@app.get("/", response_class=HTMLResponse)
def new_entry(request: Request):
    if not authorized(request):
        return RedirectResponse("/gate?next=/", status_code=303)
    if not configured():
        return templates.TemplateResponse(request, "setup.html", {})

    try:
        db_schema = schema()
    except na.NotionError as error:
        return templates.TemplateResponse(
            request, "setup.html", {"error": notion_error_message(error)}
        )

    statuses = na.select_options(db_schema, FIELD_STATUS) or FALLBACK_STATUSES
    config = quotelib.load_config()
    return templates.TemplateResponse(
        request,
        "new.html",
        {
            "statuses": statuses,
            "default_status": "예정" if "예정" in statuses else statuses[0],
            "work_types": work_type_choices(db_schema, config),
            "owners": na.select_options(db_schema, FIELD_OWNER),
            "today": date.today().isoformat(),
            "db_url": db_schema.get("url", ""),
            "area_unit": config.get("면적단위", "㎡"),
            "company": config.get("회사", {}).get("상호명", ""),
        },
    )


@app.get("/quote", response_class=HTMLResponse)
def quote_form(request: Request):
    if not authorized(request):
        return RedirectResponse("/gate?next=/quote", status_code=303)

    config = quotelib.load_config()
    unit = config.get("면적단위", "㎡")
    groups = []
    for name, entry in quotelib.work_types(config).items():
        groups.append(
            {
                "name": name,
                "rows": [
                    {
                        "name": row.get("품목", ""),
                        "price": f"{int(row.get('단가', 0)):,}",
                        "basis": f"면적 1{unit}당"
                        if isinstance(row.get("수량"), str)
                        else f"{row.get('수량', 1)}식",
                    }
                    for row in entry.get("품목") or []
                ],
            }
        )
    return templates.TemplateResponse(
        request,
        "quote.html",
        {
            "groups": groups,
            "area_unit": unit,
            "default_work_type": config.get("공사명", ""),
            "today": date.today().isoformat(),
            "company": config.get("회사", {}).get("상호명", ""),
        },
    )


@app.get("/entries", response_class=HTMLResponse)
def entry_list(request: Request, status: str = ""):
    if not authorized(request):
        return RedirectResponse("/gate?next=/entries", status_code=303)
    if not configured():
        return templates.TemplateResponse(request, "setup.html", {})

    try:
        db_schema = schema()
        result = notion().query(
            DATABASE_ID,
            page_size=40,
            sorts=[{"timestamp": "last_edited_time", "direction": "descending"}],
        )
    except na.NotionError as error:
        return templates.TemplateResponse(
            request, "setup.html", {"error": notion_error_message(error)}
        )

    entries = []
    for page in result.get("results", []):
        properties = page.get("properties") or {}
        entries.append(
            {
                "id": page["id"].replace("-", ""),
                "url": page.get("url", ""),
                "title": na.plain(properties.get(FIELD_TITLE)) or "(제목 없음)",
                "work": na.plain(properties.get(FIELD_WORK)),
                "status": na.plain(properties.get(FIELD_STATUS)),
                "date": na.plain(properties.get(FIELD_DATE)),
                "owner": na.plain(properties.get(FIELD_OWNER)),
                "address": na.plain(properties.get(FIELD_ADDRESS)),
            }
        )

    statuses = na.select_options(db_schema, FIELD_STATUS) or FALLBACK_STATUSES
    if status:
        entries = [entry for entry in entries if entry["status"] == status]

    return templates.TemplateResponse(
        request,
        "list.html",
        {
            "entries": entries,
            "statuses": statuses,
            "active_status": status,
            "db_url": db_schema.get("url", ""),
        },
    )


@app.get("/entries/{page_id}", response_class=HTMLResponse)
def progress_form(request: Request, page_id: str):
    if not authorized(request):
        return RedirectResponse(f"/gate?next=/entries/{page_id}", status_code=303)
    if not configured():
        return templates.TemplateResponse(request, "setup.html", {})

    try:
        db_schema = schema()
        page = notion().page(page_id)
    except na.NotionError as error:
        return templates.TemplateResponse(
            request, "setup.html", {"error": notion_error_message(error)}
        )

    properties = page.get("properties") or {}
    statuses = na.select_options(db_schema, FIELD_STATUS) or FALLBACK_STATUSES
    current = na.plain(properties.get(FIELD_STATUS))
    return templates.TemplateResponse(
        request,
        "update.html",
        {
            "page_id": page_id,
            "page_url": page.get("url", ""),
            "title": na.plain(properties.get(FIELD_TITLE)) or "(제목 없음)",
            "work_type": na.plain(properties.get(FIELD_WORK)),
            "work_date": na.plain(properties.get(FIELD_DATE)),
            "address": na.plain(properties.get(FIELD_ADDRESS)),
            "statuses": statuses,
            "current_status": current,
            "owners": na.select_options(db_schema, FIELD_OWNER),
            "after_filled": bool((properties.get(FIELD_AFTER) or {}).get("files")),
        },
    )


# ------------------------------------------------------------------ API 라우트


@app.post("/api/quote")
def create_quote_pdf(
    request: Request,
    customer: str = Form(...),
    area: str = Form(...),
    work_type: str = Form(""),
    amount: str = Form(""),
    quote_date: str = Form(""),
    project: str = Form(""),
):
    """고객명·면적만으로 견적서 PDF를 만들어 바로 내려준다. 노션이 없어도 동작한다."""
    if not authorized(request):
        raise HTTPException(401, "접속 코드를 다시 입력해 주세요.")

    area_value = parse_area(area)
    if area_value is None:
        raise HTTPException(400, "면적을 숫자로 입력해 주세요.")
    try:
        day = date.fromisoformat(quote_date) if quote_date else None
    except ValueError:
        raise HTTPException(400, "견적일 형식이 올바르지 않습니다.")

    try:
        filename, pdf, _ = build_pdf(
            customer,
            area_value,
            work_type=work_type.strip() or None,
            final_amount=int(parse_amount(amount)) if parse_amount(amount) else None,
            quote_date=day,
            project=project.strip() or None,
        )
    except quotelib.QuoteError as error:
        raise HTTPException(400, str(error))

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{urlquote(filename)}",
        },
    )


@app.post("/api/entries")
async def create_entry(
    request: Request,
    title: str = Form(...),
    work_type: str = Form(""),
    status: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    owner: str = Form(""),
    address: str = Form(""),
    phone: str = Form(""),
    amount: str = Form(""),
    area: str = Form(""),
    memo: str = Form(""),
    photos: list[UploadFile] = File(default=[]),
    quotes: list[UploadFile] = File(default=[]),
    before_photos: list[UploadFile] = File(default=[]),
    after_photos: list[UploadFile] = File(default=[]),
):
    if not authorized(request):
        raise HTTPException(401, "접속 코드를 다시 입력해 주세요.")
    if not configured():
        raise HTTPException(503, "서버에 노션 토큰/DB ID가 설정되지 않았습니다.")
    title = title.strip()
    if not title:
        raise HTTPException(400, "현장명을 입력해 주세요.")

    area_value = parse_area(area)
    parsed_amount = parse_amount(amount)
    warning = ""

    try:
        db_schema = schema()
        photo_uploads = await collect_uploads(photos, as_image=True)
        quote_uploads = await collect_uploads(quotes, as_image=False)
        before_uploads = await collect_uploads(before_photos, as_image=True)
        after_uploads = await collect_uploads(after_photos, as_image=True)

        # 면적을 넣었으면 회사 양식 그대로 견적서를 만들어 첨부한다.
        if area_value is not None:
            try:
                filename, pdf, built = build_pdf(
                    title,
                    area_value,
                    work_type=work_type.strip() or None,
                    final_amount=int(parsed_amount) if parsed_amount else None,
                )
                quote_uploads.insert(0, notion().upload(filename, pdf, "application/pdf"))
                if parsed_amount is None:
                    parsed_amount = float(built.total)
            except quotelib.QuoteError as error:
                logger.warning("견적서 자동 생성 실패: %s", error)
                warning = f"견적서 자동 생성을 건너뛰었습니다: {error}"

        properties: dict[str, Any] = {FIELD_TITLE: {"title": na.rich_text(title)}}
        if work_type.strip() and has_property(db_schema, FIELD_WORK, "select"):
            properties[FIELD_WORK] = {"select": {"name": work_type.strip()}}
        if status and has_property(db_schema, FIELD_STATUS, "select"):
            properties[FIELD_STATUS] = {"select": {"name": status}}
        if start_date and has_property(db_schema, FIELD_DATE, "date"):
            value: dict[str, Any] = {"start": start_date}
            if end_date and end_date != start_date:
                value["end"] = end_date
            properties[FIELD_DATE] = {"date": value}
        if owner.strip() and has_property(db_schema, FIELD_OWNER, "select"):
            properties[FIELD_OWNER] = {"select": {"name": owner.strip()}}
        if address.strip() and has_property(db_schema, FIELD_ADDRESS, "rich_text"):
            properties[FIELD_ADDRESS] = {"rich_text": na.rich_text(address.strip())}
        if phone.strip() and has_property(db_schema, FIELD_PHONE, "phone_number"):
            properties[FIELD_PHONE] = {"phone_number": phone.strip()}
        if parsed_amount is not None and has_property(db_schema, FIELD_AMOUNT, "number"):
            properties[FIELD_AMOUNT] = {"number": parsed_amount}
        if area_value is not None and has_property(db_schema, FIELD_AREA, "number"):
            properties[FIELD_AREA] = {"number": area_value}
        if quote_uploads and has_property(db_schema, FIELD_QUOTE, "files"):
            properties[FIELD_QUOTE] = na.files_property(quote_uploads)
        if before_uploads and has_property(db_schema, FIELD_BEFORE, "files"):
            properties[FIELD_BEFORE] = na.files_property(before_uploads)
        if after_uploads and has_property(db_schema, FIELD_AFTER, "files"):
            properties[FIELD_AFTER] = na.files_property(after_uploads)

        children: list[dict] = []
        if memo.strip():
            children.append(na.heading("메모"))
            children.extend(na.paragraphs(memo))
        if photo_uploads:
            children.append(na.heading("현장 사진"))
            children.extend(na.image_block(upload) for upload in photo_uploads)
        # 속성이 없는 DB면 본문에 대신 붙여 사진·파일을 잃지 않게 한다.
        if quote_uploads and FIELD_QUOTE not in properties:
            children.append(na.heading("견적서"))
            children.extend(na.file_block(upload) for upload in quote_uploads)
        for label, uploads, field in (
            ("BEFORE", before_uploads, FIELD_BEFORE),
            ("AFTER", after_uploads, FIELD_AFTER),
        ):
            if uploads and field not in properties:
                children.append(na.heading(label))
                children.extend(na.image_block(upload) for upload in uploads)

        page = notion().create_page(DATABASE_ID, properties, children)
    except na.NotionError as error:
        logger.warning("등록 실패: %s", error)
        raise HTTPException(502, notion_error_message(error))

    # 새 담당자 선택지가 생겼을 수 있으니 스키마 캐시를 비운다.
    _schema_cache["value"] = None
    return JSONResponse(
        {
            "ok": True,
            "id": page["id"].replace("-", ""),
            "url": page.get("url", ""),
            "message": f"'{title}' 등록 완료",
            "warning": warning,
        }
    )


@app.post("/api/entries/{page_id}/progress")
async def update_progress(
    request: Request,
    page_id: str,
    status: str = Form(""),
    owner: str = Form(""),
    memo: str = Form(""),
    photos: list[UploadFile] = File(default=[]),
    after_photos: list[UploadFile] = File(default=[]),
):
    if not authorized(request):
        raise HTTPException(401, "접속 코드를 다시 입력해 주세요.")
    if not configured():
        raise HTTPException(503, "서버에 노션 토큰/DB ID가 설정되지 않았습니다.")
    sent_files = [item for item in [*photos, *after_photos] if item and item.filename]
    if not (status or memo.strip() or sent_files):
        raise HTTPException(400, "변경할 상태나 남길 내용이 없습니다.")

    try:
        db_schema = schema()
        page = notion().page(page_id)
        photo_uploads = await collect_uploads(photos, as_image=True)
        after_uploads = await collect_uploads(after_photos, as_image=True)

        properties: dict[str, Any] = {}
        if status and has_property(db_schema, FIELD_STATUS, "select"):
            properties[FIELD_STATUS] = {"select": {"name": status}}
        if owner.strip() and has_property(db_schema, FIELD_OWNER, "select"):
            properties[FIELD_OWNER] = {"select": {"name": owner.strip()}}

        # AFTER 칸이 비어 있을 때만 채운다. 이미 있으면 덮어써서 잃지 않도록 본문에만 붙인다.
        after_field_filled = bool(((page.get("properties") or {}).get(FIELD_AFTER) or {}).get("files"))
        after_to_property = (
            after_uploads and not after_field_filled
            and has_property(db_schema, FIELD_AFTER, "files")
        )
        if after_to_property:
            properties[FIELD_AFTER] = na.files_property(after_uploads)
        if properties:
            notion().update_page(page_id, properties)

        label = " · ".join(part for part in [date.today().isoformat(), status, owner.strip()] if part)
        children: list[dict] = [na.divider(), na.heading(label)]
        children.extend(na.paragraphs(memo))
        children.extend(na.image_block(upload) for upload in photo_uploads)
        if after_uploads and not after_to_property:
            children.append(na.heading("AFTER"))
            children.extend(na.image_block(upload) for upload in after_uploads)
        notion().append_blocks(page_id, children)
        page = notion().page(page_id)
    except na.NotionError as error:
        logger.warning("진행 업데이트 실패: %s", error)
        raise HTTPException(502, notion_error_message(error))

    return JSONResponse(
        {
            "ok": True,
            "id": page_id,
            "url": page.get("url", ""),
            "message": f"진행상태 업데이트 완료{f' ({status})' if status else ''}",
        }
    )


@app.get("/healthz")
def healthz():
    return {"ok": True, "configured": configured()}
