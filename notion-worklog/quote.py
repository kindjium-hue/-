#!/usr/bin/env python3
"""청명종합설비 견적서 자동 생성.

고객명과 면적만 넣으면 기존 견적서 양식(A4) 그대로 PDF를 만든다.
좌표·색·표 구조는 실제 견적서 PDF에서 그대로 뽑아 왔고,
품목·단가·특이사항은 `quote_config.json`에서 고친다.

    python quote.py --고객 "탑동 881~8" --면적 10
    python quote.py --고객 "매탄동 현대아파트" --면적 24 --금액 1800000 -o 견적서.pdf
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import fitz  # PyMuPDF

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = BASE_DIR / "quote_config.json"

# --------------------------------------------------------------- 양식 좌표 (pt)
# 원본 견적서 PDF에서 추출한 값. 좌상단 원점, A4.

PAGE_SIZE = (595.32, 841.92)
LEFT, RIGHT = 40.9, 553.6

TITLE_BASELINE = 77.0
TITLE_RULE = (213.4, 86.4, 379.3)  # x0, y, x1

INFO_TOP, INFO_BOTTOM = 97.4, 218.7
INFO_SPLIT = 244.0  # 좌측 인사말 칸 | 공급자 칸
SUPPLIER_LABEL_RIGHT = 270.4  # 공/급/자 세로 라벨 열
SUPPLIER_COLS = (270.4, 329.4, 405.9, 468.7, 553.6)
SUPPLIER_ROWS = (97.4, 121.7, 145.9, 170.2, 194.4, 218.7)
GREETING_CENTERS = (129.2, 158.4, 187.7)
SEAL_RECT = (515.9, 119.6, 551.1, 153.5)
SEAL_LEFT_GUARD = 525.0  # 도장을 피해 대표자 이름을 놓는 오른쪽 한계

SUM_TOP, SUM_BOTTOM = 218.7, 251.6
HEAD_TOP, HEAD_BOTTOM = 251.6, 272.9
BODY_TOP, BODY_BOTTOM = 272.9, 617.2
TOTAL_TOP, TOTAL_BOTTOM = 617.2, 653.4
FINAL_TOP, FINAL_BOTTOM = 653.4, 689.1

PROJECT_RIGHT = 154.5  # 공사명 열 오른쪽
BODY_COLS = (154.5, 270.0, 328.9, 415.5, 497.3)  # 품목|수량|단가|금액|비고 경계
ROW_HEIGHT = 36.2

NOTE_TOP, NOTE_HEAD_BOTTOM, NOTE_BOTTOM = 699.7, 719.3, 793.2
NOTE_FIRST_BASELINE = 733.0
NOTE_STEP = 18.1
NOTE_INDENT = 54.8

FOOT_TOP, FOOT_BOTTOM = 797.3, 816.6
FOOT_COLS = (40.9, 96.3, 184.4, 244.1, 328.9, 405.5, 553.6)

PAD = 8.8
BASELINE_SHIFT = 0.36  # 셀 세로 중앙에서 기준선까지 (글자 크기 배수)

BLACK = (0, 0, 0)
GRAY = (0.502, 0.502, 0.502)
RULE_GRAY = (0.647, 0.647, 0.647)
HEADER_FILL = (0.867, 0.922, 0.969)
FINAL_FILL = (1.0, 1.0, 0.8)

BORDER_WIDTH = 1.6
LINE_WIDTH = 0.9
THIN_WIDTH = 0.7

# 한국어 명조 계열을 먼저 찾고, 없으면 고딕으로 떨어진다.
FONT_CANDIDATES = (
    ("/usr/share/fonts/truetype/nanum/NanumMyeongjo.ttf",
     "/usr/share/fonts/truetype/nanum/NanumMyeongjoBold.ttf"),
    ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
     "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
    ("C:/Windows/Fonts/batang.ttc", "C:/Windows/Fonts/batang.ttc"),
    ("C:/Windows/Fonts/malgun.ttf", "C:/Windows/Fonts/malgunbd.ttf"),
    ("/System/Library/Fonts/Supplemental/AppleMyungjo.ttf",
     "/System/Library/Fonts/Supplemental/AppleMyungjo.ttf"),
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc",
     "/System/Library/Fonts/AppleSDGothicNeo.ttc"),
)

DIGIT_NAMES = "영일이삼사오육칠팔구"
SMALL_UNITS = ("", "십", "백", "천")
BIG_UNITS = ("", "만", "억", "조")


class QuoteError(RuntimeError):
    pass


# ------------------------------------------------------------------ 자료 구조


@dataclass
class Item:
    name: str
    quantity: float
    unit_price: int
    note: str = ""

    @property
    def amount(self) -> int:
        return int(round(self.quantity * self.unit_price))


@dataclass
class Quote:
    customer: str
    area: float
    items: list[Item]
    quote_date: date
    project: str
    config: dict = field(repr=False, default_factory=dict)
    final_amount: int | None = None

    @property
    def subtotal(self) -> int:
        return sum(item.amount for item in self.items)

    @property
    def total(self) -> int:
        """고객에게 청구하는 최종 금액. 네고 금액을 지정하지 않으면 합계와 같다."""
        return self.subtotal if self.final_amount is None else self.final_amount


# ------------------------------------------------------------------ 계산 부분


def load_config(path: str | Path | None = None) -> dict:
    path = Path(path or DEFAULT_CONFIG)
    if not path.exists():
        raise QuoteError(f"설정 파일이 없습니다: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_items(area: float, config: dict) -> list[Item]:
    """면적에 비례하는 항목과 고정 항목을 섞어 견적 항목을 만든다."""
    items: list[Item] = []
    for row in config.get("품목", []):
        raw_quantity = row.get("수량", 1)
        if isinstance(raw_quantity, str):
            if raw_quantity.strip() not in ("면적", "area"):
                raise QuoteError(f"수량 값을 모르겠습니다: {raw_quantity!r} (숫자 또는 \"면적\")")
            quantity = area
        else:
            quantity = float(raw_quantity)
        if quantity <= 0:
            continue
        items.append(
            Item(
                name=str(row["품목"]),
                quantity=quantity,
                unit_price=int(row["단가"]),
                note=str(row.get("비고", "")),
            )
        )
    if not items:
        raise QuoteError("품목이 하나도 없습니다. quote_config.json의 `품목`을 확인하세요.")
    return items


def build_quote(
    customer: str,
    area: float,
    *,
    final_amount: int | None = None,
    quote_date: date | None = None,
    project: str | None = None,
    config: dict | None = None,
) -> Quote:
    customer = (customer or "").strip()
    if not customer:
        raise QuoteError("고객명(현장명)을 입력해 주세요.")
    if area <= 0:
        raise QuoteError("면적은 0보다 커야 합니다.")

    config = config or load_config()
    return Quote(
        customer=customer,
        area=area,
        items=build_items(area, config),
        quote_date=quote_date or date.today(),
        project=project or config.get("공사명", ""),
        config=config,
        final_amount=final_amount,
    )


def korean_amount(value: int) -> str:
    """1200000 → '일백이십만' (견적서 원본 표기 방식)."""
    value = int(round(value))
    if value == 0:
        return "영"
    groups: list[int] = []
    while value:
        groups.append(value % 10000)
        value //= 10000

    parts: list[str] = []
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if not group:
            continue
        chunk = ""
        for position in (3, 2, 1, 0):
            digit = (group // 10**position) % 10
            if digit:
                chunk += DIGIT_NAMES[digit] + SMALL_UNITS[position]
        parts.append(chunk + BIG_UNITS[index])
    return "".join(parts)


def money(value: float) -> str:
    return f"{value:,.0f}"


def quantity_text(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def date_text(day: date) -> str:
    return f"{day.year} 년 {day.month} 월 {day.day}일"


def suggest_filename(quote: Quote) -> str:
    company = quote.config.get("회사", {}).get("상호명", "견적서")
    customer = re.sub(r"[^\w가-힣().~-]+", "", quote.customer.replace(" ", ""))
    return f"견적서_{company}_{customer}_{quote.quote_date:%Y%m%d}.pdf"


# -------------------------------------------------------------------- 그리기


def find_fonts() -> tuple[str, str]:
    """본문용 한글 폰트(보통/굵게) 경로를 찾는다."""
    override = os.getenv("QUOTE_FONT")
    if override:
        return override, os.getenv("QUOTE_FONT_BOLD", override)
    for regular, bold in FONT_CANDIDATES:
        if Path(regular).exists():
            return regular, bold if Path(bold).exists() else regular
    for pattern in ("NanumMyeongjo*.ttf", "NanumGothic*.ttf", "*Gothic*.tt[fc]"):
        found = sorted(Path("/usr/share/fonts").rglob(pattern))
        if found:
            return str(found[0]), str(found[0])
    raise QuoteError(
        "한글 폰트를 찾지 못했습니다.\n"
        "  우분투/데비안: sudo apt-get install fonts-nanum\n"
        "  그 외: QUOTE_FONT=/폰트/경로.ttf 환경변수로 지정하세요."
    )


class Sheet:
    """한 장짜리 견적서를 그리는 얇은 캔버스."""

    def __init__(self, page: fitz.Page, regular: str, bold: str):
        self.page = page
        self._metrics = {False: fitz.Font(fontfile=regular), True: fitz.Font(fontfile=bold)}
        page.insert_font(fontname="qr", fontfile=regular)
        page.insert_font(fontname="qb", fontfile=bold)

    def width(self, text: str, size: float, bold: bool) -> float:
        return self._metrics[bold].text_length(text, fontsize=size)

    def fit(self, text: str, size: float, bold: bool, limit: float) -> float:
        """칸을 넘치면 들어갈 때까지 글자 크기를 줄인다."""
        while size > 5 and self.width(text, size, bold) > limit:
            size -= 0.25
        return size

    def text(self, x: float, baseline: float, text: str, size: float = 10,
             bold: bool = False, align: str = "left") -> None:
        if not text:
            return
        width = self.width(text, size, bold)
        if align == "center":
            x -= width / 2
        elif align == "right":
            x -= width
        self.page.insert_text(
            (x, baseline), text, fontname="qb" if bold else "qr", fontsize=size, color=BLACK
        )

    def cell(self, x0: float, x1: float, y0: float, y1: float, text: str, size: float = 10,
             bold: bool = False, align: str = "center", pad: float = PAD) -> None:
        if not text:
            return
        size = self.fit(text, size, bold, (x1 - x0) - 2 * pad)
        baseline = (y0 + y1) / 2 + size * BASELINE_SHIFT
        if align == "center":
            self.text((x0 + x1) / 2, baseline, text, size, bold, "center")
        elif align == "right":
            self.text(x1 - pad, baseline, text, size, bold, "right")
        else:
            self.text(x0 + pad, baseline, text, size, bold, "left")

    def fill(self, x0: float, y0: float, x1: float, y1: float, color) -> None:
        self.page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=None, fill=color)

    def border(self, x0: float, y0: float, x1: float, y1: float,
               width: float = BORDER_WIDTH, color=BLACK) -> None:
        self.page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=color, width=width)

    def line(self, x0: float, y0: float, x1: float, y1: float,
             width: float = LINE_WIDTH, color=BLACK) -> None:
        self.page.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1), color=color, width=width)


def render_document(quote: Quote) -> fitz.Document:
    regular, bold = find_fonts()
    document = fitz.open()
    page = document.new_page(width=PAGE_SIZE[0], height=PAGE_SIZE[1])
    sheet = Sheet(page, regular, bold)

    _draw_title(sheet)
    _draw_info(sheet, quote)
    _draw_summary(sheet, quote)
    _draw_table(sheet, quote)
    _draw_notes(sheet, quote)
    _draw_footer(sheet, quote)
    _draw_seal(page, quote)
    return document


def _draw_title(sheet: Sheet) -> None:
    sheet.text(PAGE_SIZE[0] / 2, TITLE_BASELINE, "견 적 서", size=20, bold=True, align="center")
    x0, y, x1 = TITLE_RULE
    sheet.line(x0, y, x1, y, width=2.25, color=RULE_GRAY)


def _draw_info(sheet: Sheet, quote: Quote) -> None:
    company = quote.config.get("회사", {})

    # 라벨 칸 배경
    sheet.fill(INFO_SPLIT, INFO_TOP, SUPPLIER_COLS[1], INFO_BOTTOM, HEADER_FILL)
    for row in (1, 3, 4):  # 대표자 / 종목 / 팩스 라벨
        sheet.fill(SUPPLIER_COLS[2], SUPPLIER_ROWS[row], SUPPLIER_COLS[3],
                   SUPPLIER_ROWS[row + 1], HEADER_FILL)

    sheet.border(LEFT, INFO_TOP, RIGHT, INFO_BOTTOM)
    sheet.line(INFO_SPLIT, INFO_TOP, INFO_SPLIT, INFO_BOTTOM)

    # 좌측 인사말 칸
    greeting = (
        date_text(quote.quote_date),
        f"{quote.customer} 귀중" if not quote.customer.endswith("귀중") else quote.customer,
        "아래와 같이 견적합니다.",
    )
    for center, line in zip(GREETING_CENTERS, greeting):
        size = sheet.fit(line, 12, True, (INFO_SPLIT - LEFT) - 2 * PAD)
        sheet.text((LEFT + INFO_SPLIT) / 2, center + size * BASELINE_SHIFT,
                   line, size, bold=True, align="center")

    # 공 / 급 / 자 세로 라벨
    for center, label in zip((131.2, 158.3, 185.4), "공급자"):
        sheet.text((INFO_SPLIT + SUPPLIER_LABEL_RIGHT) / 2, center + 11 * BASELINE_SHIFT,
                   label, 11, bold=True, align="center")

    # 공급자 표 내부 선 (원본은 회색 얇은 선)
    for row_y in SUPPLIER_ROWS[1:-1]:
        sheet.line(SUPPLIER_COLS[0], row_y, SUPPLIER_COLS[4], row_y, THIN_WIDTH, GRAY)
    sheet.line(SUPPLIER_COLS[1], INFO_TOP, SUPPLIER_COLS[1], INFO_BOTTOM, THIN_WIDTH, GRAY)
    for row in (1, 3, 4):
        for column in (2, 3):
            sheet.line(SUPPLIER_COLS[column], SUPPLIER_ROWS[row],
                       SUPPLIER_COLS[column], SUPPLIER_ROWS[row + 1], THIN_WIDTH, GRAY)

    rows = (
        ("등록번호", company.get("등록번호", ""), None, None),
        ("상  호  명", company.get("상호명", ""), "대  표  자", company.get("대표자", "")),
        ("주       소", company.get("주소", ""), None, None),
        ("업       태", company.get("업태", ""), "종      목", company.get("종목", "")),
        ("전화번호", company.get("전화번호", ""), "팩      스", company.get("팩스", "")),
    )
    for index, (label, value, label2, value2) in enumerate(rows):
        top, bottom = SUPPLIER_ROWS[index], SUPPLIER_ROWS[index + 1]
        sheet.cell(SUPPLIER_COLS[0], SUPPLIER_COLS[1], top, bottom, label, 10, bold=True)
        if label2 is None:
            sheet.cell(SUPPLIER_COLS[1], SUPPLIER_COLS[4], top, bottom, value, 10, bold=True)
            continue
        sheet.cell(SUPPLIER_COLS[1], SUPPLIER_COLS[2], top, bottom, value, 10, bold=True)
        sheet.cell(SUPPLIER_COLS[2], SUPPLIER_COLS[3], top, bottom, label2, 10, bold=True)
        # 대표자 칸 오른쪽에는 도장이 찍히므로, 이름을 원본처럼 왼쪽으로 붙인다.
        value_right = SEAL_LEFT_GUARD if index == 1 else SUPPLIER_COLS[4]
        sheet.cell(SUPPLIER_COLS[3], value_right, top, bottom, value2, 10, bold=True)


def _draw_summary(sheet: Sheet, quote: Quote) -> None:
    sheet.fill(LEFT, SUM_TOP, RIGHT, HEAD_BOTTOM, HEADER_FILL)
    sheet.border(LEFT, SUM_TOP, RIGHT, SUM_BOTTOM)
    sheet.line(PROJECT_RIGHT, SUM_TOP, PROJECT_RIGHT, SUM_BOTTOM)

    center = (LEFT + PROJECT_RIGHT) / 2
    sheet.text(center, 228.8 + 11 * BASELINE_SHIFT, "합 계 금 액", 11, bold=True, align="center")
    sheet.text(center, 242.4 + 11 * BASELINE_SHIFT,
               quote.config.get("부가세문구", "(부가세별도)"), 11, bold=True, align="center")

    text = f"일금 {korean_amount(quote.total)}원정 ₩{money(quote.total)}"
    sheet.cell(PROJECT_RIGHT, RIGHT, SUM_TOP, SUM_BOTTOM, text, 11, bold=True)


def _draw_table(sheet: Sheet, quote: Quote) -> None:
    headers = ("공사명", "품목", "단가", "금액", "비고")
    edges = (LEFT, PROJECT_RIGHT, BODY_COLS[2], BODY_COLS[3], BODY_COLS[4], RIGHT)
    for index, label in enumerate(headers):
        sheet.cell(edges[index], edges[index + 1], HEAD_TOP, HEAD_BOTTOM, label, 10, bold=True)
    sheet.border(LEFT, HEAD_TOP, RIGHT, HEAD_BOTTOM)
    for x in (PROJECT_RIGHT, BODY_COLS[2], BODY_COLS[3], BODY_COLS[4]):
        sheet.line(x, HEAD_TOP, x, HEAD_BOTTOM)

    # 본문 틀: 품목 열은 수량과 나뉜다.
    sheet.border(LEFT, BODY_TOP, RIGHT, FINAL_BOTTOM)
    for x in (PROJECT_RIGHT, *BODY_COLS[1:]):
        sheet.line(x, BODY_TOP, x, FINAL_BOTTOM)

    count = len(quote.items)
    row_height = ROW_HEIGHT
    available = TOTAL_TOP - BODY_TOP
    if count * row_height > available:  # 항목이 많으면 줄 높이를 줄인다
        row_height = available / count

    for index, item in enumerate(quote.items):
        top = BODY_TOP + index * row_height
        bottom = top + row_height
        sheet.line(PROJECT_RIGHT, bottom, RIGHT, bottom)
        sheet.cell(PROJECT_RIGHT, BODY_COLS[1], top, bottom, item.name, 11, bold=True)
        sheet.cell(BODY_COLS[1], BODY_COLS[2], top, bottom,
                   quantity_text(item.quantity), 11, align="right")
        sheet.cell(BODY_COLS[2], BODY_COLS[3], top, bottom, money(item.unit_price), 9, align="right")
        sheet.cell(BODY_COLS[3], BODY_COLS[4], top, bottom, money(item.amount), 9, align="right")
        if item.note:
            sheet.cell(BODY_COLS[4], RIGHT, top, bottom, item.note, 9)

    # 공사명(병합 칸)은 채워진 줄 가운데에 놓는다.
    used_bottom = BODY_TOP + count * row_height
    sheet.cell(LEFT, PROJECT_RIGHT, BODY_TOP, used_bottom, quote.project, 12, bold=True)

    # 합계 / 최종 네고 금액
    sheet.fill(LEFT + 1, FINAL_TOP + 1, RIGHT - 1, FINAL_BOTTOM - 1, FINAL_FILL)
    for x in (PROJECT_RIGHT, *BODY_COLS[1:]):
        sheet.line(x, FINAL_TOP, x, FINAL_BOTTOM)
    sheet.line(LEFT, TOTAL_TOP, RIGHT, TOTAL_TOP)
    sheet.line(LEFT, FINAL_TOP, RIGHT, FINAL_TOP)

    sheet.cell(LEFT, PROJECT_RIGHT, TOTAL_TOP, TOTAL_BOTTOM, "합계", 10, bold=True)
    sheet.cell(BODY_COLS[3], BODY_COLS[4], TOTAL_TOP, TOTAL_BOTTOM,
               money(quote.subtotal), 10, align="right")
    sheet.cell(LEFT, PROJECT_RIGHT, FINAL_TOP, FINAL_BOTTOM, "최종 네고 금액", 10, bold=True)
    sheet.cell(BODY_COLS[3], BODY_COLS[4], FINAL_TOP, FINAL_BOTTOM,
               money(quote.total), 10, align="right")


def _draw_notes(sheet: Sheet, quote: Quote) -> None:
    sheet.fill(LEFT, NOTE_TOP, RIGHT, NOTE_HEAD_BOTTOM, HEADER_FILL)
    sheet.border(LEFT, NOTE_TOP, RIGHT, NOTE_BOTTOM)
    sheet.line(LEFT, NOTE_HEAD_BOTTOM, RIGHT, NOTE_HEAD_BOTTOM, THIN_WIDTH, GRAY)
    sheet.cell(LEFT, RIGHT, NOTE_TOP, NOTE_HEAD_BOTTOM, "특    이    사    항", 11, bold=True)

    lines = list(quote.config.get("특이사항", []))
    room = int((NOTE_BOTTOM - NOTE_FIRST_BASELINE) // NOTE_STEP) + 1
    for index, line in enumerate(lines[:room]):
        size = sheet.fit(line, 11, True, RIGHT - NOTE_INDENT - PAD)
        sheet.text(NOTE_INDENT, NOTE_FIRST_BASELINE + index * NOTE_STEP, line, size, bold=True)


def _draw_footer(sheet: Sheet, quote: Quote) -> None:
    for index in (0, 2, 4):  # 라벨 칸 배경
        sheet.fill(FOOT_COLS[index], FOOT_TOP, FOOT_COLS[index + 1], FOOT_BOTTOM, HEADER_FILL)
    sheet.border(LEFT, FOOT_TOP, RIGHT, FOOT_BOTTOM)
    for x in FOOT_COLS[1:-1]:
        sheet.line(x, FOOT_TOP, x, FOOT_BOTTOM)

    values = (
        "담당", quote.config.get("담당", ""),
        "연 락 처", quote.config.get("연락처", ""),
        "결제방법", quote.config.get("결제방법", ""),
    )
    for index, text in enumerate(values):
        sheet.cell(FOOT_COLS[index], FOOT_COLS[index + 1], FOOT_TOP, FOOT_BOTTOM,
                   text, 10, bold=index % 2 == 0)


def _draw_seal(page: fitz.Page, quote: Quote) -> None:
    seal = quote.config.get("회사", {}).get("도장")
    if not seal:
        return
    path = Path(seal)
    if not path.is_absolute():
        path = BASE_DIR / path
    if not path.exists():
        return
    page.insert_image(fitz.Rect(*SEAL_RECT), filename=str(path), keep_proportion=True)


# ------------------------------------------------------------------ 내보내기


def render_bytes(quote: Quote) -> bytes:
    document = render_document(quote)
    try:
        try:
            # 쓴 글자만 남기고 폰트를 잘라낸다. 한글 폰트를 통째로 넣으면 3MB가 넘어
            # 노션 무료 플랜(파일당 5MB)에 부담이 된다. 이걸 거치면 100KB 안쪽.
            document.subset_fonts(verbose=False)
        except Exception:  # 폰트 잘라내기를 못 하는 버전이면 그대로 저장한다
            pass
        return document.tobytes(garbage=4, deflate=True, deflate_fonts=True)
    finally:
        document.close()


def render_pdf(quote: Quote, out_path: str | Path | None = None) -> Path:
    path = Path(out_path) if out_path else Path(suggest_filename(quote))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_bytes(quote))
    return path


# ------------------------------------------------------------------------ CLI


def parse_amount(raw: str | None) -> int | None:
    if raw is None:
        return None
    cleaned = str(raw).replace(",", "").replace("원", "").strip()
    if not cleaned:
        return None
    if cleaned.endswith("%"):
        raise QuoteError("--금액에는 숫자를 넣어 주세요. 할인율은 --할인 을 쓰세요.")
    return int(float(cleaned))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="고객명과 면적만 넣으면 견적서 PDF를 만듭니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--고객", "--customer", dest="customer", required=True,
                        help="고객명 또는 현장명 (예: 탑동 881~8)")
    parser.add_argument("--면적", "--area", dest="area", type=float, required=True,
                        help="시공 면적 (㎡)")
    parser.add_argument("--금액", "--final", dest="final",
                        help="최종 네고 금액. 생략하면 합계 그대로")
    parser.add_argument("--할인", "--discount", dest="discount", type=float,
                        help="합계에서 깎을 비율(%%). 예: 15 → 15%% 할인, 만원 단위 내림")
    parser.add_argument("--날짜", "--date", dest="day", help="견적일 (YYYY-MM-DD, 기본 오늘)")
    parser.add_argument("--공사명", dest="project", help="표 왼쪽 공사명 (기본 설정값)")
    parser.add_argument("--설정", dest="config", help="설정 파일 경로 (기본 quote_config.json)")
    parser.add_argument("-o", "--out", dest="out", help="저장할 PDF 경로")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        day = date.fromisoformat(args.day) if args.day else None
        quote = build_quote(
            args.customer,
            args.area,
            final_amount=parse_amount(args.final),
            quote_date=day,
            project=args.project,
            config=config,
        )
        if args.discount is not None:
            if not 0 <= args.discount < 100:
                raise QuoteError("--할인은 0 이상 100 미만이어야 합니다.")
            discounted = quote.subtotal * (1 - args.discount / 100)
            quote.final_amount = int(discounted // 10000 * 10000)
        path = render_pdf(quote, args.out)
    except QuoteError as error:
        print(f"실패: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"실패: 값을 읽을 수 없습니다 ({error})", file=sys.stderr)
        return 1

    print(f"만들었습니다: {path}")
    print(f"  면적 {quantity_text(quote.area)}{quote.config.get('면적단위', '㎡')}"
          f" · 합계 {money(quote.subtotal)}원 · 청구 {money(quote.total)}원")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
