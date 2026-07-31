#!/usr/bin/env python3
"""수학 태도 릴스 렌더러 — 1080x1920 / 30fps / H.264 MP4

python3 render/make_reels.py [출력경로]
"""
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import draw_lib as L  # noqa: E402

W, H, FPS = 1080, 1920, 30
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "out", "math-attitude-reels.mp4")
COVER = os.path.join(os.path.dirname(OUT), "cover.png")

F_BOLD = "/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf"
F_REG = "/usr/share/fonts/truetype/nanum/NanumSquareRoundR.ttf"
F_SQ = "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf"

WHITE = (244, 247, 250)
MUTED = (136, 148, 166)
DIM = (92, 103, 120)
MINT = (52, 224, 161)
CORAL = (255, 96, 96)
AMBER = (255, 197, 61)
PAPER = (240, 236, 227)
RULE = (206, 199, 185)

_fonts = {}


def font(path, size):
    key = (path, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(path, size)
    return _fonts[key]


def clamp01(x):
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def eo(x):
    """ease-out cubic"""
    return 1 - (1 - clamp01(x)) ** 3


def eio(x):
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def seg(t, start, dur):
    """구간 진행도 0..1"""
    return clamp01((t - start) / dur)


def rise(t, start, dur=0.55, travel=38):
    """페이드 + 아래에서 위로. (alpha, dy) 반환"""
    p = eo(seg(t, start, dur))
    return int(255 * p), (1 - p) * travel


def out_fade(t, start, dur=0.35):
    return 1 - clamp01((t - start) / dur)


def rgba(color, alpha):
    a = max(0, min(255, int(alpha)))
    return (color[0], color[1], color[2], a)


def text(d, xy, s, f, color, alpha=255, anchor="mm", spacing=16):
    if alpha <= 0:
        return
    d.multiline_text(xy, s, font=f, fill=rgba(color, alpha), anchor=anchor,
                     align="center", spacing=spacing)


# ---------------------------------------------------------------- 배경
def build_bg():
    bg = Image.new("RGB", (W, H), (11, 14, 19))
    d = ImageDraw.Draw(bg)
    # 모눈종이 격자
    step = 60
    for x in range(0, W + 1, step):
        d.line([(x, 0), (x, H)], fill=(20, 25, 33), width=1)
    for y in range(0, H + 1, step):
        d.line([(0, y), (W, y)], fill=(20, 25, 33), width=1)
    # 상단 은은한 글로우
    glow = Image.new("L", (W // 4, H // 4), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-60, -140, W // 4 + 60, 190], fill=110)
    glow = glow.resize((W, H)).filter(ImageFilter.GaussianBlur(90))
    bg = Image.composite(Image.new("RGB", (W, H), (30, 52, 46)), bg, glow)
    return bg


BG = build_bg()
# 실제 학습지 사진 (assets/worksheet-a.jpg = 빼곡히 푼 것, -b.jpg = 손대지 않은 것)
CARD_A, CARD_B, USING_PHOTO = L.cards(392, 524)
CARD_A2, CARD_B2, _ = L.cards(344, 460)
# 손그림 학생 — 바른 자세 / 엎드린 자세


def fit_h(im, h):
    return im.resize((max(1, round(im.width * h / im.height)), int(h)), Image.LANCZOS)


_UP = L.student("upright", 1100, MINT, (84, 94, 110))
_SL = L.student("slumped", 1100, CORAL, (84, 94, 110))
STU_UP_S, STU_SL_S = fit_h(_UP, 268), fit_h(_SL, 268)     # 학습지 아래 작게
STU_UP_L, STU_SL_L = fit_h(_UP, 442), fit_h(_SL, 442)     # 인물 장면


def paste_top(base, im, cx, top, alpha=255):
    """윗변 기준 배치 — 화면 아래쪽 안전 영역을 넘지 않게 계산하기 쉽다"""
    if alpha <= 0:
        return
    if alpha < 255:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha / 255)))
    base.alpha_composite(im, (int(cx - im.width / 2), int(top)))


def paste(base, im, cx, cy, alpha=255, scale=1.0):
    if alpha <= 0:
        return
    if scale != 1.0:
        nw, nh = max(1, int(im.width * scale)), max(1, int(im.height * scale))
        im = im.resize((nw, nh), Image.LANCZOS)
    if alpha < 255:
        im = im.copy()
        a = im.getchannel("A").point(lambda v: int(v * alpha / 255))
        im.putalpha(a)
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def chip(d, cx, cy, label, color, alpha=255, fs=38, padx=30, pady=14):
    f = font(F_BOLD, fs)
    tw = d.textlength(label, font=f)
    w2, h2 = tw / 2 + padx, fs / 2 + pady
    d.rounded_rectangle([cx - w2, cy - h2, cx + w2, cy + h2], radius=int(h2),
                        fill=rgba(color, alpha * 0.16), outline=rgba(color, alpha * 0.8), width=2)
    text(d, (cx, cy + 2), label, f, color, alpha)


