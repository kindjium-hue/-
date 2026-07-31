#!/usr/bin/env python3
"""손그림(스케치) 스타일 드로잉 유틸 — 학생 일러스트 / 학습지 카드"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

SS = 3  # 슈퍼샘플링 배율 (PIL 선은 안티에일리어싱이 없어 크게 그린 뒤 축소)
UW, UH = 820, 620  # 일러스트 기준 좌표계


# ---------------------------------------------------------------- 곡선 / 획
def smooth(pts, samples=14):
    """Catmull-Rom 보간 → 부드러운 폴리라인"""
    if len(pts) < 3:
        return list(pts)
    p = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(len(p) - 3):
        p0, p1, p2, p3 = p[i], p[i + 1], p[i + 2], p[i + 3]
        for j in range(samples):
            t = j / samples
            t2, t3 = t * t, t * t * t
            x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t +
                       (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t +
                       (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1])* t3)
            out.append((x, y))
    out.append(tuple(pts[-1]))
    return out


def stroke(d, pts, color, width=7, alpha=255, passes=2, jitter=2.6, seed=0, curve=True):
    """연필로 두어 번 덧그린 듯한 획"""
    base = smooth(pts) if (curve and len(pts) > 2) else list(pts)
    rnd = random.Random(seed)
    for k in range(passes):
        j = 0 if k == 0 else jitter
        a = alpha if k == 0 else int(alpha * 0.45)
        path = [(x + rnd.uniform(-j, j), y + rnd.uniform(-j, j)) for x, y in base]
        d.line(path, fill=color + (a,), width=int(width * (1 if k == 0 else 0.75)),
               joint="curve")


def circle_pts(cx, cy, r, n=34, wobble=0.0, seed=0):
    rnd = random.Random(seed)
    return [(cx + (r + rnd.uniform(-wobble, wobble)) * math.cos(2 * math.pi * i / n),
             cy + (r + rnd.uniform(-wobble, wobble)) * math.sin(2 * math.pi * i / n))
            for i in range(n + 1)]


# ---------------------------------------------------------------- 학생 일러스트
def _furniture():
    """책상 · 의자 · 바닥 (두 학생 공통)"""
    return [
        [(112, 292), (110, 434)],                      # 의자 등받이
        [(96, 436), (306, 434)],                       # 의자 좌판
        [(126, 436), (122, 588)],                      # 의자 다리
        [(288, 436), (292, 588)],
        [(392, 350), (800, 350)],                      # 책상 상판
        [(392, 350), (392, 372)],
        [(392, 372), (800, 372)],
        [(430, 372), (427, 588)],                      # 책상 다리
        [(762, 372), (766, 588)],
    ]


def _arc(cx, cy, r, a0, a1, n=16):
    return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
            for a in [a0 + (a1 - a0) * i / n for i in range(n + 1)]]


def _body(kind):
    """자세별 인체 · 소품 경로"""
    if kind == "upright":
        body = [
            [(214, 428), (222, 362), (229, 302), (238, 264)],       # 곧은 등
            [(240, 266), (252, 252)],                               # 목
            [(238, 280), (302, 332), (366, 352)],                   # 팔
            [(214, 430), (348, 434)],                               # 허벅지
            [(348, 434), (356, 588)],                               # 종아리
            [(340, 588), (398, 586)],                               # 발
        ]
        head = (264, 212, 47)
        hair = _arc(264, 212, 50, 198, 342)                         # 정수리 머리선
        props = [
            [(366, 352), (412, 374)],                               # 쥐고 있는 연필
            [(452, 338), (600, 338), (600, 350), (452, 350), (452, 338)],  # 펴 놓은 학습지
        ]
    else:
        body = [
            [(214, 430), (244, 374), (292, 338), (352, 324), (408, 318)],  # 구부정한 등
            [(408, 318), (428, 306)],                               # 목
            [(356, 324), (410, 352), (596, 356)],                   # 책상에 뻗은 팔
            [(214, 432), (352, 452)],
            [(352, 452), (418, 588)],
            [(402, 588), (462, 586)],
        ]
        head = (478, 294, 47)                                       # 팔 위에 얹은 머리
        hair = _arc(478, 294, 50, 162, 318)
        props = [
            [(636, 350), (704, 342)],                               # 굴러다니는 연필
            [(640, 348), (646, 355)],
            [(724, 338), (800, 338), (800, 350), (724, 350), (724, 338)],  # 손 안 댄 학습지
        ]
    return body, head, hair, props


def student(kind, width=900, color=(52, 224, 161), furn=(120, 133, 150),
            lw=7, alpha=255, bgfill=(11, 14, 19)):
    """kind: 'upright' | 'slumped' → RGBA 이미지"""
    w, h = UW * SS, UH * SS
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def S(pts):
        return [(x * SS, y * SS) for x, y in pts]

    for i, p in enumerate(_furniture()):
        stroke(d, S(p), furn, lw * SS * 0.8, int(alpha * 0.75), passes=2,
               jitter=2.0 * SS, seed=100 + i, curve=False)

    body, head, hair, props = _body(kind)
    for i, p in enumerate(props):
        stroke(d, S(p), color, lw * SS * 0.75, int(alpha * 0.85), passes=1,
               jitter=1.8 * SS, seed=50 + i, curve=False)
    for i, p in enumerate(body):
        stroke(d, S(p), color, lw * SS, alpha, passes=2, jitter=2.4 * SS, seed=i)
    cx, cy, r = head
    # 머리 뒤로 지나가는 팔·책상 선을 가려 실루엣이 또렷해지도록 배경색으로 채운다
    d.ellipse([(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS],
              fill=bgfill + (int(alpha * 0.96),))
    stroke(d, S(circle_pts(cx, cy, r, wobble=1.2, seed=7)), color, lw * SS, alpha,
           passes=2, jitter=2.0 * SS, seed=21)
    stroke(d, S(hair), color, lw * SS * 0.85, int(alpha * 0.9), passes=1,
           jitter=1.5 * SS, seed=33)

    scale = width / UW
    img = img.resize((int(w * scale / SS), int(h * scale / SS)), Image.LANCZOS)
    return img.crop(img.getbbox())  # 투명 여백 제거 → 배치 계산이 정확해진다


# ---------------------------------------------------------------- 학습지 카드
PAPER = (240, 236, 227)
RULE = (198, 191, 177)
PENCIL = (86, 84, 80)


def _sketch_graph(d, x, y, size, seed, dense):
    """학습지 안의 좌표평면 그림"""
    rnd = random.Random(seed)
    stroke(d, [(x, y + size), (x + size, y + size)], RULE, 3, 255, 1, 1.0, seed, False)
    stroke(d, [(x, y), (x, y + size)], RULE, 3, 255, 1, 1.0, seed + 1, False)
    if dense:
        stroke(d, [(x + 6, y + size - 6), (x + size * 0.55, y + size * 0.35),
                   (x + size * 0.95, y + 8)], PENCIL, 4, 230, 2, 1.6, seed + 2)
        d.polygon([(x + 10, y + size - 8), (x + size * 0.6, y + size * 0.5),
                   (x + size * 0.6, y + size - 8)], outline=PENCIL + (150,))
    else:
        for _ in range(3):
            a = (x + rnd.uniform(0, size), y + rnd.uniform(0, size))
            b = (x + rnd.uniform(0, size), y + rnd.uniform(0, size))
            stroke(d, [a, b], PENCIL, 4, 120, 1, 2.4, rnd.randint(0, 999), False)


def worksheet(dense=True, w=392, h=524, seed=1):
    """사진이 없을 때 쓰는 학습지 카드 (그림자 포함 RGBA)"""
    rnd = random.Random(seed)
    pad = 34
    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad + 14, pad + w, pad + h + 14],
                                         radius=22, fill=(0, 0, 0, 155))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(20)))

    c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=22, fill=PAPER + (255,))
    d.rounded_rectangle([0, 0, w - 1, 76], radius=22, fill=(226, 221, 210, 255))
    d.rectangle([0, 54, w - 1, 76], fill=(226, 221, 210, 255))
    d.line([(0, 76), (w, 76)], fill=(190, 183, 169, 255), width=2)
    d.rectangle([28, 26, 92, 50], fill=(150, 165, 190, 255))       # 문항 번호 블록
    d.rectangle([106, 32, 210, 44], fill=(176, 170, 158, 255))

    y = 108
    while y < h - 150:
        wid = w - 76 if rnd.random() > 0.3 else int((w - 76) * 0.62)
        d.rounded_rectangle([38, y, 38 + wid, y + 8], radius=4, fill=RULE + (255,))
        y += 34
    _sketch_graph(d, 60, h - 150, 110, seed, dense)

    if dense:  # 빼곡한 풀이 흔적
        for i in range(26):
            x0 = rnd.uniform(190, w - 50)
            y0 = rnd.uniform(120, h - 40)
            stroke(d, [(x0, y0), (x0 + rnd.uniform(14, 52), y0 + rnd.uniform(-6, 6))],
                   PENCIL, 3, rnd.randint(150, 225), 1, 1.4, i, False)
    else:      # 손 안 댄 여백 + 낙서
        for i in range(4):
            x0 = rnd.uniform(200, w - 90)
            y0 = rnd.uniform(140, h - 90)
            stroke(d, [(x0, y0), (x0 + 40, y0 + 26), (x0 + 8, y0 + 44), (x0 + 52, y0 + 60)],
                   PENCIL, 4, 120, 1, 2.6, i + 60)

    img.alpha_composite(c, (pad, pad))
    return img


def photo_card(path, crop=None, rotate=0, w=392, h=524, tone=None, boost=1.0):
    """실제 사진에서 학습지 한 장을 잘라 카드로 만든다.

    crop: 원본 기준 (left, top, right, bottom) 비율 0~1
    rotate: 사진이 누워 있으면 90 / -90 / 180
    boost: 작게 줄여도 연필 자국이 보이도록 대비를 올리는 값
    """
    src = Image.open(path).convert("RGB")
    if rotate:
        src = src.rotate(rotate, expand=True)
    if crop:
        W0, H0 = src.size
        src = src.crop((int(crop[0] * W0), int(crop[1] * H0),
                        int(crop[2] * W0), int(crop[3] * H0)))
    # 카드 비율에 맞춰 중앙 크롭
    tr, sr = w / h, src.width / src.height
    if sr > tr:
        nw = int(src.height * tr)
        src = src.crop(((src.width - nw) // 2, 0, (src.width + nw) // 2, src.height))
    else:
        nh = int(src.width / tr)
        src = src.crop((0, (src.height - nh) // 2, src.width, (src.height + nh) // 2))
    src = src.resize((w, h), Image.LANCZOS)
    if boost != 1.0:
        src = ImageEnhance.Contrast(src).enhance(boost)
        src = ImageEnhance.Brightness(src).enhance(1.06)

    pad = 34
    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad + 14, pad + w, pad + h + 14],
                                         radius=22, fill=(0, 0, 0, 160))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(20)))

    c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    c.paste(src, (0, 0))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=22, fill=255)
    c.putalpha(mask)
    if tone:
        d = ImageDraw.Draw(c)
        d.rounded_rectangle([0, h - 12, w - 1, h - 1], radius=6, fill=tone + (255,))
    img.alpha_composite(c, (pad, pad))
    return img


ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

# 실제 학습지 사진 배치. assets/crop.json 으로 덮어쓸 수 있다.
#   a = 빼곡히 푼 학습지, b = 거의 손대지 않은 학습지
#   rotate : 사진 속 글자가 누워 있으면 -90 / 90 / 180 으로 세운다
#   box    : 회전 후 이미지 기준 (좌, 상, 우, 하) 비율 0~1
CROP = {
    "a": {"file": "worksheet-a.jpg", "rotate": -90, "box": [0.03, 0.02, 0.60, 0.98],
          "boost": 1.30},
    "b": {"file": "worksheet-b.jpg", "rotate": -90, "box": [0.27, 0.03, 0.87, 0.97],
          "boost": 1.30},
}
_cj = os.path.join(ASSETS, "crop.json")
if os.path.exists(_cj):
    import json
    with open(_cj, encoding="utf-8") as fh:
        for k, v in json.load(fh).items():
            CROP.setdefault(k, {}).update(v)


def cards(w=392, h=524):
    """사진이 있으면 사진 카드, 없으면 그린 카드를 (A, B, 사진사용여부)로 반환"""
    made = []
    for key in ("a", "b"):
        cfg = CROP[key]
        p = os.path.join(ASSETS, cfg["file"])
        if not os.path.exists(p):
            break
        made.append(photo_card(p, cfg["box"], cfg["rotate"], w, h,
                               boost=cfg.get("boost", 1.0)))
    if len(made) == 2:
        return made[0], made[1], True
    return worksheet(True, w, h, 1), worksheet(False, w, h, 9), False