# ---------------------------------------------------------------- 장면
def s1_hook(base, d, t, dur):
    a, dy = rise(t, 0.15, 0.6, 46)
    text(d, (W / 2, 700 + dy), "수학을 잘하고 싶다면", font(F_REG, 62), MUTED, a)

    a2, dy2 = rise(t, 0.55, 0.6, 54)
    text(d, (W / 2, 880 + dy2), "태도부터", font(F_BOLD, 130), WHITE, a2)
    a3, dy3 = rise(t, 0.8, 0.6, 54)
    text(d, (W / 2, 1030 + dy3), "바꿔 보세요", font(F_BOLD, 130), MINT, a3)

    p = eo(seg(t, 1.35, 0.55))
    if p > 0:
        f = font(F_BOLD, 130)
        tw = d.textlength("바꿔 보세요", font=f)
        x0 = W / 2 - tw / 2
        d.rounded_rectangle([x0, 1104, x0 + tw * p, 1116], radius=6, fill=rgba(MINT, 210))

    a4, _ = rise(t, 2.1, 0.5, 0)
    text(d, (W / 2, 1270), "1년을 갈라놓은 건 머리가 아니었습니다", font(F_REG, 40), DIM, a4 * 0.9)


def s2_cards(base, d, t, dur):
    pl = eo(seg(t, 0.35, 0.7))
    pr = eo(seg(t, 0.5, 0.7))
    paste(base, CARD_A, 292 - (1 - pl) * 220, 980, int(255 * pl))
    paste(base, CARD_B, 788 + (1 - pr) * 220, 980, int(255 * pr))

    # 학습지 아래, 그 종이의 주인이 앉아 있던 자세를 손그림으로
    ab = int(150 * eo(seg(t, 1.5, 0.9)))
    paste_top(base, STU_UP_S, 292, 1330, ab)
    paste_top(base, STU_SL_S, 788, 1330, ab)

    a, dy = rise(t, 0.1, 0.5, 34)
    text(d, (W / 2, 470 + dy), "여기 두 장의 학습지가 있습니다", font(F_BOLD, 58), WHITE, a)
    a2, _ = rise(t, 0.9, 0.5, 0)
    text(d, (W / 2, 570), "비슷한 수준에서 출발한 두 아이의 것입니다",
         font(F_REG, 44), MUTED, a2)


def s3_same(base, d, t, dur):
    a, dy = rise(t, 0.1, 0.5, 30)
    text(d, (W / 2, 560 + dy), "조건은 똑같았습니다", font(F_BOLD, 62), WHITE, a)

    items = ["같은 출발점", "같은 문제량", "같은 수업"]
    for i, s in enumerate(items):
        st = 0.55 + i * 0.42
        ai, dyi = rise(t, st, 0.5, 34)
        y = 860 + i * 190 + dyi
        d.ellipse([228, y - 40, 308, y + 40], outline=rgba(MINT, ai * 0.85), width=4)
        p = eo(seg(t, st + 0.12, 0.3))
        if p > 0:
            pts = [(250, y + 2), (264, y + 18), (288, y - 16)]
            seq = [pts[0], (pts[0][0] + (pts[1][0] - pts[0][0]) * min(1, p * 2),
                            pts[0][1] + (pts[1][1] - pts[0][1]) * min(1, p * 2))]
            if p > 0.5:
                q = (p - 0.5) * 2
                seq.append((pts[1][0] + (pts[2][0] - pts[1][0]) * q,
                            pts[1][1] + (pts[2][1] - pts[1][1]) * q))
            d.line(seq, fill=rgba(MINT, ai), width=7, joint="curve")
        text(d, (360, y), s, font(F_BOLD, 66), WHITE, ai, anchor="lm")


def s4_gap(base, d, t, dur):
    a, dy = rise(t, 0.05, 0.5, 30)
    text(d, (W / 2, 520 + dy), "그런데 1년 뒤,", font(F_BOLD, 62), WHITE, a)

    x0, y0, x1 = 190, 1180, 880
    d.line([(x0, y0), (x1, y0)], fill=rgba(DIM, 70), width=2)
    p = eio(seg(t, 0.5, 1.5))
    if p > 0:
        up, flat = [], []
        n = max(2, int(60 * p))
        for i in range(n + 1):
            u = (i / n) * p
            x = x0 + (x1 - x0) * u
            up.append((x, y0 - 330 * (u ** 1.7)))
            flat.append((x, y0 + 12 * math.sin(u * 9)))
        d.line(flat, fill=rgba(DIM, 230), width=8, joint="curve")
        d.line(up, fill=rgba(MINT, 255), width=10, joint="curve")
        d.ellipse([up[-1][0] - 13, up[-1][1] - 13, up[-1][0] + 13, up[-1][1] + 13], fill=rgba(MINT, 255))
        d.ellipse([flat[-1][0] - 11, flat[-1][1] - 11, flat[-1][0] + 11, flat[-1][1] + 11], fill=rgba(DIM, 255))

    a2, _ = rise(t, 1.75, 0.45, 0)
    text(d, (x1 + 20, 830), "성적이\n오른 아이", font(F_BOLD, 42), MINT, a2, anchor="lm", spacing=10)
    text(d, (x1 + 20, 1200), "제자리인\n아이", font(F_BOLD, 42), DIM, a2, anchor="lm", spacing=10)

    a3, dy3 = rise(t, 2.25, 0.55, 30)
    text(d, (W / 2, 1500 + dy3), "지금은 수준 차이 때문에\n반을 나눠 수업합니다",
         font(F_REG, 54), WHITE, a3)


def s5_head(base, d, t, dur):
    a, dy = rise(t, 0.05, 0.5, 30)
    text(d, (W / 2, 720 + dy), "다들 이걸", font(F_REG, 52), MUTED, a)
    a2, dy2 = rise(t, 0.3, 0.5, 34)
    f = font(F_BOLD, 108)
    text(d, (W / 2, 850 + dy2), "'수학 머리'", f, WHITE, a2)
    a3, _ = rise(t, 0.55, 0.5, 0)
    text(d, (W / 2, 960), "라고 부릅니다", font(F_REG, 52), MUTED, a3)

    p = eo(seg(t, 1.2, 0.45))
    if p > 0:
        tw = d.textlength("'수학 머리'", font=f)
        x0 = W / 2 - tw / 2
        d.line([(x0 - 14, 856), (x0 - 14 + (tw + 28) * p, 856)], fill=rgba(CORAL, 240), width=9)

    a4, dy4 = rise(t, 1.85, 0.55, 40)
    text(d, (W / 2, 1200 + dy4), "아니요.", font(F_REG, 60), MUTED, a4)
    a5, dy5 = rise(t, 2.15, 0.6, 46)
    text(d, (W / 2, 1330 + dy5), "태도입니다.", font(F_BOLD, 124), AMBER, a5)


def s6_a(base, d, t, dur):
    paste_top(base, STU_UP_L, W / 2, 1140, int(190 * eo(seg(t, 0.15, 0.9))))

    ac, _ = rise(t, 0.05, 0.45, 0)
    chip(d, W / 2, 400, "성적이 오른 아이", MINT, ac, 40)

    a, dy = rise(t, 0.4, 0.55, 34)
    text(d, (W / 2, 550 + dy), "방향을 코칭해 주면", font(F_REG, 54), MUTED, a)

    for i, (s, st) in enumerate([("\"잘 안 되더라도", 0.85), ("일단 해볼게요\"", 1.35)]):
        a2, dy2 = rise(t, st, 0.5, 36)
        y = 740 + i * 172 + dy2
        f = font(F_BOLD, 76)
        tw = d.textlength(s, font=f)
        d.rounded_rectangle([W / 2 - tw / 2 - 34, y - 60, W / 2 + tw / 2 + 34, y + 60],
                            radius=30, fill=rgba(MINT, a2 * 0.16))
        text(d, (W / 2, y), s, f, WHITE, a2)

    a3, dy3 = rise(t, 2.05, 0.55, 30)
    text(d, (W / 2, 1040 + dy3), "틀려도 손이 먼저 움직입니다", font(F_BOLD, 52), MINT, a3)


def s7_b(base, d, t, dur):
    paste_top(base, STU_SL_L, W / 2, 1140, int(190 * eo(seg(t, 0.15, 0.9))))

    ac, _ = rise(t, 0.05, 0.45, 0)
    chip(d, W / 2, 400, "1년째 제자리인 아이", CORAL, ac, 40)

    lines = [
        ("\"에이, 나만 못해.\"", 0.45),
        ("\"못 풀어요.\"", 1.30),
        ("\"읽기도 싫어요.\"", 2.15),
    ]
    for i, (s, st) in enumerate(lines):
        a, dy = rise(t, st, 0.5, 36)
        y = 548 + i * 172 + dy
        f = font(F_BOLD, 76)
        tw = d.textlength(s, font=f)
        d.rounded_rectangle([W / 2 - tw / 2 - 34, y - 60, W / 2 + tw / 2 + 34, y + 60],
                            radius=30, fill=rgba(CORAL, a * 0.16))
        text(d, (W / 2, y), s, f, WHITE, a)

    a5, dy5 = rise(t, 3.05, 0.6, 30)
    text(d, (W / 2, 1030 + dy5), "푸는 게 아니라 글씨만 읽어 보자고 해도\n그것마저 거부합니다.",
         font(F_REG, 46), MUTED, a5, spacing=14)


def s8_result(base, d, t, dur):
    pc = eo(seg(t, 0.9, 0.7))
    paste(base, CARD_A2, 296, 1140, int(255 * pc))
    paste(base, CARD_B2, 784, 1140, int(255 * pc))

    a, dy = rise(t, 0.1, 0.55, 40)
    text(d, (W / 2, 520 + dy), "미안하지만,", font(F_REG, 56), MUTED, a)
    a2, dy2 = rise(t, 0.45, 0.6, 46)
    text(d, (W / 2, 650 + dy2), "결과는 뻔합니다.", font(F_BOLD, 104), WHITE, a2)
    p = eo(seg(t, 1.0, 0.5))
    if p > 0:
        d.rounded_rectangle([W / 2 - 280 * p, 730, W / 2 + 280 * p, 736], radius=3,
                            fill=rgba(CORAL, 200))

    ac, _ = rise(t, 1.8, 0.5, 0)
    chip(d, 296, 1520, "매일 시도한 1년", MINT, ac, 34)
    chip(d, 784, 1520, "매일 미룬 1년", CORAL, ac, 34)


def s9_end(base, d, t, dur):
    a, dy = rise(t, 0.1, 0.55, 34)
    text(d, (W / 2, 640 + dy), "실력의 차이는\n머리에서 시작되지 않습니다",
         font(F_REG, 56), MUTED, a)

    a2, dy2 = rise(t, 0.75, 0.55, 40)
    text(d, (W / 2, 970 + dy2), "\"해볼게요\"", font(F_BOLD, 104), MINT, a2)
    a3, dy3 = rise(t, 1.1, 0.55, 40)
    text(d, (W / 2, 1110 + dy3), "\"못 해요\"", font(F_BOLD, 104), CORAL, a3)

    a4, dy4 = rise(t, 1.6, 0.6, 34)
    text(d, (W / 2, 1300 + dy4), "그 한마디에서 갈립니다.", font(F_BOLD, 66), WHITE, a4)

    a5, _ = rise(t, 2.3, 0.6, 0)
    chip(d, W / 2, 1520, "오늘은 한 문제, 읽는 것부터", AMBER, a5, 40)


SCENES = [
    (3.6, s1_hook),
    (4.8, s2_cards),
    (3.9, s3_same),
    (5.0, s4_gap),
    (4.4, s5_head),
    (4.4, s6_a),
    (5.8, s7_b),
    (4.4, s8_result),
    (5.2, s9_end),
]
TOTAL = sum(s[0] for s in SCENES)


def render_frame(t_global):
    base = BG.copy().convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    acc = 0.0
    for dur, fn in SCENES:
        if acc <= t_global < acc + dur:
            fn(layer, d, t_global - acc, dur)
            # 장면 전환 시 살짝 어둡게
            fade = min(clamp01((t_global - acc) / 0.25), out_fade(t_global, acc + dur - 0.25, 0.25))
            if fade < 1:
                d.rectangle([0, 0, W, H], fill=(11, 14, 19, int(255 * (1 - fade) * 0.85)))
            break
        acc += dur

    base.alpha_composite(layer)
    # 상단 진행 바
    pd = ImageDraw.Draw(base)
    pd.rectangle([0, 0, W, 7], fill=(255, 255, 255, 26))
    pd.rectangle([0, 0, int(W * clamp01(t_global / TOTAL)), 7], fill=MINT + (210,))
    return base.convert("RGB")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    frames = int(TOTAL * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "slow", "-crf", "19",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(frames):
        img = render_frame(i / FPS)
        if i == int(1.9 * FPS):
            img.save(COVER)
        p.stdin.write(img.tobytes())
        if i % 60 == 0:
            print(f"  {i}/{frames}", flush=True)
    p.stdin.close()
    if p.wait() != 0:
        sys.exit("ffmpeg 실패")
    print(f"완료: {OUT}  ({TOTAL:.1f}s, {frames} frames)")


if __name__ == "__main__":
    main()
